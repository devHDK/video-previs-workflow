"""Sampled Blender geometry checks; not a generated-video quality score."""

def framing_issues(points, margin=0):
    issues = []
    if any(z <= 0 for x, y, z in points): issues.append('behind_camera')
    if any(x < margin or x > 1-margin or y < margin or y > 1-margin for x, y, z in points):
        issues.append('outside_frame')
    return issues


def contact_issue(bottom, ground, tolerance, frame, windows):
    if not any(start <= frame <= end for start, end in windows): return None
    if bottom < ground - tolerance: return 'penetrating_ground'
    if bottom > ground + tolerance: return 'floating'
    return None


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
                    issues += framing_issues(projected, settings.get('margin', 0))
                    center = sum(corners, Vector()) / len(corners)
                    ray = center - camera.matrix_world.translation
                    if ray.length > 1e-6:
                        hit = scene.ray_cast(graph, camera.matrix_world.translation, ray.normalized(), distance=ray.length)
                        if hit[0] and hit[4] is not None and hit[4].original != obj.original:
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
