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

if __name__ == '__main__': unittest.main()
