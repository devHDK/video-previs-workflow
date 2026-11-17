"""Readiness checks before paid video generation. Reads project state; never edits it or calls a provider."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from motion import figure_moves, members, travel  # noqa: E402


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dict(value): return value if isinstance(value, dict) else {}
def _list(value): return value if isinstance(value, list) else []
def _text(value): return isinstance(value, str) and value.strip() != ''
def _number(value): return type(value) in (int, float)
def _positive(value): return _number(value) and value > 0


SETUP_FIELDS = ('premise', 'tone', 'avoid', 'lead', 'setting')  # required; `hook` is optional. Same in story-design check_story.py
SETUP_NEEDED = 'setup needs premise, tone, avoid, lead and setting'


def _setup_ok(data): return all(_text(_dict(_dict(data).get('setup')).get(field)) for field in SETUP_FIELDS)


def _unchanged(root, record):
    path = record.get('path')
    return isinstance(path, str) and (root / path).is_file() and sha256(root / path) == record.get('sha256')


def _approved(state, key): return _dict(state.get(key)).get('approval') == 'approved'


def frame_at(t, fps): return int(t * fps + 0.5)  # round each cut once, so shot lengths never drift


def check_reference(ref, spec=None, max_duration=None):
    """Reference breakdown shape; given the previs spec, also each shot's frames against the reference cuts;
    given the model's longest take, also that a continuous source take was not split while it fits."""
    if not isinstance(ref, dict): return ['reference must be an object']
    source, errors = _dict(ref.get('source')), []
    if not (_text(source.get('path')) and _text(source.get('sha256'))):
        errors.append('reference: source.path and source.sha256 are required')
    if not _setup_ok(ref): errors.append(f'reference: {SETUP_NEEDED}')
    shots = ref.get('shots')
    if not isinstance(shots, list) or not shots: return errors + ['reference: shots must be a nonempty list']
    fps = _dict(spec).get('fps')
    if spec is not None and not (_number(fps) and fps > 0):
        errors.append('previs: spec fps required for reference timing'); spec = None
    frames = {s.get('id'): s.get('frames') for s in _list(_dict(spec).get('shots')) if isinstance(s, dict)}
    ids, previous_end, runs = set(), 0, []  # runs: [first shot id, seconds, shots] per uncut source take
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
        samples = [e for e in map(_dict, _list(shot.get('camera_evidence'))) if _number(e.get('t')) and start <= e['t'] <= end
                   and (_positive(e.get('subject_px')) or _positive(e.get('background_px')))]
        if len(samples) < 2 or len(samples) != len(_list(shot.get('camera_evidence'))):  # measured, not eyeballed
            errors.append(f'reference {sid}: camera_evidence needs 2+ samples with t and subject_px or background_px')
        if shot.get('continues_previous') is True:
            if not runs: errors.append(f'reference {sid}: continues_previous on the first shot')
            elif not _text(shot.get('split_reason')):
                errors.append(f'reference {sid}: split_reason is required when a shot continues the previous one')
        if shot.get('continues_previous') is True and runs: runs[-1][1] += end - start; runs[-1][2] += 1
        else: runs.append([sid, end - start, 1])
        for event in map(_dict, _list(shot.get('events'))):
            t = event.get('t')
            if not (_number(t) and _text(event.get('event'))): errors.append(f'reference {sid}: events need t and event')
            elif not start <= t < end: errors.append(f'reference {sid}: event at {t} s is outside the shot')  # a cut opens the next shot
        if spec is None or _text(shot.get('decision')): continue  # a recorded decision approves the deviation
        expected = frame_at(end, fps) - frame_at(start, fps)
        if sid not in frames: errors.append(f'reference {sid}: shot not in previs spec')
        elif frames[sid] != expected: errors.append(f'{sid}: previs frames {frames[sid]} differ from reference timing {expected}')
    if _positive(max_duration):
        errors += [f'reference {first}: take of {seconds:.1f} s fits max_duration_s {max_duration:g}; merge the split shots'
                   for first, seconds, count in runs if count > 1 and seconds <= max_duration]
    elif any(count > 1 for first, seconds, count in runs):  # an unchecked split would only be caught at `ready`, after previs
        errors.append('reference: a split take needs --max-duration (generation_profile.max_duration_s) to be checked')
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
    return check_reference(ref, spec, _dict(state.get('generation_profile')).get('max_duration_s'))


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
    errors = [] if _setup_ok(data) else [f'story: {SETUP_NEEDED}']
    if _text(data.get('purpose')) and _text(_dict(data.get('target_action')).get('action')) \
            and _text(_dict(data.get('structure')).get('id')):
        return errors
    return ['story: purpose, target_action and structure are required'] + errors


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
    props = {a['role_id'] for a in map(_dict, _list(state.get('assets')))
             if isinstance(a.get('role_id'), str) and a.get('approval') == 'approved' and a.get('kind') == 'prop'}
    for role in dict.fromkeys(r for r in roles.values() if isinstance(r, str) and r in props):
        handling = _dict(_dict(shot.get('props')).get(role))  # a prop with no stated source appears from nowhere in the take
        if not all(_text(handling.get(key)) for key in ('origin', 'holder', 'exit')):
            errors.append(f'{sid}: prop {role} needs origin, holder and exit')
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
        missing = [sid for sid, sha in shas.items() if sha is None]
        if missing:  # a null hash in a review must never stand in for an unapproved frame
            errors.append(f"continuity: role {role} cannot be reviewed until every shot using it has an approved keyframe "
                          f"({', '.join(missing)})")
        elif not review or review.get('approval') != 'approved':
            errors.append(f'continuity: role {role} needs an approved cross-shot keyframe review')
        elif _dict(review.get('keyframe_sha256')) != shas:
            errors.append(f'continuity: role {role} review is stale (keyframes changed)')
    return errors


PROFILE_NEEDED = 'generation_profile: model, max_duration_s and duration_step_s are required'


def profile_errors(state):
    """What the generator can do decides shot structure, so it is recorded before the story or reference is approved."""
    profile = _dict(state.get('generation_profile'))
    ok = _text(profile.get('model')) and _positive(profile.get('max_duration_s')) and _positive(profile.get('duration_step_s'))
    return [] if ok else [PROFILE_NEEDED]


def _spec(state, root):
    path = _dict(state.get('previs')).get('spec_path')
    if not isinstance(path, str) or not (root / path).is_file(): return {}
    try: return _dict(json.loads((root / path).read_text()))
    except ValueError: return {}


def duration_errors(state, root, shot_ids=None):
    """A take longer than the model's limit cannot be generated: every shot, or the sum of a job's covered shots."""
    limit, spec = _dict(state.get('generation_profile')).get('max_duration_s'), _spec(state, root)
    fps = spec.get('fps')
    if not (_positive(limit) and _positive(fps)): return []  # a missing profile is reported by profile_errors
    seconds = {s.get('id'): s['frames'] / fps for s in map(_dict, _list(spec.get('shots')))
               if isinstance(s.get('id'), str) and _number(s.get('frames'))}
    over = lambda who, value: [f'{who} {value:.1f} s exceeds generation_profile.max_duration_s {limit:g}'] if value > limit else []
    if shot_ids is not None:
        return over('job: take of', sum(seconds.get(sid, 0) for sid in shot_ids if isinstance(sid, str)))
    return [e for shot in map(_dict, _list(state.get('shots'))) if isinstance(shot.get('id'), str)
            for e in over(f"{shot['id']}:", seconds.get(shot['id'], 0))]


def kind_errors(state):
    return [f"asset {a.get('role_id')} {a.get('version')}: kind must be character, prop or set"
            for a in map(_dict, _list(state.get('assets')))
            if a.get('approval') == 'approved' and a.get('kind') not in ('character', 'prop', 'set')]


def unresolved_notes(record):
    """A review note is closed as fixed or accepted, with evidence; anything else blocks approval."""
    notes = _dict(record).get('review_notes')
    if notes is None: return False
    return not isinstance(notes, list) or any(
        _dict(n).get('resolution') not in ('fixed', 'accepted') or not _text(_dict(n).get('evidence')) for n in notes)


def note_errors(state):
    """Defects noted in review may not ride along on an approved asset or keyframe."""
    errors = [f"asset {a.get('role_id')} {a.get('version')}: unresolved review note" for a in map(_dict, _list(state.get('assets')))
              if a.get('approval') == 'approved' and unresolved_notes(a)]
    for shot in map(_dict, _list(state.get('shots'))):
        errors += [f"{shot.get('id')}: keyframe {k.get('path')}: unresolved review note" for k in map(_dict, _list(shot.get('keyframes')))
                   if k.get('approval') == 'approved' and unresolved_notes(k)]
    return errors


def budget_errors(state):
    budget = _dict(state.get('budget'))
    reserve, quote = budget.get('retry_reserve'), budget.get('max_shot_quote')
    if _number(reserve) and _number(quote) and quote >= 0 and reserve >= quote: return []  # 0/0 = all video via web Unlimited
    return ['budget: retry_reserve must cover max_shot_quote']


GROUP_SIZE = 5  # from this many figures on one role, how they move together is a decision of its own
MATCH_S = 0.75  # a previs action counts as listed when a reference event or a decision lies this close to it


def _figures(spec_shot, roles):
    """role -> the capsule-rooted figures mapped to it; parts of a figure, props and set pieces do not count."""
    objects = {o['id']: o for o in map(_dict, _list(_dict(spec_shot).get('objects'))) if isinstance(o.get('id'), str)}
    found = {}
    for oid in members(objects):
        role = _dict(roles).get(oid)
        if isinstance(role, str) and objects[oid].get('shape') == 'capsule': found.setdefault(role, []).append(objects[oid])
    return found


def group_errors(shot, spec_shot):
    """A crowd written without saying whether it moves as one or raggedly comes out in lockstep."""
    sid, errors = shot.get('id'), []
    for role, figures in _figures(spec_shot, shot.get('object_roles')).items():
        if len(figures) < GROUP_SIZE: continue
        group = _dict(_dict(shot.get('group_motion')).get(role))
        if group.get('sync') not in ('unison', 'ragged'):
            errors.append(f'{sid}: {len(figures)} figures share role {role}; group_motion.{role}.sync must be unison or ragged')
        elif group['sync'] == 'ragged' and not _positive(group.get('spread_s')):
            errors.append(f'{sid}: group_motion.{role}.spread_s required (seconds each member may lead or lag: half the measured width)')
    return errors


def motion_errors(shot, spec_shot, fps, ref_shot):
    """Reference-led: every turn, direction change or stop a figure makes in previs is a reference event or a recorded
    decision, and a figure that travels has its route written in the reference."""
    sid, errors, ref_shot = shot.get('id'), [], _dict(ref_shot)
    frames, start = _dict(spec_shot).get('frames'), ref_shot.get('start')
    if not (_positive(frames) and _positive(fps) and _number(start)): return []
    listed = [e['t'] - start for e in map(_dict, _list(ref_shot.get('events'))) if _number(e.get('t'))]
    listed += [d['t'] for d in map(_dict, _list(shot.get('unlisted_motion'))) if _number(d.get('t')) and _text(d.get('decision'))]
    for role, figures in _figures(spec_shot, shot.get('object_roles')).items():
        if len(figures) >= GROUP_SIZE: continue
        for item in figures:
            if not _list(item.get('keys')): continue
            for move in figure_moves(item, frames, fps):
                if not any(abs(move['t'] - t) <= MATCH_S for t in listed):
                    size = f" {move['degrees']} deg" if 'degrees' in move else ''
                    errors.append(f"{sid}: {role} {move['kind']}{size} at {move['t']:g} s has no reference event; list it in the "
                                  f'reference or record an unlisted_motion decision')
            metres = travel(item, frames)
            if metres > 1 and not _text(_dict(ref_shot.get('travel')).get(role)):
                errors.append(f'reference {sid}: travel.{role} required (destination, route, who stands beside it): '
                              f'it moves {metres:.1f} m in previs')
    return errors


def _reference(state, root):
    record = _dict(state.get('reference'))
    if record.get('approval') != 'approved' or not isinstance(record.get('path'), str): return {}
    try: return _dict(json.loads((root / record['path']).read_text()))
    except (OSError, ValueError): return {}


def blocking_errors(state, root, shot_ids=None):
    spec, ref = _spec(state, root), _reference(state, root)
    spec_shots = {s.get('id'): s for s in map(_dict, _list(spec.get('shots')))}
    ref_shots = {s.get('id'): s for s in map(_dict, _list(ref.get('shots')))}
    errors = []
    for shot in map(_dict, _list(state.get('shots'))):
        sid = shot.get('id')
        if not isinstance(sid, str) or sid not in spec_shots or (shot_ids is not None and sid not in shot_ids): continue
        errors += group_errors(shot, spec_shots[sid])
        if sid in ref_shots: errors += motion_errors(shot, spec_shots[sid], spec.get('fps'), ref_shots[sid])
    return errors


def check_qa(state, root):
    """After generation: a selected take per shot, a result for every required event, a measured spread per group."""
    if not isinstance(state, dict): return ['state must be an object']
    errors = []
    for shot in map(_dict, _list(state.get('shots'))):
        sid, take = shot.get('id'), shot.get('selected_output')
        take = take if isinstance(take, str) else _dict(take).get('take')
        if not (isinstance(take, str) and (root / take).is_file()): errors.append(f'{sid}: selected_output take file required')
        results = _dict(shot.get('event_results'))
        for event in _list(shot.get('required_events')):
            name = event if isinstance(event, str) else _dict(event).get('event')
            result = _dict(results.get(name))
            if result.get('result') not in ('pass', 'accepted') or not _text(result.get('evidence')):
                errors.append(f'{sid}: event needs a pass or accepted result with evidence: {name}')
        for role, group in _dict(shot.get('group_motion')).items():
            group = _dict(group); measured, target = group.get('measured_s'), group.get('spread_s')
            if not _number(measured): errors.append(f'{sid}: group_motion.{role}.measured_s required (media.py spread on the take)')
            elif group.get('sync') == 'ragged' and _positive(target) and not 0.5 * target <= measured <= 2 * target \
                    and not (group.get('result') == 'accepted' and _text(group.get('evidence'))):
                errors.append(f'{sid}: group {role} spread {measured:g} s is outside 0.5-2x the target {target:g} s')
    return errors


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
    return (errors + blocking_errors(state, root) + continuity_errors(state) + kind_errors(state) + note_errors(state)
            + profile_errors(state) + duration_errors(state, root) + budget_errors(state))


def check_submission(state, job, root):
    """One paid job: its shot must be ready and the job must not eat the retry reserve unless it is a retry."""
    if not isinstance(state, dict) or not isinstance(job, dict): return ['state and job must be objects']
    sid = job.get('shot')
    by_id = {s['id']: s for s in _list(state.get('shots')) if isinstance(s, dict) and isinstance(s.get('id'), str)}
    shot = by_id.get(sid) if isinstance(sid, str) else None
    if shot is None: return [f'{sid}: shot not found in state']
    covered = job.get('shots', [sid])  # a sequence take covers consecutive shots and starts on the first one's keyframe
    if not (isinstance(covered, list) and covered and covered[0] == sid): return ['job: shots must begin with shot']
    errors = story_errors(state, root)
    if _dict(state.get('previs')).get('approval') != 'approved': errors.append('previs: approval required')
    spec_errors, objects = spec_objects(state, root)
    errors += spec_errors
    roles = set()
    for cid in covered:
        if not isinstance(cid, str) or cid not in by_id: errors.append(f'{cid}: shot not found in state'); continue
        errors += shot_errors(state, by_id[cid], [] if spec_errors else objects.get(cid), root)
        roles |= {r for r in _dict(by_id[cid].get('object_roles')).values() if isinstance(r, str)}
    errors += blocking_errors(state, root, covered) + continuity_errors(state, roles)
    errors += kind_errors(state) + note_errors(state) + profile_errors(state) + duration_errors(state, root, covered)
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
    paid = not (job.get('route') == 'manual' and quote == 0)  # the limit counts paid submissions; free manual takes are only tallied
    if paid and num('attempts_used') >= num('max_attempts'): errors.append('budget: attempt limit reached')
    return errors


def _report(errors):
    print('\n'.join(errors) if errors else 'OK')
    sys.exit(1 if errors else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('ready', help='whole project ready for paid video generation'); q.add_argument('state')
    q = sub.add_parser('submit', help='one paid video job'); q.add_argument('state'); q.add_argument('job')
    q = sub.add_parser('qa', help='selected takes checked against required events'); q.add_argument('state')
    q = sub.add_parser('reference', help='reference breakdown file, before approval'); q.add_argument('file')
    q.add_argument('--max-duration', type=float, help="the model's longest take in seconds, to check split takes")
    a = p.parse_args()
    if a.action == 'reference': _report(check_reference(json.loads(Path(a.file).read_text()), max_duration=a.max_duration))
    state_path = Path(a.state).resolve()
    state = json.loads(state_path.read_text())
    if a.action == 'ready': _report(check_project(state, state_path.parent))
    if a.action == 'qa': _report(check_qa(state, state_path.parent))
    else: _report(check_submission(state, json.loads(Path(a.job).read_text()), state_path.parent))


if __name__ == '__main__': main()
