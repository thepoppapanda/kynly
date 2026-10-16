# Stage 6B, checkpoint 1: persistent queue storage

This checkpoint stores jobs in `queue.sqlite3` under the supplied data directory.
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

Expect 13 passing tests and exit 0. Both submissions return the same job ID,
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
