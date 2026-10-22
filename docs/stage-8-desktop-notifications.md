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
