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
These files have not yet been runtime-tested on the target PC.

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
LM Studio container networking, OpenClaw, and GPU workers are later stages.
No Docker socket or host project folders are mounted into n8n.
