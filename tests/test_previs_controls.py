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

    def test_review_frames_groups_and_crop_ok(self):
        m = module('validate_spec'); s = scene(); shot = s['shots'][0]
        shot['review_frames'] = [1, 24]; shot['audit'] = {'subjects': ['hero'], 'groups': [['hero']], 'crop_ok': ['hero']}
        self.assertEqual(m.validate(s), [])
        for bad in ([0], [49], 'all', [1.5]):
            s = scene(); s['shots'][0]['review_frames'] = bad
            self.assertIn('s01: review_frames must be integers within 1..frames', m.validate(s))
        for audit, message in (({'groups': [['ghost']]}, 's01: audit groups must be lists of object ids'),
                               ({'groups': 'hero'}, 's01: audit groups must be lists of object ids'),
                               ({'crop_ok': ['ghost']}, 's01: audit crop_ok must list object ids')):
            s = scene(); s['shots'][0]['audit'] = audit
            self.assertIn(message, m.validate(s))

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

    def test_crop_ok_drops_outside_frame_but_keeps_behind_camera(self):
        m = module('audit_previs')
        self.assertEqual(m.framing_issues([(1.1, .5, 1)], .05, crop_ok=True), [])
        self.assertEqual(m.framing_issues([(.5, .5, -1)], .05, crop_ok=True), ['behind_camera'])

    def test_same_group_is_not_an_occluder(self):
        m = module('audit_previs'); groups = [['lead_head', 'lead_face', 'lead_mask']]
        self.assertTrue(m.same_group('lead_head', 'lead_mask', groups))
        self.assertFalse(m.same_group('lead_head', 'c00_torso', groups))
        self.assertFalse(m.same_group('lead_head', 'lead_mask', []))

    def test_ground_only_checks_contact_windows(self):
        m = module('audit_previs')
        self.assertEqual(m.contact_issue(.5, 0, .05, 20, [[1, 5]]), None)
        self.assertEqual(m.contact_issue(.5, 0, .05, 2, [[1, 5]]), 'floating')
        self.assertEqual(m.contact_issue(-.5, 0, .05, 2, [[1, 5]]), 'penetrating_ground')

class RenderOptionTests(unittest.TestCase):
    def setUp(self):
        self.m = module('render_previs'); self.shot = scene()['shots'][0]  # 48 frames

    def test_default_stills_are_first_middle_last_plus_review_frames(self):
        self.shot['objects'][0]['keys'].insert(1, {'frame': 30, 'position': [1, 0, 1]})
        self.assertEqual(self.m.stills_for(self.shot), [1, 24, 48])  # a key frame alone adds no still
        self.shot['review_frames'] = [7, 30]
        self.assertEqual(self.m.stills_for(self.shot), [1, 7, 24, 30, 48])

    def test_picked_frames_replace_defaults_and_are_range_checked(self):
        self.assertEqual(self.m.stills_for(self.shot, [30, 2, 2]), [2, 30])
        with self.assertRaisesRegex(ValueError, r's01: frame 49 is outside 1\.\.48'):
            self.m.stills_for(self.shot, [49])

    def test_parse_size(self):
        self.assertEqual(self.m.parse_size('1080x1920'), (1080, 1920))
        for bad in ('1080', '1081x1920', '0x10', 'axb'):
            with self.assertRaisesRegex(ValueError, '--size must be WxH with even positive integers'):
                self.m.parse_size(bad)

    def test_pick_shots(self):
        spec = scene()
        self.assertEqual([s['id'] for s in self.m.pick_shots(spec, None)], ['s01'])
        with self.assertRaisesRegex(ValueError, 'unknown shot s09'):
            self.m.pick_shots(spec, 's09')

def duel(cam2=(2, -5, 1.6), **audit2):
    """Two figures on the x axis, s01 seen from -y, s02 from cam2."""
    def fig(i, x): return {'id': i, 'shape': 'capsule', 'color': [.5, .5, .5], 'scale': [1, 1, 1],
                           'keys': [{'frame': 1, 'position': [x, 0, 0]}]}
    def shot(sid, cam, audit): return {'id': sid, 'frames': 24, 'camera': {'position': list(cam), 'target': [0, 0, 1]},
                                       'objects': [fig('a', -1), fig('b', 1)], 'audit': audit}
    return {'version': 1, 'fps': 24, 'width': 360, 'height': 640,
            'shots': [shot('s01', (0, -6, 1.6), {'line': ['a', 'b']}),
                      shot('s02', cam2, dict({'line': ['a', 'b']}, **audit2))]}

CROSSED = [{'frame': 1, 'object': 'camera', 'issues': ['line_crossed']}]


class StagingTests(unittest.TestCase):
    def setUp(self): self.m = module('audit_previs'); self.v = module('validate_spec')

    def found(self, spec, sid='s02'): return self.m.staging_findings(spec)[sid]['findings']

    def test_same_side_passes_and_names_the_check(self):
        spec = duel(); self.assertEqual(self.v.validate(spec), [])
        self.assertEqual(self.m.staging_findings(spec),
                         {'s01': {'checks': ['action_line'], 'findings': []},
                          's02': {'checks': ['action_line'], 'findings': []}})

    def test_cut_to_the_far_side_is_reported_on_the_later_shot(self):
        spec = duel((2, 5, 1.6))
        self.assertEqual(self.found(spec), CROSSED)
        self.assertEqual(self.found(spec, 's01'), [])

    def test_pair_order_does_not_matter(self):
        spec = duel(); spec['shots'][1]['audit']['line'] = ['b', 'a']
        self.assertEqual(self.found(spec), [])
        spec = duel((2, 5, 1.6)); spec['shots'][1]['audit']['line'] = ['b', 'a']
        self.assertEqual(self.found(spec), CROSSED)

    def test_recorded_crossing_and_camera_on_the_line_are_not_reported(self):
        self.assertEqual(self.found(duel((2, 5, 1.6), line_cross_ok=True)), [])
        self.assertEqual(self.m.line_side(duel((-6, 0.2, 1.6))['shots'][1], 1), 0)
        self.assertEqual(self.found(duel((-6, 0.2, 1.6))), [])

    def test_only_the_previous_shot_with_the_same_pair_counts(self):
        spec = duel((2, 5, 1.6)); spec['shots'][1]['objects'].append(
            dict(spec['shots'][1]['objects'][1], id='c')); spec['shots'][1]['audit']['line'] = ['a', 'c']
        self.assertEqual(self.found(spec), [])
        spec = duel((2, 5, 1.6)); cutaway = copy.deepcopy(spec['shots'][0]); cutaway.update(id='s01b', audit={})
        spec['shots'].insert(1, cutaway)
        self.assertEqual(self.found(spec), [])
        self.assertNotIn('s01b', self.m.staging_findings(spec))

    def test_side_is_read_at_the_frames_either_side_of_the_cut(self):
        spec = duel((2, 5, 1.6))
        spec['shots'][0]['camera']['keys'] = [{'frame': 1, 'position': [0, -6, 1.6]}, {'frame': 24, 'position': [3, 6, 1.6]}]
        self.assertEqual(self.v.validate(spec), [])
        self.assertEqual((self.m.line_side(spec['shots'][0], 1), self.m.line_side(spec['shots'][0], 24)), (-1, 1))
        self.assertEqual(self.found(spec), [])

    def test_screen_travel_is_signed_by_the_camera_side(self):
        shot = scene()['shots'][0]                      # hero walks 2 m along +x, camera at [6, -8, 5]
        self.assertAlmostEqual(self.m.screen_travel(shot, 'hero'), 1.6, places=6)
        shot['camera']['position'] = [6, 8, 5]
        self.assertAlmostEqual(self.m.screen_travel(shot, 'hero'), -1.6, places=6)

    def test_reversed_screen_direction_is_reported_at_the_last_frame(self):
        spec = scene(); spec['shots'][0]['audit'] = {'screen_direction': {'hero': 'left'}}
        self.assertEqual(self.v.validate(spec), [])
        self.assertEqual(self.m.staging_findings(spec), {'s01': {'checks': ['screen_direction'], 'findings': [
            {'frame': 48, 'object': 'hero', 'issues': ['screen_direction_reversed']}]}})
        spec['shots'][0]['audit'] = {'screen_direction': {'hero': 'right'}}
        self.assertEqual(self.found(spec, 's01'), [])

    def test_travel_toward_the_camera_is_neither_left_nor_right(self):
        for want in ('left', 'right'):
            spec = scene(); shot = spec['shots'][0]
            shot['camera'] = {'position': [0, -8, 5], 'target': [0, 0, 1]}
            shot['objects'][0]['keys'] = [{'frame': 1, 'position': [0, 2, 1]}, {'frame': 48, 'position': [0, -2, 1]}]
            shot['audit'] = {'screen_direction': {'hero': want}}
            self.assertEqual(self.found(spec, 's01'), [])

    def test_follow_camera_and_top_down_camera(self):
        shot = scene()['shots'][0]; shot['camera'] = {'position': [0, -8, 3], 'follow': 'hero'}
        self.assertGreater(self.m.screen_travel(shot, 'hero'), 1.5)
        spec = duel((0, 0, 10)); top = spec['shots'][1]; top['camera']['target'] = [0, 0, 0]
        top['audit']['screen_direction'] = {'a': 'right'}
        self.assertEqual(self.m.screen_travel(top, 'a'), 0.0)
        self.assertEqual(self.m.line_side(top, 1), 0)
        self.assertEqual(self.found(spec), [])

    def test_spec_without_the_new_keys_has_no_staging(self):
        self.assertEqual(self.m.staging_findings(scene()), {})

    def test_merge_keeps_the_audit_shape_and_recomputes_status(self):
        base = {'shot': 's01', 'checks': [], 'findings': [], 'status': 'not_configured'}
        self.assertEqual(self.m.merge_staging(base, None), base)
        self.assertEqual(self.m.merge_staging(base, {'checks': ['action_line'], 'findings': []})['status'], 'passed_sampled_checks')
        merged = self.m.merge_staging(dict(base, checks=['framing_bounds'], status='passed_sampled_checks'),
                                      {'checks': ['action_line'], 'findings': CROSSED})
        self.assertEqual((merged['checks'], merged['findings'], merged['status']),
                         (['framing_bounds', 'action_line'], CROSSED, 'issues'))
        self.assertEqual(base['checks'], [])            # the input is not edited

    def test_rejects_malformed_staging_settings(self):
        for audit, message in (({'line': ['a']}, 's02: audit line must be two different object ids'),
                               ({'line': ['a', 'a']}, 's02: audit line must be two different object ids'),
                               ({'line': ['a', 'zz']}, 's02: audit line must be two different object ids'),
                               ({'line': 'ab'}, 's02: audit line must be two different object ids'),
                               ({'line': None}, 's02: audit line must be two different object ids'),
                               ({'line_cross_ok': 'yes'}, 's02: audit line_cross_ok must be true or false'),
                               ({'screen_direction': {'a': 'up'}}, 's02: audit screen_direction must map object ids to left or right'),
                               ({'screen_direction': {'zz': 'left'}}, 's02: audit screen_direction must map object ids to left or right'),
                               ({'screen_direction': ['a']}, 's02: audit screen_direction must map object ids to left or right')):
            spec = duel(); spec['shots'][1]['audit'] = audit
            self.assertEqual(self.v.validate(spec), [message], audit)

if __name__ == '__main__': unittest.main()
