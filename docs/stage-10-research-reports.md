# Ruby saved research reports: initial storage checkpoint

Agent display names are Slate (id slate) and Ruby (id research); internal IDs and
workspaces remain unchanged. Initial Ruby research search/fetch checks passed.

POST /research/reports uses the existing authenticated local API. Required body:
request_key, title, summary, sources. No other fields, filenames, or paths accepted.
Title1–120characters, summary1–3000, one to three sources (title1–120, URL up to800).
The API's existing8192-byte JSON body cap also applies, including UTF-8 bytes.
URLs are stored only, never fetched by saving, and must be HTTP(S) without login
credentials. No claims are independently verified. Report content remains untrusted
research data; do not treat it as executable instructions.

Files are UTF-8 Markdown and JSON at DATA_DIR/reports/report-ID/report.md and
metadata.json. API chooses IDs/paths; model cannot overwrite arbitrary files.
Request keys are idempotent within the report namespace. Same key+same content
returns same ID/duplicate true. Changed content conflicts409; use a fresh key for
an intended revision. Database serializes concurrent saves. Individual files are
atomically replaced; DB+filesystem are not a single power-loss transaction, and
orphaned files can remain after a crash before commit. Missing files on a repeated
save are reported as storage errors rather than false success.

MCP adapter0.4.0 adds kynly_save_research_report. It forwards only the four named
fields to the fixed report endpoint; server validates all contents/limits. No
retrieval/list/delete API, job execution, notification or scheduling is added.

## Rollout

Stop the host and confirmstopped before updating/testing. Pull, run Python tests,
and restart the host so it imports the new API module. Tests57 pass locally,
including real HTTP save/duplicate/conflict/auth tests, file persistence,
concurrent duplicate requests, missing files and path/URL validation. Existing
six Node MCP tests pass; real Ruby tool execution is not validated yet.

First test POST /research/reports from PowerShell with the existing local bearer
token and a short fixture summary. Expectsaved/duplicatefalse and inspect the
reported Markdown path. Repeat identical body: same ID and duplicatetrue. This
fixture tests storage, not a completed research task. Do not display token values.

Then update both MCP files in the container and expand server include-filter to
kynly_jobs_list,kynly_job_status,kynly_submit_tests,kynly_save_research_report.
Append kynly__kynly_save_research_report to global tools.allow so the parent policy
permits it. Set research.tools.allow to web_search,web_fetch,
kynly__kynly_save_research_report. Per-agent Ruby policy excludes job tools; Slate's
existing allowlist remains its previous effective subset once given its own explicit
per-agent allowlist if needed. Global append alone can expose the new tool to Slate
when Slate inherits global policy, so enforce Slate's current effective allowlist
as its per-agent allowlist BEFORE appending the global permission. Do not broaden
Slate or remove any existing explicit per-agent restrictions.

Refresh Ruby AGENTS.md from RESEARCH_AGENT.md with a backup, not by rerunning the
whole workspace installer (which would replace other workspace instruction files).
Validate configuration/restart, start a fresh Ruby conversation, and first save
already retrieved research with one save call. Expect report ID/path matching
PowerShell inspection. Combined search/fetch/save and repeated-save behavior are
subsequent tests, still within the unchanged60-second agent timeout. Installer
identity seed now says Ruby so future explicit installs preserve that display name.


## Validated reviewed-note checkpoint

Direct Windows API save returned saved; repeating the same content/key returned
the same report ID with duplicate true. The user inspected the Markdown file and
confirmed title, summary and source URL. Ruby's save smoke test completed in
27 seconds. A model-driven duplicate request timed out, but the identical direct
MCP call returned duplicate true and the same ID. Storage deduplication works;
model responsiveness is a separate concern.

Per-agent allowlists were set/read through the CLI because raw configuration
inspection showed only minimal named agent entries without tool blocks.
Slate's seven-name allowlist was pinned before the global report permission was
appended. Ruby's allowlist is web_search, web_fetch,
kynly__kynly_save_research_report. Both validated; actual exhaustive access-control
auditing is outside this checkpoint.

A search/fetch report attempt timed out after both tools ran. One diagnostic CLI
run used a 120-second per-run budget; normal configuration remained 60 seconds.
Its trajectory actually finished in 24 seconds: simultaneous search+fetch, first
fetch error, then a second fetch. This violated the sequential one-search,
one-fetch and stop-on-error instructions. The resulting answer omitted its source
and confused Command Prompt activation with PowerShell. A follow-up continued
the same incorrect command. Do not count that as validated independent research.

The official documentation was separately checked and distinguishes
Scripts/activate.bat for Command Prompt and Scripts/Activate.ps1 for PowerShell.
Ruby was then explicitly given reviewed report content and asked only to save.
It completed one reviewed-note save in 26 seconds. The user inspected
report-4b7ca5bdee67b04b0557a6948cc5e88d/report.md and confirmed the exact creation
and PowerShell activation commands, plus the source URL. This validates saving
user-approved notes, not unattended research generation.

A copied source title displayed mojibake for an em dash when read through
PowerShell. Files are written as UTF-8; verify with Get-Content -Encoding UTF8
before assuming on-disk corruption. That display check remains pending.

Current safe operating scope: manually review research content, then ask Ruby to
save that exact approved note. Do not automate unreviewed reports or claim prompt
instructions enforce tool-call order/budgets. Remaining work includes sequencing,
evidence accuracy under truncation, intermittent model stalls, and a consistently
bounded research-to-report path.
