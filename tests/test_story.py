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

    def test_non_object(self):
        self.assertEqual(self.m.check([]), ['story must be an object'])

    def test_core_fields_required(self):
        del self.s['purpose']
        self.s['target_action']['cue'] = ''
        self.assertIn('purpose is required', self.errors())
        self.assertIn('target_action.cue is required', self.errors())

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
        self.assertIn(f"{self.s['beats'][0]['id']}: serves must be purpose or target_action", self.errors())

    def test_nonstring_structure_id_reported_not_raised(self):
        self.s['structure']['id'] = ['obstacle_payoff']
        self.assertIn('structure.id is required', self.errors())

    def test_tension_range(self):
        self.s['beats'][0]['tension'] = 6
        self.assertIn(f"{self.s['beats'][0]['id']}: tension must be an integer 0-5", self.errors())


if __name__ == '__main__':
    unittest.main()
