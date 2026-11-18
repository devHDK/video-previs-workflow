import copy
import importlib.util
import hashlib
import json
import shutil
import subprocess
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

    def test_clamp_times(self):
        self.assertEqual(module('media').clamp_times([-1, 0.24, 25.0, 30], 25.0), [0, 0.24, 24.95, 24.95])

    def test_pair_needs_two_times(self):
        with self.assertRaisesRegex(ValueError, 'times must list 2 or more seconds'):
            module('media').pair('a.mp4', 'b.mp4', Path(tempfile.gettempdir()) / 'never-written.jpg', times=[1.0])

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_pair_at_times_builds_one_column_per_time(self):
        m = module('media')
        with tempfile.TemporaryDirectory() as t:
            a, b, out = Path(t) / 'a.mp4', Path(t) / 'b.mp4', Path(t) / 'sheet.jpg'
            for path, color in ((a, 'red'), (b, 'blue')):
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={color}:s=64x64:r=24:d=1',
                                '-pix_fmt', 'yuv420p', str(path)], check=True)
            m.pair(a, b, out, times=[0, 0.5, 5])  # 5 s is past both clips: clamped, not an error
            video = m.probe(out)['streams'][0]
            self.assertEqual((video['width'], video['height']), (810, 960))

    def test_every_media_subcommand_help_exits_zero(self):
        for sub in ('probe', 'extract', 'encode', 'assemble', 'compare', 'pair', 'continuity', 'cuts', 'sheet'):
            done = subprocess.run([sys.executable, str(SCRIPTS / 'media.py'), sub, '--help'], capture_output=True)
            self.assertEqual(done.returncode, 0, sub)

class CutTests(unittest.TestCase):
    def test_shots_from_cuts_cover_duration(self):
        self.assertEqual(module('media').shots_from_cuts([3.5, 1.5, 0, 4.75], 4.75), [
            {'id': 's01', 'start': 0, 'end': 1.5}, {'id': 's02', 'start': 1.5, 'end': 3.5},
            {'id': 's03', 'start': 3.5, 'end': 4.75}])

    def test_merge_runs_keeps_the_strongest_of_each_run(self):
        m = module('media'); c = lambda t, s: {'t': t, 'score': s}
        self.assertEqual(m.merge_runs([]), [])
        self.assertEqual(m.merge_runs([c(1.0, .2)]), [c(1.0, .2)])
        run = [c(3.40, .12), c(3.45, .10), c(3.52, .15), c(3.57, .11)]
        self.assertEqual(m.merge_runs(run + [c(5.0, .26)]), [dict(c(3.52, .15), **{'from': 3.4, 'to': 3.57}), c(5.0, .26)])
        self.assertEqual(m.merge_runs([c(1.0, .2), c(1.1, .3), c(1.21, .1)]), [dict(c(1.1, .3), **{'from': 1.0, 'to': 1.1}), c(1.21, .1)])   # 0.1 apart joins, more does not
        self.assertEqual(m.merge_runs([c(5.0, .2), c(1.0, .2)]), [c(1.0, .2), c(5.0, .2)])                       # sorted first, nothing dropped

    def test_parse_scene_scores(self):
        log = ('[Parsed_metadata_2 @ 0x1] frame:0    pts:45      pts_time:1.5\n'
               '[Parsed_metadata_2 @ 0x1] lavfi.scene_score=0.412345\n'
               '[Parsed_metadata_2 @ 0x1] frame:1    pts:105     pts_time:3.5\n'
               '[Parsed_metadata_2 @ 0x1] lavfi.scene_score=0.180000\n')
        self.assertEqual(module('media').parse_scene_scores(log), [(1.5, 0.412345), (3.5, 0.18)])

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_weak_scene_changes_become_candidates(self):
        m, gate = module('media'), module('gate')
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'ref.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=0xFF0000:s=64x64:r=30:d=1',
                            '-f', 'lavfi', '-i', 'color=c=0x990000:s=64x64:r=30:d=1',
                            '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=30:d=1',
                            '-f', 'lavfi', '-i', 'color=c=white:s=64x64:r=30:d=1', '-filter_complex',
                            '[0][1][2][3]concat=n=4:v=1[v]', '-map', '[v]', '-pix_fmt', 'yuv420p', str(src)], check=True)
            draft = m.cuts(src, Path(t) / 'a')  # measured scene scores: 0.26 at 1 s, 0.14 at 2 s, 1.0 at 3 s
            self.assertEqual([(round(s['start'], 2), round(s['end'], 2)) for s in draft['shots']], [(0, 3.0), (3.0, 4.0)])
            self.assertEqual(draft['candidates'], [{'t': 1.0, 'score': 0.26}])           # 0.14 is under the default floor of 0.2
            self.assertEqual(m.cuts(src, Path(t) / 'a2', low=0.1)['candidates'], [{'t': 1.0, 'score': 0.26}, {'t': 2.0, 'score': 0.14}])
            self.assertIn('reference: candidate cut at 1 s needs a decision', gate.check_reference(draft))
            self.assertEqual(m.cuts(src, Path(t) / 'b', threshold=0.3, low=0.3)['candidates'], [])
            still = Path(t) / 'still.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:r=30:d=1',
                            '-pix_fmt', 'yuv420p', str(still)], check=True)
            flat = m.cuts(still, Path(t) / 'c')
            self.assertEqual((len(flat['shots']), flat['candidates']), (1, []))

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_cuts_writes_draft_frames_and_clips(self):
        m, gate = module('media'), module('gate')
        with tempfile.TemporaryDirectory() as t:
            src, out = Path(t) / 'ref.mp4', Path(t) / 'reference/v001'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:r=30:d=1',
                            '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=30:d=1', '-filter_complex',
                            '[0][1]concat=n=2:v=1[v]', '-map', '[v]', '-pix_fmt', 'yuv420p', str(src)], check=True)
            draft = m.cuts(src, out)
            self.assertEqual([(round(s['start'], 2), round(s['end'], 2)) for s in draft['shots']], [(0, 1.0), (1.0, 2.0)])
            self.assertEqual(draft['source']['sha256'], hashlib.sha256(src.read_bytes()).hexdigest())
            self.assertEqual((draft['source']['rights'], draft['match'], draft['candidates']), ('', '', []))
            self.assertTrue(all(s['plan'] == {'source': '', 'what': '', 'caption': ''} for s in draft['shots']))
            for shot in draft['shots']:
                for path in shot['stills'] + [shot['clip']]: self.assertTrue(Path(path).is_file(), path)
            self.assertEqual(json.loads((out / 'reference-draft.json').read_text()), draft)
            self.assertLessEqual({f'reference {s}: camera and action are required' for s in ('s01', 's02')},
                                 set(gate.check_reference(draft)))
            with self.assertRaises(FileExistsError): m.cuts(src, out)



@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.m = module('media')
        for name, color, size in (('k1', 'red', '90x160'), ('k2', 'green', '90x160'), ('k3', 'blue', '90x160'),
                                  ('k3b', 'white', '90x160'), ('k4', 'gray', '90x160'), ('wide', 'yellow', '160x90')):
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={color}:s={size}', '-frames:v', '1',
                            str(self.root / f'{name}.png')], check=True)
        key = lambda p, a: {'kind': 'start', 'path': p, 'approval': a, 'sha256': 'h' + p[1:-4]}
        self.state = {'shots': [
            {'id': 's01', 'object_roles': {'hero': 'hero', 'seat': 'cabin'}, 'keyframes': [key('k1.png', 'approved')]},
            {'id': 's02', 'object_roles': {'hero': 'hero', 'house_0': 'village'}, 'keyframes': [key('k2.png', 'approved')]},
            {'id': 's03', 'object_roles': {'hero': 'hero', 'house_0': 'village', 'goo': None}, 'keyframes': [key('k3.png', 'pending')]},
            {'id': 's04', 'object_roles': {'house_0': 'village'}, 'keyframes': [key('k4.png', 'rejected')]}]}
        self.path = self.root / 'state.json'

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        return [{k: r[k] for k in ('role', 'shots')} for r in self.m.continuity_rows(self.state)]

    def test_rows_group_shared_roles(self):
        self.assertEqual(self.rows(), [{'role': 'hero', 'shots': ['s01', 's02', 's03']},
                                       {'role': 'village', 'shots': ['s02', 's03']}])

    def test_pending_used_when_no_approved(self):
        shot = self.state['shots'][2]
        self.assertEqual(self.m.current_keyframe(shot)['path'], 'k3.png')
        shot['keyframes'].append({'kind': 'start', 'path': 'k3b.png', 'approval': 'pending'})
        self.assertEqual(self.m.current_keyframe(shot)['path'], 'k3b.png')
        shot['keyframes'].insert(0, {'kind': 'start', 'path': 'k1.png', 'approval': 'approved'})
        self.assertEqual(self.m.current_keyframe(shot)['path'], 'k1.png')
        self.assertIsNone(self.m.current_keyframe(self.state['shots'][3]))

    def test_sheet_size(self):
        self.state['shots'][1]['keyframes'][0]['path'] = 'wide.png'  # a landscape frame still tiles
        self.path.write_text(json.dumps(self.state))
        rows = self.m.continuity(self.path, self.root / 'sheet.png')
        self.assertEqual([r['role'] for r in rows], ['hero', 'village'])
        self.assertEqual(rows[1]['keyframe_sha256'], {'s02': 'h2', 's03': 'h3'})  # what was shown, ready to copy into a review
        stream = self.m.probe(self.root / 'sheet.png')['streams'][0]
        self.assertEqual((stream['width'], stream['height']), (810, 960))

    def test_refuses_existing_output(self):
        self.path.write_text(json.dumps(self.state))
        (self.root / 'sheet.png').write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            self.m.continuity(self.path, self.root / 'sheet.png')

    def test_no_shared_roles_raises(self):
        self.state['shots'] = self.state['shots'][:1]
        self.path.write_text(json.dumps(self.state))
        with self.assertRaisesRegex(ValueError, 'no role appears in 2\\+ shots with keyframes'):
            self.m.continuity(self.path, self.root / 'sheet.png')

if __name__ == '__main__':
    unittest.main()
