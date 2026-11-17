"""Group motion, unlisted figure motion and take QA: checks added after a single-take production where the crowd
came out in lockstep and the lead gained a sidestep the reference never had."""
import importlib.util
import math
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/video-previs-workflow/scripts'
sys.path.insert(0, str(SCRIPTS))
import motion  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def figure(fid, keys, shape='capsule'):
    return {'id': fid, 'shape': shape, 'keys': [{'frame': f, 'position': [x, y, 0], 'rotation': [0, 0, math.radians(yaw)]}
                                                for f, x, y, yaw in keys]}


def walker():
    """Stands 1 s, turns 180 over 1 s, walks 4 m in 3 s."""
    return figure('lead', [(1, 0, 0, 0), (25, 0, 0, 0), (49, 0, 0, 180), (121, 0, 4, 180)])


def sidestepper():
    """The same walk with a quarter turn at 3.5 s that the reference never had."""
    return figure('lead', [(1, 0, 0, 0), (25, 0, 0, 0), (49, 0, 0, 180), (85, 0, 2, 180), (97, 0, 2.4, 270), (121, 0, 4, 270)])


class MemberTests(unittest.TestCase):
    def test_parts_belong_to_their_root(self):
        self.assertEqual(motion.members(['lead', 'lead_head', 'lead_face', 'cup', 's00_-1p50', 's00_-1p50_torso']),
                         ['cup', 'lead', 's00_-1p50'])


class FigureMoveTests(unittest.TestCase):
    def moves(self, item, frames=121):
        return motion.figure_moves(item, frames, 24)

    def test_turn_is_found_with_its_time_and_size(self):
        turns = [m for m in self.moves(walker()) if m['kind'] == 'turn']
        self.assertEqual(len(turns), 1)
        self.assertAlmostEqual(turns[0]['t'], 1.0, delta=0.05); self.assertEqual(turns[0]['degrees'], 180)

    def test_small_turn_is_ignored(self):
        item = figure('lead', [(1, 0, 0, 0), (25, 0, 0, 30), (121, 0, 0, 30)])
        self.assertEqual(self.moves(item), [])

    def test_sidestep_shows_as_direction_changes(self):
        item = figure('lead', [(1, 0, 0, 0), (49, 0, 3, 0), (61, 1.5, 3, 0), (121, 1.5, 6, 0)])
        kinds = [m['kind'] for m in self.moves(item)]
        self.assertEqual(kinds.count('direction'), 2)

    def test_stop_between_two_walks(self):
        item = figure('lead', [(1, 0, 0, 0), (37, 0, 2, 0), (61, 0, 2, 0), (121, 0, 5, 0)])
        stops = [m for m in self.moves(item) if m['kind'] == 'stop']
        self.assertEqual(len(stops), 1); self.assertAlmostEqual(stops[0]['t'], 1.5, delta=0.3)

    def test_standing_still_from_the_start_is_not_a_stop(self):
        self.assertEqual([m for m in self.moves(walker()) if m['kind'] == 'stop'], [])

    def test_travel_length(self):
        self.assertAlmostEqual(motion.travel(walker(), 121), 4.0, delta=0.01)


def crowd(n):
    return [figure(f's{i:02d}', [(1, i, 5, 0), (121, i, 5, 0)]) for i in range(n)]


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.g = load('gate')
        self.spec = {'id': 's01', 'frames': 121, 'objects': crowd(6) + [figure('wall', [(1, 0, 9, 0)], 'cube')] * 1}
        self.shot = {'id': 's01', 'object_roles': dict({f's{i:02d}': 'student' for i in range(6)}, wall='yard')}

    def errors(self):
        return self.g.group_errors(self.shot, self.spec)

    def test_group_without_record_is_rejected(self):
        self.assertEqual(self.errors(), ['s01: 6 figures share role student; group_motion.student.sync must be unison or ragged'])

    def test_unison_passes(self):
        self.shot['group_motion'] = {'student': {'sync': 'unison'}}
        self.assertEqual(self.errors(), [])

    def test_ragged_needs_a_spread(self):
        self.shot['group_motion'] = {'student': {'sync': 'ragged'}}
        self.assertIn('spread_s', self.errors()[0])
        self.shot['group_motion']['student']['spread_s'] = 0.25
        self.assertEqual(self.errors(), [])

    def test_four_figures_are_not_a_group(self):
        self.spec['objects'] = crowd(4); self.shot['object_roles'] = {f's{i:02d}': 'student' for i in range(4)}
        self.assertEqual(self.errors(), [])

    def test_set_pieces_and_parts_do_not_count(self):
        parts = [dict(figure('lead_' + p, [(1, 0, 0, 0)], 'sphere')) for p in 'abcdef']
        self.spec['objects'] = [walker()] + parts + [figure(f'riser{i}', [(1, 0, i, 0)], 'cube') for i in range(8)]
        self.shot['object_roles'] = dict({o['id']: 'lead' for o in [walker()] + parts}, **{f'riser{i}': 'yard' for i in range(8)})
        self.assertEqual(self.errors(), [])


class UnlistedMotionTests(unittest.TestCase):
    def setUp(self):
        self.g = load('gate')
        self.shot = {'id': 's01', 'object_roles': {'lead': 'lead'}}
        self.ref = {'id': 's01', 'start': 10.0, 'end': 15.0, 'travel': {'lead': 'walks straight to the gap right of the front-row boy'},
                    'events': [{'t': 11.0, 'event': 'turns away'}]}

    def errors(self, item=None):
        spec = {'id': 's01', 'frames': 121, 'objects': [item or walker()]}
        return self.g.motion_errors(self.shot, spec, 24, self.ref)

    def test_motion_listed_in_the_reference_passes(self):
        self.assertEqual(self.errors(), [])

    def test_turn_with_no_reference_event_is_rejected(self):
        e = self.errors(sidestepper())
        self.assertEqual(len(e), 1)
        self.assertIn('lead turn 90 deg at 3.5 s', e[0]); self.assertIn('unlisted_motion', e[0])

    def test_decision_accepts_the_added_motion(self):
        self.shot['unlisted_motion'] = [{'t': 3.5, 'decision': 'user: sidestep kept so she stays centred'}]
        self.assertEqual(self.errors(sidestepper()), [])

    def test_decision_without_text_does_not_count(self):
        self.shot['unlisted_motion'] = [{'t': 3.5}]
        self.assertEqual(len(self.errors(sidestepper())), 1)

    def test_travelling_figure_needs_a_route_in_the_reference(self):
        del self.ref['travel']
        self.assertEqual(self.errors(), ['reference s01: travel.lead required (destination, route, who stands beside it): '
                                         'it moves 4.0 m in previs'])

    def test_objects_without_keys_are_skipped(self):
        self.assertEqual(self.g.motion_errors(self.shot, {'id': 's01', 'frames': 48, 'objects': [{'id': 'lead'}]}, 24, self.ref), [])


class QaTests(unittest.TestCase):
    def setUp(self):
        self.g = load('gate'); self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / 'take.mp4').write_bytes(b'x')
        self.shot = {'id': 's01', 'selected_output': 'take.mp4', 'required_events': ['hero lands', {'t': 2, 'event': 'crowd bows'}],
                     'event_results': {'hero lands': {'result': 'pass', 'evidence': 'qa/pair.jpg 1.2 s'},
                                       'crowd bows': {'result': 'accepted', 'evidence': 'User: "ok"'}}}
        self.state = {'shots': [self.shot]}

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self):
        return self.g.check_qa(self.state, self.root)

    def test_every_event_passed_or_accepted(self):
        self.assertEqual(self.errors(), [])

    def test_missing_failed_or_unevidenced_event_blocks(self):
        self.shot['event_results']['hero lands'] = {'result': 'fail', 'evidence': 'x'}
        del self.shot['event_results']['crowd bows']
        self.assertEqual(self.errors(), ['s01: event needs a pass or accepted result with evidence: hero lands',
                                         's01: event needs a pass or accepted result with evidence: crowd bows'])

    def test_take_file_required(self):
        self.shot['selected_output'] = 'gone.mp4'
        self.assertEqual(self.errors(), ['s01: selected_output take file required'])

    def test_group_needs_a_measured_spread(self):
        self.shot['group_motion'] = {'student': {'sync': 'ragged', 'spread_s': 0.27}}
        self.assertEqual(self.errors(), ['s01: group_motion.student.measured_s required (media.py spread on the take)'])

    def test_ragged_group_far_from_target_blocks_unless_accepted(self):
        group = {'sync': 'ragged', 'spread_s': 0.27, 'measured_s': 0.09}
        self.shot['group_motion'] = {'student': group}
        self.assertEqual(self.errors(), ['s01: group student spread 0.09 s is outside 0.5-2x the target 0.27 s'])
        group.update(result='accepted', evidence='User: "fine"')
        self.assertEqual(self.errors(), [])
        group.update(result=None, measured_s=0.3)
        self.assertEqual(self.errors(), [])


if __name__ == '__main__':
    unittest.main()
