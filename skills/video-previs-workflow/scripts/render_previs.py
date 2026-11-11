"""Background-only Blender renderer: -- SPEC NEW_OUTPUT_DIR [--review-only].
Writes per-shot .blend, audit.json, handoff.json, review stills and optionally full PNG sequences.
"""
import argparse
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_spec import validate
from motion import object_at, camera_at
from audit_previs import audit_scene


def capsule_mesh(bpy):
    # Foot-rooted capsule, total height 2 m, radius .35 m, one connected mesh.
    vertices, faces = [], []
    rings = []
    for i in range(9):
        angle = -math.pi / 2 + i * math.pi / 16
        rings.append((.35 * math.cos(angle), .35 + .35 * math.sin(angle)))
    for i in range(9):
        angle = i * math.pi / 16
        rings.append((.35 * math.cos(angle), 1.65 + .35 * math.sin(angle)))
    for radius, z in rings:
        for j in range(16):
            angle = j * 2 * math.pi / 16
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), z))
    for i in range(len(rings) - 1):
        for j in range(16):
            a = i * 16 + j; b = i * 16 + (j + 1) % 16
            faces.append((a, b, b + 16, a + 16))
    mesh = bpy.data.meshes.new('Capsule'); mesh.from_pydata(vertices, [], faces); mesh.update()
    obj = bpy.data.objects.new('Capsule', mesh); bpy.context.scene.collection.objects.link(obj)
    return obj


def build_shot(bpy, spec, shot):
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    engines = scene.render.bl_rna.properties['engine'].enum_items.keys()
    engine = next((name for name in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE') if name in engines), None)
    if engine is None:
        raise RuntimeError('This Blender build has no supported EEVEE engine.')
    scene.render.engine = engine
    scene.render.resolution_x = spec['width']; scene.render.resolution_y = spec['height']
    scene.render.resolution_percentage = 100
    scene.render.fps = spec['fps']; scene.render.fps_base = 1.0
    scene.frame_start = 1; scene.frame_end = shot['frames']
    world = bpy.data.worlds.new('World'); world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (.12, .12, .12, 1)
    scene.world = world
    bpy.ops.object.camera_add()
    camera = bpy.context.object; camera.name = 'CAM_' + shot['id']
    camera.rotation_mode = 'QUATERNION'; camera.data.clip_start = .05
    camera.data.clip_end = 10000; camera.data.sensor_width = 36; scene.camera = camera
    bpy.ops.object.light_add(type='AREA', location=(0, -3, 8))
    light = bpy.context.object; light.data.energy = 1200; light.data.shape = 'DISK'; light.data.size = 8
    objects = {}
    for item in shot['objects']:
        if item['shape'] == 'capsule': obj = capsule_mesh(bpy)
        else:
            if item['shape'] == 'cube': bpy.ops.mesh.primitive_cube_add()
            elif item['shape'] == 'sphere': bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8)
            else: bpy.ops.mesh.primitive_cylinder_add(vertices=16)
            obj = bpy.context.object
        obj.name = 'PROXY_' + item['id']; obj.scale = item['scale']
        obj['role_id'] = item['id']; obj.rotation_mode = 'XYZ'
        material = bpy.data.materials.new(item['id']); material.use_nodes = True
        material.diffuse_color = (*item['color'], 1)
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED': node.inputs['Base Color'].default_value = (*item['color'], 1)
        obj.data.materials.append(material); objects[item['id']] = obj
        for frame in range(1, shot['frames'] + 1):
            state = object_at(item, frame)
            obj.location = state['position']; obj.rotation_euler = state['rotation']
            obj.keyframe_insert(data_path='location', frame=frame)
            obj.keyframe_insert(data_path='rotation_euler', frame=frame)
    previous_quaternion = None
    for frame in range(1, shot['frames'] + 1):
        state = camera_at(shot, frame)
        camera.location = state['position']
        quat = (Vector(state['target']) - camera.location).to_track_quat('-Z', 'Y')
        if previous_quaternion is not None: quat.make_compatible(previous_quaternion)
        camera.rotation_quaternion = quat; previous_quaternion = quat.copy()
        camera.data.lens = state['lens']
        camera.keyframe_insert(data_path='location', frame=frame)
        camera.keyframe_insert(data_path='rotation_quaternion', frame=frame)
        camera.data.keyframe_insert(data_path='lens', frame=frame)
    # Every integer frame is explicitly baked; no reliance on version-specific F-curve traversal.
    scene.frame_set(1)
    return scene, objects


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('spec', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--review-only', action='store_true')
    options = p.parse_args(args)
    spec = json.loads(options.spec.read_text()); errors = validate(spec)
    if errors: raise SystemExit('\n'.join(errors))
    import bpy
    if not bpy.app.background:
        raise RuntimeError('Use a separate --background Blender process; this renderer resets its own scene.')
    output = options.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    summary = []
    offset = 0
    for shot in spec['shots']:
        scene, objects = build_shot(bpy, spec, shot)
        folder = output / shot['id']; folder.mkdir()
        audit = audit_scene(scene, shot, objects)
        (folder / 'audit.json').write_text(json.dumps(audit, indent=2))
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = str(folder / 'frame_')
        bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'scene.blend'))
        review_frames = sorted({1, (shot['frames'] + 1)//2, shot['frames']} |
                               {k['frame'] for o in shot['objects'] for k in o['keys']} |
                               {k['frame'] for k in shot['camera'].get('keys', [])})
        try:
            for frame in review_frames:
                scene.frame_set(frame); scene.render.filepath = str(folder / f'review_{frame:04d}.png')
                bpy.ops.render.render(write_still=True)
        finally:
            scene.frame_set(1); scene.render.filepath = str(folder / 'frame_')
        if not options.review_only: bpy.ops.render.render(animation=True)
        summary.append({'shot': shot['id'], 'start_frame': offset, 'end_frame_exclusive': offset + shot['frames'],
                        'review_frames': review_frames, 'audit_status': audit['status'],
                        'camera': shot['camera'], 'roles': [{'id': o['id'], 'shape': o['shape'], 'color': o['color']} for o in shot['objects']]})
        offset += shot['frames']
    (output / 'handoff.json').write_text(json.dumps({'fps': spec['fps'], 'review_only': options.review_only,
        'timeline_convention': 'zero-based end-exclusive', 'shots': summary}, indent=2))
    print(f'Previs artifacts saved: {output}; inspect audit findings and actual review images before approval.')

if __name__ == '__main__': main()
