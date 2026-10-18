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
