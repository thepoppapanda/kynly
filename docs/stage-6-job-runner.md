# Stage 6A: bounded host-side job runner

Python 3.10+ and Docker Desktop required. Run on Windows, outside containers.
No Python packages are needed. This is a synchronous single-workspace runner,
not a persistent queue or an agent. It accepts named tasks only, never a
model-generated shell command.

Stage 5's worker baseline passed on the user's PC: four sample tests, exit 0,
intentional exit 7, UID/GID 10001, host/container write persistence, and two
regression failures followed by restored passing tests. Final code diff was
requested but not explicitly reported.

## First run

From D:\Projects\kynly:

```powershell
git pull origin main
py -3 --version
py -3 .\scripts\run_job.py run tests --timeout 30 --data-dir D:\KynlyData\jobs
$LASTEXITCODE
```

Stop if Python is unavailable or older than 3.10; report the error.
The already-built dev-worker image is required. If needed, rebuild using the
Stage 5 guide. No agent receives Docker access.

Expected: job ID, results directory, status passed, exit 0, four tests OK.
Each directory contains result.json and output.log. Results include SHA256-based
added/removed/modified path lists, not an automatic patch or rollback.

## Failure test

```powershell
py -3 .\scripts\run_job.py run probe-failure --timeout 30 --data-dir D:\KynlyData\jobs
$LASTEXITCODE
```

Expected: failed, exit 7.

## Timeout test

```powershell
py -3 .\scripts\run_job.py run probe-timeout --timeout 5 --data-dir D:\KynlyData\jobs
$LASTEXITCODE
```

Expected: timed_out, exit 124. Cleanup may add up to approximately 25 seconds
if Docker is slow/unresponsive. Inspect result.json cleanup information and
confirm its generated container name is absent from docker ps -a.
The timeout includes container startup; it is not only Python execution time.

## Cancellation and overlap tests

Start a probe in terminal A:

```powershell
py -3 .\scripts\run_job.py run probe-timeout --timeout 90 --data-dir D:\KynlyData\jobs
```

While it runs, submit tests from terminal B. Expected: workspace busy, exit 1.
Then cancel using terminal A's printed ID:

```powershell
py -3 .\scripts\run_job.py cancel job-REPLACE_WITH_ACTUAL_ID --data-dir D:\KynlyData\jobs
```

Expected: terminal A ends cancelled with exit 130. The cancel command acknowledges
a request, not completed cancellation. Check terminal A and result.json.

## Verification and limits

Host-side tests:
```powershell
py -3 -m unittest discover -s tests -v
```

Six tests passed in the preparation environment using real short-lived Python
subprocesses. Windows locking and Docker lifecycle behavior require target tests.
The runner uses a fixed checkout-local OS file lock, so changing data-dir
cannot bypass the same checkout's lock. This doesn't cover separate checkouts
that independently point to a shared external folder, or manual editor writes.

Keep result directories outside Git; .kynly lock files are ignored.
Default worker isolation remains in Compose. Interactive containers launched
manually are outside this runner's timeout, locking, and cancellation.

Cancellation and timeouts attempt to remove the exact job container and stop
its Docker client. Always inspect cleanup errors; Docker daemon failure may
prevent cleanup. Force-killing the host runner/PC can leave a container running
and result status stale. Automatic startup reconciliation is NOT implemented;
do not assume crash recovery or a persisted queue exists.

Next: verify all lifecycle tests, then add durable queue admission, crash
reconciliation, bounded log retention, per-job worktrees, API endpoints, and
agent submission. Current runner tasks only run tests or diagnostic probes;
they do not yet edit source autonomously.
