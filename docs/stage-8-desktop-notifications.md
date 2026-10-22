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
If the registered identity is missing or its notification setting disabled, the
script reports an error instead of silently claiming success. Dedicated Kynly
application identity, notification click actions and branding remain future work.
No action buttons or arbitrary scripts are constructed from message text; XML
text nodes escape title/message content. Title limit80, message limit500.

The script uses Windows PowerShell5.1 and Windows Runtime native toast APIs,
with the existing Microsoft.Windows.PowerShell shortcut identity. It requires an
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
