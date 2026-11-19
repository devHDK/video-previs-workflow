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


SETUP = {f: 'x' for f in ('premise', 'tone', 'avoid', 'lead', 'setting')}  # `hook` is optional, so the fixtures leave it out
PER_SHOT = {'generation_mode': 'per_shot', 'duration_s': 2}  # every video job says how it is generated
PLAN_NEEDED = "generation_plan: the user's choice of per_shot, multi_cut or one_take for each take is not recorded"
LOOK = {'camera': {'holder': 'lead', 'lens': 'phone', 'motion': 'handheld', 'views': ['pov', 'selfie']},
        'pace': {'avg_shot_s': 2, 'cuts': 'hard'}, 'speech': 'none', 'captions': 'info',
        'colour': {'light': 'available', 'grade': 'phone_auto'}, 'world': 'lived_in', 'performance': 'to_camera'}


def ready_project(root: Path) -> dict:
    (root / 'story.json').write_text(json.dumps(
        {'purpose': 'p', 'target_action': {'action': 'save'}, 'structure': {'id': 'relief'}, 'setup': SETUP}))
    (root / 'scene.json').write_text(json.dumps(
        {'fps': 24, 'shots': [{'id': 's01', 'frames': 48, 'objects': [{'id': 'hero'}, {'id': 'slide'}, {'id': 'ground'}]}]}))
    for name in ('k.png', 'hero.png', 'slide.png'):
        (root / name).write_bytes(name.encode())
    asset = lambda role, kind: {'role_id': role, 'version': 'v001', 'sha256': sha(root / f'{role}.png'), 'approval': 'approved',
                                'kind': kind}
    return {
        'story': {'path': 'story.json', 'sha256': sha(root / 'story.json'), 'approval': 'approved'},
        'previs': {'spec_path': 'scene.json', 'approval': 'approved'},
        'generation_profile': {'route': 'manual', 'model': 'm', 'max_duration_s': 30, 'duration_step_s': 1},
        'generation_plan': {'takes': [{'mode': 'per_shot', 'shots': ['s01']}], 'evidence': 'user: one job per shot'},
        'assets': [asset('hero', 'character'), asset('slide', 'prop')],
        'shots': [{'id': 's01', 'required_events': ['hero lands'],
                   'object_roles': {'hero': 'hero', 'slide': 'slide', 'ground': None},
                   'props': {'slide': {'origin': 'stands in the yard from frame 1', 'holder': 'none', 'exit': 'stays', 'count': 1,
                                       'states': [{'t': 0, 'where': 'in the yard'}]}},
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

    def insert(self, **fields):
        self.state['shots'].append(dict(self.shot, id='s02', object_roles={}, props={}, asset_bindings=[], **dict({'frames': 24}, **fields)))
        return self.state['shots'][-1]

    def test_no_previs_shot_must_state_its_roles(self):
        shot = self.insert(no_previs='close insert'); del shot['object_roles']
        self.assertEqual(self.errors(), ['s02: object_roles required for a shot without previs (name what is in the frame, or {})'])
        for bad in ('hero', ['hero'], None):
            shot['object_roles'] = bad
            self.assertEqual(self.errors(), ['s02: object_roles required for a shot without previs (name what is in the frame, or {})'], bad)
        shot['object_roles'] = {}
        self.assertEqual(self.errors(), [])

    def test_missing_spec_does_not_blame_no_previs_shots(self):
        self.insert(no_previs='close insert'); (self.root / 'scene.json').unlink()
        self.assertNotIn('s02: no_previs is set but the shot is in the previs spec', self.errors())
        self.assertIn('previs: spec file not found', self.errors())

    def test_shot_without_blocking_may_skip_previs_with_a_reason(self):
        shot = self.insert()
        self.assertEqual(self.errors(), ['s02: shot not found in previs spec'])
        shot['no_previs'] = 'close insert: one hand and a card, nothing to place'
        self.assertEqual(self.errors(), [])
        shot['no_previs'] = '  '
        self.assertEqual(self.errors(), ['s02: shot not found in previs spec'])
        for bad in (7, ['x'], True):
            shot['no_previs'] = bad
            self.assertEqual(self.errors(), ['s02: shot not found in previs spec'])

    def test_no_previs_shot_stays_out_of_the_spec_and_keeps_its_length_limit(self):
        self.shot['no_previs'] = 'x'
        self.assertEqual(self.errors(), ['s01: no_previs is set but the shot is in the previs spec'])
        del self.shot['no_previs']
        shot = self.insert(no_previs='close insert', frames=24 * 31)
        self.assertEqual(self.errors(), ['s02: 31.0 s exceeds generation_profile.max_duration_s 30'])
        job = dict(PER_SHOT, shot='s02', quote=28, start_frame_sha256=sha(self.root / 'k.png'))
        self.state['generation_plan']['takes'].append({'mode': 'per_shot', 'shots': ['s02']})
        self.assertEqual(self.g.check_submission(self.state, job, self.root), ['job: take of 31.0 s exceeds generation_profile.max_duration_s 30'])
        for bad in (12.5, 12.0, None, 0, -1, True, '24'):
            shot['frames'] = bad
            expected = ['s02: frames must be a positive integer for a shot without previs']
            self.assertEqual(self.errors(), expected)
            self.assertEqual(self.g.check_submission(self.state, job, self.root), expected)

    def test_legacy_state_reports_without_raising(self):
        self.state = {'previs': {'spec_path': 'scene.json', 'approval': 'approved'},
                      'shots': [{'id': 's01', 'frames': 72, 'asset_bindings': []}], 'budget': {'cap': 200}}
        e = self.errors()
        for msg in ('story: approved story design or reference breakdown required', 's01: required_events missing',
                    's01: object slide has no role decision (map to a role or null)',
                    's01: approved start keyframe required', 'budget: retry_reserve must cover max_shot_quote',
                    'generation_profile: model, max_duration_s and duration_step_s are required'):
            self.assertIn(msg, e)

    def test_empty_state_reports_without_raising(self):
        self.state = {}
        e = self.errors()
        self.assertIn('story: approved story design or reference breakdown required', e)
        self.assertIn('previs: approval required', e)

    def test_ready_needs_the_recorded_generation_choice(self):
        del self.state['generation_plan']
        self.assertEqual(self.errors(), [PLAN_NEEDED])

    def test_plan_takes_are_well_formed(self):
        plan = self.state['generation_plan']
        for bad in ({'mode': 'fast', 'shots': ['s01']}, {'mode': 'per_shot'}, {'mode': 'per_shot', 'shots': [['s01']]}, 'per_shot'):
            plan['takes'] = [bad]
            self.assertEqual(self.errors(), ['generation_plan: each take needs a mode (per_shot, multi_cut or one_take) and its shots'], bad)
        for bad in ({'mode': 'per_shot', 'shots': ['s01', 's02']}, {'mode': 'multi_cut', 'shots': ['s01']}):
            plan['takes'] = [bad]
            self.assertEqual(self.errors(), ['generation_plan: per_shot takes one shot and multi_cut two or more'], bad)
        plan['takes'] = [{'mode': 'one_take', 'shots': ['s01', 's02']}, {'mode': 'per_shot', 'shots': ['s02']}]
        self.assertEqual(self.errors(), ['generation_plan: s02 is in two takes'])

    def test_story_change_detected(self):
        (self.root / 'story.json').write_text('{}')
        self.assertIn('story: file missing or changed since approval', self.errors())

    def test_story_core_fields_required(self):
        (self.root / 'story.json').write_text('{}')
        self.state['story']['sha256'] = sha(self.root / 'story.json')
        self.assertIn('story: target_action.action is required', self.errors())

    def story(self, **fields):
        data = dict({'target_action': {'action': 'save'}, 'setup': SETUP}, **fields)  # no purpose, no structure: a mood piece
        (self.root / 'story.json').write_text(json.dumps(data)); self.state['story']['sha256'] = sha(self.root / 'story.json')

    def look(self, **changes):
        look = json.loads(json.dumps(LOOK))
        for path, value in changes.items():
            *parents, leaf = path.split('__'); node = look
            for key in parents: node = node[key]
            node[leaf] = value
        self.story(version=2, setup=dict(SETUP, look=look))

    def test_story_without_purpose_or_structure_passes(self):
        self.story()
        self.assertEqual(self.errors(), [])

    def test_version_2_story_needs_a_look(self):
        self.story(version=2)
        self.assertEqual(self.errors(), ['story: setup.look is required'])
        self.look(camera__holder='drone')
        self.assertIn('story: setup.look.camera.holder must be one of: lead, companion, unseen', self.errors())

    def test_each_shot_names_a_view_the_look_lists(self):
        self.look()  # one 48-frame shot at 24 fps: 2.0 s, the look's average
        self.assertEqual(self.errors(), ['s01: view must be one of: selfie, pov, mirror, propped, insert, observer'])
        self.shot['view'] = 'pov'
        self.assertEqual(self.errors(), [])
        self.shot['view'] = 'observer'  # a camera nobody in the scene holds
        self.assertEqual(self.errors(), ['s01: view observer is not in setup.look.camera.views; give view_reason or change the look'])
        self.shot['view_reason'] = 'the stylist films one shot on her phone'
        self.assertEqual(self.errors(), [])

    def test_cut_rhythm_stays_within_30_percent_of_the_look(self):
        self.shot['view'] = 'pov'
        for average, ok in ((1.6, True), (2.8, True), (1.5, False), (4, False)):
            self.look(pace__avg_shot_s=average)
            expected = [] if ok else [f'pace: shots average 2.0 s, outside 30 % of setup.look.pace.avg_shot_s {average:g}']
            self.assertEqual(self.errors(), expected, average)

    def test_no_previs_shots_count_toward_the_rhythm(self):
        self.shot['view'] = 'pov'
        self.insert(no_previs='close insert', view='pov')['frames'] = 240  # 10 s: the average becomes 6 s
        self.look()
        self.assertEqual(self.errors(), ['pace: shots average 6.0 s, outside 30 % of setup.look.pace.avg_shot_s 2'])

    def test_story_without_a_look_asks_nothing_of_the_shots(self):
        self.assertNotIn('view', self.shot)  # version 1 stories and their projects keep passing
        self.assertEqual(self.errors(), [])

    def test_story_setup_required(self):
        data = json.loads((self.root / 'story.json').read_text()); data['setup']['tone'] = ' '
        (self.root / 'story.json').write_text(json.dumps(data)); self.state['story']['sha256'] = sha(self.root / 'story.json')
        self.assertIn('story: setup needs premise, tone, avoid, lead and setting', self.errors())

    def test_unresolved_asset_note_blocks(self):
        self.state['assets'][0]['review_notes'] = [{'note': 'masks read as face paint'}]
        self.assertIn('asset hero v001: unresolved review note', self.errors())

    def test_unresolved_keyframe_note_blocks(self):
        self.shot['keyframes'][0]['review_notes'] = [{'note': 'n', 'resolution': 'accepted', 'evidence': ''}]
        self.assertIn('s01: keyframe k.png: unresolved review note', self.errors())

    def test_resolved_notes_pass(self):
        self.state['assets'][0]['review_notes'] = [{'note': 'n', 'resolution': 'accepted', 'evidence': 'User: fine as is'}]
        self.shot['keyframes'][0]['review_notes'] = [{'note': 'n', 'resolution': 'fixed', 'evidence': 'v002'}]
        self.assertEqual(self.errors(), [])

    def test_malformed_notes_count_as_unresolved(self):
        self.state['assets'][0]['review_notes'] = 'later'
        self.assertIn('asset hero v001: unresolved review note', self.errors())

    def test_superseded_asset_notes_ignored(self):
        self.state['assets'].append({'role_id': 'hero', 'version': 'v000', 'sha256': 'old', 'approval': 'superseded',
                                     'review_notes': [{'note': 'n'}]})
        self.assertEqual(self.errors(), [])

    def test_asset_kind_required(self):
        self.state['assets'][0]['kind'] = 'hero'
        self.assertIn('asset hero v001: kind must be character, prop or set', self.errors())

    def test_prop_needs_origin_holder_exit(self):
        self.shot['props']['slide']['origin'] = ''
        self.assertIn('s01: prop slide needs origin, holder and exit', self.errors())

    def test_prop_needs_count(self):
        del self.shot['props']['slide']['count']
        self.assertIn('s01: prop slide needs count (how many exist in the whole take)', self.errors())

    def test_prop_needs_states(self):
        self.shot['props']['slide']['states'] = [{'t': 0}]
        self.assertIn('s01: prop slide needs states ({t, where} for each place it is held, from the first frame)', self.errors())

    def test_props_wrong_type_reported_not_raised(self):
        self.shot['props'] = ['slide']
        self.assertIn('s01: prop slide needs origin, holder and exit', self.errors())

    def test_character_needs_no_props_entry(self):
        self.assertNotIn('hero', self.shot['props'])
        self.assertEqual(self.errors(), [])

    def test_generation_profile_required(self):
        del self.state['generation_profile']
        self.assertIn('generation_profile: model, max_duration_s and duration_step_s are required', self.errors())

    def test_generation_profile_wrong_type_reported_not_raised(self):
        self.state['generation_profile'] = ['Seedance']
        self.assertIn('generation_profile: model, max_duration_s and duration_step_s are required', self.errors())

    def test_shot_longer_than_model_limit(self):
        self.state['generation_profile']['max_duration_s'] = 1.5
        self.assertIn('s01: 2.0 s exceeds generation_profile.max_duration_s 1.5', self.errors())

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
         'events': [{'t': 1.0, 'event': 'hero lands'}],
         'camera_evidence': [{'t': 0, 'subject_px': 100}, {'t': 1.0, 'subject_px': 60}]},
        {'id': 's02', 'start': 1.5, 'end': 3.5, 'camera': 'CU push in', 'action': 'hero waves',
         'camera_evidence': [{'t': 1.5, 'background_px': 40}, {'t': 3.0, 'background_px': 40}]}])
    state['reference'] = {'path': 'reference.json', 'sha256': sha(root / 'reference.json'), 'approval': 'approved'}
    return state


def write_reference(root, shots, rights='own', match='shot', upload_agreed=None, candidates=None, version=1, setup=SETUP):
    source = {'path': 'inputs/reference.mp4', 'sha256': 'abc', 'rights': rights, 'upload_agreed': upload_agreed}
    ref = {'version': version, 'source': {k: v for k, v in source.items() if v is not None}, 'setup': setup, 'shots': shots,
           'match': match, 'candidates': candidates}
    (root / 'reference.json').write_text(json.dumps({k: v for k, v in ref.items() if v is not None}))


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

    def rewrite(self, shots, **fields):
        write_reference(self.root, shots, **fields)
        self.state['reference']['sha256'] = sha(self.root / 'reference.json')

    def test_candidates_need_a_decision(self):
        self.rewrite(self.shots(), candidates=[{'t': 0.5, 'score': 0.2}])
        self.assertIn('reference: candidate cut at 0.5 s needs a decision', self.errors())
        self.rewrite(self.shots(), candidates=[{'t': 0.5, 'score': 0.2, 'decision': 'not a cut: flash'}])
        self.assertEqual(self.errors(), [])
        for bad in ('x', [3], [{'t': 'a'}]):
            self.rewrite(self.shots(), candidates=bad)
            self.assertIn('reference: candidates must be a list of {t, score, decision}', self.errors())

    def test_rights_and_match_are_required(self):
        for change, message in (({'rights': None}, 'reference: source.rights must be own or third_party'),
                                ({'rights': 'fair use'}, 'reference: source.rights must be own or third_party'),
                                ({'match': None}, 'reference: match must be format or shot'),
                                ({'match': 'loose'}, 'reference: match must be format or shot')):
            self.rewrite(self.shots(), **change)
            self.assertEqual(self.errors(), [message], change)

    def test_shot_without_previs_still_follows_the_reference_cut(self):
        spec = json.loads((self.root / 'scene.json').read_text()); spec['shots'] = spec['shots'][:1]
        (self.root / 'scene.json').write_text(json.dumps(spec))
        self.assertEqual(self.errors(), ['reference s02: shot not in previs spec'])
        self.state['shots'].append(dict(self.state['shots'][0], id='s02', object_roles={}, props={}, asset_bindings=[],
                                        frames=48, no_previs='POV detail'))
        self.assertEqual(self.errors(), [])
        self.state['shots'][1]['frames'] = 40
        self.assertEqual(self.errors(), ['s02: frames 40 differ from reference timing 48'])

    def test_format_match_needs_a_plan_per_shot(self):
        self.rewrite(self.shots(), match='format')
        self.assertEqual(self.errors(), [f'reference {s}: plan needs source (generated, footage or reuse) and what' for s in ('s01', 's02')])
        for bad in ('footage', ['x'], {'source': 'stock', 'what': 'x'}, {'source': 'footage'}):
            self.rewrite([dict(s, plan=bad) for s in self.shots()], match='format')
            self.assertEqual(len(self.errors()), 2, bad)
        self.rewrite([dict(s, plan={'source': 'generated', 'what': 'new shot'}) for s in self.shots()], match='format')
        self.assertEqual(self.errors(), [])
        self.rewrite(self.shots())                                   # match: shot asks for no plan
        self.assertEqual(self.errors(), [])

    def test_footage_and_reused_shots_need_no_previs(self):
        spec = json.loads((self.root / 'scene.json').read_text()); spec['shots'] = spec['shots'][:1]
        (self.root / 'scene.json').write_text(json.dumps(spec))
        shots = self.shots(); shots[0]['plan'] = {'source': 'generated', 'what': 'hero slides in'}
        for source in ('footage', 'reuse'):
            shots[1]['plan'] = {'source': source, 'what': 'sign clip 0468'}
            self.rewrite(shots, match='format'); self.assertEqual(self.errors(), [], source)
        shots[1]['plan'] = {'source': 'generated', 'what': 'x'}
        self.rewrite(shots, match='format'); self.assertEqual(self.errors(), ['reference s02: shot not in previs spec'])

    def test_format_match_needs_no_camera_evidence(self):
        PLAN = {'source': 'generated', 'what': 'x'}
        bare = [dict(s, camera_evidence=[], plan=PLAN) for s in self.shots()]
        self.rewrite(bare)                                   # match: shot
        self.assertEqual(self.errors(), [f'reference {s}: camera_evidence needs 2+ samples with t and subject_px or background_px'
                                         for s in ('s01', 's02')])
        self.rewrite(bare, match='format')
        self.assertEqual(self.errors(), [])
        self.rewrite([dict(s, camera_evidence=[{'t': 'x'}], plan=PLAN) for s in self.shots()], match='format')   # given, so it must be sound
        self.assertEqual(len(self.errors()), 2)

    def test_third_party_footage_as_job_input_needs_a_recorded_agreement(self):
        base = dict(PER_SHOT, shot='s01', quote=28, start_frame_sha256=sha(self.root / 'k.png'))
        job = dict(base, inputs=[{'path': './inputs/reference.mp4', 'slot': 'video 1'}, {'path': 'previs/s01.mp4'}])
        self.assertEqual(self.g.check_submission(self.state, job, self.root), [])            # own footage
        self.rewrite(self.shots(), rights='third_party')
        self.assertEqual(self.g.check_submission(self.state, job, self.root),
                         ['s01: job input ./inputs/reference.mp4 is third-party reference footage; record source.upload_agreed first'])
        for bad in ('x', [3], [{'path': 7}]):
            self.assertEqual(self.g.check_submission(self.state, dict(base, inputs=bad), self.root), [])
        self.rewrite([dict(s, clip=f'reference/v001/{s["id"]}.mp4', stills=[f'reference/v001/{s["id"]}-start.png'])
                      for s in self.shots()], rights='third_party')
        for path in ('reference/v001/../v001/s01.mp4', 'reference/v001/s02-start.png'):
            errors = self.g.check_submission(self.state, dict(base, inputs=[{'path': path}]), self.root)
            self.assertEqual(errors, [f's01: job input {path} is third-party reference footage; record source.upload_agreed first'])
        absolute = str(self.root / 'inputs/reference.mp4')
        self.assertEqual(self.g.check_submission(self.state, dict(base, inputs=[{'path': absolute}]), self.root),
                         [f's01: job input {absolute} is third-party reference footage; record source.upload_agreed first'])
        self.rewrite(self.shots(), rights='third_party', upload_agreed='User: "ok to upload the reel as motion reference"')
        self.assertEqual(self.g.check_submission(self.state, job, self.root), [])

    def shots(self):
        return json.loads((self.root / 'reference.json').read_text())['shots']

    def test_approved_reference_replaces_story(self):
        self.assertEqual(self.errors(), [])

    def test_submission_accepts_reference(self):
        job = dict(PER_SHOT, shot='s01', quote=28, start_frame_sha256=sha(self.root / 'k.png'))
        self.assertEqual(self.g.check_submission(self.state, job, self.root), [])

    def test_version_2_reference_carries_the_look_it_was_measured_for(self):
        write_reference(self.root, self.shots(), version=2); self.state['reference']['sha256'] = sha(self.root / 'reference.json')
        self.assertEqual(self.errors(), ['reference: setup.look is required'])
        look = dict(LOOK, pace={'avg_shot_s': 1.75, 'cuts': 'hard'})  # the two shots are 1.5 s and 2 s
        write_reference(self.root, self.shots(), version=2, setup=dict(SETUP, look=look))
        self.state['reference']['sha256'] = sha(self.root / 'reference.json')
        self.assertEqual(self.errors(), ['s01: view must be one of: selfie, pov, mirror, propped, insert, observer'])
        self.state['shots'][0]['view'] = 'selfie'
        self.assertEqual(self.errors(), [])

    def test_reference_setup_required(self):
        ref = json.loads((self.root / 'reference.json').read_text()); ref['setup'] = ['funny']
        (self.root / 'reference.json').write_text(json.dumps(ref)); self.state['reference']['sha256'] = sha(self.root / 'reference.json')
        self.assertIn('reference: setup needs premise, tone, avoid, lead and setting', self.errors())

    EVIDENCE = 'reference s01: camera_evidence needs 2+ samples with t and subject_px or background_px'

    def test_camera_evidence_required(self):
        shots = self.shots(); shots[0]['camera_evidence'] = [{'t': 0, 'subject_px': 100}]; self.rewrite(shots)
        self.assertIn(self.EVIDENCE, self.errors())

    def test_camera_evidence_wrong_type_reported_not_raised(self):
        shots = self.shots(); shots[0]['camera_evidence'] = [{'t': 'a'}, 'x']; self.rewrite(shots)
        self.assertIn(self.EVIDENCE, self.errors())

    def test_split_take_that_fits_must_merge(self):
        shots = self.shots(); shots[1].update(continues_previous=True, split_reason='web limit'); self.rewrite(shots)
        self.assertIn('reference s01: take of 3.5 s fits max_duration_s 30; merge the split shots', self.errors())

    def test_split_take_over_limit_passes_with_reason(self):
        self.state['generation_profile']['max_duration_s'] = 3
        shots = self.shots(); shots[1].update(continues_previous=True, split_reason='3.5 s take, 3 s limit'); self.rewrite(shots)
        self.assertEqual(self.errors(), [])

    def test_split_needs_reason(self):
        self.state['generation_profile']['max_duration_s'] = 3
        shots = self.shots(); shots[1]['continues_previous'] = True; self.rewrite(shots)
        self.assertIn('reference s02: split_reason is required when a shot continues the previous one', self.errors())

    def test_split_take_cannot_be_checked_without_a_limit(self):
        shots = self.shots(); shots[1].update(continues_previous=True, split_reason='web limit')
        ref = {'version': 1, 'source': {'path': 'a', 'sha256': 'b', 'rights': 'own'}, 'match': 'shot', 'setup': SETUP, 'shots': shots}
        self.assertEqual(self.g.check_reference(ref),
                         ['reference: a split take needs --max-duration (generation_profile.max_duration_s) to be checked'])

    def test_first_shot_cannot_continue(self):
        shots = self.shots(); shots[0]['continues_previous'] = True; self.rewrite(shots)
        self.assertIn('reference s01: continues_previous on the first shot', self.errors())

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
        shots[1]['camera_evidence'][0]['t'] = 1.6  # the fixture sample at 1.5 s now falls before the moved cut
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
                                 'camera_evidence': [{'t': 3.5, 'subject_px': 20}, {'t': 3.9, 'subject_px': 20}],
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
        self.job = dict(PER_SHOT, shot='s01', quote=28, start_frame_sha256=sha(self.root / 'k.png'))

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self):
        return self.g.check_submission(self.state, self.job, self.root)

    def test_submission_within_budget_passes(self):
        self.assertEqual(self.errors(), [])

    def test_job_says_how_it_is_generated(self):
        del self.job['generation_mode']
        self.assertEqual(self.errors(), ['job: generation_mode required (per_shot, multi_cut or one_take)'])

    def test_job_follows_the_recorded_choice(self):
        self.state['generation_plan']['takes'] = [{'mode': 'one_take', 'shots': ['s01']}]  # the user chose a one-take
        self.assertEqual(self.errors(), ['job: per_shot of s01 is not a take in generation_plan'])
        self.job['retry_of'] = 'j0'  # a pickup may redo part of its take another way
        self.assertEqual(self.errors(), [])
        self.state['generation_plan']['takes'] = [{'mode': 'one_take', 'shots': ['s09']}]
        self.assertEqual(self.errors(), ['job: per_shot of s01 is not a take in generation_plan'])

    def test_choice_is_recorded_with_the_users_words(self):
        take = {'mode': 'per_shot', 'shots': ['s01']}
        for bad in ({}, {'takes': [take]}, {'takes': [take], 'evidence': ' '}, {'takes': [], 'evidence': 'ok'}, 'per_shot'):
            self.state['generation_plan'] = bad
            self.assertEqual(self.errors(), [PLAN_NEEDED], bad)

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

    def test_submission_blocked_by_unresolved_note(self):
        self.state['assets'][0]['review_notes'] = [{'note': 'n'}]
        self.assertIn('asset hero v001: unresolved review note', self.errors())

    def test_manual_zero_quote_job_ignores_attempt_limit(self):
        self.budget.update(attempts_used=5, max_shot_quote=0, retry_reserve=0)
        self.job.update(quote=0, route='manual')
        self.assertEqual(self.errors(), [])

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




class GateContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.g = load('gate')
        self.state = ready_project(self.root)
        (self.root / 'scene.json').write_text(json.dumps({'fps': 24, 'shots': [
            {'id': s, 'frames': 48, 'objects': [{'id': 'hero'}, {'id': 'slide'}, {'id': 'ground'}]} for s in ('s01', 's02')]}))
        (self.root / 'k2.png').write_bytes(b'k2')
        s02 = json.loads(json.dumps(self.state['shots'][0])); s02['id'] = 's02'
        s02['keyframes'] = [{'kind': 'start', 'path': 'k2.png', 'sha256': sha(self.root / 'k2.png'), 'approval': 'approved'}]
        self.state['shots'].append(s02)
        self.review = lambda role: {'role_id': role, 'approval': 'approved',
                                    'keyframe_sha256': {'s01': sha(self.root / 'k.png'), 's02': sha(self.root / 'k2.png')}}

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self):
        return self.g.check_project(self.state, self.root)

    def test_shared_role_needs_review(self):
        e = self.errors()
        for role in ('hero', 'slide'):
            self.assertIn(f'continuity: role {role} needs an approved cross-shot keyframe review', e)

    def test_matching_review_passes(self):
        self.state['continuity'] = [self.review('hero'), self.review('slide')]
        self.assertEqual(self.errors(), [])

    def test_review_stale_after_keyframe_change(self):
        self.state['continuity'] = [self.review('hero'), self.review('slide')]
        (self.root / 'k3.png').write_bytes(b'k3')
        self.state['shots'][1]['keyframes'] = [{'kind': 'start', 'path': 'k3.png', 'sha256': sha(self.root / 'k3.png'), 'approval': 'approved'}]
        self.assertIn('continuity: role hero review is stale (keyframes changed)', self.errors())

    def test_review_missing_shot_is_stale(self):
        hero = self.review('hero'); del hero['keyframe_sha256']['s02']
        self.state['continuity'] = [hero, self.review('slide')]
        self.assertIn('continuity: role hero review is stale (keyframes changed)', self.errors())

    def test_unapproved_review_rejected(self):
        hero = self.review('hero'); hero['approval'] = 'pending'
        self.state['continuity'] = [hero, self.review('slide')]
        self.assertIn('continuity: role hero needs an approved cross-shot keyframe review', self.errors())

    def test_single_shot_role_not_checked(self):
        self.state['shots'][1]['object_roles'] = {'hero': 'hero', 'slide': None, 'ground': None}
        self.state['continuity'] = [self.review('hero')]
        self.assertEqual([e for e in self.errors() if e.startswith('continuity')], [])

    def test_unapproved_keyframe_cannot_be_reviewed(self):
        self.state['shots'][1]['keyframes'][0]['approval'] = 'pending'
        hero = self.review('hero'); hero['keyframe_sha256']['s02'] = None
        slide = self.review('slide'); slide['keyframe_sha256']['s02'] = None
        self.state['continuity'] = [hero, slide]
        msg = 'continuity: role hero cannot be reviewed until every shot using it has an approved keyframe (s02)'
        self.assertIn(msg, self.errors())
        job = dict(PER_SHOT, shot='s01', quote=28, start_frame_sha256=sha(self.root / 'k.png'))
        self.assertIn(msg, self.g.check_submission(self.state, job, self.root))

    def test_submit_checks_roles_of_its_shot(self):
        job = dict(PER_SHOT, shot='s01', quote=28, start_frame_sha256=sha(self.root / 'k.png'))
        e = self.g.check_submission(self.state, job, self.root)
        self.assertIn('continuity: role hero needs an approved cross-shot keyframe review', e)



class GateSequenceJobTests(unittest.TestCase):
    """A sequence take covers consecutive shots: submit checks every covered shot, the start frame is the first shot's."""
    tearDown = GateContinuityTests.tearDown

    def setUp(self):
        GateContinuityTests.setUp(self)  # same two-shot project, without inheriting its tests
        self.state['continuity'] = [self.review('hero'), self.review('slide')]
        self.job = {'shot': 's01', 'shots': ['s01', 's02'], 'quote': 28, 'start_frame_sha256': sha(self.root / 'k.png'),
                    'generation_mode': 'one_take', 'duration_s': 4}
        self.state['generation_plan'] = {'takes': [{'mode': 'one_take', 'shots': ['s01', 's02']}], 'evidence': 'user: one take'}

    def sub(self):
        return self.g.check_submission(self.state, self.job, self.root)

    def test_sequence_job_passes_when_all_shots_ready(self):
        self.assertEqual(self.sub(), [])

    def test_sequence_job_checks_every_covered_shot(self):
        self.state['shots'][1]['required_events'] = []
        self.assertIn('s02: required_events missing', self.sub())

    def test_sequence_take_must_fit_model_limit(self):
        self.state['generation_profile']['max_duration_s'] = 3
        self.assertIn('job: take of 4.0 s exceeds generation_profile.max_duration_s 3', self.sub())

    def test_sequence_job_unknown_shot(self):
        self.job['shots'] = ['s01', 's09']
        self.assertIn('s09: shot not found in state', self.sub())

    def test_malformed_shot_id_reported_not_raised(self):
        self.state['shots'].append({'id': ['s03']})
        self.assertEqual(self.sub(), [])

    def test_sequence_must_begin_with_shot(self):
        self.job['shots'] = ['s02', 's01']
        self.assertIn('job: shots must begin with shot', self.sub())

if __name__ == '__main__':
    unittest.main()
