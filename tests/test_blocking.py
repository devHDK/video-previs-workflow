import unittest
from test_workflow import module, scene

class BlockingTests(unittest.TestCase):
    def setUp(self): self.m = module('blocking')

    def near(self, a, b): self.assertTrue(all(abs(x - y) < 1e-9 for x, y in zip(a, b)), (a, b))

    def test_frame_of_matches_gate_rounding(self):
        self.assertEqual([self.m.frame_of(t, 24) for t in (0, 0.24, 8.4)], [1, 7, 203])
        self.assertEqual(self.m.frame_of(18.8, 24, start=8.4), 250)

    def test_track_interpolates_and_clamps(self):
        f = self.m.track([(0, 0.0), (2, 10.0)])
        self.assertEqual([f(-1), f(1), f(5)], [0.0, 5.0, 10.0])
        self.assertEqual(self.m.track([(0, [0, 0]), (4, [2, -4])])(1), [0.5, -1.0])

    def test_local_to_world_follows_facing(self):
        self.near(self.m.local_to_world([1, 2], 0, [0, 0.1, 1.4]), [1, 1.9, 1.4])
        self.near(self.m.local_to_world([1, 2], 90, [0, 0.1, 1.4]), [1.1, 2, 1.4])
        self.near(self.m.local_to_world([1, 2], 180, [0, 0.1, 1.4], z0=0.5), [1, 2.1, 1.9])
        self.near(self.m.local_to_world([0, 0], 0, [0.2, 0, 0]), [-0.2, 0, 0])

    def test_person_is_valid_spec_and_face_follows_facing(self):
        at = lambda frame: ([0, 0], 0.0, 0 if frame == 1 else 180)
        body, head, face = self.m.person('lead', at, [1, 5], [1, 1, 1])
        self.assertEqual([o['id'] for o in (body, head, face)], ['lead', 'lead_head', 'lead_face'])
        self.assertLess(face['keys'][0]['position'][1], 0)
        self.assertGreater(face['keys'][1]['position'][1], 0)
        s = scene(); s['shots'][0].update(frames=5, objects=[body, head, face])
        self.assertEqual(module('validate_spec').validate(s), [])

if __name__ == '__main__': unittest.main()
