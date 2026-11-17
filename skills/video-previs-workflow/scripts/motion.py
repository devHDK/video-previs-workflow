"""Deterministic frame samples shared by validation and Blender baking, and what a figure does along its path."""
import math

def sample(keys, frame, interpolation='linear', defaults=None):
    state = dict(defaults or {'rotation': [0, 0, 0]})
    expanded = []
    for key in keys:
        state = dict(state, **key)
        expanded.append(state)
    if frame <= expanded[0]['frame']: return dict(expanded[0])
    if frame >= expanded[-1]['frame']: return dict(expanded[-1])
    for a, b in zip(expanded, expanded[1:]):
        if a['frame'] <= frame <= b['frame']:
            t = (frame - a['frame']) / (b['frame'] - a['frame'])
            if interpolation == 'smooth': t = t * t * (3 - 2 * t)
            out = {'frame': frame}
            for name in a.keys() - {'frame'}:
                left, right = a[name], b[name]
                out[name] = ([x + (y - x) * t for x, y in zip(left, right)]
                             if isinstance(left, list) else left + (right - left) * t)
            return out


def object_at(item, frame):
    return sample(item['keys'], frame, item.get('interpolation', 'linear'))


def camera_at(shot, frame):
    camera = shot['camera']
    defaults = {'position': camera['position'], 'target': [0, 0, 0] if camera.get('follow') else camera.get('target', [0, 0, 0]),
                'lens': camera.get('lens', 40)}
    keys = camera.get('keys', [{'frame': 1}])
    if camera.get('follow'):
        keys = [{k: v for k, v in key.items() if k != 'target'} for key in keys]
    result = sample(keys, frame,
                    camera.get('interpolation', 'linear'), defaults)
    if camera.get('follow'):
        item = next(o for o in shot['objects'] if o['id'] == camera['follow'])
        position = object_at(item, frame)['position']
        result['target'] = [x + y for x, y in zip(position, camera.get('offset', [0, 0, 0]))]
    return result


def members(ids):
    """Root ids: an id that is another id plus '_part' is a part of that figure (blocking.person), not a member."""
    ids = set(ids)
    return sorted(i for i in ids if not any(i != root and i.startswith(root + '_') for root in ids))


def _path(item, frames):
    states = [object_at(item, f) for f in range(1, frames + 1)]
    return [s['position'] for s in states], [math.degrees(s['rotation'][2]) for s in states]


def travel(item, frames):
    """Metres a figure's root covers on the ground over the shot."""
    points, _ = _path(item, frames)
    return sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:]))


def figure_moves(item, frames, fps, turn=45, stop=0.5, walking=0.2):
    """Turns, direction changes and stops of one figure, read from its baked path, as {'kind', 't', ...} with t in
    seconds from the shot start. These are the actions a generated take will show whether or not anyone listed them."""
    points, yaw = _path(item, frames)
    moves, start = [], 0
    for i in range(1, frames + 1):  # a turn is one run of rotation in the same direction
        step = yaw[i] - yaw[i - 1] if i < frames else 0
        before = yaw[i - 1] - yaw[i - 2] if i - 1 > start else step
        if abs(step) < 0.01 or step * before < 0:
            if abs(yaw[i - 1] - yaw[start]) >= turn:
                moves.append({'kind': 'turn', 't': round(start / fps, 2), 'degrees': round(abs(yaw[i - 1] - yaw[start]))})
            start = i if abs(step) < 0.01 else i - 1
    span = max(1, round(fps / 4))  # quarter-second strides smooth out key jitter
    strides = [(i / fps, math.dist(points[i][:2], points[i + span][:2]) / (span / fps),
                math.degrees(math.atan2(points[i + span][1] - points[i][1], points[i + span][0] - points[i][0])))
               for i in range(0, frames - span, span)]
    last, rest, moved = None, None, False
    for t, speed, heading in strides:
        if speed < walking:
            if moved and rest is None: rest = t
            continue
        if rest is not None and t - rest >= stop: moves.append({'kind': 'stop', 't': round(rest, 2), 'seconds': round(t - rest, 2)})
        if last is not None and abs((heading - last + 180) % 360 - 180) >= turn:
            moves.append({'kind': 'direction', 't': round(t, 2), 'degrees': round(abs((heading - last + 180) % 360 - 180))})
        last, rest, moved = heading, None, True
    return sorted(moves, key=lambda m: m['t'])
