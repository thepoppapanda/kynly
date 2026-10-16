"""Host-side, single-workspace development job runner (Python 3.10+)."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


TASKS = {
    "tests": ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
    "probe-failure": ["python", "-c", "raise SystemExit(7)"],
    "probe-timeout": ["python", "-c", "import time; time.sleep(120)"],
}
TERMINAL = {"passed", "failed", "timed_out", "cancelled", "interrupted"}


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def workspace_lock(path):
    """OS releases this lock if the host runner dies. Lock file itself remains."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Workspace busy: another runner owns this workspace") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        handle.close()


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in {".git", "__pycache__", ".venv"} for part in relative.parts):
            continue
        result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def changes(before, after):
    return {
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "modified": sorted(k for k in before.keys() & after.keys() if before[k] != after[k]),
    }


def monitor(process, timeout, cancel_path):
    deadline = time.monotonic() + timeout
    while True:
        code = process.poll()
        if code is not None:
            return ("passed" if code == 0 else "failed"), code
        if cancel_path.exists():
            return "cancelled", 130
        if time.monotonic() >= deadline:
            return "timed_out", 124
        time.sleep(0.1)


def cleanup_container(name):
    try:
        completed = subprocess.run(
            ["docker", "rm", "-f", name], capture_output=True, text=True, timeout=15
        )
        return {"exit_code": completed.returncode,
                "output": (completed.stdout + completed.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit_code": None, "error": str(error)}


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run_job(args):
    repo = Path(__file__).resolve().parents[1]
    workspace = repo / "examples" / "worker-sandbox"
    if not workspace.is_dir() or not (repo / "compose.yaml").is_file():
        raise RuntimeError("Run from a complete Kynly checkout")
    data = Path(args.data_dir).expanduser().resolve()
    # Fixed lock location: changing --data-dir cannot bypass workspace serialization.
    lock = repo / ".kynly" / "worker-sandbox.lock"
    with workspace_lock(lock):
        job_id = "job-" + uuid.uuid4().hex
        directory = data / job_id
        directory.mkdir(parents=True)
        name = "kynly-" + job_id
        result = {"job_id": job_id, "task": args.task, "status": "running",
                  "started_at": now(), "timeout_seconds": args.timeout,
                  "workspace": str(workspace), "container": name,
                  "log": str(directory / "output.log")}
        save_json(directory / "result.json", result)
        print("Job ID: " + job_id, flush=True)
        print("Results: " + str(directory), flush=True)
        command = ["docker", "compose", "--project-directory", str(repo),
                   "-f", str(repo / "compose.yaml"), "--profile", "development",
                   "run", "--rm", "--no-deps", "--name", name, "dev-worker"]
        command += TASKS[args.task]
        before = snapshot(workspace)
        process = None
        try:
            with (directory / "output.log").open("wb") as log:
                process = subprocess.Popen(command, cwd=repo, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT)
                status, code = monitor(process, args.timeout, directory / "cancel.request")
                result.update(status=status, exit_code=code)
        except KeyboardInterrupt:
            result.update(status="interrupted", exit_code=130)
        except Exception as error:
            result.update(status="failed", exit_code=1, error=str(error))
        finally:
            # Always clean up by exact generated name; never prune unrelated containers.
            result["cleanup"] = cleanup_container(name)
            stop_process(process)
            try:
                result["changes"] = changes(before, snapshot(workspace))
            except OSError as error:
                result["snapshot_error"] = str(error)
            result["finished_at"] = now()
            save_json(directory / "result.json", result)
        print("Status: " + result["status"], flush=True)
        print("Exit code: " + str(result["exit_code"]), flush=True)
        print((directory / "output.log").read_text(encoding="utf-8", errors="replace"))
        return result["exit_code"]


def cancel_job(args):
    # Refuse traversal; only generated job IDs can name result directories.
    suffix = args.job_id.removeprefix("job-")
    if not args.job_id.startswith("job-") or len(suffix) != 32 or any(
            c not in "0123456789abcdef" for c in suffix):
        raise RuntimeError("Invalid job ID")
    directory = Path(args.data_dir).expanduser().resolve() / args.job_id
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if result["status"] != "running":
        print("Job already finished: " + result["status"])
        return 0
    (directory / "cancel.request").touch()
    print("Cancellation requested; the active host runner must acknowledge it.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    run = commands.add_parser("run")
    run.add_argument("task", choices=TASKS)
    run.add_argument("--timeout", type=float, default=30)
    run.add_argument("--data-dir", required=True)
    cancel = commands.add_parser("cancel")
    cancel.add_argument("job_id")
    cancel.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    if args.operation == "run" and not 0 < args.timeout <= 3600:
        parser.error("timeout must be greater than 0 and no more than 3600 seconds")
    try:
        return run_job(args) if args.operation == "run" else cancel_job(args)
    except (OSError, RuntimeError, ValueError) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
