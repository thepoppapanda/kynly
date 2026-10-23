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
