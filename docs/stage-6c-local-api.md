# Stage 6C: local queue API

Stage 6B queue execution, explicit recovery, repeat recovery, and execution after
recovery passed on the user's Windows PC. This checkpoint adds HTTP access to
queue submission and status; it does not start a worker or expose Docker commands.
Standard library only. Binding is fixed to 127.0.0.1, default port8787.
This is a development API; container access and background service startup are
separate checkpoints. Do not change the bind address to expose it to the LAN.

All routes require Authorization: Bearer TOKEN. No browser-origin requests or
CORS are supported. Request bodies are JSON, at most8192 bytes. Task choices and
timeout limits are those of the existing runner. Tokens are not logged or passed
on the command line. Job responses omit filesystem paths. GET /jobs returns up
to50 newest jobs. There is no file-download, execution, or recovery endpoint.

| Method | Route | Behavior |
|---|---|---|
| GET | /health | Storage connectivity; does not assert Docker/worker readiness |
| POST | /jobs | task, request_key, optional timeout_seconds (default30) |
| GET | /jobs | Newest50 jobs |
| GET | /jobs/JOB_ID | Job status and exit code |
| POST | /jobs/JOB_ID/cancel | Empty object body; cancel queued job |

Success is200, including duplicate submissions. Errors:401 token missing/wrong,
403 browserOrigin,400 bad input,404 missing route/job,409 request-key conflict or
active cancellation unsupported,503 unavailable storage. Active cancellation
remains the runner CLI; recovery remains the queue CLI.

## Windows checkpoint

Terminal A:

```powershell
cd D:\Projects\kynly
git pull --ff-only
py -3 -m unittest discover -s tests -v
$LASTEXITCODE
New-Item -ItemType Directory -Force .kynly | Out-Null
if (!(Test-Path .kynly\api-token.txt)) {
    $tokenBytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($tokenBytes)
    $rng.Dispose()
    [Convert]::ToBase64String($tokenBytes) | Set-Content -Encoding ASCII .kynly\api-token.txt
}
$env:KYNLY_API_TOKEN = (Get-Content -Raw .kynly\api-token.txt).Trim()
py -3 .\scripts\queue_api.py --data-dir D:\KynlyData\queue
```

Expect28 tests, OK/0. API remains running untilCtrl+C. The token file is beneath
existing ignored .kynly, never commit it or paste its contents into chat. Protect
it as a local credential. To rotate, stop the API, remove this file, and rerun the
generation block; update clients before restarting. Never overwrite .env.

Terminal B:

```powershell
cd D:\Projects\kynly
$headers = @{ Authorization = 'Bearer ' + (Get-Content -Raw .kynly\api-token.txt).Trim() }
Invoke-RestMethod http://127.0.0.1:8787/health -Headers $headers
$body = @{ task='tests'; request_key='api-smoke-001'; timeout_seconds=30 } | ConvertTo-Json
$job = Invoke-RestMethod http://127.0.0.1:8787/jobs -Method Post -Headers $headers -ContentType application/json -Body $body
$job
$duplicate = Invoke-RestMethod http://127.0.0.1:8787/jobs -Method Post -Headers $headers -ContentType application/json -Body $body
$job.job_id -eq $duplicate.job_id
py -3 .\scripts\job_queue.py --data-dir D:\KynlyData\queue work
Invoke-RestMethod ("http://127.0.0.1:8787/jobs/" + $job.job_id) -Headers $headers
```

Expecthealth statusok, executes_jobsfalse; jobqueued; duplicate comparisonTrue;
workerpassed/0; API then reports that same jobpassed/0. API itself must not create
a container until work is run. A request without headers should fail401:

```powershell
try {
    Invoke-RestMethod http://127.0.0.1:8787/health
} catch {
    [int]$_.Exception.Response.StatusCode
}
```

Tests exercise real HTTP requests in-process on ephemeral loopback ports, plus
all queue and runner tests. Windows end-to-end validation remains pending.
Docker n8n/OpenClaw access is not yet wired; localhost inside those containers
is not this Windows API. The next checkpoint will address that deliberately.
