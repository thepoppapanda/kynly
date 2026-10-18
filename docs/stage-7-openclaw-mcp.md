# OpenClaw read-only Kynly MCP connector

The installed OpenClaw2026.10.3 CLI supports mcp add/set/probe/tools/reload and
its Docker container reached the loopback host API with401 (no token).
This milestone adds only kynly_jobs_list and kynly_job_status over stdio.
No submit/cancel, command execution, arbitrary URL, or file-reading tool is exposed.
The adapter uses Node22+ built-ins and newline-delimited JSON-RPC; no npm packages.
Credential loading is internal from the fixed private container path.

Files: integrations/openclaw/kynly-mcp.mjs and kynly-mcp.test.mjs.
Copy them into the existing persistent OpenClaw volume; this is an operator code
installation, not an expansion of agent filesystem permissions. Read-only here
means exposed tool operations; the private bearer credential currently has the
same API privileges as n8n. Separate scoped API credentials remain future work.
Do not grant the agent exec access or access to the private credential directory.

```powershell
cd D:\Projects\kynly
git pull --ff-only
docker compose exec openclaw node -e "require('fs').mkdirSync('/home/node/.openclaw/kynly-tools',{recursive:true,mode:448})"
docker compose cp .\integrations\openclaw\kynly-mcp.mjs openclaw:/home/node/.openclaw/kynly-tools/kynly-mcp.mjs
docker compose cp .\integrations\openclaw\kynly-mcp.test.mjs openclaw:/home/node/.openclaw/kynly-tools/kynly-mcp.test.mjs
Get-Content -Raw .kynly\api-token.txt | docker compose exec -T openclaw node -e "let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{const f='/home/node/.openclaw/kynly-tools/api-token.txt';require('fs').writeFileSync(f,s.trim(),{mode:384});require('fs').chmodSync(f,384);console.log('Credential saved');})"
docker compose exec openclaw node --test /home/node/.openclaw/kynly-tools/kynly-mcp.test.mjs
docker compose exec openclaw node dist/index.js mcp add --help
```

Expect4 Node tests pass. The tests use a temporary credential and ephemeral HTTP
server; they do not expose the real token or change the real queue. Registration
and tool-policy changes wait for the installed add-command options. Do not alter
current allow/deny settings, tool search, loop protection, or context limits yet.
Current adapter protocol version2025-03-26; actual installed MCP negotiation and
model use require follow-up testing. It limits API requests to10seconds and
refuses redirects. Original private token should never be pasted in chat, workflow
exports or git. Credential is in the existing secret-bearing OpenClaw volume.

## Fixed tests submission (adapter 0.2.0)

Read-only discovery, authenticated API reads, and model calls for known and missing
jobs passed. A model stall also affected direct LM Studio inference; model reload
restored READY and the missing-job tool returned404. No timeout increase was made.
An explanation that completed jobs are removed was speculative: completed queue
records are retained.

The adapter now also advertises kynly_submit_tests. Its only argument is request_key
(1–100 ASCII letters/digits/period/underscore/colon/hyphen, first character alphanumeric).
It POSTs exactly tasktests, timeout_seconds30. No command, task selector, path, URL,
cancel, or timeout argument is exposed. Same key repeats are deduplicated by the
existing queue database. Keys are global within that database, including n8n jobs;
use the openclaw- prefix for clarity. Different keys intentionally create new jobs.
Queue receipts are not proof that tests passed; query the recorded job status later.

```powershell
cd D:\Projects\kynly
git pull --ff-only
docker compose cp .\integrations\openclaw\kynly-mcp.mjs openclaw:/home/node/.openclaw/kynly-tools/kynly-mcp.mjs
docker compose cp .\integrations\openclaw\kynly-mcp.test.mjs openclaw:/home/node/.openclaw/kynly-tools/kynly-mcp.test.mjs
docker compose exec openclaw node --test /home/node/.openclaw/kynly-tools/kynly-mcp.test.mjs
docker compose exec openclaw node dist/index.js mcp tools --help
```

Expect6 passing Node tests. Next update the server include-filter and global tool
allowlist using installed CLI options, validate, and restart/reset the session.
Do not remove existing read/status tools or enable tool search. Until both policy
layers allow the new tool, the model should retain only previous connector access.
The private token file is retained; no recopy or display is necessary.
Model submission test will use openclaw-tests-001, one call, reporting the job ID
and recorded status. Retry with the same key must return the same job ID. Then
query status once after worker completion and compare it against the queue record.

## Slate instructions and validated submission

The user confirmed one tests submission, passed/0 on status lookup, and the same
job ID on duplicate submission with openclaw-tests-001. The queued response made
an unsupported notification promise; no notification service is configured.
KYNLY_JOB_RULES.md supplies explicit reporting and retry rules. These instructions
improve behavior but are not a technical authorization boundary; adapter/API
validation and existing tool policy still enforce executable scope.

Install the rules in a managed block in the existing workspace AGENTS.md, preserving
other content and making a timestamped backup before each change. Use fresh chat
for verification. Test one status call and the question whether the connector can
notify later: it should report that notifications are not configured, without
submitting another job. Existing tests-only tools remain unchanged.
Actual Windows sign-in behavior remains unvalidated until a fresh sign-in; the
manual task and background host lifecycle checks passed.
