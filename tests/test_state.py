import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from test_workflow import module, SCRIPTS

class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.m = module('state'); self.path = self.root / 'state.json'; self.lockdir = self.root / 'submission.lock'
        self.path.write_text(json.dumps({'budget': {'cap': 20, 'settled': 0, 'reserved': 0, 'attempts_used': 0},
            'assets': [{'role_id': 'hero', 'version': 'v001', 'approval': 'pending'}], 'jobs': []}))

    def tearDown(self): self.tmp.cleanup()
    def state(self): return json.loads(self.path.read_text())
    def paid(self):
        self.m.lock(self.path, 'host', 'images'); self.m.reserve(self.path, {'request_id': 'j1', 'route': 'mcp', 'quote': 1})

    def test_second_lock_refused(self):
        self.m.lock(self.path, 'a', 'p')
        with self.assertRaisesRegex(ValueError, 'lock exists'): self.m.lock(self.path, 'b', 'p')

    def test_reserve_needs_lock_and_unique_id(self):
        with self.assertRaisesRegex(ValueError, 'lock required'): self.m.reserve(self.path, {'request_id': 'j1', 'quote': 1})
        self.paid()
        with self.assertRaisesRegex(ValueError, 'request_id already exists'): self.m.reserve(self.path, {'request_id': 'j1', 'quote': 1})

    def test_paid_job_lifecycle(self):
        self.paid(); self.assertEqual(self.state()['budget']['reserved'], 1)
        self.m.submit(self.path, 'j1', 'prov-1'); self.assertTrue(self.lockdir.is_dir())
        (self.root / 'out.png').write_bytes(b'x'); self.m.settle(self.path, 'j1', 1, ['out.png'])
        s = self.state(); job = s['jobs'][0]
        self.assertEqual((s['budget']['settled'], s['budget']['reserved'], s['budget']['attempts_used']), (1, 0, 1))
        self.assertEqual((job['status'], job['actual_charge'], job['provider_job_id']), ('succeeded', 1, 'prov-1'))
        self.assertEqual(job['outputs'], [{'path': 'out.png', 'sha256': hashlib.sha256(b'x').hexdigest()}])
        self.assertFalse(self.lockdir.exists())

    def test_manual_take_counts_separately_and_frees_lock_at_handoff(self):
        self.m.lock(self.path, 'host', 'video'); self.m.reserve(self.path, {'request_id': 'v1', 'route': 'manual', 'quote': 0})
        self.m.submit(self.path, 'v1')
        s = self.state()
        self.assertEqual((s['jobs'][0]['status'], s['budget']['attempts_used'], s['budget']['manual_takes']), ('handed_off', 0, 1))
        self.assertFalse(self.lockdir.exists())
        self.m.settle(self.path, 'v1', 0)             # no lock needed to record the returned take
        self.assertEqual(self.state()['jobs'][0]['status'], 'succeeded')

    def test_settle_twice_refused_without_double_count(self):
        self.paid(); self.m.submit(self.path, 'j1'); self.m.settle(self.path, 'j1', 1)
        with self.assertRaisesRegex(ValueError, 'job j1 is succeeded; already settled'): self.m.settle(self.path, 'j1', 1)
        self.assertEqual(self.state()['budget']['settled'], 1)

    def test_unknown_job_keeps_lock_and_can_be_settled(self):
        self.paid(); self.m.submit(self.path, 'j1')
        s = self.state(); s['jobs'][0]['status'] = 'unknown'; self.path.write_text(json.dumps(s))
        with self.assertRaisesRegex(ValueError, 'lock in use by j1'): self.m.unlock(self.path)
        self.m.settle(self.path, 'j1', 1)
        s = self.state()
        self.assertEqual((s['jobs'][0]['status'], s['budget']['settled'], s['budget']['reserved']), ('succeeded', 1, 0))
        self.assertFalse(self.lockdir.exists())

    def test_settle_without_submit_still_counts_the_attempt(self):
        self.paid(); self.m.settle(self.path, 'j1', 1)
        self.assertEqual(self.state()['budget']['attempts_used'], 1)

    def test_cancelled_reservation_counts_no_attempt_and_frees_lock(self):
        self.paid(); self.m.settle(self.path, 'j1', 0, status='cancelled')
        s = self.state()
        self.assertEqual((s['budget']['attempts_used'], s['budget']['reserved']), (0, 0))
        self.assertFalse(self.lockdir.exists())

    def test_malformed_existing_job_does_not_crash_after_write(self):
        s = self.state(); s['jobs'].append({'id': 'old', 'status': 'running'}); self.path.write_text(json.dumps(s))
        self.paid(); self.m.submit(self.path, 'j1')
        self.assertEqual(self.state()['jobs'][1]['status'], 'running')
        self.assertTrue(self.lockdir.is_dir())  # the nameless running job still holds it

    def test_settling_a_returned_manual_take_leaves_another_lock_alone(self):
        self.m.lock(self.path, 'host', 'video'); self.m.reserve(self.path, {'request_id': 'v1', 'route': 'manual', 'quote': 0})
        self.m.submit(self.path, 'v1')
        self.m.lock(self.path, 'host-b', 'images')  # taken while v1 is out with the user
        self.m.settle(self.path, 'v1', 0)
        self.assertTrue(self.lockdir.is_dir())

    def test_cli_reports_unexpected_errors_in_one_line(self):
        done = subprocess.run([sys.executable, str(SCRIPTS / 'state.py'), 'unlock', str(self.root / 'missing.json')],
                              capture_output=True, text=True)
        self.assertEqual((done.returncode, len(done.stdout.strip().splitlines()), done.stderr), (1, 1, ''))

    def test_unlock_refused_while_job_active(self):
        self.paid()
        with self.assertRaisesRegex(ValueError, 'lock in use by j1'): self.m.unlock(self.path)

    def test_approve_asset_records_evidence(self):
        self.m.approve(self.path, 'asset', 'hero@v001', 'User: ok')
        asset = self.state()['assets'][0]
        self.assertEqual((asset['approval'], asset['evidence']), ('approved', 'User: ok')); self.assertTrue(asset['approved_at'])

    def test_approve_refuses_unresolved_note_and_unknown_record(self):
        s = self.state(); s['assets'][0]['review_notes'] = [{'note': 'n'}]; self.path.write_text(json.dumps(s))
        with self.assertRaisesRegex(ValueError, 'unresolved review note'): self.m.approve(self.path, 'asset', 'hero@v001', 'User: ok')
        with self.assertRaisesRegex(ValueError, 'unknown record'): self.m.approve(self.path, 'asset', 'ghost@v001', 'User: ok')

    def test_cli_help_and_error_exit_code(self):
        for sub in ('lock', 'unlock', 'reserve', 'submit', 'settle', 'approve'):
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPTS / 'state.py'), sub, '--help'], capture_output=True).returncode, 0)
        job = self.root / 'job.json'; job.write_text(json.dumps({'request_id': 'j1', 'quote': 1}))
        done = subprocess.run([sys.executable, str(SCRIPTS / 'state.py'), 'reserve', str(self.path), str(job)], capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stdout.strip()), (1, 'lock required'))
        done = subprocess.run([sys.executable, str(SCRIPTS / 'state.py'), 'unlock', str(self.path)], capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, 'OK'))   # no lock, nothing active: nothing to do

    def test_init_creates_and_refuses_overwrite(self):
        new = self.root / 'p' / 'state.json'; new.parent.mkdir()
        self.m.init(new, 'demo')
        self.assertEqual(json.loads(new.read_text())['project_id'], 'demo')
        with self.assertRaisesRegex(ValueError, 'state exists'): self.m.init(new, 'demo')

    def test_init_creates_the_project_folder(self):
        new = self.root / 'projects' / 'demo' / 'state.json'  # a new production starts in a folder of its own
        self.m.init(new, 'demo')
        self.assertEqual(json.loads(new.read_text())['project_id'], 'demo')

    def test_put_generation_plan(self):
        plan = {'takes': [{'mode': 'multi_cut', 'shots': ['s01', 's02']}], 'evidence': 'user: multi-cut'}
        self.m.put(self.path, 'generation_plan', plan)
        self.assertEqual(json.loads(self.path.read_text())['generation_plan'], plan)

    def test_put_section_shot_and_pending_record(self):
        self.m.put(self.path, 'generation_profile', {'model': 'm', 'max_duration_s': 30})
        self.m.put(self.path, 'shot', {'id': 's01', 'frames': 48}); self.m.put(self.path, 'shot', {'id': 's01', 'props': {}})
        (self.root / 'ref.json').write_text('{}')
        self.m.put(self.path, 'reference', {'path': 'ref.json', 'approval': 'approved'})
        s = self.state()
        self.assertEqual(s['generation_profile']['model'], 'm')
        self.assertEqual(s['shots'], [{'id': 's01', 'frames': 48, 'props': {}}])
        self.assertEqual((s['reference']['approval'], s['reference']['sha256']), ('pending', hashlib.sha256(b'{}').hexdigest()))

    def test_put_refuses_a_record_without_its_path(self):
        before = self.path.read_bytes()
        for section, data, message in (('reference', {'version': 1, 'shots': []}, 'reference: path required'),
                                       ('story', {'purpose': 'p'}, 'story: path required'), ('previs', {'path': 'previs/v001'}, 'previs: spec_path required'),
                                       ('reference', {'path': 7}, 'reference: path required')):
            with self.assertRaisesRegex(ValueError, message): self.m.put(self.path, section, data)
            self.assertEqual(self.path.read_bytes(), before)
        self.m.put(self.path, 'previs', {'path': 'previs/v001', 'spec_path': 'scene.json'})
        self.assertEqual(self.state()['previs']['approval'], 'pending')

    def test_put_budget_keeps_counters(self):
        self.paid(); self.m.put(self.path, 'budget', {'cap': 60, 'settled': 99, 'reserved': 99, 'attempts_used': 99})
        b = self.state()['budget']
        self.assertEqual((b['cap'], b['settled'], b['reserved'], b['attempts_used']), (60, 0, 1, 0))

    def test_charge_corrects_a_settled_job(self):
        self.paid(); self.m.submit(self.path, 'j1'); self.m.settle(self.path, 'j1', 3.125)
        self.m.charge(self.path, 'j1', 2, 'provider transactions 2026-11-18')
        s = self.state()
        self.assertEqual((s['budget']['settled'], s['jobs'][0]['actual_charge'], s['jobs'][0]['charge_evidence']),
                         (2, 2, 'provider transactions 2026-11-18'))
        with self.assertRaisesRegex(ValueError, 'not settled'):
            self.m.lock(self.path, 'h', 'p'); self.m.reserve(self.path, {'request_id': 'j2', 'quote': 1}); self.m.charge(self.path, 'j2', 1, 'x')

if __name__ == '__main__': unittest.main()


class RecordTests(unittest.TestCase):
    """Asset, keyframe and review-note records written by state.py instead of by hand."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.m = module('state'); self.path = self.root / 'state.json'
        for name in ('hero-v001.png', 'hero-v002.png', 'k1.png', 'k2.png', 'mid.png'): (self.root / name).write_bytes(name.encode())
        self.path.write_text(json.dumps({'assets': [], 'shots': [{'id': 's01', 'object_roles': {'hero': 'hero', 'floor': None}}]}))

    def tearDown(self): self.tmp.cleanup()
    def state(self): return json.loads(self.path.read_text())
    def sha(self, name): return hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def test_asset_record_is_pending_with_hash(self):
        self.m.asset(self.path, 'hero@v001', 'character', 'hero-v001.png')
        a = self.state()['assets'][0]
        self.assertEqual((a['role_id'], a['version'], a['kind'], a['approval'], a['sha256'], a['working_path']),
                         ('hero', 'v001', 'character', 'pending', self.sha('hero-v001.png'), 'hero-v001.png'))

    def test_asset_records_where_footage_came_from(self):
        self.m.asset(self.path, 'hero@v001', 'character', 'hero-v001.png')
        self.m.asset(self.path, 'room@v001', 'set', 'hero-v001.png', source='footage', origin='IMG_0549 0.5 s, top 30 %')
        plain, room = self.state()['assets'][-2:]
        self.assertEqual((plain['source'], 'origin' in plain), ('generated', False))
        self.assertEqual((room['source'], room['origin']), ('footage', 'IMG_0549 0.5 s, top 30 %'))
        with self.assertRaisesRegex(ValueError, 'source must be generated, existing or footage'):
            self.m.asset(self.path, 'x@v001', 'set', 'hero-v001.png', source='stock')

    def test_asset_rejects_bad_kind_missing_file_and_duplicate(self):
        with self.assertRaisesRegex(ValueError, 'kind'): self.m.asset(self.path, 'hero@v001', 'person', 'hero-v001.png')
        with self.assertRaisesRegex(ValueError, 'not found'): self.m.asset(self.path, 'hero@v001', 'character', 'gone.png')
        self.m.asset(self.path, 'hero@v001', 'character', 'hero-v001.png')
        with self.assertRaisesRegex(ValueError, 'exists'): self.m.asset(self.path, 'hero@v001', 'character', 'hero-v001.png')

    def test_approving_a_new_version_supersedes_the_old_one(self):
        for v in ('v001', 'v002'):
            self.m.asset(self.path, f'hero@{v}', 'character', f'hero-{v}.png'); self.m.approve(self.path, 'asset', f'hero@{v}', 'ok')
        self.assertEqual([a['approval'] for a in self.state()['assets']], ['superseded', 'approved'])

    def test_keyframe_record_and_start_supersede(self):
        self.m.keyframe(self.path, 's01', 'k1.png', 'start', 1); self.m.approve(self.path, 'keyframe', 'k1.png', 'ok')
        self.m.keyframe(self.path, 's01', 'mid.png', 'reference', 120); self.m.approve(self.path, 'keyframe', 'mid.png', 'ok')
        self.m.keyframe(self.path, 's01', 'k2.png', 'start', 1); self.m.approve(self.path, 'keyframe', 'k2.png', 'ok')
        keys = {k['path']: k for k in self.state()['shots'][0]['keyframes']}
        self.assertEqual((keys['k1.png']['approval'], keys['mid.png']['approval'], keys['k2.png']['approval']),
                         ('superseded', 'approved', 'approved'))
        self.assertEqual((keys['mid.png']['previs_frame'], keys['k2.png']['sha256']), (120, self.sha('k2.png')))

    def test_keyframe_rejects_unknown_shot_and_kind(self):
        with self.assertRaisesRegex(ValueError, 'unknown shot'): self.m.keyframe(self.path, 's09', 'k1.png', 'start', 1)
        with self.assertRaisesRegex(ValueError, 'kind'): self.m.keyframe(self.path, 's01', 'k1.png', 'middle', 1)

    def test_note_blocks_approval_until_resolved(self):
        self.m.asset(self.path, 'hero@v001', 'character', 'hero-v001.png')
        self.m.note(self.path, 'asset', 'hero@v001', note='cap is on')
        with self.assertRaisesRegex(ValueError, 'unresolved'): self.m.approve(self.path, 'asset', 'hero@v001', 'ok')
        self.m.note(self.path, 'asset', 'hero@v001', resolve='accepted', evidence='User: "fine"')
        self.m.approve(self.path, 'asset', 'hero@v001', 'ok')
        self.assertEqual(self.state()['assets'][0]['review_notes'], [{'note': 'cap is on', 'resolution': 'accepted', 'evidence': 'User: "fine"'}])

    def test_note_needs_text_or_a_resolution_with_evidence(self):
        self.m.asset(self.path, 'hero@v001', 'character', 'hero-v001.png')
        with self.assertRaisesRegex(ValueError, 'note'): self.m.note(self.path, 'asset', 'hero@v001')
        with self.assertRaisesRegex(ValueError, 'evidence'): self.m.note(self.path, 'asset', 'hero@v001', resolve='fixed')

    def test_bind_ties_approved_assets_to_shots_by_role(self):
        self.m.asset(self.path, 'hero@v001', 'character', 'hero-v001.png'); self.m.approve(self.path, 'asset', 'hero@v001', 'ok')
        self.m.bind(self.path)
        self.assertEqual(self.state()['shots'][0]['asset_bindings'],
                         [{'role_id': 'hero', 'version': 'v001', 'sha256': self.sha('hero-v001.png')}])

    def test_bind_names_roles_without_an_approved_asset(self):
        with self.assertRaisesRegex(ValueError, 'hero'): self.m.bind(self.path)
