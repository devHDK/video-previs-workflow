import copy
import unittest
from test_workflow import module, scene
from test_previs_controls import duel


def walking(spec):
    """s02's figure a walks 3 m toward -y and carries a head part."""
    a = spec['shots'][1]['objects'][0]
    a['keys'] = [{'frame': 1, 'position': [-1, 0, 0]}, {'frame': 24, 'position': [-1, -3, 0]}]
    head = copy.deepcopy(a); head.update(id='a_head', shape='sphere'); spec['shots'][1]['objects'].append(head)
    return spec


class PlanLayoutTests(unittest.TestCase):
    def setUp(self): self.m = module('floor_plan')

    def test_cameras_lines_and_bounds(self):
        layout = self.m.plan_layout(duel((2, 5, 1.6)), ['s01', 's02'])
        self.assertEqual(layout['bounds'], [-1, -6, 2, 5])
        first, second = layout['shots']
        self.assertEqual((first['id'], first['camera'], first['aim'], first['paths']), ('s01', [[0, -6]], [0, 1], []))
        self.assertEqual(first['line'], [[-1, 0], [1, 0]])
        self.assertAlmostEqual(first['half_angle'], 0.2479, places=4)
        self.assertEqual((second['id'], second['camera']), ('s02', [[2, 5]]))

    def test_only_roots_that_travel_get_a_path(self):
        layout = self.m.plan_layout(walking(duel()), ['s02'])
        (path,) = layout['shots'][0]['paths']
        self.assertEqual((path['id'], path['color'], len(path['points'])), ('a', [.5, .5, .5], 24))
        self.assertEqual((path['points'][0], path['points'][-1]), ([-1, 0], [-1, -3]))

    def test_moving_camera_gives_one_point_per_frame(self):
        spec = duel()
        spec['shots'][0]['camera']['keys'] = [{'frame': 1, 'position': [0, -6, 1.6]}, {'frame': 24, 'position': [3, -6, 1.6]}]
        camera = self.m.plan_layout(spec, ['s01'])['shots'][0]['camera']
        self.assertEqual((len(camera), camera[0], camera[-1]), (24, [0, -6], [3, -6]))

    def test_landscape_frame_and_keyed_lens(self):
        spec = duel(); spec.update(width=1920, height=1080)
        self.assertAlmostEqual(self.m.plan_layout(spec, ['s01'])['shots'][0]['half_angle'], 0.4229, places=4)
        spec['shots'][0]['camera']['keys'] = [{'frame': 1, 'lens': 80}, {'frame': 24, 'lens': 20}]
        self.assertAlmostEqual(self.m.plan_layout(spec, ['s01'])['shots'][0]['half_angle'], 0.2213, places=4)

    def test_follow_camera_top_down_camera_and_no_line(self):
        spec = scene(); spec['shots'][0]['camera'] = {'position': [0, -8, 3], 'follow': 'hero'}
        shot = self.m.plan_layout(spec, ['s01'])['shots'][0]
        self.assertEqual((shot['aim'], shot['line']), ([0, 1], None))
        spec = duel((0, 0, 10)); spec['shots'][1]['camera']['target'] = [0, 0, 0]
        self.assertIsNone(self.m.plan_layout(spec, ['s02'])['shots'][0]['aim'])

    def test_roots_standing_elsewhere_than_in_the_first_shot_are_marked(self):
        spec = walking(duel())
        self.assertEqual([s['moved'] for s in self.m.plan_layout(spec, ['s01', 's02'])['shots']], [[], []])
        for item, x in zip(spec['shots'][1]['objects'], (3, 5, 3)): item['keys'] = [{'frame': 1, 'position': [x, 0, 0]}]
        spec['shots'][1]['objects'].append(dict(spec['shots'][1]['objects'][1], id='late'))
        first, second = self.m.plan_layout(spec, ['s01', 's02'])['shots']
        self.assertEqual(first['moved'], [])
        self.assertEqual(second['moved'], [{'id': 'a', 'color': [.5, .5, .5], 'point': [3, 0]},
                                           {'id': 'b', 'color': [.5, .5, .5], 'point': [5, 0]},
                                           {'id': 'late', 'color': [.5, .5, .5], 'point': [5, 0]}])
        self.assertEqual(self.m.plan_layout(spec, ['s02'])['shots'][0]['moved'], [])

    def test_unknown_shot_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'unknown shot s09'):
            self.m.plan_layout(duel(), ['s01', 's09'])

if __name__ == '__main__': unittest.main()
