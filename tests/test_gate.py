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
        for msg in ('story: approved story design or reference breakdown required', 's01: required_events missing',
                    's01: object slide has no role decision (map to a role or null)',
                    's01: approved start keyframe required', 'budget: retry_reserve must cover max_shot_quote'):
            self.assertIn(msg, e)

    def test_empty_state_reports_without_raising(self):
        self.state = {}
        e = self.errors()
        self.assertIn('story: approved story design or reference breakdown required', e)
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

    def test_all_web_unlimited_budget_passes(self):
        self.state['budget'].update(retry_reserve=0, max_shot_quote=0)
        self.assertEqual(self.errors(), [])

    def test_negative_quote_rejected(self):
        self.state['budget'].update(retry_reserve=0, max_shot_quote=-1)
        self.assertIn('budget: retry_reserve must cover max_shot_quote', self.errors())

    def test_list_role_reported_not_raised(self):
        self.shot['object_roles']['slide'] = ['slide']
        self.assertIn('s01: object slide role must be a string or null', self.errors())

    def test_nonstring_asset_role_ignored_not_raised(self):
        self.state['assets'][1]['role_id'] = ['slide']
        self.assertIn('s01: role slide needs an approved asset bound to this shot', self.errors())

    def test_nonstring_shot_id_reported_not_raised(self):
        self.shot['id'] = ['s01']
        self.assertIn('shot id must be a string', self.errors())

    def test_two_approved_start_keyframes_reported(self):
        (self.root / 'k2.png').write_bytes(b'k2')
        self.shot['keyframes'].append({'kind': 'start', 'path': 'k2.png', 'sha256': sha(self.root / 'k2.png'),
                                       'approval': 'approved'})
        self.assertIn('s01: more than one approved start keyframe', self.errors())

    def test_role_bound_to_different_versions_across_shots(self):
        scene = json.loads((self.root / 'scene.json').read_text())
        scene['shots'].append({'id': 's02', 'objects': [{'id': 'slide'}]})
        (self.root / 'scene.json').write_text(json.dumps(scene))
        (self.root / 'slide2.png').write_bytes(b'slide2')
        self.state['assets'].append({'role_id': 'slide', 'version': 'v002', 'sha256': sha(self.root / 'slide2.png'),
                                     'approval': 'approved'})
        self.state['shots'].append({'id': 's02', 'required_events': ['slide seen'], 'object_roles': {'slide': 'slide'},
                                    'asset_bindings': [{'role_id': 'slide', 'sha256': sha(self.root / 'slide2.png')}],
                                    'keyframes': [dict(self.shot['keyframes'][0])]})
        self.assertIn('role slide is bound to different versions across shots', self.errors())


def reference_project(root: Path) -> dict:
    """Reference-led route: an approved reference breakdown replaces the story; previs timing follows its cuts."""
    state = ready_project(root)
    del state['story']
    (root / 'scene.json').write_text(json.dumps({'fps': 24, 'shots': [
        {'id': 's01', 'frames': 36, 'objects': [{'id': 'hero'}, {'id': 'slide'}, {'id': 'ground'}]},
        {'id': 's02', 'frames': 48, 'objects': []}]}))
    write_reference(root, [
        {'id': 's01', 'start': 0, 'end': 1.5, 'camera': 'MS eye level, static', 'action': 'hero slides in',
         'events': [{'t': 1.0, 'event': 'hero lands'}]},
        {'id': 's02', 'start': 1.5, 'end': 3.5, 'camera': 'CU push in', 'action': 'hero waves'}])
    state['reference'] = {'path': 'reference.json', 'sha256': sha(root / 'reference.json'), 'approval': 'approved'}
    return state


def write_reference(root, shots):
    (root / 'reference.json').write_text(json.dumps(
        {'version': 1, 'source': {'path': 'inputs/reference.mp4', 'sha256': 'abc'}, 'shots': shots}))


class GateReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.g = load('gate')
        self.state = reference_project(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self):
        return self.g.check_project(self.state, self.root)

    def rewrite(self, shots):
        write_reference(self.root, shots)
        self.state['reference']['sha256'] = sha(self.root / 'reference.json')

    def shots(self):
        return json.loads((self.root / 'reference.json').read_text())['shots']

    def test_approved_reference_replaces_story(self):
        self.assertEqual(self.errors(), [])

    def test_submission_accepts_reference(self):
        job = {'shot': 's01', 'quote': 28, 'start_frame_sha256': sha(self.root / 'k.png')}
        self.assertEqual(self.g.check_submission(self.state, job, self.root), [])

    def test_unapproved_reference_is_not_enough(self):
        self.state['reference']['approval'] = 'pending'
        self.assertIn('story: approved story design or reference breakdown required', self.errors())

    def test_reference_change_detected(self):
        (self.root / 'reference.json').write_text('{}')
        self.assertIn('reference: file missing or changed since approval', self.errors())

    def test_previs_frames_must_follow_reference_cuts(self):
        spec = json.loads((self.root / 'scene.json').read_text())
        spec['shots'][1]['frames'] = 40
        (self.root / 'scene.json').write_text(json.dumps(spec))
        self.assertIn('s02: previs frames 40 differ from reference timing 48', self.errors())

    def test_cut_boundaries_round_without_drift(self):
        shots = self.shots()
        shots[0]['end'] = shots[1]['start'] = 1.5333  # 30 fps cut: 36.8 -> boundary 37
        self.rewrite(shots)
        spec = json.loads((self.root / 'scene.json').read_text())
        spec['shots'][0]['frames'], spec['shots'][1]['frames'] = 37, 47
        (self.root / 'scene.json').write_text(json.dumps(spec))
        self.assertEqual(self.errors(), [])

    def test_reference_shot_missing_from_previs(self):
        shots = self.shots() + [{'id': 's03', 'start': 3.5, 'end': 4.0, 'camera': 'WS', 'action': 'exit'}]
        self.rewrite(shots)
        self.assertIn('reference s03: shot not in previs spec', self.errors())

    def test_recorded_decision_exempts_timing(self):
        shots = self.shots() + [{'id': 's03', 'start': 3.5, 'end': 4.0, 'camera': 'WS', 'action': 'exit',
                                 'decision': 'dropped: user approved ending on s02'}]
        self.rewrite(shots)
        self.assertEqual(self.errors(), [])

    def test_shots_must_be_contiguous_from_zero(self):
        shots = self.shots()
        shots[1]['start'] = 1.6
        self.rewrite(shots)
        self.assertIn('reference s02: gap or overlap with previous shot', self.errors())

    def test_camera_and_action_required(self):
        shots = self.shots()
        shots[0]['action'] = ''
        self.rewrite(shots)
        self.assertIn('reference s01: camera and action are required', self.errors())

    def test_event_outside_shot_reported(self):
        shots = self.shots()
        shots[0]['events'] = [{'t': 2.0, 'event': 'late'}]
        self.rewrite(shots)
        self.assertIn('reference s01: event at 2.0 s is outside the shot', self.errors())

    def test_event_at_cut_belongs_to_next_shot(self):
        shots = self.shots()
        shots[0]['events'] = [{'t': 1.5, 'event': 'cut'}]
        self.rewrite(shots)
        self.assertIn('reference s01: event at 1.5 s is outside the shot', self.errors())

    def test_source_required(self):
        (self.root / 'reference.json').write_text(json.dumps({'shots': self.shots()}))
        self.state['reference']['sha256'] = sha(self.root / 'reference.json')
        self.assertIn('reference: source.path and source.sha256 are required', self.errors())

    def test_malformed_reference_reports_without_raising(self):
        for shots in ('x', [], ['x'], [{'id': 's01', 'start': 'a'}]):
            self.rewrite(shots)
            self.assertTrue(self.errors())

    def test_standalone_check_skips_timing(self):
        self.assertEqual(self.g.check_reference(json.loads((self.root / 'reference.json').read_text())), [])


class GateSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.g = load('gate')
        self.state = ready_project(self.root)
        self.budget = self.state['budget']
        self.job = {'shot': 's01', 'quote': 28, 'start_frame_sha256': sha(self.root / 'k.png')}

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self):
        return self.g.check_submission(self.state, self.job, self.root)

    def test_submission_within_budget_passes(self):
        self.assertEqual(self.errors(), [])

    def test_submission_cannot_consume_retry_reserve(self):
        self.budget['settled'] = 50
        self.assertIn('budget: submission would consume the retry reserve', self.errors())

    def test_retry_may_use_reserve_down_to_exact_quote(self):
        self.budget['settled'] = 72
        self.job['retry_of'] = 's01-v001'
        self.assertEqual(self.errors(), [])

    def test_retry_over_available_rejected(self):
        self.budget['settled'] = 80
        self.job['retry_of'] = 's01-v001'
        self.assertIn('budget: quote exceeds available credits', self.errors())

    def test_unresolved_reservation_counts(self):
        self.budget['reserved'] = 50
        self.assertIn('budget: submission would consume the retry reserve', self.errors())

    def test_quote_above_max_shot_quote_rejected(self):
        self.job['quote'] = 60
        self.assertIn('budget: job quote exceeds max_shot_quote', self.errors())

    def test_zero_budget_blocks_paid_job(self):
        self.budget.update(retry_reserve=0, max_shot_quote=0)
        self.assertIn('budget: job quote exceeds max_shot_quote', self.errors())

    def test_zero_quote_manual_job_passes(self):
        self.budget.update(retry_reserve=0, max_shot_quote=0)
        self.job.update(quote=0, route='manual')
        self.assertEqual(self.errors(), [])

    def test_zero_quote_requires_manual_route(self):
        self.budget.update(retry_reserve=0, max_shot_quote=0)
        self.job['quote'] = 0
        self.assertIn('budget: only manual jobs may be quoted 0', self.errors())

    def test_missing_cap_blocks_zero_quote_job(self):
        self.budget.update(retry_reserve=0, max_shot_quote=0)
        del self.budget['cap']
        self.job.update(quote=0, route='manual')
        self.assertIn('budget: cap required', self.errors())

    def test_job_start_frame_must_match_keyframe(self):
        self.job['start_frame_sha256'] = 'other'
        self.assertIn('s01: job start frame is not the approved keyframe', self.errors())

    def test_attempt_limit(self):
        self.budget['attempts_used'] = 5
        self.assertIn('budget: attempt limit reached', self.errors())

    def test_unknown_shot(self):
        self.job['shot'] = 's09'
        self.assertIn('s09: shot not found in state', self.errors())

    def test_other_shot_errors_do_not_block(self):
        self.state['shots'].append({'id': 's02'})
        self.assertEqual(self.errors(), [])
        self.assertTrue(self.g.check_project(self.state, self.root))


if __name__ == '__main__':
    unittest.main()
