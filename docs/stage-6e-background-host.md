# Stage 6E: manually managed background API and worker

Prior Windows checks passed: n8n scheduling, watch lock/idle shutdown, and active
interruption after container-absence verification. This checkpoint adds a detached
Python host containing the loopback API and queue worker. No Windows startup task
is installed. Docker Desktop must already run before processing jobs.

Stop the foreground API and watch worker first. Keep test schedules unpublished.
Do not run tests while a watch/background worker holds the checkout worker lock.

```powershell
cd D:\Projects\kynly
git pull --ff-only
py -3 -m unittest discover -s tests -v
$LASTEXITCODE
py -3 .\scripts\background_host.py start --data-dir D:\KynlyData\queue
py -3 .\scripts\background_host.py status
```

Expect37 tests OK/0, then statusrunning with PID, port8787 and queue data directory.
The token is loaded from existing ignored .kynly/api-token.txt; it is never put
in the command line, state receipt, or output. Paths with spaces are supported
by subprocess argument lists. A second start returns the existing host state and
does not launch another worker. Check returned data_dir/port rather than assuming
a second start changes an existing host's configuration.

```powershell
py -3 .\scripts\background_host.py start --data-dir D:\KynlyData\queue
```

Expect same PID and instance. The API and watch worker now survive closing their
launch terminal. Status is based on an OS lifetime lock plus a receipt; it is not
a Docker readiness check. Authenticated /health checks storage/API separately.

Manually run the existing n8n workflow with request_key n8n-background-001. Expect
automatic pickup and passed/0 using its GET status node, with no foreground work
command. Keep the scheduled test unpublished.

```powershell
py -3 .\scripts\background_host.py stop
py -3 .\scripts\background_host.py status
```

Stop is a request, returning stopping. The worker completes its current bounded
job, then shuts down the API and releases both locks. Status should become stopped
within a few seconds when idle; while active allow its timeout plus cleanup time.
Do not forcibly kill the host to speed up graceful shutdown. API requests accepted
before final shutdown can remain queued for next start. The stop request uses an
instance-specific file so old stop files cannot stop a future instance.

Restart and verify idle stop again. Logs append at .kynly/background/host.log,
and state.json tracks start, stop or failure. Logs currently have no rotation.
These local files are ignored by git. Job logs/results remain under the queue's
runs directory. If statusstale/failed after forced termination, inspect the host
log, terminate any orphaned process tree if necessary, and run explicit queue
recovery before starting. No automatic retry or automatic recovery is added.

```powershell
Get-Content .kynly\background\host.log -Tail 60
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue recover
```

A port already in use or existing foreground worker prevents startup; inspect
host.log rather than changing bind addresses. Fixed bind remains127.0.0.1. n8n
container connectivity already passed on this PC. Installed startup-at-sign-in,
restart supervision, log rotation, and GPU admission remain future checkpoints.

Tests cover real idle server/worker shutdown and stale-state detection, alongside
all existing queue, API, recovery and runner tests. Windows detached launch and
active finish-before-stop need the manual checks on this page.
