"""Sampled Blender geometry checks; not a generated-video quality score."""
import math
from motion import object_at, camera_at

LINE_NEUTRAL = 0.1  # sine of the angle to the action line under which a camera counts as on it (about 6 degrees)
SCREEN_MIN = 0.5    # metres of net sideways travel before a figure has a screen direction

def framing_issues(points, margin=0, crop_ok=False):
    issues = []
    if any(z <= 0 for x, y, z in points): issues.append('behind_camera')
    if not crop_ok and any(x < margin or x > 1-margin or y < margin or y > 1-margin for x, y, z in points):
        issues.append('outside_frame')
    return issues


def same_group(a, b, groups):
    """Proxies of one figure (head, face marker, mask) are not occluders of each other."""
    return any(a in group and b in group for group in groups)


def contact_issue(bottom, ground, tolerance, frame, windows):
    if not any(start <= frame <= end for start, end in windows): return None
    if bottom < ground - tolerance: return 'penetrating_ground'
    if bottom > ground + tolerance: return 'floating'
    return None


def _ground(shot, object_id, frame):
    return object_at(next(o for o in shot['objects'] if o['id'] == object_id), frame)['position'][:2]


def line_side(shot, frame):
    """Which side of the audit.line pair the camera stands on at this frame: 1, -1, or 0 when it is on the line."""
    a, b = (_ground(shot, i, frame) for i in sorted(shot['audit']['line']))
    c = camera_at(shot, frame)['position']
    along = (b[0] - a[0], b[1] - a[1])
    out = (c[0] - (a[0] + b[0]) / 2, c[1] - (a[1] + b[1]) / 2)
    lengths = math.hypot(*along) * math.hypot(*out)
    if lengths < 1e-6: return 0
    sine = (along[0] * out[1] - along[1] * out[0]) / lengths
    return 0 if abs(sine) < LINE_NEUTRAL else 1 if sine > 0 else -1


def screen_travel(shot, object_id):
    """Net metres the object's root moves toward screen right over the shot, on the ground plane."""
    total, before = 0.0, _ground(shot, object_id, 1)
    for frame in range(2, shot['frames'] + 1):
        here, camera = _ground(shot, object_id, frame), camera_at(shot, frame)
        forward = (camera['target'][0] - camera['position'][0], camera['target'][1] - camera['position'][1])
        length = math.hypot(*forward)
        if length >= 1e-6:
            total += ((here[0] - before[0]) * forward[1] - (here[1] - before[1]) * forward[0]) / length
        before = here
    return total


def staging_findings(spec):
    """Action line and screen direction per shot id, read from the whole spec; shots that declare neither are absent."""
    result, previous = {}, None
    for shot in spec['shots']:
        audit = shot.get('audit', {})
        checks, findings = [], []
        if 'line' in audit:
            checks.append('action_line')
            if previous is not None and set(previous.get('audit', {}).get('line', [])) == set(audit['line']) \
                    and audit.get('line_cross_ok') is not True:
                sides = line_side(previous, previous['frames']), line_side(shot, 1)
                if 0 not in sides and sides[0] != sides[1]:
                    findings.append({'frame': 1, 'object': 'camera', 'issues': ['line_crossed']})
        if 'screen_direction' in audit:
            checks.append('screen_direction')
            for object_id, want in audit['screen_direction'].items():
                metres = screen_travel(shot, object_id)
                if abs(metres) >= SCREEN_MIN and (metres > 0) != (want == 'right'):
                    findings.append({'frame': shot['frames'], 'object': object_id, 'issues': ['screen_direction_reversed']})
        if checks: result[shot['id']] = {'checks': checks, 'findings': findings}
        previous = shot
    return result


def merge_staging(audit, staging):
    """The shot's audit with its staging checks added; unchanged when the shot declares none."""
    if staging is None: return audit
    checks, findings = audit['checks'] + staging['checks'], audit['findings'] + staging['findings']
    return dict(audit, checks=checks, findings=findings, status='issues' if findings else 'passed_sampled_checks')


def audit_scene(scene, shot, objects):
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    settings = shot.get('audit', {})
    frames = set(range(1, shot['frames'] + 1, settings.get('step', 1)))
    frames.add(shot['frames'])
    for item in shot['objects']:
        frames.update(k['frame'] for k in item['keys'])
        for pair in item.get('ground_contact', []): frames.update(pair)
    frames.update(k['frame'] for k in shot['camera'].get('keys', []))
    subjects = settings.get('subjects', [])
    checks = ['framing_bounds', 'center_ray_occlusion'] if subjects else []
    if any(o.get('ground_contact') for o in shot['objects']): checks.append('declared_ground_contact')
    findings = []
    previous = scene.frame_current
    try:
        for frame in sorted(frames):
            scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            camera = scene.camera.evaluated_get(graph)
            for item in shot['objects']:
                obj = objects[item['id']].evaluated_get(graph)
                corners = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
                issues = []
                if item['id'] in subjects:
                    projected = [world_to_camera_view(scene, camera, v) for v in corners]
                    issues += framing_issues(projected, settings.get('margin', 0), item['id'] in settings.get('crop_ok', []))
                    center = sum(corners, Vector()) / len(corners)
                    ray = center - camera.matrix_world.translation
                    if ray.length > 1e-6:
                        hit = scene.ray_cast(graph, camera.matrix_world.translation, ray.normalized(), distance=ray.length)
                        if hit[0] and hit[4] is not None and hit[4].original != obj.original \
                                and not same_group(item['id'], hit[4].original.get('role_id'), settings.get('groups', [])):
                            issues.append('center_occluded')
                contact = contact_issue(min(p.z for p in corners), settings.get('ground_z', 0),
                                        settings.get('tolerance', .05), frame, item.get('ground_contact', []))
                if contact: issues.append(contact)
                if issues: findings.append({'frame': frame, 'object': item['id'], 'issues': issues})
    finally:
        scene.frame_set(previous)
    return {'shot': shot['id'], 'sampled_frames': sorted(frames), 'checks': checks,
            'subjects': subjects, 'findings': findings,
            'status': ('not_configured' if not checks else 'issues' if findings else 'passed_sampled_checks'),
            'limits': 'Bounding boxes and a center ray only; not mesh collision, full visibility, limb contact, or AI video fidelity.'}
