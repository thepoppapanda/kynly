# Stage 6D: continuously waiting queue worker

The local API and manual n8n health, submit, deduplication, worker execution, and
status lookup passed on the user's Windows PC. This checkpoint adds foreground
watch mode. It is not yet an installed Windows background service.

```powershell
cd D:\Projects\kynly
git pull --ff-only
py -3 -m unittest discover -s tests -v
$LASTEXITCODE
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue work --watch
```

Expect32 tests OK/0. The worker stays alive when idle and checks for jobs every
2seconds. Optional --poll-seconds accepts0.1 through60. It holds the checkout
queue-worker OS lock for its entire lifetime, including idle time. Transactions
are closed before waiting. Only one watch/one-shot/recovery owner per checkout
can run. Do not run unit tests while a real worker holds this checkout lock.

Keep the API running in its own terminal. In the unpublished Kynly API Test n8n
workflow change the submission request_key from n8n-smoke-001 to n8n-watch-001.
Execute manually. The watch terminal should pick up and finish the new job
without a separate work command. The immediately following status node may see
queued/running; rerun that GET node a few seconds later using the submission
output. Expect passed/0. Executing the submission again with the same key must
return the same job; it must not execute again. New intended jobs need new keys.

In another terminal, attempting work while watch is idle should fail busy/1:

```powershell
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue work
$LASTEXITCODE
```

PressCtrl+C once in the watch terminal while idle. Expect Worker stopped and
exit130, then verify a one-shot work can acquire the lock:

```powershell
$LASTEXITCODE
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue work
```

Expect completed empty if no jobs remain. Ctrl+C during an active job uses the
existing runner cleanup, commits interrupted/130, and stops without claiming
another job. This active-stop behavior is unit tested with runner receipts;
Windows active Ctrl+C container cleanup remains a separate manual check. Forced
process termination still requires explicit recover before work/watch can resume.
Docker failure or unresolved running state stops dispatch rather than retrying.

Watch mode does not retain an ever-growing in-memory completed-job list; durable
queue rows and run files remain the history. It polls the local SQLite database,
not the HTTP API. No scheduling, automatic restart, GPU admission, or concurrency
across independent checkouts is added. API executes_jobs remainsfalse because
the API process itself only stores requests. New unit tests cover idle arrival,
stop/lock release, active interruption halting the next job, and poll validation.

## Active Ctrl+C follow-up

Windows idle stop, lock release, and scheduled n8n execution passed. The active
stop test saved an interrupted/130 terminal receipt but queue synchronization
stopped with Container cleanup unconfirmed. Explicit recovery imported that
receipt and found no container. The original removal command's exact failure
has not yet been inspected, so the precise Windows signal behavior is unproven.

Cleanup now verifies exact-name container absence through a successful Docker
container-list request if removal fails or times out. A successful empty result
normalizes cleanup to0 while retaining the original removal exit code and the
verification output. A live container or daemon failure remains unresolved.
35 tests pass, including removal interruption with confirmed absence, a remaining
container, and unavailable daemon. Repeat the active stop on Windows with a fresh
request key active-stop-002. Expect interrupted/130 recorded directly in the queue,
worker stopped, no container, and recover returning an empty list. If it still
blocks, retain and inspect the job's result.json cleanup field before recovering.
