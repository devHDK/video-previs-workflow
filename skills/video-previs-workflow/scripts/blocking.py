"""Helpers for a project's scene generator script: times to frames, tracks, body-relative positions and a person
proxy that shows which way it faces. Crowds, folds and props stay in the project script."""
import math


def frame_of(t, fps, start=0.0):
    """1-based shot-local frame of time t; each boundary is rounded once, as the gate does for reference cuts."""
    return int(t * fps + 0.5) - int(start * fps + 0.5) + 1


def track(keys):
    """Piecewise-linear value over time from [(t, value)], value a number or a list; clamped at both ends."""
    def at(t):
        if t <= keys[0][0]: return keys[0][1]
        for (ta, a), (tb, b) in zip(keys, keys[1:]):
            if ta <= t <= tb:
                u = (t - ta) / (tb - ta)
                return [x + (y - x) * u for x, y in zip(a, b)] if isinstance(a, list) else a + (b - a) * u
        return keys[-1][1]
    return at


def local_to_world(root_xy, facing_deg, offset, z0=0.0):
    """World position of a point given relative to a figure: offset = [own-right, forward, up].
    Facing 0 looks toward -y (a camera placed at negative y); +90 turns the face toward +x."""
    a = math.radians(facing_deg)
    forward, right = (math.sin(a), -math.cos(a)), (-math.cos(a), -math.sin(a))
    return [root_xy[0] + offset[0] * right[0] + offset[1] * forward[0],
            root_xy[1] + offset[0] * right[1] + offset[1] * forward[1], z0 + offset[2]]


def person(pid, at, frames, body_color, head_color=(0.15, 0.1, 0.08), face_color=(0.87, 0.66, 0.55), height=1.62):
    """Body capsule, head sphere and a face marker, so a turn reads in the render (a bare capsule has no front).
    at(frame) -> (root_xy, z0, facing_deg); frames must start at 1."""
    k = height / 1.62
    def part(suffix, shape, color, scale, offset):
        keys = []
        for frame in frames:
            root, z0, facing = at(frame)
            keys.append({'frame': frame, 'position': local_to_world(root, facing, [v * k for v in offset], z0),
                         'rotation': [0, 0, math.radians(facing)]})
        return {'id': pid + suffix, 'shape': shape, 'color': list(color), 'scale': [v * k for v in scale], 'keys': keys}
    return [part('', 'capsule', body_color, [0.52, 0.44, 0.68], [0, 0, 0]),
            part('_head', 'sphere', head_color, [0.095, 0.105, 0.115], [0, 0, 1.48]),
            part('_face', 'cube', face_color, [0.065, 0.012, 0.08], [0, 0.095, 1.47])]
