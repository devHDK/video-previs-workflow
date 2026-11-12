"""Readiness checks before paid video generation. Reads project state; never edits it or calls a provider."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dict(value): return value if isinstance(value, dict) else {}
def _list(value): return value if isinstance(value, list) else []
def _text(value): return isinstance(value, str) and value.strip() != ''
def _number(value): return type(value) in (int, float)


def _unchanged(root, record):
    path = record.get('path')
    return isinstance(path, str) and (root / path).is_file() and sha256(root / path) == record.get('sha256')


def _approved(state, key): return _dict(state.get(key)).get('approval') == 'approved'


def frame_at(t, fps): return int(t * fps + 0.5)  # round each cut once, so shot lengths never drift


def check_reference(ref, spec=None):
    """Reference breakdown shape; given the previs spec, also each shot's frames against the reference cuts."""
    if not isinstance(ref, dict): return ['reference must be an object']
    source, errors = _dict(ref.get('source')), []
    if not (_text(source.get('path')) and _text(source.get('sha256'))):
        errors.append('reference: source.path and source.sha256 are required')
    shots = ref.get('shots')
    if not isinstance(shots, list) or not shots: return errors + ['reference: shots must be a nonempty list']
    fps = _dict(spec).get('fps')
    if spec is not None and not (_number(fps) and fps > 0):
        errors.append('previs: spec fps required for reference timing'); spec = None
    frames = {s.get('id'): s.get('frames') for s in _list(_dict(spec).get('shots')) if isinstance(s, dict)}
    ids, previous_end = set(), 0
    for shot in shots:
        sid = shot.get('id') if isinstance(shot, dict) else None
        if not _text(sid) or sid in ids: errors.append('reference: shot id must be unique and nonempty'); continue
        ids.add(sid)
        start, end = shot.get('start'), shot.get('end')
        if not (_number(start) and _number(end) and start < end):
            errors.append(f'reference {sid}: start and end must be numbers with start < end'); continue
        if abs(start - previous_end) > 1e-3: errors.append(f'reference {sid}: gap or overlap with previous shot')
        previous_end = end
        if not (_text(shot.get('camera')) and _text(shot.get('action'))):
            errors.append(f'reference {sid}: camera and action are required')
        for event in map(_dict, _list(shot.get('events'))):
            t = event.get('t')
            if not (_number(t) and _text(event.get('event'))): errors.append(f'reference {sid}: events need t and event')
            elif not start <= t < end: errors.append(f'reference {sid}: event at {t} s is outside the shot')  # a cut opens the next shot
        if spec is None or _text(shot.get('decision')): continue  # a recorded decision approves the deviation
        expected = frame_at(end, fps) - frame_at(start, fps)
        if sid not in frames: errors.append(f'reference {sid}: shot not in previs spec')
        elif frames[sid] != expected: errors.append(f'{sid}: previs frames {frames[sid]} differ from reference timing {expected}')
    return errors


def reference_errors(state, root):
    record = _dict(state.get('reference'))
    if not _unchanged(root, record): return ['reference: file missing or changed since approval']
    try: ref = json.loads((root / record['path']).read_text())
    except ValueError: ref = None
    spec, path = None, _dict(state.get('previs')).get('spec_path')
    if isinstance(path, str) and (root / path).is_file():  # a missing spec is reported by spec_objects
        try: spec = _dict(json.loads((root / path).read_text()))
        except ValueError: pass
    return check_reference(ref, spec)


def story_errors(state, root):
    """Direction: an approved story design, or for a reference-led video an approved reference breakdown."""
    if not (_approved(state, 'story') or _approved(state, 'reference')):
        return ['story: approved story design or reference breakdown required']
    errors = reference_errors(state, root) if _approved(state, 'reference') else []
    return errors + (_story_file_errors(state, root) if _approved(state, 'story') else [])


def _story_file_errors(state, root):
    story = _dict(state.get('story'))
    if not _unchanged(root, story): return ['story: file missing or changed since approval']
    try: data = _dict(json.loads((root / story['path']).read_text()))
    except ValueError: data = {}
    if _text(data.get('purpose')) and _text(_dict(data.get('target_action')).get('action')) \
            and _text(_dict(data.get('structure')).get('id')):
        return []
    return ['story: purpose, target_action and structure are required']


def spec_objects(state, root):
    path = _dict(state.get('previs')).get('spec_path')
    if not isinstance(path, str) or not (root / path).is_file(): return ['previs: spec file not found'], {}
    try: spec = _dict(json.loads((root / path).read_text()))
    except ValueError: return ['previs: spec file is not valid JSON'], {}
    objects = {}
    for shot in _list(spec.get('shots')):
        if isinstance(shot, dict) and isinstance(shot.get('id'), str):
            objects[shot['id']] = [o['id'] for o in _list(shot.get('objects'))
                                   if isinstance(o, dict) and isinstance(o.get('id'), str)]
    return [], objects


def _shas(records, approved_only=False):
    found = {}
    for r in _list(records):
        if isinstance(r, dict) and isinstance(r.get('role_id'), str) and _text(r.get('sha256')) \
                and (not approved_only or r.get('approval') == 'approved'):
            found.setdefault(r.get('role_id'), set()).add(r['sha256'])
    return found


def approved_start_sha(shot):
    for k in _list(shot.get('keyframes')):
        if isinstance(k, dict) and k.get('kind') == 'start' and k.get('approval') == 'approved': return k.get('sha256')
    return None


def shot_errors(state, shot, objects, root):
    sid, errors = shot.get('id'), []
    if objects is None: errors.append(f'{sid}: shot not found in previs spec'); objects = []
    if not _list(shot.get('required_events')): errors.append(f'{sid}: required_events missing')
    roles = _dict(shot.get('object_roles'))
    errors += [f'{sid}: object {oid} has no role decision (map to a role or null)' for oid in objects if oid not in roles]
    errors += [f'{sid}: object {oid} role must be a string or null' for oid, r in roles.items()
               if r is not None and not isinstance(r, str)]
    approved, bound = _shas(state.get('assets'), approved_only=True), _shas(shot.get('asset_bindings'))
    for role in dict.fromkeys(r for r in roles.values() if isinstance(r, str)):
        if not approved.get(role, set()) & bound.get(role, set()):
            errors.append(f'{sid}: role {role} needs an approved asset bound to this shot')
    starts = [k for k in _list(shot.get('keyframes'))
              if isinstance(k, dict) and k.get('kind') == 'start' and k.get('approval') == 'approved']
    if not starts: errors.append(f'{sid}: approved start keyframe required')
    elif len(starts) > 1: errors.append(f'{sid}: more than one approved start keyframe')
    for k in _list(shot.get('keyframes')):
        if isinstance(k, dict) and k.get('approval') == 'approved' and not _unchanged(root, k):
            errors.append(f"{sid}: keyframe {k.get('path')} missing or changed since approval")
    return errors


def continuity_errors(state, roles=None):
    """Every role used by 2+ shots needs an approved review whose keyframe hashes match the current approved keyframes."""
    uses = {}
    for shot in _list(state.get('shots')):
        if isinstance(shot, dict) and isinstance(shot.get('id'), str):
            for role in dict.fromkeys(r for r in _dict(shot.get('object_roles')).values() if isinstance(r, str)):
                uses.setdefault(role, {})[shot['id']] = approved_start_sha(shot)
    reviews = {r.get('role_id'): r for r in _list(state.get('continuity')) if isinstance(r, dict)}
    errors = []
    for role, shas in uses.items():
        if len(shas) < 2 or (roles is not None and role not in roles): continue
        review = reviews.get(role)
        if not review or review.get('approval') != 'approved':
            errors.append(f'continuity: role {role} needs an approved cross-shot keyframe review')
        elif _dict(review.get('keyframe_sha256')) != shas:
            errors.append(f'continuity: role {role} review is stale (keyframes changed)')
    return errors


def budget_errors(state):
    budget = _dict(state.get('budget'))
    reserve, quote = budget.get('retry_reserve'), budget.get('max_shot_quote')
    if _number(reserve) and _number(quote) and quote >= 0 and reserve >= quote: return []  # 0/0 = all video via web Unlimited
    return ['budget: retry_reserve must cover max_shot_quote']


def check_project(state, root):
    if not isinstance(state, dict): return ['state must be an object']
    errors = story_errors(state, root)
    if _dict(state.get('previs')).get('approval') != 'approved': errors.append('previs: approval required')
    spec_errors, objects = spec_objects(state, root)
    errors += spec_errors
    versions = {}
    for shot in _list(state.get('shots')):
        if not isinstance(shot, dict): continue
        if not isinstance(shot.get('id'), str): errors.append('shot id must be a string'); continue
        errors += shot_errors(state, shot, [] if spec_errors else objects.get(shot['id']), root)
        for role, shas in _shas(shot.get('asset_bindings')).items(): versions.setdefault(role, set()).update(shas)
    errors += [f'role {role} is bound to different versions across shots' for role, shas in versions.items() if len(shas) > 1]
    return errors + continuity_errors(state) + budget_errors(state)


def check_submission(state, job, root):
    """One paid job: its shot must be ready and the job must not eat the retry reserve unless it is a retry."""
    if not isinstance(state, dict) or not isinstance(job, dict): return ['state and job must be objects']
    sid = job.get('shot')
    shot = next((s for s in _list(state.get('shots')) if isinstance(s, dict) and s.get('id') == sid), None)
    if shot is None: return [f'{sid}: shot not found in state']
    errors = story_errors(state, root)
    if _dict(state.get('previs')).get('approval') != 'approved': errors.append('previs: approval required')
    spec_errors, objects = spec_objects(state, root)
    errors += spec_errors + shot_errors(state, shot, [] if spec_errors else objects.get(sid), root)
    errors += continuity_errors(state, {r for r in _dict(shot.get('object_roles')).values() if isinstance(r, str)})
    start = approved_start_sha(shot)
    if start is not None and job.get('start_frame_sha256') != start:
        errors.append(f'{sid}: job start frame is not the approved keyframe')
    errors += budget_errors(state)
    budget, quote = _dict(state.get('budget')), job.get('quote')
    if not _number(quote): return errors + ['budget: job quote required']
    if not _number(budget.get('cap')): errors.append('budget: cap required')
    if quote < 0: errors.append('budget: job quote must not be negative')
    elif quote == 0 and job.get('route') != 'manual': errors.append('budget: only manual jobs may be quoted 0')  # MCP always bills
    num = lambda key: budget[key] if _number(budget.get(key)) else 0  # missing cap or max_attempts -> 0 -> blocked
    if quote > num('max_shot_quote'): errors.append('budget: job quote exceeds max_shot_quote')  # reserve sized from it
    available = num('cap') - num('settled') - num('reserved')
    if job.get('retry_of'):
        if quote > available: errors.append('budget: quote exceeds available credits')
    elif available - quote < num('retry_reserve'):
        errors.append('budget: submission would consume the retry reserve')
    if num('attempts_used') >= num('max_attempts'): errors.append('budget: attempt limit reached')
    return errors


def _report(errors):
    print('\n'.join(errors) if errors else 'OK')
    sys.exit(1 if errors else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('ready', help='whole project ready for paid video generation'); q.add_argument('state')
    q = sub.add_parser('submit', help='one paid video job'); q.add_argument('state'); q.add_argument('job')
    q = sub.add_parser('reference', help='reference breakdown file, before approval'); q.add_argument('file')
    a = p.parse_args()
    if a.action == 'reference': _report(check_reference(json.loads(Path(a.file).read_text())))
    state_path = Path(a.state).resolve()
    state = json.loads(state_path.read_text())
    if a.action == 'ready': _report(check_project(state, state_path.parent))
    else: _report(check_submission(state, json.loads(Path(a.job).read_text()), state_path.parent))


if __name__ == '__main__': main()
