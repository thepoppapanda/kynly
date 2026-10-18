import importlib.util
from pathlib import Path
import subprocess
import unittest

spec = importlib.util.spec_from_file_location('startup', Path(__file__).resolve().parents[1]/'scripts'/'startup_host.py')
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


class StartupTests(unittest.TestCase):
    def test_ready_daemon(self):
        startup.wait_for_docker(run=lambda *a, **k: subprocess.CompletedProcess([], 0, '29.4.0', ''))

    def test_retries_until_ready(self):
        replies = iter([subprocess.CompletedProcess([], 1, '', 'not ready'), subprocess.CompletedProcess([], 0, '29', '')])
        startup.wait_for_docker(run=lambda *a, **k: next(replies), sleep=lambda _: None)

    def test_unavailable_daemon_has_bounded_wait(self):
        current = [0]
        def sleep(seconds):
            current[0] += seconds
        def unavailable(*args, **kwargs):
            raise FileNotFoundError('docker')
        with self.assertRaises(RuntimeError):
            startup.wait_for_docker(timeout=6, run=unavailable, clock=lambda: current[0], sleep=sleep)
        self.assertEqual(current[0], 6)


if __name__ == '__main__':
    unittest.main()
