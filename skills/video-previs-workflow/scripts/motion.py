"""Deterministic frame samples shared by validation and Blender baking."""

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
