import copy
import sys
from pathlib import Path
import unittest
from test_workflow import module, scene
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/video-previs-workflow/scripts'))

class MotionTests(unittest.TestCase):
    def test_linear_and_smooth_interpolation_hold_endpoints(self):
        m = module('motion')
        keys = [{'frame': 1, 'position': [0, 0, 0]}, {'frame': 5, 'position': [4, 0, 0]}]
        self.assertEqual(m.sample(keys, 3)['position'], [2, 0, 0])
        self.assertEqual(m.sample(keys, 10)['position'], [4, 0, 0])
        self.assertAlmostEqual(m.sample(keys, 2, 'smooth')['position'][0], .625)

    def test_camera_follows_subject_and_interpolates_lens(self):
        m = module('motion'); s = scene()['shots'][0]
        s['camera'] = {'position': [0, -8, 3], 'follow': 'hero', 'offset': [0, 0, .5],
                       'keys': [{'frame': 1, 'position': [0, -8, 3], 'lens': 35},
                                {'frame': 48, 'position': [2, -8, 3], 'lens': 50}]}
        camera = m.camera_at(s, 48)
        self.assertEqual(camera['position'], [2, -8, 3])
        self.assertEqual(camera['target'], [2, 0, 1.5])
        self.assertEqual(camera['lens'], 50)

    def test_rotation_omitted_retains_previous_pose(self):
        m = module('motion')
        keys = [{'frame': 1, 'position': [0, 0, 0], 'rotation': [0, 0, 1]},
                {'frame': 3, 'position': [1, 0, 0]}]
        self.assertEqual(m.sample(keys, 2)['rotation'], [0, 0, 1])

class ControlValidationTests(unittest.TestCase):
    def test_follow_ignores_unused_base_target(self):
        m = module('validate_spec')
        for target in (None, [6, -8, 5]):
            s = scene(); camera = s['shots'][0]['camera']
            camera.update(follow='hero', target=target,
                          keys=[{'frame': 1, 'position': [6, -8, 5]}, {'frame': 48, 'position': [5, -8, 5]}])
            self.assertEqual(m.validate(s), [])

    def test_first_key_can_override_coincident_base_target(self):
        m = module('validate_spec'); s = scene(); camera = s['shots'][0]['camera']
        camera['target'] = camera['position'][:]
        camera['keys'] = [{'frame': 1, 'target': [0, 0, 1]}]
        self.assertEqual(m.validate(s), [])

    def test_rejects_invalid_lens_follow_and_camera_keys(self):
        m = module('validate_spec')
        for patch in [{'lens': -35}, {'follow': 'missing'}, {'keys': []},
                      {'keys': [{'frame': 0, 'position': [0, 0, 0]}]}]:
            s = scene(); s['shots'][0]['camera'].update(patch)
            self.assertTrue(m.validate(s), patch)

    def test_capsule_and_declared_ground_contact(self):
        m = module('validate_spec'); s = scene(); obj = s['shots'][0]['objects'][0]
        obj['shape'] = 'capsule'; obj['ground_contact'] = [[1, 12], [36, 48]]
        self.assertEqual(m.validate(s), [])
        obj['ground_contact'] = [[10, 4]]
        self.assertTrue(m.validate(s))

    def test_rejects_unknown_subject_and_bad_audit_settings(self):
        m = module('validate_spec')
        for audit in [{'subjects': ['missing']}, {'step': 0}, {'margin': .8}, {'ground_z': float('nan')}]:
            s = scene(); s['shots'][0]['audit'] = audit
            self.assertTrue(m.validate(s), audit)

    def test_camera_crossing_target_rejected(self):
        m = module('validate_spec'); s = scene()
        s['shots'][0]['camera'] = {'position': [-1, 0, 0], 'target': [0, 0, 0],
            'keys': [{'frame': 1, 'position': [-1, 0, 0]}, {'frame': 3, 'position': [1, 0, 0]}]}
        self.assertTrue(m.validate(s))

class AuditTests(unittest.TestCase):
    def test_projection_flags_behind_camera_and_edges(self):
        m = module('audit_previs')
        self.assertEqual(m.framing_issues([(0.5, .5, 1)], .05), [])
        self.assertIn('behind_camera', m.framing_issues([(.5, .5, -1)], .05))
        self.assertIn('outside_frame', m.framing_issues([(1.1, .5, 1)], .05))

    def test_ground_only_checks_contact_windows(self):
        m = module('audit_previs')
        self.assertEqual(m.contact_issue(.5, 0, .05, 20, [[1, 5]]), None)
        self.assertEqual(m.contact_issue(.5, 0, .05, 2, [[1, 5]]), 'floating')
        self.assertEqual(m.contact_issue(-.5, 0, .05, 2, [[1, 5]]), 'penetrating_ground')

if __name__ == '__main__': unittest.main()
