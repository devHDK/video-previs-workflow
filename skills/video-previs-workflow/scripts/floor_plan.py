"""Floor plan of shots that share a location: where each camera stands, who travels where, seen from above.
plan_layout needs no Blender; render_plan draws the layout over a shot scene built by render_previs."""
import math
from motion import object_at, camera_at, members, travel

PATH_MIN = 0.5  # metres a figure root must travel before its path is drawn
WHITE, LINE_COLOR = (1, 1, 1), (1, .85, 0)


def _xy(position): return [round(position[0], 4), round(position[1], 4)]


def plan_layout(spec, shot_ids):
    by_id = {shot['id']: shot for shot in spec['shots']}
    sensor = 36 if spec['width'] >= spec['height'] else 36 * spec['width'] / spec['height']
    shots, xs, ys, base = [], [], [], None
    for shot_id in shot_ids:
        if shot_id not in by_id: raise ValueError(f'unknown shot {shot_id}')
        shot = by_id[shot_id]; frames = range(1, shot['frames'] + 1)
        objects = {o['id']: o for o in shot['objects']}
        cameras = [camera_at(shot, f) for f in frames]
        camera = [_xy(c['position']) for c in cameras]
        if all(point == camera[0] for point in camera): camera = camera[:1]
        heading = [cameras[0]['target'][i] - cameras[0]['position'][i] for i in (0, 1)]
        length = math.hypot(*heading)
        roots = {i: [_xy(object_at(objects[i], f)['position']) for f in frames] for i in objects}
        for points in list(roots.values()) + [camera]:
            xs += [p[0] for p in points]; ys += [p[1] for p in points]
        line = shot.get('audit', {}).get('line')
        if base is None: base = {i: points[0] for i, points in roots.items()}
        shots.append({'id': shot_id, 'camera': camera,
                      'aim': [round(v / length, 4) for v in heading] if length >= 1e-6 else None,
                      'half_angle': round(math.atan(sensor / 2 / cameras[0]['lens']), 4),
                      'paths': [{'id': i, 'color': objects[i]['color'], 'points': roots[i]}
                                for i in members(objects) if travel(objects[i], shot['frames']) > PATH_MIN],
                      'moved': [{'id': i, 'color': objects[i]['color'], 'point': roots[i][0]}
                                for i in members(objects) if base.get(i) != roots[i][0]],
                      'line': [roots[i][0] for i in line] if line else None})
    return {'bounds': [min(xs), min(ys), max(xs), max(ys)], 'shots': shots}


def render_plan(bpy, scene, layout, path):
    """One top-down still of the scene's proxies with every listed shot's camera, travel paths and action line."""
    xmin, ymin, xmax, ymax = layout['bounds']
    extent = max(xmax - xmin, ymax - ymin, 4) * 1.25
    width, mark, z = extent / 150, extent / 75, 50
    materials = {}

    def material(color):
        key = tuple(color)
        if key not in materials:
            materials[key] = bpy.data.materials.new('PLAN'); materials[key].diffuse_color = (*key, 1)
        return materials[key]

    def mesh(quads, color):
        vertices = [(x, y, z) for quad in quads for x, y in quad]
        data = bpy.data.meshes.new('PLAN'); data.from_pydata(vertices, [], [tuple(range(i, i + 4)) for i in range(0, len(vertices), 4)])
        data.update(); data.materials.append(material(color))
        scene.collection.objects.link(bpy.data.objects.new('PLAN', data))

    def strip(points, color):
        quads = []
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            length = math.hypot(bx - ax, by - ay)
            if length < 1e-6: continue
            nx, ny = -(by - ay) / length * width / 2, (bx - ax) / length * width / 2
            quads.append([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)])
        if quads: mesh(quads, color)

    def square(point, color):
        x, y = point; h = mark / 2
        mesh([[(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)]], color)

    def label(text, point):
        curve = bpy.data.curves.new('PLAN', 'FONT'); curve.body = text; curve.size = extent / 40
        curve.materials.append(material(WHITE))
        obj = bpy.data.objects.new('PLAN', curve); obj.location = (point[0] + mark, point[1] + mark, z)
        scene.collection.objects.link(obj)

    for shot in layout['shots']:
        at = shot['camera'][0]
        if shot['aim'] is None: square(at, WHITE)
        else:
            heading = math.atan2(shot['aim'][1], shot['aim'][0])
            for side in (-1, 1):
                angle = heading + side * shot['half_angle']
                strip([at, (at[0] + extent / 8 * math.cos(angle), at[1] + extent / 8 * math.sin(angle))], WHITE)
        strip(shot['camera'], WHITE)
        label(shot['id'], at)
        for figure in shot['paths']:
            strip(figure['points'], figure['color']); square(figure['points'][-1], figure['color'])
            label(figure['id'], figure['points'][-1])
        for figure in shot['moved']:
            square(figure['point'], figure['color']); label(f"{figure['id']} {shot['id']}", figure['point'])
        if shot['line']:
            (ax, ay), (bx, by) = shot['line']; length = math.hypot(bx - ax, by - ay) or 1
            ux, uy = (bx - ax) / length * extent / 20, (by - ay) / length * extent / 20
            strip([(ax - ux, ay - uy), (bx + ux, by + uy)], LINE_COLOR)

    data = bpy.data.cameras.new('PLAN_CAM'); data.type = 'ORTHO'; data.ortho_scale = extent; data.clip_end = 10000
    camera = bpy.data.objects.new('PLAN_CAM', data); camera.location = ((xmin + xmax) / 2, (ymin + ymax) / 2, 100)
    scene.collection.objects.link(camera); scene.camera = camera
    scene.frame_set(1)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'FLAT'; scene.display.shading.color_type = 'MATERIAL'
    scene.view_settings.view_transform = 'Standard'
    scene.world.color = (.12, .12, .12)
    scene.render.resolution_x = scene.render.resolution_y = 1080; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'; scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
