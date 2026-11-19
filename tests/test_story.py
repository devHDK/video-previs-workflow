import importlib.util
import json
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / 'skills/story-design'


def load_check_story():
    spec = importlib.util.spec_from_file_location('check_story', SKILL / 'scripts/check_story.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.m = load_check_story()
        self.s = json.loads((SKILL / 'assets/example-story.json').read_text())

    def errors(self):
        return self.m.check(self.s)

    def pay(self):
        return [b['id'] for b in self.s['beats']].index(self.s['payoff_beat'])

    def test_example_is_valid_obstacle_payoff(self):
        self.assertEqual(self.s['structure']['id'], 'obstacle_payoff')
        self.assertEqual(self.errors(), [])

    def test_setup_fields_required(self):
        for field in self.m.SETUP_FIELDS:
            self.s = json.loads((SKILL / 'assets/example-story.json').read_text()); del self.s['setup'][field]
            self.assertIn(f'setup.{field} is required', self.errors())

    def test_setup_hook_is_optional(self):
        del self.s['setup']['hook']  # not every piece has a joke or a twist
        self.assertEqual(self.errors(), [])

    def test_setup_wrong_type_reported_not_raised(self):
        self.s['setup'] = 'funny'
        self.assertEqual([e for e in self.errors() if e.startswith('setup.')],
                         [f'setup.{f} is required' for f in self.m.SETUP_FIELDS] + ['setup.look is required'])

    def test_non_object(self):
        self.assertEqual(self.m.check([]), ['story must be an object'])

    def test_action_required(self):
        self.s['target_action']['action'] = ''
        self.assertIn('target_action.action is required', self.errors())

    def test_purpose_is_optional_until_something_serves_it(self):
        del self.s['purpose']
        self.assertEqual(self.errors(), ['purpose is required when a beat or element serves it'])
        for item in self.s['beats'] + self.s['elements']:
            if item['serves'] == 'purpose': item['serves'] = 'mood'  # a mood piece has nothing to teach
        self.assertEqual(self.errors(), [])

    def test_cue_is_optional(self):
        del self.s['target_action']['cue'], self.s['target_action']['beat']  # nothing is asked for on screen
        self.assertEqual(self.errors(), [])

    def test_cue_needs_the_beat_where_it_lands(self):
        del self.s['target_action']['beat']
        self.assertIn('target_action.beat must name a beat', self.errors())

    def calm(self):
        for b in self.s['beats']: b.pop('obstacle', None)

    def test_no_conflict_needs_no_structure_id(self):
        del self.s['structure']['id']; self.calm()
        self.assertEqual(self.errors(), [])

    def test_obstacle_needs_a_structure(self):
        del self.s['structure']['id']
        self.assertIn('structure.id is required when a beat has an obstacle', self.errors())

    def test_order_reason_always_required(self):
        self.s['structure'] = {}; self.calm()
        self.assertEqual(self.errors(), ['structure.why is required'])

    def fresh(self):
        self.s = json.loads((SKILL / 'assets/example-story.json').read_text())
        return self.s['setup']['look']

    def test_example_is_version_2_with_a_look(self):
        self.assertEqual(self.s['version'], 2)
        self.assertIsInstance(self.s['setup']['look'], dict)

    def test_look_required_from_version_2(self):
        del self.s['setup']['look']
        self.assertEqual(self.errors(), ['setup.look is required'])
        self.s['version'] = 1  # stories approved before the look existed stay valid
        self.assertEqual(self.errors(), [])

    def test_every_look_pick_is_required_and_listed(self):
        for path, values in self.m.LOOK.items():
            for bad in (None, 'drone', ['lead']):
                look = self.fresh()
                *parents, leaf = path.split('.')
                for key in parents: look = look[key]
                if bad is None: del look[leaf]
                else: look[leaf] = bad
                self.assertEqual(self.errors(), [f"setup.look.{path} must be one of: {', '.join(values)}"], (path, bad))

    def test_views_are_distinct_listed_names(self):
        for bad in ([], ['pov', 'pov'], ['drone'], [{'a': 1}], 'pov', None):
            self.fresh()['camera']['views'] = bad
            self.assertEqual(self.errors(), ['setup.look.camera.views must list one or more of: '
                                             'selfie, pov, mirror, propped, insert, observer'], bad)

    def test_average_shot_length_is_a_positive_number(self):
        for bad in (0, -1, '2', None, True):
            self.fresh()['pace']['avg_shot_s'] = bad
            self.assertEqual(self.errors(), ['setup.look.pace.avg_shot_s must be a positive number'], bad)

    def test_wrong_typed_look_reported_not_raised(self):
        for bad in ('vlog', ['vlog'], None):
            self.fresh(); self.s['setup']['look'] = bad
            self.assertEqual(self.errors(), ['setup.look is required'], bad)
        self.fresh()['camera'] = 'phone'
        self.assertEqual(len([e for e in self.errors() if e.startswith('setup.look.camera.')]), 4)

    def test_no_spoken_line_when_speech_is_none(self):
        beat = self.s['beats'][0]; beat['line'] = 'Just this much, please.'
        self.assertEqual(self.errors(), [f"{beat['id']}: line is not allowed when setup.look.speech is none"])
        self.s['setup']['look']['speech'] = 'dialogue'
        self.assertEqual(self.errors(), [])

    def test_info_captions_are_written_in_the_beats(self):
        self.s['setup']['look']['captions'] = 'info'
        self.assertEqual(self.errors(), [f"{b['id']}: caption is required when setup.look.captions is info" for b in self.s['beats']])
        for b in self.s['beats']: b['caption'] = 'a mini amenities pack'
        self.assertEqual(self.errors(), [])

    def test_unknown_structure_lists_ids(self):
        self.s['structure']['id'] = 'hero_journey'
        self.assertIn('structure.id must be one of: obstacle_payoff, cliffhanger, relief, reveal, info_list, custom',
                      self.errors())

    def test_float_boundaries_are_contiguous(self):
        self.s['beats'][0]['start'] = 0
        self.s['beats'][0]['end'] = 0.1 + 0.2
        self.s['beats'][1]['start'] = 0.3
        self.assertEqual(self.errors(), [])

    def test_gap_reported(self):
        b = self.s['beats']
        b[1]['start'] = b[0]['end'] + 0.5
        self.assertIn(f"{b[1]['id']}: gap or overlap with previous beat", self.errors())

    def test_two_active_obstacles_required(self):
        for b in self.s['beats']:
            b.pop('obstacle', None)
        self.assertIn('obstacle_payoff needs at least 2 pre-payoff beats with an active obstacle; found 0',
                      self.errors())

    def test_tension_peaks_before_payoff(self):
        self.s['beats'][0]['tension'] = 5
        self.s['beats'][self.pay() - 1]['tension'] = 4
        self.assertIn('tension must peak in the beat right before payoff_beat', self.errors())

    def test_cta_not_before_payoff(self):
        self.s['target_action']['beat'] = self.s['beats'][0]['id']
        self.assertIn('target_action.beat must not come before payoff_beat', self.errors())

    def test_info_list_needs_no_obstacle(self):
        self.s['structure']['id'] = 'info_list'
        for b in self.s['beats']:
            b.pop('obstacle', None)
            b['tension'] = 1
        self.assertEqual(self.errors(), [])

    def test_element_needs_reason(self):
        self.s['elements'][0]['why'] = ''
        self.assertIn(f"element {self.s['elements'][0]['id']}: why is required", self.errors())

    def test_serves_must_be_purpose_or_action(self):
        self.s['beats'][0]['serves'] = 'fun'
        self.assertIn(f"{self.s['beats'][0]['id']}: serves must be purpose, target_action or mood", self.errors())

    def test_nonstring_structure_id_reported_not_raised(self):
        self.s['structure']['id'] = ['obstacle_payoff']
        self.assertIn('structure.id must be one of: obstacle_payoff, cliffhanger, relief, reveal, info_list, custom', self.errors())

    def test_tension_range(self):
        self.s['beats'][0]['tension'] = 6
        self.assertIn(f"{self.s['beats'][0]['id']}: tension must be an integer 0-5", self.errors())


if __name__ == '__main__':
    unittest.main()
