# Stage 6B queue checkpoints

Checkpoint 1 stores jobs in `queue.sqlite3` under the supplied data directory.
It does not launch Docker, claim jobs, recover interrupted execution, or provide an API.
Use a local SSD directory. Keep the existing Stage 6A jobs directory separate.
Python standard library only; no packages or services to install.

From PowerShell in D:\Projects\kynly:

```powershell
git pull --ff-only
py -3 -m unittest discover -s tests -v
$LASTEXITCODE
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue submit tests --request-key queue-smoke-001
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue submit tests --request-key queue-smoke-001
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue list
```

The checkpoint-1 version had 13 passing tests and exit 0; checkpoint 2 has 18. Both submissions return the same job ID,
with status `queued`, and the list contains one smoke-test job on a clean queue.
Close/reopen PowerShell, return to the checkout, and list again: the job persists.

Copy the returned job ID into these commands:

```powershell
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue show JOB_ID
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue cancel JOB_ID
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue submit tests --request-key queue-smoke-001
```

Expect `queued`, then `cancelled`; resubmitting that key still returns the original
cancelled job. A fresh intended execution needs a fresh request key. Keys are scoped
to this queue database and must contain 1–200 characters.

```powershell
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue submit probe-failure --request-key queue-smoke-001
$LASTEXITCODE
```

Expect a parameter-conflict error and exit 1. The existing job stays unchanged.
No containers should be created by any command in this checkpoint.

SQLite transactions serialize simultaneous submissions. Sequence numbers record
submission order; listing shows newest first. Storage currently supports only
queued/cancelled states. The schema is preliminary until execution and recovery
are added; do not connect n8n/OpenClaw or rely on this as a production dispatcher yet.
Unit tests cover persistence in another Python process, simultaneous duplicate
submissions, conflicting keys, cancellation, validation, ordering and limits.
Windows manual verification remains required.


## Checkpoint 2: bounded queue execution

Queue storage validation passed on the user's Windows PC. The schema now migrates
transactionally to support running and terminal states while preserving existing
jobs, cancellation and request keys. Do not run an older queue script against the
upgraded database.

`work` drains queued jobs in submission order and exits when none remain. It does
not poll indefinitely. One queue worker per checkout holds an OS lock, including
across different queue data directories. The existing runner still takes its
workspace lock. Avoid manual worker runs while draining the queue.

Each queue job retains its ID through execution. Results are saved under
`D:\KynlyData\queue\runs\JOB_ID`, including output.log and result.json.
A failed test job does not stop later jobs; the worker CLI returns 0 if dispatch
completed normally. Inspect individual job status/exit_code for task failures.

```powershell
cd D:\Projects\kynly
git pull --ff-only
py -3 -m unittest discover -s tests -v
$LASTEXITCODE
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue submit tests --request-key dispatch-tests-001
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue submit probe-failure --request-key dispatch-failure-001
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue submit tests --request-key dispatch-tests-002
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue work
$LASTEXITCODE
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue list
docker ps -a --filter "name=kynly-job-"
```

Expect 18 passing unit tests, then jobs executed in order: passed/0, failed/7,
passed/0. Worker exits 0. Listing is newest first, so use sequence/request_key to
identify execution order. The earlier cancelled smoke-test job stays cancelled.
No job containers should remain. Running work a second time completes an empty
list and starts no containers.

Queued cancellation remains available. For an active job use the existing runner:
`py -3 .\scripts\run_job.py cancel JOB_ID --data-dir D:\KynlyData\queue\runs`.
Queue cancel explicitly rejects running jobs to avoid reporting a false cancellation.

An unexpected runner error, abrupt interruption, or unconfirmed cleanup stops the
worker and preserves running state. A subsequent worker refuses to launch more
jobs in that database until recovery is implemented. Do not delete running rows
or switch queue directories to work around this. Automatic crash recovery and
an API are the next checkpoint. No n8n or OpenClaw execution connection exists yet.
The runner locks cover this checkout, not arbitrary checkouts or manual Docker
commands. Tests exercise dispatch decisions with simulated runner receipts;
actual Docker validation must be performed on the Windows host.

## Checkpoint 3: explicit restart recovery

Checkpoint 2 sequential execution and empty-queue behavior passed on Windows.
Run `recover` after an unexpected worker shutdown, before `work`. It takes both
checkout locks, cleans only exact generated container names for running jobs,
and saves recovery.json next to the original, unchanged logs/results. A valid
terminal receipt is imported; otherwise status becomes interrupted with code130.
It never resubmits jobs. Repeat recover is a no-op once states are resolved.
If Docker cleanup fails, the job remains running and dispatch stays blocked.
This is explicit recovery, not an automatic Windows service or retry policy.

First pull and run the 23 tests:

```powershell
git pull --ff-only
py -3 -m unittest discover -s tests -v
$LASTEXITCODE
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue recover
```

Expect OK/0 and an empty recovered list on the existing healthy queue.

For a real interruption test use this separate queue. These commands target only
the Python worker process created here and its children; no other Python processes.
Run all commands in the same PowerShell session so $worker is retained:

```powershell
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\recovery-test submit probe-timeout --timeout 120 --request-key recovery-sleep-001
$pythonExe = py -3 -c "import sys; print(sys.executable)"
$worker = Start-Process -FilePath $pythonExe -ArgumentList '.\scripts\job_queue.py','--data-dir','D:\KynlyData\recovery-test','work' -NoNewWindow -PassThru
```

Wait until the job prints its ID and Docker shows its running sleep container:

```powershell
docker ps --filter "name=kynly-job-"
```

Then promptly stop that worker tree (before the 120-second timeout), and recover:

```powershell
taskkill /PID $worker.Id /T /F
$worker.WaitForExit()
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\recovery-test work
$LASTEXITCODE
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\recovery-test recover
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\recovery-test list
docker ps -a --filter "name=kynly-job-"
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\recovery-test recover
```

Expect work to refuse unresolved running state and exit1. Recover removes any
remaining container and marks this job interrupted/130 (not passed or queued).
The next recover returns an empty list. Logs and recovery evidence remain under
D:\KynlyData\recovery-test\runs. If the job already timed out naturally, use a new
request key and repeat; that does not test abrupt worker loss.

Finally submit tests with a new key to recovery-test, run work, and expect passed/0:

```powershell
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\recovery-test submit tests --request-key recovery-followup-001
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\recovery-test work
```

Current scope is one checkout on a local disk. Recovery cannot coordinate other
checkouts or manually launched containers. Terminate a stranded worker's process
tree before recovery, since an orphaned Docker CLI is outside the OS file lock.
Full machine power-loss durability, a background service, and the status API are
not validated by these tests. Docker recovery tests run manually on Windows;
unit tests simulate daemon responses and persisted receipts.
