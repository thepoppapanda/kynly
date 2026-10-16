# Kynly

Local AI chat, tools, creative workers, and scheduled automation.

## Verified local baseline

Windows 11 26H2 (user reported); Ryzen 7 9800X3D; 64 GB RAM;
Radeon RX 7900 XTX 24 GB. WSL package 3.0.3.0, Ubuntu and
docker-desktop on WSL 2. Git 2.39.2.windows.1, Docker 29.4.0,
Compose 5.1.2. LM Studio 0.4.26; Blender 5.2.2; Unity 6000.5.6f1.

D: SSD has approximately 1.5 TB free; F: external HDD has 18 TB free.
Qwen model ID: qwen2.5-7b-instruct. Local chat, automatic function
selection, validated local addition, and tool-result follow-up passed.
Mistral 7B v0.3 chat passed but tool calling remains unresolved.

## Stage 3: n8n and PostgreSQL

Run from the repository in Windows PowerShell with Docker Desktop running:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\init-local.ps1
git check-ignore .env
docker compose config --quiet
docker compose pull
docker compose up -d --wait --wait-timeout 300
docker compose ps
Invoke-WebRequest -UseBasicParsing http://localhost:5678/healthz/readiness
```

Stop if a command fails. Open http://localhost:5678 and create your local
owner account. Both services should report healthy; readiness should return 200.
The owner account is separate from the generated database password.
Do not paste .env or unredacted rendered Compose configuration into chats.

n8n is pinned to 2.43.5 (the stable version listed by its docs when prepared).
PostgreSQL is pinned to major 16; its minor tag can advance on pull.
The user validated this stack on the target PC on October 14, 2026; results below.

### Persistence test

Create and save a workflow named Kynly persistence test with a Manual Trigger.
Run it once. Run `docker compose down`, then
`docker compose up -d --wait --wait-timeout 300`.
Verify the account and workflow remain. Never add --volumes / -v to down
unless deliberately deleting the data.

### Schedule test

Create a separate Schedule Trigger workflow every minute, followed by Edit
Fields setting marker=kynly-schedule-test and timestamp={{ $now.toISO() }}.
Save and publish/activate it as the UI requires. Close the browser for three
minutes, reopen it, and verify successful executions with increasing timestamps.
Then disable the test schedule. Sleep/offline catch-up is not implemented here.

### Storage and operation

Data uses Docker-managed named volumes, NOT D:\KynlyData.
The repository's drive does not determine Docker volume placement.
Check Docker Desktop's disk image location before accumulating substantial data.
The database has no published host port; n8n binds only to Windows loopback.
Restart policies work while Docker runs; boot-before-login is not configured.
Closing the browser does not stop services.

Keep .env unchanged after initialization; changing the password does not
change an existing database password, and losing the encryption key can make
stored n8n credentials unreadable. Back up the database, n8n volume, and .env
together before upgrades. Archive paths alone are not a backup procedure.

For failures: `docker compose logs --tail 80 n8n postgres`.
Review logs for secrets before sharing.
LM Studio container networking passed. OpenClaw baseline is verified below; GPU workers remain later stages.
No Docker socket or host project folders are mounted into n8n.

## Progress checkpoint — October 14, 2026

Tests were performed by the user on the Windows PC and reported in the setup session.

| Stage | Result |
| --- | --- |
| 1: Prerequisites | Passed: Ubuntu and docker-desktop use WSL 2; Docker hello-world succeeded |
| 2: Local inference | Passed: Qwen chat API, automatic tool selection, argument validation, local execution, and tool-result follow-up |
| 3: Persistent automation | Passed: n8n and PostgreSQL healthy; account/workflow survived container recreation |
| 3: Background schedule | Passed with browser closed; test workflow unpublished afterward |
| 3: Container networking | Passed: host.docker.internal:1234/v1/models returned Qwen |
| 3: Workflow inference | Passed: n8n HTTP Request to LM Studio returned expected response |
| 4: OpenClaw | Not started; next session begins here |

The manually created test workflows currently live in the local n8n database.
They have not been exported or committed to this repository. Local secrets,
database contents, and owner-account details are not committed.

### Earlier status-only checkpoint — October 15, 2026

OpenClaw 2026.10.3 (59cb447) is deployed through Compose with image digest
`sha256:70b8dbd23f8d27a206f43f9828fdebc87289e50d56dc55177354c9270d764026`.
Its external state volume is `kynly_openclaw_data`; Windows access is bound
to `127.0.0.1:18789`. Token authentication and browser connection passed.
Gateway restart, reconnection, and retained conversation were observed.

#### Working configuration (local state, not committed)

- LM Studio loaded context: 16384.
- Provider: `custom-host-docker-internal-1234`.
- Model: `qwen2.5-7b-instruct`.
- Model metadata: `contextWindow: 32768`, `contextTokens: 16384`, `maxTokens: 512`.
- `agents.defaults.params.maxTokens: 512`.
- `tools.profile: "minimal"`, `tools.toolSearch: false`.
- `tools.allow: ["session_status"]`; no global deny/alsoAllow values.
- Do not set `agents.defaults.contextTokens`: this release rejects that retired key.
- Local configuration backups exist as `openclaw.json.before-chat-repair`
  and `openclaw.json.chat-only-working`. These include secrets and must remain private.

Earlier testing encountered repeated tool operations (319 operations, 47 blocked)
and stale replies. The original provider metadata incorrectly advertised 128000
tokens while LM Studio loaded 8192. Multiple settings were changed during recovery;
the individual root cause has not been isolated. A 512-token cap limits each
model response; it is not a total tool-call/turn limit. General agent reliability
and loop limits are not yet verified.

#### Latest verified test

In a fresh dashboard session:
1. Asked for one session_status call and the current model.
2. Received the correct model report (user measured 6 seconds, 76 tokens).
3. Asked for 12 minus 5 without tools; received 7 (1 second, 2 tokens).
4. Session-specific trajectory confirmed exactly one session_status call returning
   ok in the first turn, and no tool calls in the second.

Use the exact dashboard session key when inspecting traces. Unscoped tail output
can select the main session instead of the conversation being tested.

```powershell
docker compose exec openclaw node dist/index.js sessions --agent slate --active 15 --json
docker compose exec openclaw node dist/index.js sessions tail --agent slate --session-key "<dashboard-session-key>" --tail 40
```

Current milestone: restricted OpenClaw chat/status baseline passes. Stage 4's
scoped file-access and denied-access checks remain pending, followed by restart
verification of the final scoped policy. Keep the one-tool allowlist until that
test is prepared. Do not restore full tool access.

Configuration validation before startup:
```powershell
docker compose run --rm -T --no-deps openclaw config validate
```

Compose files alone do not reproduce onboarding or these local policy settings
on a fresh machine; a version-validated provisioning script is still needed.
No credentials, state database, or local configuration backups are committed.

### Verified n8n-to-LM Studio request

HTTP Request node: POST
`http://host.docker.internal:1234/v1/chat/completions`.
JSON body, timeout 120000 milliseconds:

```json
{
  "model": "qwen2.5-7b-instruct",
  "messages": [
    {
      "role": "user",
      "content": "Reply with exactly: Kynly workflow inference is working."
    }
  ],
  "temperature": 0,
  "max_tokens": 60,
  "stream": false
}
```

Expected result: `choices[0].message.content` contains the requested sentence.
This is a manual workflow; publication is not needed.

### Remaining milestones

4. OpenClaw installation inspection, deployment, local model and scoped tool test.
5. Container development worker and separate Windows worker.
6. Persistent resource-aware job coordinator (one heavy GPU job and up to two light jobs).
7. Bounded research with saved source evidence.
8. Email search, drafting, and separately controlled sending.
9. Queued image generation and GPU memory release checks.
10. 3D generation, Blender inspection, and Unity worker integration.
11. Studio UI independent of background execution.
12. Repeatable installer, repair, backup/restore, and startup verification.

## Latest checkpoint — October 15, 2026, 21:03 America/Indianapolis

Stage 4 scoped read baseline now passes; restart verification of this final
configuration remains pending. Earlier checkpoints above are historical.

### Current local configuration

- LM Studio serves `qwen/qwen3-14b` (Qwen3-14B Q4_K_M) with API-confirmed
  loaded context 16384; native maximum 32768.
- Last selected LM Studio runtime: `llama.cpp-win-x86_64-amd-rocm-avx2@1.22.2`.
- OpenClaw provider remains `custom-host-docker-internal-1234`, pointing to
  `http://host.docker.internal:1234/v1`.
- Primary model is that provider's `qwen/qwen3-14b`, retaining its local auth profile.
- Model metadata: contextWindow 32768, contextTokens 16384, maxTokens 512.
- Per-model parameters: temperature 0.7, topP 0.8, maxTokens 512.
- tools.profile=coding; tools.allow=[session_status, read];
  tools.toolSearch=false; tools.fs.workspaceOnly=true.
- tools.loopDetection.enabled=true; agents.defaults.timeoutSeconds=60.
- Test prompts use /no_think.
- Runtime exposed 3 tools despite the two-name allowlist: an earlier export
  identified skills_read in addition to read and session_status. Do not treat
  the allowlist as proof of the complete effective tool surface.
- A general job coordinator/concurrency limit has not yet been implemented.

### Evidence from the final scoped-read session

User reported: one read returned exactly
"Inventory: 23 brass washers. Inspection code: R8Q2-P6M5."
in 16 seconds / 62 tokens.

For the harmless outside-workspace file, the assistant reported a sandbox-root
path denial. The same session's trajectory then confirmed:
- first turn: one read call, read ok, completed successfully;
- second turn: one read call, read error, completed successfully;
- no repeating tool sequence in either turn.

This supports the scoped boundary test. The final trace redacts arguments and
error details; the exact outside-path error payload was not exported in this
session. These two cases do not constitute a complete sandbox/security audit.

### Diagnostic findings and limits

Earlier READ_OK-style fixtures produced refusals, fabricated contents, and in
some runs tool loops. A redacted export established that the intended file was
read successfully and its marker was recorded, while the final answer invented
different text.

Direct mock-tool tests reproduced incorrect answers with Qwen2.5 and Qwen3 in
LM Studio and with the same Qwen3 GGUF in standalone llama.cpp. A meaningful
prose result ("Inventory: 37 copper gears. Inspection code: N7P4-Z2Q9.")
was then reported accurately through both standalone llama.cpp and LM Studio.

The marker resembling a success acknowledgment is a plausible contributor,
not a proven complete root cause. Model, context, tool policy, prompt, and
runtime changes were made during diagnosis, so no single fix was isolated.
Do not describe the earlier failures as a confirmed LM Studio or Vulkan bug.

Standalone llama 0.6.0-dev, build 11630 / commit 6868a52cb, was tested on
127.0.0.1:8081 using the existing GGUF. It is a diagnostic comparison only;
Kynly still uses LM Studio. Keep only the intended GPU model server loaded.

Loop detection and the 60-second timeout passed configuration validation.
Their actual ability to terminate a runaway has not been demonstrated in the
final setup. A 512-token response cap is not a total run/tool-call budget.

### Next test

Restart OpenClaw; reconnect and create a fresh dashboard session. Repeat the
meaningful workspace read and outside-workspace denial, then one no-tool
arithmetic follow-up. Inspect the exact session key's trajectory.
If these pass, close Stage 4's initial scoped-read milestone and begin Stage 5
with isolated development workers. Do not enable shell/write tools on this
agent as part of that transition.

All onboarding credentials and live policy settings remain in the local
OpenClaw volume, not in Git. Provisioning scripts must eventually reproduce
the validated configuration without copying secrets.
