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
