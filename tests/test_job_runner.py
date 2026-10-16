import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "job_runner", Path(__file__).resolve().parents[1] / "scripts" / "run_job.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def watch(self, code, timeout=5, cancelled=False):
        with tempfile.TemporaryDirectory() as folder:
            cancel = Path(folder) / "cancel.request"
            if cancelled:
                cancel.touch()
            process = subprocess.Popen([sys.executable, "-c", code],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                return runner.monitor(process, timeout, cancel)
            finally:
                runner.stop_process(process)

    def test_real_success_process(self):
        self.assertEqual(self.watch("pass"), ("passed", 0))

    def test_real_failure_preserves_exit_code(self):
        self.assertEqual(self.watch("raise SystemExit(7)"), ("failed", 7))

    def test_timeout_is_distinct_from_failure(self):
        self.assertEqual(self.watch("import time; time.sleep(30)", timeout=0.15),
                         ("timed_out", 124))

    def test_cancellation_is_distinct_from_timeout(self):
        self.assertEqual(self.watch("import time; time.sleep(30)", cancelled=True),
                         ("cancelled", 130))

    def test_workspace_lock_rejects_second_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / "workspace.lock"
            with runner.workspace_lock(lock):
                with self.assertRaises(RuntimeError):
                    with runner.workspace_lock(lock):
                        self.fail("second writer acquired lock")
            with runner.workspace_lock(lock):
                pass

    def test_changes_distinguish_add_remove_and_modify(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "keep").write_text("unchanged")
            (root / "edit").write_text("old")
            (root / "remove").write_text("remove")
            before = runner.snapshot(root)
            (root / "edit").write_text("new")
            (root / "remove").unlink()
            (root / "add").write_text("new")
            self.assertEqual(runner.changes(before, runner.snapshot(root)),
                             {"added": ["add"], "removed": ["remove"], "modified": ["edit"]})
