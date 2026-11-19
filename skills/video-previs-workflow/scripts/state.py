"""Write project state: the submission lock, job reservation and settlement, and approvals.
gate.py only reads state; this is the one script that edits it. It never calls a provider."""
import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate import unresolved_notes

# A job in one of these keeps the lock; a handed-off manual job does not. `unknown` (set by hand after an interrupted
# submission) is unresolved: it keeps its reservation and the lock until it is settled.
ACTIVE = ('reserved', 'submitting', 'running', 'unknown')


def _now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _load(path):
    return json.loads(Path(path).read_text())


def _save(path, state):
    path = Path(path)
    state['revision'] = (state['revision'] if type(state.get('revision')) is int else 0) + 1
    state['updated_at'] = _now()
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _lock_dir(path):
    return Path(path).resolve().parent / 'submission.lock'


def _active(state):
    return [str(j.get('request_id')) for j in state.get('jobs') or [] if isinstance(j, dict) and j.get('status') in ACTIVE]


def _job(state, request_id):
    for job in state.get('jobs') or []:
        if isinstance(job, dict) and job.get('request_id') == request_id: return job
    raise ValueError('unknown request_id')


def _count(state, job):
    budget = state.setdefault('budget', {})
    counter = 'attempts_used' if job.get('quote', 0) > 0 else 'manual_takes'  # the attempt limit counts paid submissions only
    budget[counter] = budget.get(counter, 0) + 1


def _release_if_idle(path, state, held):
    """Only a job that held the lock gives it back: settling a returned manual take must not drop a lock taken since."""
    if held and not _active(state): shutil.rmtree(_lock_dir(path), ignore_errors=True)


def lock(state_path, owner, purpose):
    folder = _lock_dir(state_path)
    try: folder.mkdir()  # atomic: only one host gets it
    except FileExistsError:
        note = folder / 'owner.json'
        raise ValueError(f"lock exists: {note.read_text().strip() if note.is_file() else 'no owner file'}")
    (folder / 'owner.json').write_text(json.dumps({'owner': owner, 'since': _now(), 'purpose': purpose}))


def unlock(state_path):
    active = _active(_load(state_path))
    if active: raise ValueError(f"lock in use by {', '.join(active)}")
    shutil.rmtree(_lock_dir(state_path), ignore_errors=True)


def reserve(state_path, job):
    if not _lock_dir(state_path).is_dir(): raise ValueError('lock required')
    state = _load(state_path)
    request_id, quote = job.get('request_id'), job.get('quote')
    if not (isinstance(request_id, str) and request_id.strip() and type(quote) in (int, float) and quote >= 0):
        raise ValueError('job needs request_id and quote >= 0')
    jobs = state.setdefault('jobs', [])
    if any(isinstance(j, dict) and j.get('request_id') == request_id for j in jobs): raise ValueError('request_id already exists')
    jobs.append(dict(job, status='reserved', reservation=quote))
    budget = state.setdefault('budget', {})
    budget['reserved'] = budget.get('reserved', 0) + quote
    _save(state_path, state)


def submit(state_path, request_id, provider_job_id=None):
    state = _load(state_path); job = _job(state, request_id)
    if job.get('status') != 'reserved': raise ValueError(f"job {request_id} is {job.get('status')}; expected reserved")
    job.update(status='handed_off' if job.get('route') == 'manual' else 'running', submitted_at=_now())
    if provider_job_id: job['provider_job_id'] = provider_job_id
    _count(state, job)
    _save(state_path, state)
    _release_if_idle(state_path, state, held=True)


def settle(state_path, request_id, charge, outputs=(), status='succeeded'):
    state = _load(state_path); job = _job(state, request_id)
    previous = job.get('status')
    if previous not in ACTIVE + ('handed_off',): raise ValueError(f'job {request_id} is {previous}; already settled')
    root, records = Path(state_path).resolve().parent, []
    for path in outputs:
        if not (root / path).is_file(): raise ValueError(f'output not found: {path}')
        records.append({'path': str(path), 'sha256': hashlib.sha256((root / path).read_bytes()).hexdigest()})
    job.update(status=status, actual_charge=charge, outputs=records, settled_at=_now())
    if previous == 'reserved' and status != 'cancelled': _count(state, job)  # settled without `submit`: still an attempt
    budget = state.setdefault('budget', {})
    budget['settled'] = budget.get('settled', 0) + charge
    budget['reserved'] = budget.get('reserved', 0) - job.get('reservation', 0)
    _save(state_path, state)
    _release_if_idle(state_path, state, held=previous in ACTIVE)


def charge(state_path, request_id, amount, evidence):
    """Correct a settled job's charge from the provider's own record (a balance difference can include other sessions)."""
    state = _load(state_path); job = _job(state, request_id)
    if 'settled_at' not in job: raise ValueError(f'job {request_id} is not settled')
    if not (isinstance(evidence, str) and evidence.strip()): raise ValueError('evidence required: where the amount was read')
    budget = state.setdefault('budget', {})
    budget['settled'] = budget.get('settled', 0) - job.get('actual_charge', 0) + amount
    job.update(actual_charge=amount, charge_evidence=evidence)
    _save(state_path, state)


def init(state_path, project_id):
    if Path(state_path).exists(): raise ValueError('state exists')
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)  # a new production starts in a folder of its own
    _save(state_path, {'project_id': project_id, 'stage': 'story', 'assets': [], 'shots': [], 'jobs': [], 'continuity': []})


COUNTERS = ('settled', 'reserved', 'attempts_used', 'manual_takes')  # owned by reserve/submit/settle/charge
SECTIONS = ('output', 'generation_profile', 'generation_plan', 'budget', 'story', 'reference', 'previs', 'handoff', 'shot')


def put(state_path, section, data):
    """Merge a JSON object into a section, or into the shot with its id. Never approves and never moves budget counters."""
    if section not in SECTIONS or not isinstance(data, dict): raise ValueError(f"section must be one of {', '.join(SECTIONS)} with a JSON object")
    state = _load(state_path)
    if section == 'shot':
        if not isinstance(data.get('id'), str): raise ValueError('shot needs an id')
        shots = state.setdefault('shots', [])
        target = next((x for x in shots if isinstance(x, dict) and x.get('id') == data['id']), None)
        if target is None: shots.append(data)
        else: target.update(data)
    else:
        if section == 'budget': data = {k: v for k, v in data.items() if k not in COUNTERS}
        if section in ('story', 'reference', 'previs'):  # a changed file is a new, unapproved record
            need = 'spec_path' if section == 'previs' else 'path'  # the record points at a file; it is not the file
            if not isinstance(data.get(need), str): raise ValueError(f'{section}: {need} required')
            path = data.get('path') or data.get('spec_path')
            data = dict(data, approval='pending')
            if section != 'previs': data['sha256'] = _hashed(state_path, path) if isinstance(path, str) else None
            state[section] = data
        else: state.setdefault(section, {}).update(data)
    _save(state_path, state)


def _record(state, kind, ident):
    if kind in ('story', 'reference', 'previs'): found = [state.get(kind)]
    elif kind == 'asset':
        found = [a for a in state.get('assets') or [] if isinstance(a, dict) and f"{a.get('role_id')}@{a.get('version')}" == ident]
    elif kind == 'keyframe':
        found = [k for s in state.get('shots') or [] if isinstance(s, dict)
                 for k in s.get('keyframes') or [] if isinstance(k, dict) and k.get('path') == ident]
    elif kind == 'continuity':
        found = [c for c in state.get('continuity') or [] if isinstance(c, dict) and c.get('role_id') == ident]
    else: found = []
    if not found or not isinstance(found[0], dict): raise ValueError('unknown record')
    return found[0]


def approve(state_path, kind, ident, evidence):
    state = _load(state_path); record = _record(state, kind, ident)
    if unresolved_notes(record): raise ValueError('unresolved review note')  # a defect is fixed or accepted first
    for older in _rivals(state, kind, record):  # one approved version per role, one approved start frame per shot
        if older is not record and older.get('approval') == 'approved': older['approval'] = 'superseded'
    record.update(approval='approved', evidence=evidence, approved_at=_now())
    _save(state_path, state)


def _rivals(state, kind, record):
    if kind == 'asset': return [a for a in state.get('assets') or [] if isinstance(a, dict) and a.get('role_id') == record.get('role_id')]
    if kind == 'keyframe' and record.get('kind') == 'start':
        return [k for s in state.get('shots') or [] if isinstance(s, dict) and record in (s.get('keyframes') or [])
                for k in s['keyframes'] if isinstance(k, dict) and k.get('kind') == 'start']
    return []


def _hashed(state_path, path):
    file = Path(state_path).resolve().parent / path
    if not file.is_file(): raise ValueError(f'file not found: {path}')
    return hashlib.sha256(file.read_bytes()).hexdigest()


def asset(state_path, ident, kind, path, source='generated', origin=None):
    """Add a pending asset record `role@version` with the hash of its file."""
    role, _, version = ident.partition('@')
    if not (role and version): raise ValueError('asset is named role@version')
    if kind not in ('character', 'prop', 'set'): raise ValueError('kind must be character, prop or set')
    if source not in ('generated', 'existing', 'footage'): raise ValueError('source must be generated, existing or footage')
    digest, state = _hashed(state_path, path), _load(state_path)
    assets = state.setdefault('assets', [])
    if any(isinstance(a, dict) and (a.get('role_id'), a.get('version')) == (role, version) for a in assets): raise ValueError('asset exists')
    assets.append({'role_id': role, 'version': version, 'kind': kind, 'source': source, 'original_path': str(path),
                   'original_sha256': digest, 'working_path': str(path), 'sha256': digest, 'approval': 'pending', 'review_notes': [],
                   **({'origin': origin} if origin else {})})
    _save(state_path, state)


def keyframe(state_path, shot_id, path, kind, previs_frame):
    """Add a pending keyframe to a shot: kind start/end, or reference for a mid-take state image."""
    if kind not in ('start', 'end', 'reference'): raise ValueError('kind must be start, end or reference')
    digest, state = _hashed(state_path, path), _load(state_path)
    shot = next((s for s in state.get('shots') or [] if isinstance(s, dict) and s.get('id') == shot_id), None)
    if shot is None: raise ValueError('unknown shot')
    keys = shot.setdefault('keyframes', [])
    if any(isinstance(k, dict) and k.get('path') == str(path) for k in keys): raise ValueError('keyframe exists')
    keys.append({'kind': kind, 'path': str(path), 'sha256': digest, 'previs_frame': previs_frame, 'approval': 'pending', 'review_notes': []})
    _save(state_path, state)


def note(state_path, kind, ident, note=None, resolve=None, evidence=None):
    """Write a defect on an asset or keyframe, or close every open one as fixed/accepted with evidence."""
    state = _load(state_path); notes = _record(state, kind, ident).setdefault('review_notes', [])
    if note: notes.append({'note': note})
    elif resolve in ('fixed', 'accepted'):
        if not (isinstance(evidence, str) and evidence.strip()): raise ValueError('evidence required: the new version or the user\'s words')
        for item in notes:
            if isinstance(item, dict) and item.get('resolution') not in ('fixed', 'accepted'): item.update(resolution=resolve, evidence=evidence)
    else: raise ValueError('give a note, or a resolution (fixed or accepted) with evidence')
    _save(state_path, state)


def bind(state_path):
    """Bind the approved version of every role to each shot that uses it."""
    state = _load(state_path)
    approved = {a['role_id']: a for a in state.get('assets') or [] if isinstance(a, dict) and a.get('approval') == 'approved'}
    for shot in state.get('shots') or []:
        roles = list(dict.fromkeys(r for r in (shot.get('object_roles') or {}).values() if isinstance(r, str)))
        missing = [r for r in roles if r not in approved]
        if missing: raise ValueError(f"{shot.get('id')}: no approved asset for {', '.join(missing)}")
        shot['asset_bindings'] = [{'role_id': r, 'version': approved[r].get('version'), 'sha256': approved[r].get('sha256')} for r in roles]
    _save(state_path, state)


def select_takes(state_path, rows):
    import delivery_check
    state = _load(state_path)
    root = Path(state_path).resolve().parent
    shots = {s['id']: s for s in state['shots']}
    if not isinstance(rows,list) or not rows:
        raise ValueError('selection needs a nonempty list')
    from gate import _spec
    frame_counts = {s['id']: s.get('frames') for s in _spec(state,root).get('shots', [])}
    seen, sources = set(), {}
    changed = False
    for row in rows:
        sid = row['shot']
        if sid not in shots or sid in seen:
            raise ValueError(f'{sid}: missing or duplicate shot')
        seen.add(sid)
        shot = shots[sid]
        job = _job(state, row['request_id'])
        if job.get('status') != 'succeeded' or sid not in job.get('shots',[job.get('shot')]):
            raise ValueError(f'{sid}: job must cover shot and have succeeded')
        source = row['source']
        record = next((r for r in job['outputs'] if r['path']==source),None)
        if source not in sources:
            sources[source] = (_hashed(state_path,source),delivery_check.video_info(root/source))
        digest, info = sources[source]
        if not record or record['sha256'] != digest:
            raise ValueError(f'{sid}: source differs from ingested output')
        start,end,target,hold = (row[k] for k in ('start','end','target_frames','hold_frames'))
        if not all(type(n) is int for n in (start,end,target,hold)) or not 0 <= start < end <= info['frames']:
            raise ValueError(f'{sid}: invalid source range')
        take = delivery_check.video_info(root/row['take'])
        if take['fps'] != info['fps'] or target != end-start+hold or hold < 0 or take['frames'] != target or target != frame_counts.get(sid,shot.get('frames')):
            raise ValueError(f'{sid}: selected frame counts or rates disagree')
        if hold and not (isinstance(row.get('hold_acceptance'), str) and row['hold_acceptance'].strip()):
            raise ValueError(f'{sid}: review and accept padded preview first')
        selection = dict(row,sha256=_hashed(state_path,row['take']),source_sha256=digest)
        if shot.get('selected_output') != selection:
            shot['selected_output'] = selection
            shot.pop('event_results',None)
            shot.pop('prop_results',None)
            for group in shot.get('group_motion',{}).values():
                for key in ('measured_s','result','evidence'):
                    group.pop(key,None)
            changed = True
    for job in state.get('jobs',[]):
        if job.get('generation_mode') != 'one_take':
            continue
        previous = None
        for sid in job.get('shots',[job.get('shot')]):
            selection = shots.get(sid,{}).get('selected_output')
            if not isinstance(selection,dict) or selection.get('request_id') != job['request_id']:
                previous = None
                continue
            if selection['hold_frames'] or (previous and (previous['source'] != selection['source'] or previous['end'] != selection['start'])):
                raise ValueError(f'{sid}: one-take ranges must preserve continuous action')
            previous = selection
    if changed:
        state.pop('delivery',None)
        state['stage'] = 'edit'
        _save(state_path,state)


def deliver(state_path, manifest_path, mp4):
    from delivery_check import delivery_errors
    state = _load(state_path)
    root = Path(state_path).resolve().parent
    errors = delivery_errors(state,root,_load(manifest_path),mp4,Path(manifest_path).resolve().parent)
    if errors:
        raise ValueError('\n'.join(errors))
    record = {key: {'path': os.path.relpath(path,root),'sha256': _hashed(state_path,Path(path).resolve())}
              for key,path in [('manifest',manifest_path),('video',mp4)]}
    if state.get('delivery') != record or state.get('stage') != 'delivered':
        state.update(stage='delivered',delivery=record)
        _save(state_path,state)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('lock'); q.add_argument('state'); q.add_argument('--owner', required=True); q.add_argument('--purpose', required=True)
    q = sub.add_parser('unlock'); q.add_argument('state')
    q = sub.add_parser('reserve', help='add a job file as reserved; needs the lock'); q.add_argument('state'); q.add_argument('job')
    q = sub.add_parser('submit'); q.add_argument('state'); q.add_argument('request_id'); q.add_argument('--provider-job-id')
    q = sub.add_parser('settle'); q.add_argument('state'); q.add_argument('request_id'); q.add_argument('--charge', type=float, required=True)
    q.add_argument('--output', action='append', default=[], help='result path relative to the state folder; repeatable')
    q.add_argument('--status', default='succeeded', choices=('succeeded', 'failed', 'cancelled'))
    q = sub.add_parser('charge', help="correct a settled job's charge"); q.add_argument('state'); q.add_argument('request_id')
    q.add_argument('--charge', type=float, required=True); q.add_argument('--evidence', required=True)
    q = sub.add_parser('init', help='create an empty state file'); q.add_argument('state'); q.add_argument('--project-id', required=True)
    q = sub.add_parser('put', help='merge a JSON file into a section or a shot'); q.add_argument('state')
    q.add_argument('section', choices=SECTIONS); q.add_argument('file')
    q = sub.add_parser('approve'); q.add_argument('state')
    q.add_argument('kind', choices=('story', 'reference', 'previs', 'asset', 'keyframe', 'continuity'))
    q.add_argument('ident', help='asset: role@version; keyframe: path; continuity: role; otherwise any text')
    q.add_argument('--evidence', required=True, help="the user's words")
    q = sub.add_parser('asset', help='add a pending asset record'); q.add_argument('state'); q.add_argument('ident', help='role@version')
    q.add_argument('--kind', required=True, choices=('character', 'prop', 'set')); q.add_argument('--path', required=True)
    q.add_argument('--source', default='generated', choices=('generated', 'existing', 'footage')); q.add_argument('--origin', help='where a footage crop came from: clip, time, area')
    q = sub.add_parser('keyframe', help='add a pending keyframe to a shot'); q.add_argument('state'); q.add_argument('shot'); q.add_argument('path')
    q.add_argument('--kind', required=True, choices=('start', 'end', 'reference')); q.add_argument('--previs-frame', type=int)
    q = sub.add_parser('note', help='write or close review notes on an asset or keyframe'); q.add_argument('state')
    q.add_argument('kind', choices=('asset', 'keyframe')); q.add_argument('ident'); q.add_argument('--note')
    q.add_argument('--resolve', choices=('fixed', 'accepted')); q.add_argument('--evidence')
    q = sub.add_parser('bind', help='bind approved assets to the shots that use their roles'); q.add_argument('state')
    q = sub.add_parser('select-takes')
    q.add_argument('state'); q.add_argument('selection')
    q = sub.add_parser('deliver')
    for name in ('state','manifest','mp4'):
        q.add_argument(name)
    a = p.parse_args()
    try:
        if a.action == 'select-takes': select_takes(a.state,_load(a.selection))
        elif a.action == 'deliver': deliver(a.state,a.manifest,a.mp4)
        elif a.action == 'lock': lock(a.state, a.owner, a.purpose)
        elif a.action == 'unlock': unlock(a.state)
        elif a.action == 'reserve': reserve(a.state, json.loads(Path(a.job).read_text()))
        elif a.action == 'submit': submit(a.state, a.request_id, a.provider_job_id)
        elif a.action == 'settle': settle(a.state, a.request_id, a.charge, a.output, a.status)
        elif a.action == 'charge': charge(a.state, a.request_id, a.charge, a.evidence)
        elif a.action == 'init': init(a.state, a.project_id)
        elif a.action == 'put': put(a.state, a.section, json.loads(Path(a.file).read_text()))
        elif a.action == 'approve': approve(a.state, a.kind, a.ident, a.evidence)
        elif a.action == 'asset': asset(a.state, a.ident, a.kind, a.path, a.source, a.origin)
        elif a.action == 'keyframe': keyframe(a.state, a.shot, a.path, a.kind, a.previs_frame)
        elif a.action == 'note': note(a.state, a.kind, a.ident, a.note, a.resolve, a.evidence)
        elif a.action == 'bind': bind(a.state)
    except ValueError as error:
        print(error); sys.exit(1)
    except Exception as error:  # a malformed or missing state file: still one line, never a traceback
        print(f'{type(error).__name__}: {error}'); sys.exit(1)
    print('OK')


if __name__ == '__main__': main()
