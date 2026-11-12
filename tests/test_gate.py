import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/video-previs-workflow/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ready_project(root: Path) -> dict:
    (root / 'story.json').write_text(json.dumps(
        {'purpose': 'p', 'target_action': {'action': 'save'}, 'structure': {'id': 'relief'}}))
    (root / 'scene.json').write_text(json.dumps(
        {'shots': [{'id': 's01', 'objects': [{'id': 'hero'}, {'id': 'slide'}, {'id': 'ground'}]}]}))
    for name in ('k.png', 'hero.png', 'slide.png'):
        (root / name).write_bytes(name.encode())
    asset = lambda role: {'role_id': role, 'version': 'v001', 'sha256': sha(root / f'{role}.png'), 'approval': 'approved'}
    return {
        'story': {'path': 'story.json', 'sha256': sha(root / 'story.json'), 'approval': 'approved'},
        'previs': {'spec_path': 'scene.json', 'approval': 'approved'},
        'assets': [asset('hero'), asset('slide')],
        'shots': [{'id': 's01', 'required_events': ['hero lands'],
                   'object_roles': {'hero': 'hero', 'slide': 'slide', 'ground': None},
                   'asset_bindings': [{'role_id': r, 'sha256': sha(root / f'{r}.png')} for r in ('hero', 'slide')],
                   'keyframes': [{'kind': 'start', 'path': 'k.png', 'sha256': sha(root / 'k.png'), 'approval': 'approved'}]}],
        'budget': {'cap': 100, 'settled': 0, 'reserved': 0, 'max_attempts': 5, 'attempts_used': 0,
                   'retry_reserve': 30, 'max_shot_quote': 28}}


class GateProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.g = load('gate')
        self.state = ready_project(self.root)
        self.shot = self.state['shots'][0]

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self):
        return self.g.check_project(self.state, self.root)

    def test_ready_project_passes(self):
        self.assertEqual(self.errors(), [])

    def test_legacy_state_reports_without_raising(self):
        self.state = {'previs': {'spec_path': 'scene.json', 'approval': 'approved'},
                      'shots': [{'id': 's01', 'frames': 72, 'asset_bindings': []}], 'budget': {'cap': 200}}
        e = self.errors()
        for msg in ('story: approved story design required', 's01: required_events missing',
                    's01: object slide has no role decision (map to a role or null)',
                    's01: approved start keyframe required', 'budget: retry_reserve must cover max_shot_quote'):
            self.assertIn(msg, e)

    def test_empty_state_reports_without_raising(self):
        self.state = {}
        e = self.errors()
        self.assertIn('story: approved story design required', e)
        self.assertIn('previs: approval required', e)

    def test_story_change_detected(self):
        (self.root / 'story.json').write_text('{}')
        self.assertIn('story: file missing or changed since approval', self.errors())

    def test_story_core_fields_required(self):
        (self.root / 'story.json').write_text('{}')
        self.state['story']['sha256'] = sha(self.root / 'story.json')
        self.assertIn('story: purpose, target_action and structure are required', self.errors())

    def test_unmapped_object_reported(self):
        del self.shot['object_roles']['slide']
        self.assertIn('s01: object slide has no role decision (map to a role or null)', self.errors())

    def test_role_needs_approved_bound_asset(self):
        self.state['assets'][1]['approval'] = 'pending'
        self.assertIn('s01: role slide needs an approved asset bound to this shot', self.errors())

    def test_bound_sha_must_match_approved_asset(self):
        self.shot['asset_bindings'][1]['sha256'] = 'old'
        self.assertIn('s01: role slide needs an approved asset bound to this shot', self.errors())

    def test_required_events_missing(self):
        self.shot['required_events'] = []
        self.assertIn('s01: required_events missing', self.errors())

    def test_missing_start_keyframe(self):
        self.shot['keyframes'] = []
        self.assertIn('s01: approved start keyframe required', self.errors())

    def test_keyframe_change_detected(self):
        (self.root / 'k.png').write_bytes(b'changed')
        self.assertIn('s01: keyframe k.png missing or changed since approval', self.errors())

    def test_shot_absent_from_spec(self):
        self.shot['id'] = 's09'
        self.assertIn('s09: shot not found in previs spec', self.errors())

    def test_retry_reserve_must_cover_max_shot_quote(self):
        self.state['budget']['retry_reserve'] = 10
        self.assertIn('budget: retry_reserve must cover max_shot_quote', self.errors())


if __name__ == '__main__':
    unittest.main()
