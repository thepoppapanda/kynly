# Isolated research agent: initial validation

Slate job controls and optional desktop alerts passed. Fetching example.com and
Python venv documentation worked. DuckDuckGo returned real results once under a
search-only policy but initially errored; the model retried against instruction.
Other searches timed out before any tool call. Subsequent isolated-agent tests passed as recorded below; consistent reliability has not yet been established.

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

## Authentication correction

Research was created in /home/node/.openclaw/workspace-research using the same
Qwen3 14B provider as Slate. Its first model reference pinned Slate's saved login,
which was unavailable to the new agent. The applied correction set
agents.defaults.authInheritance.agentId to slate and research.model to
custom-host-docker-internal-1234/qwen/qwen3-14b without the @saved-login suffix.
This defines the default credential-inheritance owner for secondary agents;
it is not a copy of credential values or expanded tool permission.

The research-specific tools configuration is profile coding,
allow [web_search, web_fetch], toolSearch false, loopDetection enabled.
Slate remains default and its job-control allowlist was restored. Effective
tool-policy behavior beyond the observed research calls is not exhaustively audited.

## Observed results on the user's PC

| Check | Result | Time |
|---|---|---:|
| Research READY after authentication fix | Responded READY | 35 seconds |
| Search official Python venv documentation | One search, relevant Python sources | 11 seconds |
| Fetch official Python venv page | One fetch, accurate summary | 9 seconds |
| Combined Windows venv question | Exactly one search and one fetch, sourced answer | 29 seconds |

The combined answer used python -m venv tutorial-env and the Command Prompt
activation command tutorial-env\\Scripts\\activate. For PowerShell activation use
.\\tutorial-env\\Scripts\\Activate.ps1. The source was the official Python tutorial.
The user confirmed both tool-call counts. These tests fit the unchanged 60-second
agent timeout but are a small initial sample, not a reliability benchmark.

A screenshot shows OpenClaw Sources cards with site icons. Copied responses include
unwanted image labels. UI/copy formatting is a plausible cause, but the raw model
output was not inspected to prove it. No further prompt change was made for that.

## Remaining boundaries

DuckDuckGo is an experimental unofficial HTML-based provider; provider errors were
observed. Model stalls and a 35-second READY response remain known concerns.
Do not attribute all earlier timeouts to one proven root cause or claim the separate
agent eliminates them. Keep only the intended Qwen model loaded at context16384
during baseline tests. Stop on tool errors, respect the requested call budget,
and distinguish retrieved-page evidence from search snippets.

No research scheduling, saved-report pipeline, Slate-to-research delegation,
email access, browser automation, or research job notifications are configured.
The agent is currently used interactively through its own chat.
