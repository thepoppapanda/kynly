# Stage 6F: Windows sign-in startup

Background launch, n8n execution, duplicate starts, idle stop/restart, and graceful
stop during a bounded active job passed on Windows. This checkpoint installs an
interactive limited-privilege scheduled task for the current Windows user.
It runs30seconds after sign-in and waits up to180seconds for docker info to succeed.
Docker Desktop must be configured to start at sign-in separately; the task does
not install Docker or elevate privileges. No password is stored.

Stop the background host and wait until stopped before running tests:

```powershell
cd D:\Projects\kynly
py -3 .\scripts\background_host.py stop
py -3 .\scripts\background_host.py status
git pull --ff-only
py -3 -m unittest discover -s tests -v
$LASTEXITCODE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manage-startup.ps1
```

Expect40 tests OK/0 and the name Kynly-Background-CURRENT_USER_SID. The installer
locates the current Python interpreter and registers absolute paths and a working
directory. ExecutionPolicy Bypass applies only to this invocation. No system-wide
execution policy changes. A restricted policy may reject registration; report
that error rather than rerunning as administrator automatically.

Enable Docker Desktop's start-at-sign-in setting. Then manually test the task:

```powershell
$kynlyTask = 'Kynly-Background-' + [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
Start-ScheduledTask -TaskName $kynlyTask
Start-Sleep -Seconds 5
py -3 .\scripts\background_host.py status
Get-ScheduledTaskInfo -TaskName $kynlyTask
```

Expect hostrunning. Once the startup launcher finishes, LastTaskResult should0;
while it runs the task may report running instead. The scheduled launcher exits
after spawning the detached host, so taskReady is normal even while hostrunning.
Stopping the scheduled task does not stop the detached host; use background_host
stop. If Docker is slow, allow up to3minutes plus launcher time. Failure logs:

```powershell
Get-Content .kynly\background\startup.log -Tail 40
Get-Content .kynly\background\host.log -Tail 40
```

Rerun the task: existing running host must retain the same PID/instance. Stop the
host and start the task again to confirm relaunch. Full sign-out/sign-in is a later
manual check when convenient; do not interrupt ongoing work just to test it now.
Keep scheduled n8n test workflows unpublished until that validation is complete.

Removal (does not stop a host already running):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manage-startup.ps1 -Remove
py -3 .\scripts\background_host.py stop
```

Registration is idempotent for this Windows user and replaces this named task.
Moving the checkout or Python installation requires rerunning registration. Startup
checks Docker availability but does not start n8n/OpenClaw compose services, run
migrations beyond normal queue initialization, recover interrupted jobs, or restart
a host after a later crash. Those remain separate operator actions. Docker restarts
its services according to existing container policies; do not assume the task
recreates absent containers. Existing API token must be present locally.

40 tests cover bounded Docker wait, retry, real host lifecycle, queue/API/runner.
PowerShell registration and Windows sign-in behavior require manual validation.
