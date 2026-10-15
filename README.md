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
LM Studio container networking passed; OpenClaw and GPU workers are later stages.
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

### Resume at Stage 4

First inspect any existing Windows OpenClaw installation in PowerShell:

```powershell
Get-Command openclaw -ErrorAction SilentlyContinue |
    Select-Object Name, Source
```

If a command is found, run `openclaw --version` and record the result.
Do not start or overwrite an existing Gateway until its configuration and
deployment location are understood. Decide on a single managed deployment,
then verify local Qwen chat and one harmless tool restricted to a sample folder.

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
