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


if __name__ == '__main__':
    unittest.main()
