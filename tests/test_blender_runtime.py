"""Real smoke test; explicitly skipped if Blender is unavailable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/video-previs-workflow'
BINARY = os.environ.get('BLENDER_BIN') or shutil.which('blender')
if not BINARY and Path('/Applications/Blender.app/Contents/MacOS/Blender').is_file():
    BINARY = '/Applications/Blender.app/Contents/MacOS/Blender'

@unittest.skipUnless(BINARY, 'Blender runtime unavailable; not a render pass')
class BlenderRuntimeTests(unittest.TestCase):
    def test_tracking_review_outputs_and_saved_animation(self):
        with tempfile.TemporaryDirectory(prefix='previs-runtime-') as temp:
            root = Path(temp)
            spec = json.loads((SKILL / 'assets/tracking-jump.json').read_text())
            spec.update(width=96, height=128)
            shot = spec['shots'][0]; shot['frames'] = 3
            for item in shot['objects']:
                item['keys'] = [dict(item['keys'][0], frame=1), dict(item['keys'][-1], frame=3)]
                item.pop('ground_contact', None)
            shot['camera']['keys'][-1]['frame'] = 3
            source = root / 'scene.json'; source.write_text(json.dumps(spec))
            output = root / 'result'
            result = subprocess.run([BINARY, '--background', '--factory-startup', '--python-exit-code', '1',
                '--python', str(SKILL / 'scripts/render_previs.py'), '--', str(source), str(output), '--review-only'],
                capture_output=True, text=True, timeout=240)
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

if __name__ == '__main__': unittest.main()
