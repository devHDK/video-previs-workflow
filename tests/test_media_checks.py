import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/video-previs-workflow/scripts'
sys.path.insert(0, str(SCRIPTS))
import media  # noqa: E402

FFMPEG = unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')


class RepeatedFrameTests(unittest.TestCase):
    def test_repeat_is_a_still_frame_between_moving_ones(self):
        diffs = [0, 3.0, 3.1, 0.2, 3.0, 2.9]
        self.assertEqual(media.repeated_frames(diffs), [3])

    def test_a_held_shot_is_not_a_repeat(self):
        self.assertEqual(media.repeated_frames([0, 0.1, 0.2, 0.1, 0.2]), [])

    def test_last_frame_repeat_is_ignored(self):  # nothing after it to average with
        self.assertEqual(media.repeated_frames([0, 3.0, 3.0, 0.1]), [])

    @FFMPEG
    def test_dupes_finds_and_fixes_a_repeated_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            src, out = Path(temp) / 'src.mp4', Path(temp) / 'fixed.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=64x64:r=24:d=1', '-vf',
                            'loop=loop=1:size=1:start=10', '-c:v', 'libx264', '-crf', '10', '-pix_fmt', 'yuv420p', str(src)], check=True)
            found = media.dupes(src)  # the loop filter shows one frame twice: index 10 repeats index 9
            self.assertEqual(found['repeated'], [10])
            fixed = media.dupes(src, out)
            self.assertEqual(fixed['repeated'], [10])
            self.assertEqual(media.dupes(out)['repeated'], [])
            self.assertEqual(media.dupes(out)['frames'], found['frames'])

    @FFMPEG
    def test_fix_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / 'src.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=64x64:r=24:d=0.5', '-pix_fmt', 'yuv420p', str(src)], check=True)
            with self.assertRaises(FileExistsError): media.dupes(src, src)


class SpreadTests(unittest.TestCase):
    def cells(self, offsets, fps=24, seconds=4):
        """Each cell is a square wave of period 2 s, shifted by its own offset in seconds."""
        n = int(seconds * fps)
        return [[200 if ((i / fps - off) % 2) < 1 else 20 for off in offsets] for i in range(n)]

    def test_lockstep_has_no_spread(self):
        r = media.spread_of(self.cells([0.5] * 20), 24)
        self.assertLess(r['spread_s'], 0.03)

    def test_ragged_spread_is_half_the_p10_p90_width(self):
        offsets = [0.5 + (i - 10) * 0.05 for i in range(21)]  # -0.5..+0.5 s, uniform
        r = media.spread_of(self.cells(offsets), 24)
        self.assertAlmostEqual(r['spread_s'], 0.4, delta=0.06)  # p10-p90 of a uniform 1 s width is 0.8 s
        self.assertEqual(r['cells'], 21)

    def test_still_cells_are_left_out(self):
        frames = [row + [100] for row in self.cells([0.5] * 10)]
        self.assertEqual(media.spread_of(frames, 24)['cells'], 10)

    def test_no_motion_raises(self):
        with self.assertRaises(ValueError): media.spread_of([[100] * 5] * 48, 24)

    @FFMPEG
    def test_spread_reads_a_clip(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / 'blink.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=white:s=64x64:r=24:d=4', '-vf',
                            "drawbox=t=fill:c=black:enable='lt(mod(t,2),1)'", '-pix_fmt', 'yuv420p', str(src)], check=True)
            r = media.spread(src, 0, 4, (4, 4))
            self.assertLess(r['spread_s'], 0.05)
            self.assertGreaterEqual(r['beats'], 2)


class ReframeTests(unittest.TestCase):
    def test_filter_tracks_the_centre_and_pads_to_target(self):
        vf = media.reframe_filter([(0, 800), (2, 1000)], 1056, (360, 640), (1920, 1080))
        self.assertIn('crop=1056:1080:', vf)
        self.assertIn('800+(1000-800)*(t-0)/2', vf)
        self.assertTrue(vf.endswith('scale=360:640,setsar=1'))
        self.assertIn('pad=1056:1878', vf)  # 1056 * 16/9, rounded to even

    def test_crop_stays_inside_the_source(self):
        vf = media.reframe_filter([(0, 100)], 1056, (360, 640), (1920, 1080))
        self.assertIn('min(max(', vf); self.assertIn('\\,864)', vf)  # 1920 - 1056

    def test_rejects_crop_wider_than_source_or_no_centres(self):
        with self.assertRaises(ValueError): media.reframe_filter([(0, 100)], 2000, (360, 640), (1920, 1080))
        with self.assertRaises(ValueError): media.reframe_filter([], 1056, (360, 640), (1920, 1080))

    def test_parse_centres(self):
        self.assertEqual(media.parse_centres('0:780,3.04:1178'), [(0.0, 780.0), (3.04, 1178.0)])
        with self.assertRaises(ValueError): media.parse_centres('3:10,1:20')

    @FFMPEG
    def test_reframe_writes_target_size(self):
        with tempfile.TemporaryDirectory() as temp:
            src, out = Path(temp) / 'wide.mp4', Path(temp) / 'tall.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=25:d=1', '-pix_fmt', 'yuv420p', str(src)], check=True)
            media.reframe(src, out, (90, 160), 176, [(0, 100), (1, 200)], 24)
            video = next(s for s in media.probe(out)['streams'] if s['codec_type'] == 'video')
            self.assertEqual((video['width'], video['height'], video['r_frame_rate']), (90, 160, '24/1'))


class CliTests(unittest.TestCase):
    def test_new_subcommands_have_help(self):
        for name in ('dupes', 'spread', 'reframe'):
            r = subprocess.run([sys.executable, str(SCRIPTS / 'media.py'), name, '--help'], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)



@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
class SheetTests(unittest.TestCase):
    def size(self, path):
        video = next(s for s in media.probe(path)['streams'] if s['codec_type'] == 'video')
        return video['width'], video['height']

    def test_mixed_pixel_formats_all_reach_their_cells(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); images = []
            for i, (colour, fmt) in enumerate((('red', 'rgba'), ('green', 'rgb24'), ('blue', 'rgba'), ('white', 'gray'))):
                images.append(root / f'{i}.png')
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={colour}:s=90x160,format={fmt}', '-frames:v', '1',
                                str(images[-1])], check=True)
            media.sheet(images, root / 'sheet.png', cols=4)
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(root / 'sheet.png'), '-vf', 'scale=4:1:flags=neighbor', '-f', 'rawvideo',
                                  '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
            cells = [tuple(raw[i:i + 3]) for i in range(0, 12, 3)]
            self.assertTrue(cells[0][0] > 200 and cells[1][1] > 100 and cells[2][2] > 200 and min(cells[3]) > 200, cells)

    def test_images_tile_in_rows_and_bad_input_writes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); images = []
            for i, colour in enumerate(('red', 'green', 'blue')):
                images.append(root / f'{i}.png')
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={colour}:s=90x160', '-frames:v', '1',
                                str(images[-1])], check=True)
            legend = media.sheet(images, root / 'out/sheet.jpg')
            self.assertEqual(legend, [{'row': 1, 'col': 1, 'path': str(images[0])}, {'row': 1, 'col': 2, 'path': str(images[1])},
                                      {'row': 2, 'col': 1, 'path': str(images[2])}])
            media.sheet(images, root / 'big.jpg', cols=3, cell=(540, 960))
            self.assertEqual(self.size(root / 'big.jpg'), (1620, 960))
            with self.assertRaisesRegex(ValueError, 'cell must be WxH with positive even numbers'): media.sheet(images, root / 'bad.jpg', cell=(0, 10))
            self.assertFalse((root / 'bad.jpg').exists())
            self.assertEqual(self.size(root / 'out/sheet.jpg'), (540, 960))          # 2 columns, 2 rows
            media.sheet(images, root / 'wide.jpg', cols=3)
            self.assertEqual(self.size(root / 'wide.jpg'), (810, 480))
            with self.assertRaises(FileExistsError): media.sheet(images, root / 'wide.jpg')
            with self.assertRaisesRegex(ValueError, 'sheet needs 2 or more images'): media.sheet(images[:1], root / 'one.jpg')
            with self.assertRaisesRegex(ValueError, 'missing image'): media.sheet(images + [root / 'no.png'], root / 'gone.jpg')
            self.assertFalse((root / 'one.jpg').exists() or (root / 'gone.jpg').exists())

if __name__ == '__main__':
    unittest.main()
