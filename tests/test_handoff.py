import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/video-previs-workflow/scripts'
sys.path.insert(0, str(SCRIPTS))  # handoff.py imports media.py from the same folder


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class PackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'a.png').write_bytes(b'start frame bytes')
        (self.root / 'b.jpg').write_bytes(b'reference bytes')
        self.out = self.root / 'handoff/s01-kf-v001'
        self.h = load('handoff')
        self.job = {'provider': 'Higgsfield web', 'model': 'Seedream 5.0 Lite',
                    'settings': {'aspect_ratio': '9:16', 'quality': 'high'},
                    'inputs': [{'path': 'a.png', 'slot': 'Start frame', 'purpose': 'composition'},
                               {'path': 'b.jpg', 'slot': 'Image reference 1', 'purpose': 'traveler appearance'}],
                    'prompt': 'seated traveler asleep', 'output': {'kind': 'image', 'notes': '9:16 still'}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_pack_copies_inputs_in_order(self):
        rec = self.h.pack(self.job, self.root, self.out)
        self.assertEqual([r['packed'] for r in rec], ['01-start-frame.png', '02-image-reference-1.jpg'])
        self.assertEqual((self.out / '01-start-frame.png').read_bytes(), (self.root / 'a.png').read_bytes())
        self.assertEqual(rec[0]['sha256'], sha(self.root / 'a.png'))
        self.assertEqual(rec[0]['path'], 'a.png')
        self.assertEqual(list((self.out / 'output').iterdir()), [])

    def test_request_lists_model_settings_inputs_prompt(self):
        self.h.pack(self.job, self.root, self.out)
        text = (self.out / 'request.md').read_text()
        for s in ('Seedream 5.0 Lite', 'aspect_ratio: 9:16', '| 01-start-frame.png | Start frame | composition |',
                  '```text\nseated traveler asleep\n```', 'output/'):
            self.assertIn(s, text)

    def test_request_asks_to_check_reference_links_and_counts(self):
        self.h.pack(self.job, self.root, self.out)
        text = (self.out / 'request.md').read_text()
        self.assertIn('links to its uploaded file', text); self.assertIn('how many images and videos', text)

    def test_unicode_slot_slug(self):
        self.assertEqual(self.h.slug('시작 프레임 / 9:16'), '시작-프레임-9-16')
        self.assertEqual(self.h.slug('///'), 'input')

    def test_pack_refuses_existing_dir(self):
        self.out.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.h.pack(self.job, self.root, self.out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_missing_input_leaves_no_folder(self):
        self.job['inputs'].append({'path': 'missing.png', 'slot': 'x', 'purpose': 'y'})
        with self.assertRaisesRegex(ValueError, 'input not found: missing.png'):
            self.h.pack(self.job, self.root, self.out)
        self.assertFalse(self.out.exists())

    def test_pack_requires_model_prompt_inputs(self):
        self.job['prompt'] = ''
        with self.assertRaisesRegex(ValueError, 'job: model, prompt and inputs are required'):
            self.h.pack(self.job, self.root, self.out)
        self.assertFalse(self.out.exists())


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pack = self.root / 'handoff/s01'
        (self.pack / 'output').mkdir(parents=True)
        self.h = load('handoff')

    def tearDown(self):
        self.tmp.cleanup()

    def media(self, name, video=False):
        args = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=32x48:r=24:d=1']
        args += ['-pix_fmt', 'yuv420p'] if video else ['-frames:v', '1', '-f', 'image2']
        subprocess.run(args + [str(self.pack / 'output' / name)], check=True)

    def test_ingest_image_ignores_hidden_and_case(self):
        self.media('RESULT.PNG')
        (self.pack / 'output/.DS_Store').write_bytes(b'x')
        r = self.h.ingest(self.pack, self.root / 'kf/s01.png', 'image')
        self.assertEqual((r['width'], r['height'], r['duration'], r['fps']), (32, 48, None, None))
        self.assertEqual(r['sha256'], sha(self.root / 'kf/s01.png'))
        self.assertEqual(r['kind'], 'image')

    def test_ingest_video_reports_duration_and_fps(self):
        self.media('take.mp4', video=True)
        r = self.h.ingest(self.pack, self.root / 'take.mp4', 'video')
        self.assertAlmostEqual(r['duration'], 1.0, places=1)
        self.assertEqual(r['fps'], 24.0)

    def test_zero_or_two_results_rejected(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.h.ingest(self.pack, self.root / 'x.png', 'image')
        self.media('a.png'); self.media('b.png')
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.h.ingest(self.pack, self.root / 'x.png', 'image')

    def test_kind_mismatch_rejected(self):
        self.media('a.png')
        with self.assertRaisesRegex(ValueError, 'expected video file'):
            self.h.ingest(self.pack, self.root / 'x.mp4', 'video')

    def test_undecodable_rejected(self):
        (self.pack / 'output/result.png').write_bytes(b'not a png')
        with self.assertRaisesRegex(ValueError, 'cannot decode result.png'):
            self.h.ingest(self.pack, self.root / 'x.png', 'image')
        self.assertFalse((self.root / 'x.png').exists())

    def truncate(self, name, keep):
        f = self.pack / 'output' / name
        f.write_bytes(f.read_bytes()[:int(f.stat().st_size * keep)])

    def test_truncated_jpeg_rejected(self):
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=s=640x960', '-frames:v', '1',
                        str(self.pack / 'output/result.jpg')], check=True)
        self.truncate('result.jpg', .5)
        with self.assertRaisesRegex(ValueError, 'cannot decode result.jpg'):
            self.h.ingest(self.pack, self.root / 'kf.jpg', 'image')
        self.assertFalse((self.root / 'kf.jpg').exists())

    def test_truncated_faststart_mp4_rejected(self):
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=s=320x240:r=24:d=4', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', str(self.pack / 'output/take.mp4')], check=True)
        self.truncate('take.mp4', .6)
        with self.assertRaisesRegex(ValueError, 'cannot decode take.mp4'):
            self.h.ingest(self.pack, self.root / 'take.mp4', 'video')
        self.assertFalse((self.root / 'take.mp4').exists())

    def test_image_renamed_as_video_leaves_no_dest(self):
        self.media('still.png')
        (self.pack / 'output/still.png').rename(self.pack / 'output/still.mp4')
        with self.assertRaisesRegex(ValueError, 'still.mp4'):
            self.h.ingest(self.pack, self.root / 'take.mp4', 'video')
        self.assertFalse((self.root / 'take.mp4').exists())

    def test_dest_exists_rejected(self):
        self.media('a.png')
        (self.root / 'x.png').write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            self.h.ingest(self.pack, self.root / 'x.png', 'image')
        self.assertEqual((self.root / 'x.png').read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
