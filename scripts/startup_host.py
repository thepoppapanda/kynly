"""Wait for Docker Desktop, then launch Kynly's background host once."""
import argparse
from pathlib import Path
import subprocess
import sys
import time


def wait_for_docker(timeout=180, run=subprocess.run, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    while clock() < deadline:
        try:
            result = run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                         capture_output=True, text=True, timeout=min(5, max(0.1, deadline-clock())))
            if result.returncode == 0 and result.stdout.strip():
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
        remaining = deadline-clock()
        if remaining > 0:
            sleep(min(3, remaining))
    raise RuntimeError('Docker not ready within startup timeout; start Docker Desktop and retry the task')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    args = parser.parse_args()
    runtime = Path(__file__).resolve().parents[1] / '.kynly' / 'background'
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / 'startup.log').open('a', encoding='utf-8') as log:
        try:
            wait_for_docker()
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('background_host.py')),
                                     'start', '--data-dir', str(Path(args.data_dir).resolve())],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=30)
            return result.returncode
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            log.write(str(error) + '\n')
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
