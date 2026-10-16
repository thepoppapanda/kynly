import concurrent.futures
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import job_queue as queue


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def submit(self, key='first', task='tests', timeout=30):
        return queue.submit(self.root, task, timeout, key)

    def test_persists_across_processes(self):
        job = self.submit()
        output = subprocess.check_output([sys.executable, queue.__file__, '--data-dir', self.root, 'show', job['job_id']], text=True)
        self.assertIn(job['job_id'], output)
        self.assertEqual(queue.inspect(self.root, job['job_id'])['status'], 'queued')

    def test_duplicate_is_same_job(self):
        self.assertEqual(self.submit()['job_id'], self.submit()['job_id'])
        self.assertEqual(len(queue.inspect(self.root)), 1)

    def test_conflicting_duplicate_rejected(self):
        self.submit()
        with self.assertRaises(ValueError):
            self.submit(task='probe-failure')
        with self.assertRaises(ValueError):
            self.submit(timeout=60)

    def test_concurrent_duplicate_submissions(self):
        self.submit('initialize')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            jobs = list(pool.map(lambda _: self.submit('shared'), range(16)))
        self.assertEqual(len({job['job_id'] for job in jobs}), 1)

    def test_cancel_persists_and_does_not_resubmit(self):
        job = self.submit()
        result = queue.cancel(self.root, job['job_id'])
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(queue.cancel(self.root, job['job_id'])['finished_at'], result['finished_at'])
        self.assertEqual(self.submit()['status'], 'cancelled')

    def test_unknown_job_and_invalid_parameters(self):
        for operation in (queue.inspect, queue.cancel):
            with self.assertRaises(ValueError):
                operation(self.root, 'missing')
        for timeout in (0, -1, 3601, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.submit(timeout=timeout)
        with self.assertRaises(ValueError):
            self.submit(task='shell')

    def test_listing_order_and_limit(self):
        first = self.submit('one')
        second = self.submit('two')
        self.assertEqual([j['job_id'] for j in queue.inspect(self.root)], [second['job_id'], first['job_id']])
        self.assertEqual(len(queue.inspect(self.root, limit=1)), 1)


class DispatchTests(unittest.TestCase):
    setUp = QueueTests.setUp
    submit = QueueTests.submit
    def receipt(self, args, status='passed', code=0, cleanup=0):
        import json
        directory = Path(args.data_dir) / args.job_id
        directory.mkdir(parents=True)
        (directory / 'result.json').write_text(json.dumps({
            'job_id': args.job_id, 'status': status, 'exit_code': code,
            'finished_at': queue.now(), 'cleanup': {'exit_code': cleanup}}))

    def test_fifo_and_failure_continues(self):
        first = self.submit('one')
        second = self.submit('two', task='probe-failure')
        seen = []
        def execute(args):
            seen.append(args.job_id)
            self.receipt(args, 'failed' if args.task == 'probe-failure' else 'passed',
                         7 if args.task == 'probe-failure' else 0)
        self.assertEqual(queue.drain(self.root, execute), [first['job_id'], second['job_id']])
        self.assertEqual(seen, [first['job_id'], second['job_id']])
        self.assertEqual(queue.inspect(self.root, second['job_id'])['exit_code'], 7)
        self.assertEqual(queue.drain(self.root, execute), [])

    def test_cancelled_job_is_skipped(self):
        job = self.submit()
        queue.cancel(self.root, job['job_id'])
        self.assertEqual(queue.drain(self.root, lambda _: self.fail('Executed cancelled job')), [])

    def test_crash_blocks_further_dispatch(self):
        first = self.submit('one')
        second = self.submit('two')
        def crash(args):
            raise RuntimeError('simulated runner crash')
        with self.assertRaises(RuntimeError):
            queue.drain(self.root, crash)
        with self.assertRaises(RuntimeError):
            queue.drain(self.root, lambda _: self.fail('Started after crash'))
        self.assertEqual(queue.inspect(self.root, first['job_id'])['status'], 'running')
        self.assertEqual(queue.inspect(self.root, second['job_id'])['status'], 'queued')

    def test_cleanup_failure_stops_queue(self):
        self.submit('one')
        second = self.submit('two')
        with self.assertRaises(RuntimeError):
            queue.drain(self.root, lambda args: self.receipt(args, cleanup=1))
        self.assertEqual(queue.inspect(self.root, second['job_id'])['status'], 'queued')

    def test_worker_lock_rejects_another_worker(self):
        lock = Path(queue.__file__).resolve().parents[1] / '.kynly' / 'queue-worker.lock'
        with queue.workspace_lock(lock):
            with self.assertRaises(RuntimeError):
                queue.drain(self.root, lambda _: None)


class RecoveryTests(unittest.TestCase):
    setUp = QueueTests.setUp
    submit = QueueTests.submit
    receipt = DispatchTests.receipt

    def stranded(self):
        job = self.submit()
        with queue.database(self.root) as db:
            with db:
                db.execute("UPDATE jobs SET status='running' WHERE job_id=?", (job['job_id'],))
        return job

    def test_missing_receipt_is_interrupted_without_retry(self):
        job = self.stranded()
        names = []
        result = queue.recover(self.root, lambda name: names.append(name) or {'exit_code': 0})
        self.assertEqual(names, ['kynly-' + job['job_id']])
        self.assertEqual(result[0]['status'], 'interrupted')
        self.assertEqual(queue.inspect(self.root, job['job_id'])['exit_code'], 130)
        self.assertEqual(queue.recover(self.root, lambda _: self.fail('Repeated cleanup')), [])
        self.assertEqual(self.submit()['status'], 'interrupted')

    def test_terminal_receipt_restored(self):
        import argparse
        job = self.stranded()
        self.receipt(argparse.Namespace(data_dir=str(Path(self.root)/'runs'), job_id=job['job_id']), 'failed', 7)
        result = queue.recover(self.root, lambda _: {'exit_code': 1, 'output': 'Error: No such container'})
        self.assertEqual(result[0]['source'], 'terminal_receipt')
        self.assertEqual(queue.inspect(self.root, job['job_id'])['exit_code'], 7)

    def test_docker_unavailable_keeps_running(self):
        job = self.stranded()
        with self.assertRaises(RuntimeError):
            queue.recover(self.root, lambda _: {'exit_code': 1, 'output': 'Cannot connect to daemon'})
        self.assertEqual(queue.inspect(self.root, job['job_id'])['status'], 'running')

    def test_live_worker_blocks_recovery(self):
        lock = Path(queue.__file__).resolve().parents[1]/'.kynly'/'queue-worker.lock'
        with queue.workspace_lock(lock):
            with self.assertRaises(RuntimeError):
                queue.recover(self.root, lambda _: self.fail('Cleaned live worker'))

    def test_malformed_receipt_is_not_success(self):
        job = self.stranded()
        directory = Path(self.root)/'runs'/job['job_id']
        directory.mkdir(parents=True)
        (directory/'result.json').write_text('{broken')
        self.assertEqual(queue.recover(self.root, lambda _: {'exit_code': 0})[0]['status'], 'interrupted')


if __name__ == '__main__':
    unittest.main()
