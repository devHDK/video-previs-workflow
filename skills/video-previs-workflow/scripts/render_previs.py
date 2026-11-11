"""Run with Blender: blender --background --python SCRIPT -- SPEC NEW_OUTPUT_DIR.
Creates per-shot PNG sequences and .blend files. Assemble with media.py.
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_spec import validate


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 2: raise SystemExit(__doc__)
    spec = json.loads(Path(args[0]).read_text())
    errors = validate(spec)
    if errors: raise SystemExit('\n'.join(errors))
    import bpy
    from mathutils import Vector
    output = Path(args[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for shot in spec['shots']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
        scene.render.resolution_x = spec['width']; scene.render.resolution_y = spec['height']
        scene.render.resolution_percentage = 100; scene.render.fps = spec['fps']
        scene.frame_start = 1; scene.frame_end = shot['frames']
        world = bpy.data.worlds.new('World'); world.use_nodes = True
        world.node_tree.nodes['Background'].inputs[0].default_value = (.12, .12, .12, 1)
        scene.world = world
        bpy.ops.object.camera_add(location=shot['camera']['position'])
        camera = bpy.context.object
        camera.rotation_euler = (Vector(shot['camera']['target']) - camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.lens = 40; scene.camera = camera
        bpy.ops.object.light_add(type='AREA', location=(0, -3, 8))
        light = bpy.context.object; light.data.energy = 1200; light.data.shape = 'DISK'; light.data.size = 8
        for item in shot['objects']:
            if item['shape'] == 'cube': bpy.ops.mesh.primitive_cube_add()
            elif item['shape'] == 'sphere': bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8)
            else: bpy.ops.mesh.primitive_cylinder_add(vertices=16)
            obj = bpy.context.object; obj.name = item['id']; obj.scale = item['scale']
            material = bpy.data.materials.new(item['id']); material.diffuse_color = (*item['color'], 1)
            obj.data.materials.append(material)
            for key in item['keys']:
                obj.location = key['position']; obj.keyframe_insert(data_path='location', frame=key['frame'])
                obj.rotation_euler = key.get('rotation', [0, 0, 0]); obj.keyframe_insert(data_path='rotation_euler', frame=key['frame'])
            # Blender default Bezier interpolation is intentional; inspect contact/timing in render.
        folder = output / shot['id']; folder.mkdir()
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = str(folder / 'frame_')
        bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'scene.blend'))
        bpy.ops.render.render(animation=True)
    print(f'Previs frames saved: {output}')

if __name__ == '__main__': main()
