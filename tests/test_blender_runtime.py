"""Real smoke test; explicitly skipped if Blender is unavailable."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from test_previs_controls import duel

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/video-previs-workflow'
BINARY = os.environ.get('BLENDER_BIN') or shutil.which('blender')
if not BINARY and Path('/Applications/Blender.app/Contents/MacOS/Blender').is_file():
    BINARY = '/Applications/Blender.app/Contents/MacOS/Blender'

def small_spec(root):
    spec = json.loads((SKILL / 'assets/tracking-jump.json').read_text())
    spec.update(width=96, height=128)
    shot = spec['shots'][0]; shot['frames'] = 3
    for item in shot['objects']:
        item['keys'] = [dict(item['keys'][0], frame=1), dict(item['keys'][-1], frame=3)]
        item.pop('ground_contact', None)
    shot['camera']['keys'][-1]['frame'] = 3
    source = root / 'scene.json'; source.write_text(json.dumps(spec))
    return source


def render(source, output, *flags):
    return subprocess.run([BINARY, '--background', '--factory-startup', '--python-exit-code', '1',
        '--python', str(SKILL / 'scripts/render_previs.py'), '--', str(source), str(output), *flags],
        capture_output=True, text=True, timeout=240)


@unittest.skipUnless(BINARY, 'Blender runtime unavailable; not a render pass')
class BlenderRuntimeTests(unittest.TestCase):
    def test_frames_and_size_render_only_requested_stills(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp); output = root / 'result'
            result = render(small_spec(root), output, '--frames', '2', '--size', '64x96')
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            self.assertEqual(sorted(p.name for p in (output / 's01').glob('*.png')), ['review_0002.png'])
            self.assertEqual(struct.unpack('>II', (output / 's01/review_0002.png').read_bytes()[16:24]), (64, 96))

    def test_audit_only_writes_no_images(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp); output = root / 'result'
            result = render(small_spec(root), output, '--audit-only')
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            self.assertTrue((output / 's01/audit.json').is_file())
            self.assertEqual(list(output.rglob('*.png')) + list(output.rglob('*.blend')), [])

    def test_bad_frame_leaves_no_output_dir(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp); output = root / 'result'
            result = render(small_spec(root), output, '--frames', '9')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('s01: frame 9 is outside 1..3', result.stdout + result.stderr)
            self.assertFalse(output.exists())

    def test_tracking_review_outputs_and_saved_animation(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp)
            output = root / 'result'
            result = render(small_spec(root), output, '--review-only')
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            folder = output / 's01'
            for name in ('scene.blend', 'audit.json', 'review_0001.png', 'review_0002.png', 'review_0003.png'):
                self.assertGreater((folder / name).stat().st_size, 0)
            audit = json.loads((folder / 'audit.json').read_text())
            self.assertEqual(audit['sampled_frames'], [1, 2, 3])
            self.assertTrue(audit['checks'])
            self.assertFalse(list(folder.glob('frame_*.png')))
            verify = root / 'verify.py'
            verify.write_text('import bpy\ns=bpy.context.scene\ns.frame_set(3)\n'
                              'assert abs(s.camera.data.lens-45)<.001\n'
                              'assert abs(s.camera.location.x-3)<.001\n'
                              'assert s.frame_end==3\n')
            checked = subprocess.run([BINARY, '--background', str(folder / 'scene.blend'),
                 '--python-exit-code', '1', '--python', str(verify)], capture_output=True, text=True, timeout=60)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_line_check_sees_the_previous_shot_when_one_shot_is_picked(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp); output = root / 'result'; source = root / 'scene.json'
            source.write_text(json.dumps(duel((2, 5, 1.6))))
            result = render(source, output, '--audit-only', '--shot', 's02')
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            audit = json.loads((output / 's02/audit.json').read_text())
            self.assertIn({'frame': 1, 'object': 'camera', 'issues': ['line_crossed']}, audit['findings'])
            self.assertIn('action_line', audit['checks'])
            self.assertEqual(audit['status'], 'issues')
            self.assertFalse((output / 's01').exists())

    def plan(self, root, name, spec, *flags):
        source = root / (name + '.json'); source.write_text(json.dumps(spec))
        return render(source, root / name, *flags), root / name

    def test_plan_writes_one_image_and_its_layout(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp)
            result, output = self.plan(root, 'still', duel((2, 5, 1.6)), '--plan', 's01,s02')
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            self.assertEqual(sorted(p.name for p in output.rglob('*') if p.is_file()), ['plan.json', 'plan.png'])
            self.assertEqual(struct.unpack('>II', (output / 'plan.png').read_bytes()[16:24]), (1080, 1080))
            self.assertEqual([s['id'] for s in json.loads((output / 'plan.json').read_text())['shots']], ['s01', 's02'])
            moving = duel((2, 5, 1.6)); moving['shots'][1]['objects'][0]['keys'] = [
                {'frame': 1, 'position': [-1, 0, 0]}, {'frame': 24, 'position': [-1, -3, 0]}]
            result, walked = self.plan(root, 'walk', moving, '--plan', 's01,s02')
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            self.assertNotEqual((walked / 'plan.png').read_bytes(), (output / 'plan.png').read_bytes())

    def test_plan_option_errors_leave_no_output_dir(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp)
            for name, flags, message in (
                    ('unknown', ('--plan', 's09'), 'unknown shot s09'),
                    ('empty', ('--plan', ''), 'unknown shot '),
                    ('mixed', ('--plan', 's01', '--frames', '1'),
                     '--plan renders only the floor plan; remove --frames, --size, --shot, --review-only and --audit-only')):
                result, output = self.plan(root, name, duel(), *flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout + result.stderr)
                self.assertFalse(output.exists())

if __name__ == '__main__': unittest.main()
