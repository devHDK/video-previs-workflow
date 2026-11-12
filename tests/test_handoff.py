import hashlib
import importlib.util
import json
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


if __name__ == '__main__':
    unittest.main()
