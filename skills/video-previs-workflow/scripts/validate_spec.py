"""Validate the small, independently defined proxy scene format; no Blender needed."""
import argparse
import json
import math
import re
from pathlib import Path


def validate(spec):
    errors = []
    def need(ok, message):
        if not ok: errors.append(message)
    def integer(v): return type(v) is int and v > 0
    def vector(v, low=None, high=None, positive=False):
        return (isinstance(v, list) and len(v) == 3 and all(
            type(x) in (int, float) and math.isfinite(x)
            and (low is None or x >= low) and (high is None or x <= high)
            and (not positive or x > 0) for x in v))
    if not isinstance(spec, dict): return ['spec must be an object']
    need(spec.get('version') == 1, 'version must be 1')
    for key in ('fps', 'width', 'height'):
        need(integer(spec.get(key)), f'{key} must be a positive integer')
    for key in ('width', 'height'):
        if integer(spec.get(key)): need(spec[key] % 2 == 0, f'{key} must be even for H.264')
    shots = spec.get('shots')
    if not isinstance(shots, list) or not shots: return errors + ['shots must be a nonempty list']
    seen = set()
    for shot in shots:
        if not isinstance(shot, dict): errors.append('shot must be an object'); continue
        sid = shot.get('id')
        valid_id = isinstance(sid, str) and re.fullmatch(r'[A-Za-z0-9_-]+', sid)
        need(valid_id and sid not in seen, 'shot id must be unique and path-safe')
        if isinstance(sid, str): seen.add(sid)
        n = shot.get('frames'); need(integer(n), f'{sid}: frames must be positive integer')
        cam = shot.get('camera', {})
        if not isinstance(cam, dict): errors.append(f'{sid}: invalid camera'); cam = {}
        for key in (('position',) if 'follow' in cam else ('position', 'target')):
            need(vector(cam.get(key)), f'{sid}: camera {key} needs 3 finite numbers')
        objects = shot.get('objects')
        if not isinstance(objects, list): errors.append(f'{sid}: objects must be a list'); continue
        ids = set()
        for obj in objects:
            if not isinstance(obj, dict): errors.append(f'{sid}: object must be a dictionary'); continue
            oid = obj.get('id')
            need(isinstance(oid, str) and bool(oid) and oid not in ids, f'{sid}: unique object id required')
            if isinstance(oid, str): ids.add(oid)
            need(obj.get('shape') in ('cube', 'sphere', 'cylinder', 'capsule'), f'{sid}/{oid}: unsupported shape')
            need(vector(obj.get('color'), 0, 1), f'{sid}/{oid}: color must be RGB 0..1')
            need(vector(obj.get('scale'), positive=True), f'{sid}/{oid}: scale must be positive XYZ')
            keys = obj.get('keys')
            if not isinstance(keys, list) or not keys: errors.append(f'{sid}/{oid}: keys required'); continue
            last = 0
            for key in keys:
                if not isinstance(key, dict): errors.append('key must be an object'); continue
                f = key.get('frame')
                good = integer(f) and integer(n) and last < f <= n
                need(good, f'{sid}/{oid}: frames must increase within 1..frames')
                if good: last = f
                need(vector(key.get('position')), f'{sid}/{oid}: position must be XYZ')
                if 'rotation' in key: need(vector(key['rotation']), 'rotation must be XYZ radians')
            need(isinstance(keys[0], dict) and keys[0].get('frame') == 1, f'{sid}/{oid}: first key must be frame 1')
        # Optional controls are validated before any motion sampling.
        def finite(v): return type(v) in (int, float) and math.isfinite(v)
        need(finite(cam.get('lens', 40)) and cam.get('lens', 40) > 0, f'{sid}: lens must be positive')
        need(cam.get('interpolation', 'linear') in ('linear', 'smooth'), f'{sid}: invalid camera interpolation')
        need(vector(cam.get('offset', [0, 0, 0])), f'{sid}: offset must be XYZ')
        if 'follow' in cam:
            need(isinstance(cam['follow'], str) and cam['follow'] in ids, f'{sid}: unknown follow subject')
        if 'keys' in cam:
            ck = cam['keys']
            need(isinstance(ck, list) and bool(ck), f'{sid}: camera keys must be nonempty')
            last = 0
            for key in ck if isinstance(ck, list) else []:
                if not isinstance(key, dict): errors.append('camera key must be an object'); continue
                f = key.get('frame')
                good = integer(f) and integer(n) and last < f <= n
                need(good, f'{sid}: camera frames must increase within shot')
                if good: last = f
                for prop in ('position', 'target'):
                    if prop in key: need(vector(key[prop]), f'{sid}: invalid camera {prop}')
                if 'lens' in key: need(finite(key['lens']) and key['lens'] > 0, f'{sid}: invalid keyed lens')
                need(set(key) <= {'frame', 'position', 'target', 'lens'}, f'{sid}: unsupported camera key property')
            if isinstance(ck, list) and ck:
                need(isinstance(ck[0], dict) and ck[0].get('frame') == 1, f'{sid}: first camera key must be frame 1')
        for obj in objects:
            if not isinstance(obj, dict): continue
            need(obj.get('interpolation', 'linear') in ('linear', 'smooth'), f'{sid}: invalid object interpolation')
            for key in obj.get('keys', []) if isinstance(obj.get('keys'), list) else []:
                if isinstance(key, dict): need(set(key) <= {'frame', 'position', 'rotation'}, f'{sid}: unsupported object key property')
            windows = obj.get('ground_contact', [])
            need(isinstance(windows, list), f'{sid}: ground_contact must be a list')
            for w in windows if isinstance(windows, list) else []:
                need(isinstance(w, list) and len(w) == 2 and all(integer(x) for x in w)
                     and integer(n) and 1 <= w[0] <= w[1] <= n, f'{sid}: invalid ground contact window')
        audit = shot.get('audit', {})
        if not isinstance(audit, dict): errors.append('audit must be an object'); audit = {}
        need(integer(audit.get('step', 1)), f'{sid}: audit step must be positive integer')
        need(finite(audit.get('margin', 0)) and 0 <= audit.get('margin', 0) < .5, f'{sid}: invalid frame margin')
        need(finite(audit.get('ground_z', 0)), f'{sid}: invalid ground height')
        need(finite(audit.get('tolerance', .05)) and audit.get('tolerance', .05) >= 0, f'{sid}: invalid ground tolerance')
        subjects = audit.get('subjects', [])
        need(isinstance(subjects, list) and all(isinstance(x, str) and x in ids for x in subjects), f'{sid}: unknown audit subject')
        if not errors:
            from motion import camera_at
            for frame in range(1, n + 1):
                state = camera_at(shot, frame)
                distance = sum((a - b) ** 2 for a, b in zip(state['position'], state['target']))
                if distance < 1e-12:
                    errors.append(f'{sid}: camera coincides with target at frame {frame}')
                    break
    return errors


def timeline(spec):
    end = 0
    result = []
    for shot in spec['shots']:
        result.append((shot['id'], end, end + shot['frames']))
        end += shot['frames']
    return result


def changed_shots(before, after):
    a = {s['id']: s for s in before['shots']}
    b = {s['id']: s for s in after['shots']}
    global_change = any(before.get(k) != after.get(k) for k in ('fps', 'width', 'height'))
    order_change = list(a) != list(b)
    return sorted(k for k in a.keys() | b.keys() if global_change or order_change or a.get(k) != b.get(k))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('spec', type=Path); p.add_argument('--previous', type=Path)
    args = p.parse_args()
    spec = json.loads(args.spec.read_text())
    errors = validate(spec)
    if errors: print('\n'.join(errors)); return 1
    result = {'timeline_zero_based_end_exclusive': timeline(spec)}
    if args.previous:
        before = json.loads(args.previous.read_text())
        old_errors = validate(before)
        if old_errors: print('\n'.join(old_errors)); return 1
        result['changed_shots'] = changed_shots(before, spec)
    print(json.dumps(result, indent=2)); return 0

if __name__ == '__main__':
    raise SystemExit(main())
