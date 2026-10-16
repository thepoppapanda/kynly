# Stage 5: isolated Python development worker

Status: source prepared; Docker build and Windows filesystem behavior require
target-PC testing. Python sample tests are also run separately during preparation.

The Compose dev-worker service is opt-in through the development profile.
It mounts only examples/worker-sandbox at /workspace, runs as UID/GID 10001,
has no network or Docker socket, and receives no service credentials.
The image filesystem is read-only; /tmp is temporary and /workspace is writable.
CPU limit 2, RAM 2 GiB, process limit 128. The default test command has a
30-second timeout; interactive shells/custom commands have no automatic
wall-clock budget. This is a development fixture, not the job coordinator.

From D:\Projects\kynly with Docker Desktop running:

```powershell
git pull origin main
docker compose config --quiet
docker compose --profile development build dev-worker
docker compose --profile development run --rm --no-deps dev-worker
$LASTEXITCODE
```

Expected: four tests pass; exit code 0. Image build needs network access;
the running worker does not. The Python base image uses a moving patch tag;
a tested image digest should be recorded before deployment packaging.

## Check failures propagate

```powershell
docker compose --profile development run --rm --no-deps dev-worker python -c "raise SystemExit(7)"
$LASTEXITCODE
```

Expected: 7. This intentional failure must not be reported as successful.

## Edit and persistence check

```powershell
docker compose --profile development run --rm --no-deps dev-worker sh
```

Inside the shell:

```sh
id
printf '%s\n' 'Created inside the Kynly development worker.' > worker-note.txt
cat worker-note.txt
exit
```

Back in PowerShell, create a NEW container:

```powershell
docker compose --profile development run --rm --no-deps dev-worker cat worker-note.txt
Get-Content .\examples\worker-sandbox\worker-note.txt
```

Expected: both show the same text. The test note is ignored by Git.
If writes fail, record the permission error; do not switch the worker to root.

## Meaningful test-failure check

In your Windows editor, temporarily change the batching function to discard its
last batch. Rerun the default worker tests: they should fail with a nonzero exit.
Undo that edit and rerun: tests should pass. Inspect git diff to ensure the
temporary edit was removed. No agent is connected yet.

## Boundaries and next steps

Only this sample folder is mounted, not the repository root or other projects.
A container can read its own image files; isolation here means host files and
service secrets are not mounted. This does not sandbox mutually hostile users.

Validate test success/failure, non-root execution, write persistence, and limits
before adding agent dispatch. Later tasks: per-job worktrees/workspaces, timeouts
for arbitrary commands, cancellation, structured logs, request IDs, and a Windows
worker for native development applications. OpenClaw's current allowlist stays
unchanged; do not mount the Docker socket into it.
