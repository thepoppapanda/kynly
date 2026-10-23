# Isolated research-agent diagnostic checkpoint

Slate job controls and optional desktop alerts passed. Fetching example.com and
Python venv documentation worked. DuckDuckGo returned real results once under a
search-only policy but initially errored; the model retried against instruction.
Other searches timed out before any tool call. This is not yet reliable research.

Diagnostics: simultaneous Gemma27B/Qwen14B loading and Qwen context8192 were found.
With only Qwen loaded at16384, READY improved from46sec to10sec. Fetch took11sec
and27sec. Later search still stalled at60sec before a call. A small direct LMStudio
tool-call request succeeded. Reducing OpenClaw's tool surface allowed a search
but did not reliably eliminate timeouts. Exact causes remain unresolved. Slate's
allowlist was restored; its known job lookup passed/0 in27sec.

Installed agents add supports workspace/model/non-interactive. Current agent
slate remains default. Create research using the same configured model, without
channel bindings or changing Slate's workspace. Configure per-agent allowlist
web_search/web_fetch before use. Do not increase the60second timeout or load a
second large model as a workaround. Research and Slate share one model runtime:
separate agent/workspace is not independent inference capacity or process isolation.

The workspace installer writes ONLY /home/node/.openclaw/workspace-research,
backing up starter files before replacing them with short instructions. It archives
BOOTSTRAP.md to avoid first-run identity interviews. It does not copy Slate's job
rules or files. No filesystem/exec/job tools are granted to research. Existing
network/tool safety policy still applies. Prompt instructions are behavior guidance,
not a replacement for enforced tool policy.

Pending checks: actual creation output, config validation, effective tool surface,
auth/provider access, fresh READY timing, one search with no retry, and one fetch.
Do not claim this solves timeouts until measured. Search provider reliability and
model prompt-processing costs must remain separate findings.
