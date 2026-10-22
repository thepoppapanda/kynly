# Kynly completion tracking

`kynly-completion-tracking.json` is based on the user's exported, manually tested
workflow. It stays inactive and uses a Manual Trigger. It submits a Windows notification after Result Summary.

## Import

1. Import the JSON as a separate workflow in n8n; leave it unpublished.
2. On Submit Job, Check Job, and Desktop Notification, select the existing Header Auth credential
   for the Kynly API. Credential IDs/names were removed from the repository copy.
   No token should be pasted into node parameters or workflow JSON.
3. Keep the API and watch/background worker running. URL is
   http://host.docker.internal:8787, already validated from n8n on this PC.
4. The saved request key is n8n-desktop-001, retained for repeatable diagnostics.
   Reusing it returns the original job; to test a NEW execution change it to a fresh
   key such as n8n-desktop-002. Reuse that new key when retrying the same submission.
5. Execute the whole workflow and inspect Result Summary. Normal tests should
   report outcomepassed, job_statuspassed, exit_code0.

## Export review and adjustments

No embedded API token was found. Removed instance/version/workflow metadata,
credential references, empty pin data/tags/groups, and the Wait webhook identifier.
Preserved node IDs, names, versions, Code logic and connections so references and
branch wiring remain intact. Removed an unrelated default Code-node comment.

The supplied export omitted explicit HTTP timeouts and Wait parameters. The
repository template sets job HTTP request timeouts to5000ms and the notification timeout to30000ms with node retryoff,
and Wait to After Time Interval,5seconds. These are intended configuration
adjustments, not claims that the original defaults were known or defective.
If continuing in the existing workflow rather than importing, set these fields
there manually. Keep generic Header Auth on BOTH HTTP nodes.

## Bounds and semantics

Tracking Setup runs once. Its deadline is Date.now()+120000 and max_checks12.
Check Job -> Evaluate Status -> If true -> Wait -> Check Job is the only loop;
Submit Job and Tracking Setup are never repeated by it. Evaluate Status uses
its zero-based run index+1 for the number of checks.

All terminal job statuses end monitoring. Running/queued status continues until
12 checks or the next five-second wait would reach the deadline. The deadline is
a decision bound, not a hard end-to-end timer: an in-flight HTTP request or n8n
scheduling delay can cross it. HTTP calls have their own5second bound. The
monitoring deadline does not cover initial submission time or cancel the job.
HTTP errors stop the execution rather than silently resubmitting or polling them.
No error-notification branch is configured yet.

Result Summary separates passed, job_unsuccessful and monitoring_limit_reached.
job_finished means a terminal status was observed, including job failure, timeout,
cancellation or interruption. It does not mean passed. Monitoring-limit results
report the last observed status; the job can continue independently.

## Validation

The user confirmed existing n8n paths: passed job, repeated waiting until a20second
probe timeout, max_checks2 while the job continued, a12second deadline, and the
restored normal result summary. These checks predate the explicit parameter
normalization in the repository template. Re-import and end-to-end validation of
the adjusted template remain to be done on the user's PC.

Local check:

```text
node --test integrations/n8n/completion-tracking.test.mjs
```

Seven tests execute the actual exported Code snippets in Node VM contexts and check
HTTP/Wait settings and key loop connections. They do not emulate n8n's scheduler,
credential manager, task runner or import engine. Current export uses HTTP Request
node4.5, Code2, If2.3 and Wait1.1; retain these installed-version formats.

## Desktop notification checkpoint

The user confirmed end-to-end passed/0 summary -> submitted_to_windows -> visible
banner, then duplicate true without another banner on repeating the notification
node. The second uploaded export adds the authenticated Desktop Notification node
after Result Summary and stays unpublished. No embedded API token was found.
Credential references and instance metadata were removed as before. This export
also omits explicit request timeouts and Wait settings; the repository copy
normalizes them as documented above. Verify those fields in the live workflow.

The API records at most one attempt per job/outcome/status; submitted_to_windows
is not proof of visible delivery. This workflow monitors only its own submitted
job. It does not automatically monitor unrelated OpenClaw jobs. Failure and
monitoring-limit banners remain pending Windows end-to-end validation. Keep
normal limits max_checks12/deadline120000ms and tasktests after test changes.
