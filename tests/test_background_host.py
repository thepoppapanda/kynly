import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import background_host as host


class BackgroundTests(unittest.TestCase):
    def test_real_idle_host_start_and_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime = root / 'runtime'
            errors = []
            def target():
                try:
                    host.serve(root / 'data', 'a'*64, runtime, 'test-instance', 0)
                except BaseException as error:
                    errors.append(error)
            thread = threading.Thread(target=target)
            thread.start()
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    state = host.status(runtime)
                    if state['status'] == 'running':
                        break
                    time.sleep(0.05)
                self.assertEqual(state['status'], 'running')
                self.assertGreater(state['port'], 0)
            finally:
                runtime.mkdir(exist_ok=True)
                (runtime/'test-instance.stop').touch()
                thread.join(timeout=8)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(host.status(runtime)['status'], 'stopped')

    def test_stale_receipt_is_not_running(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            (runtime/'state.json').write_text(json.dumps({'status': 'running', 'instance': 'old'}))
            self.assertEqual(host.status(runtime)['status'], 'stale')


if __name__ == '__main__':
    unittest.main()
