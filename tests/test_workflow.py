import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/video-previs-workflow/scripts'
sys.path.insert(0, str(SCRIPTS))

def module(name):
    path = SCRIPTS / (name + '.py')
    if not path.exists():
        raise AssertionError(f'Missing implementation: {name}')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def scene():
    return {'version': 1, 'fps': 24, 'width': 360, 'height': 640,
            'shots': [{'id': 's01', 'frames': 48,
                       'camera': {'position': [6, -8, 5], 'target': [0, 0, 1]},
                       'objects': [{'id': 'hero', 'shape': 'sphere',
                                    'color': [0.2, 0.7, 0.6], 'scale': [1, 1, 1],
                                    'keys': [{'frame': 1, 'position': [0, 0, 1]},
                                             {'frame': 48, 'position': [2, 0, 1]}]}]}]}

class SpecTests(unittest.TestCase):
    def test_valid_and_exact_cut_counts(self):
        m = module('validate_spec')
        s = scene(); s['shots'].append(dict(copy.deepcopy(s['shots'][0]), id='s02', frames=48))
        self.assertEqual(m.validate(s), [])
        self.assertEqual(m.timeline(s), [('s01', 0, 48), ('s02', 48, 96)])

    def test_reject_bad_geometry_and_keys(self):
        m = module('validate_spec')
        for field, value in [('scale', [1, -1, 1]), ('color', [float('nan'), 0, 1])]:
            s = scene(); s['shots'][0]['objects'][0][field] = value
            self.assertTrue(m.validate(s))
        s = scene(); s['shots'][0]['objects'][0]['keys'][1]['frame'] = 49
        self.assertTrue(m.validate(s))

    def test_reject_duplicate_shots_and_fractional_frames(self):
        m = module('validate_spec'); s = scene()
        s['shots'].append(copy.deepcopy(s['shots'][0]))
        self.assertTrue(m.validate(s))
        s = scene(); s['shots'][0]['frames'] = 2.5
        self.assertTrue(m.validate(s))

    def test_changed_shots_include_removed_and_global_changes(self):
        m = module('validate_spec'); a = scene(); b = copy.deepcopy(a)
        self.assertEqual(m.changed_shots(a, b), [])
        b['shots'][0]['objects'][0]['color'][0] = .8
        self.assertEqual(m.changed_shots(a, b), ['s01'])
        b = copy.deepcopy(a); b['fps'] = 30
        self.assertEqual(m.changed_shots(a, b), ['s01'])
        b = copy.deepcopy(a); b['shots'] = []
        self.assertEqual(m.changed_shots(a, b), ['s01'])

class EditTests(unittest.TestCase):
    def test_decode_errors_are_fatal(self):
        m = module('media')
        self.assertTrue(hasattr(m, 'decode_command'), 'decode verification needs an explicit command contract')
        cmd = m.decode_command(Path('/tmp/final.mp4'))
        self.assertIn('-xerror', cmd)
        self.assertLess(cmd.index('-xerror'), cmd.index('-i'))

    def test_command_preserves_paths_and_exact_frames(self):
        m = module('media')
        cmd = m.clip_command(Path('/tmp/input space.mp4'), Path('/tmp/out.mp4'), 48, 24, 360, 640)
        self.assertIn('/tmp/input space.mp4', cmd)
        self.assertEqual(cmd[cmd.index('-frames:v') + 1], '48')
        self.assertIn('-n', cmd)
        self.assertIn('tpad', cmd[cmd.index('-vf') + 1])

    def test_existing_output_is_rejected(self):
        m = module('media')
        with self.assertRaises(FileExistsError):
            m.fresh_output(Path(__file__))

    def test_clip_command_applies_in_point_and_speed(self):
        m = module('media')
        cmd = m.clip_command(Path('/tmp/a.mp4'), Path('/tmp/o.mp4'), 48, 24, 360, 640, start=1.5, speed=1.05)
        self.assertLess(cmd.index('-ss'), cmd.index('-i'))
        self.assertEqual(cmd[cmd.index('-ss') + 1], '1.5')
        self.assertIn('setpts=(PTS-STARTPTS)/1.05', cmd[cmd.index('-vf') + 1])

    def test_default_clip_command_has_no_seek(self):
        self.assertNotIn('-ss', module('media').clip_command(Path('/tmp/a.mp4'), Path('/tmp/o.mp4'), 48, 24, 360, 640))

    def _manifest(self, tmp, **clip):
        (Path(tmp) / 'a.mp4').write_bytes(b'')
        p = Path(tmp) / 'edit.json'
        p.write_text(json.dumps({'fps': 24, 'width': 360, 'height': 640,
                                 'clips': [{'path': 'a.mp4', 'frames': 48, **clip}]}))
        return p

    def test_assemble_rejects_speed_outside_range(self):
        with tempfile.TemporaryDirectory() as t, self.assertRaisesRegex(ValueError, 'speed must be within 0.9-1.1'):
            module('media').assemble(self._manifest(t, speed=1.35), Path(t) / 'out.mp4')

    def test_assemble_rejects_dialogue_speed_change(self):
        with tempfile.TemporaryDirectory() as t, self.assertRaisesRegex(ValueError, 'dialogue clips must keep speed 1.0'):
            module('media').assemble(self._manifest(t, speed=1.05, dialogue=True), Path(t) / 'out.mp4')

    def test_assemble_rejects_negative_start(self):
        with tempfile.TemporaryDirectory() as t, self.assertRaisesRegex(ValueError, 'start must be >= 0'):
            module('media').assemble(self._manifest(t, start=-1), Path(t) / 'out.mp4')

    def test_sample_times_clamps_last_frame(self):
        m = module('media')
        self.assertEqual([round(x, 6) for x in m.sample_times(4.0, 5)], [0.0, 1.0, 2.0, 3.0, 3.95])
        with self.assertRaises(ValueError):
            m.sample_times(4.0, 1)

if __name__ == '__main__':
    unittest.main()
