# Windows desktop notifications: standalone checkpoint

Chosen destination: Windows desktop first; possible Discord delivery later when
a Discord bot is added. Completion monitoring workflow is saved under
integrations/n8n. This checkpoint only tests native Windows notification display.
It does not add API routes, automatically notify job completions, send external
messages, install a module, or change the OpenClaw tool allowlist.

```powershell
cd D:\Projects\kynly
git pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\show-notification.ps1
```

Expect a banner with title Kynly notification test. This initial test uses the
existing Windows PowerShell Start-menu application identity, so Windows may label
the sender Windows PowerShell. The message submission report is not proof that
a banner was displayed; verify visually or press Win+N for Notification Center.
Notifications/Do Not Disturb and Windows per-app settings may suppress banners.
If the registered identity is missing or Show() throws, the script reports the
original error and location. Windows may suppress a submitted toast; visual
confirmation is required. The optional Setting property returned null on this PC
and is not used as a prerequisite for submission. Dedicated Kynly
application identity, notification click actions and branding remain future work.
No action buttons or arbitrary scripts are constructed from message text; XML
XML escaping protects title/message content. Title limit80, message limit500.

The script uses Windows PowerShell5.1 and Windows Runtime native toast APIs,
with the registered native Windows PowerShell shortcut identity. It checks both
the legacy Microsoft.Windows.PowerShell ID and the system-directory path-based
ID observed on the user's PC. It excludes x86, ISE and third-party shortcuts. It requires an
interactive signed-in Windows user, matching the host's current task setup.
No administrator privileges or credential are required for the standalone test.
It was reviewed on the Linux development environment; Windows rendering and
WinRT interop must be validated on the user's PC. Do not claim an automatic
notification feature until the later API/n8n integration passes end to end.

After the visual check, the next checkpoint is a narrowly scoped authenticated
coordinator notification request from n8n's final summary. It should distinguish
passed, unsuccessful jobs, and monitoring limits. Delivery remains separate from
job outcome; suppressed notifications must not change a test result. Discord
can later be another destination without changing the completion monitor.

The first Windows test found a path-based Windows PowerShell AppID rather than
the initially assumed legacy ID. The script now selects the actual registered
entry. Display through this identity still requires a repeat visual test.

## Authenticated notification endpoint

Standalone banner display passed after selecting the registered path-based Windows
PowerShell identity, removing an unreliable null Setting precheck, and simplifying
XML text construction. Original PowerShell failure locations are now preserved.

POST /notifications uses the same bearer credential as the API. Body is the n8n
Result Summary object: job_id, request_key, outcome, job_status, exit_code, checks,
and optional message. The supplied message is ignored; fixed local text is built
from validated fields. Other fields are rejected. Existing job/request key must
match. Terminal outcome and exit code must match the stored job. Monitoring-limit
messages describe LAST observed queued/running status, which may be older than
the current job state. They never claim the job was cancelled or timed out.

SQLite desktop_notifications receipts live in the existing queue database. One
attempt per job/outcome/status is persisted BEFORE contacting Windows, suppressing
repeat requests, including uncertain attempts after host crashes. This is at-most
one attempt, not guaranteed delivery. Failed/unknown/attempt_started receipts are
not automatically retried; preserve them for diagnosis. A monitoring-limit alert
and a later terminal alert for the same job are distinct outcomes.

Response is HTTP200 for a stored attempt or duplicate; inspect notification_state:
submitted_to_windows, failed, submission_unknown or attempt_started. display_confirmed
is alwaysfalse because the API cannot confirm visual display. Duplicate requests
return duplicate true. Input errors use the existing API400/404 behavior. Job
status and exit code remain independent of notification failure.

Stop the background host and wait until stopped before pulling and running tests.
Then restart it so the new API route loads:

```powershell
py -3 .\scripts\background_host.py stop
py -3 .\scripts\background_host.py status
git pull --ff-only
py -3 -m unittest discover -s tests -v
py -3 .\scripts\background_host.py start --data-dir D:\KynlyData\queue
```

Expect46 Python tests OK. Native Windows calls are simulated by sender functions
in these tests; the Windows background route and n8n must be validated manually.

In Kynly Completion Tracking add HTTP Request after Result Summary:

- Name: Desktop Notification
- POST http://host.docker.internal:8787/notifications
- Generic Credential Type / Header Auth / existing Kynly Local API credential
- Send Body JSON, Using JSON, expression: {{ JSON.stringify($json) }}
- Options Timeout30000ms; automatic node retriesoff

Change Submit Job to tasktests, fresh request_key n8n-desktop-001, timeout_seconds30.
Execute the entire unpublished workflow. Expect terminal summarypassed/0, then a
Windows toast and notification_statesubmitted_to_windows, duplicatefalse. Rerun
only Desktop Notification using the same input: expect duplicatetrue, no new toast.
This alerts only jobs routed through this workflow; OpenClaw submissions do not
automatically acquire an n8n monitor or notification. API stays loopback/token
protected, and the MCP allowlist is unchanged. No arbitrary shell-command route
or Discord integration is added. Dedicated Kynly toast identity remains future
work; sender may still appear as Windows PowerShell.

## OpenClaw completion-alert opt-in

The user confirmed all three n8n alert paths: passed, failed/7, and monitoring limit.
Restore n8n tasktests/max_checks12 after diagnostics. OpenClaw opt-in now works
independently of n8n through the existing background host.

POST /jobs accepts optional boolean notify_desktop. True stores an idempotent
subscription; repeating a job's request key never clears that preference. The
response includes desktop_notification_requested after the preference is saved.
No task/timeout idempotency rule changes. Omitted/false does not subscribe a new
job. A true repeat can opt an existing job into one completion alert. This is an
additive preference, not a notification cancellation API.

Adapter0.3.0 adds optional notify_desktop boolean to kynly_submit_tests. Its task
and timeout remain fixed. The background host scans up to10 eligible terminal
subscriptions every2seconds; it doesn't ask the model to poll and doesn't need
n8n. It uses the same desktop notification attempt receipts as /notifications.
Repeats and existing terminal alerts are suppressed. Failures/uncertain attempts
remain recorded without automatic redelivery. Alerts are Windows desktop only,
not future OpenClaw chat replies or Discord messages.

Pending subscriptions survive host restarts. Jobs can finish without the host
running, but delivery waits until the host next runs. On graceful host stop,
pending alerts can likewise wait until restart. The notifier stops scheduling
new attempts on shutdown and waits up to25seconds for an active attempt. Job
execution does not depend on notification success. Unresolved running jobs still
require explicit recovery before host startup; recovery itself does not display
alerts. Recovered terminal jobs can be alerted after the host starts.

Stop the host, wait for stopped, pull, and run tests (no live watch worker):

```powershell
py -3 .\scripts\background_host.py stop
py -3 .\scripts\background_host.py status
git pull --ff-only
py -3 -m unittest discover -s tests -v
py -3 .\scripts\background_host.py start --data-dir D:\KynlyData\queue
docker compose cp .\integrations\openclaw\kynly-mcp.mjs openclaw:/home/node/.openclaw/kynly-tools/kynly-mcp.mjs
docker compose cp .\integrations\openclaw\kynly-mcp.test.mjs openclaw:/home/node/.openclaw/kynly-tools/kynly-mcp.test.mjs
docker compose exec openclaw node --test /home/node/.openclaw/kynly-tools/kynly-mcp.test.mjs
docker compose restart openclaw
```

Expect50 Python tests and6 Node tests. A fresh Slate conversation should call
kynly__kynly_submit_tests once with request_keyopenclaw-desktop-001 and
notify_desktoptrue. Report the returned job ID and desktop_notification_requested;
no status-poll loop. Expect one completion banner soon after the job finishes.
Repeat the same key and true preference: same job ID, no new execution/banner.
Only after this end-to-end check update agent instructions to describe verified
Windows alerts. Existing rules still caution against unconfigured notifications.
API subscription and dispatch decisions are tested with mocked Windows senders;
real Windows automatic delivery remains pending.


### Validated OpenClaw checkpoint

The user confirmed submission openclaw-desktop-001 returned notification_requested
true and produced a desktop completion banner. Repeating that key returned the
same job with passed/0 and no second banner. Tests-only job scope is unchanged.
KYNLY_JOB_RULES.md now describes opt-in Windows alerts, deduplication, host/session
requirements, and the distinction from later chat messages. Install the updated
managed block into the workspace AGENTS.md and use a fresh chat to verify its
explanation. The repository rule update does not update the running workspace by
itself. No Discord integration or guaranteed visual delivery is claimed.
