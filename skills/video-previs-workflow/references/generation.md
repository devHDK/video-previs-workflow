# External generation and budget

## Capability discovery

In this host, discover available Higgsfield MCP (or the user's selected provider) tools, input schemas, upload mechanism, job status/result methods, costs and authentication. Read current official documentation when needed. Tool names, models, supported resolutions, reference counts and prices are deliberately not hardcoded. A public API capability does not establish that this host's MCP exposes it.

Distinguish character reference, style reference, start/end frames and motion/control video. They are not interchangeable inputs. A chat attachment or local path is not automatically available to a remote provider: upload using its supported method and verify resulting asset role/handle before submission. If the connected tool cannot ingest the approved previs, explain the gap and propose a supported path; do not quietly claim motion transfer using only a text prompt.

If tools/auth are absent, finish available local preparation and supply a precise handoff of files, roles, settings and pending actions. Label generation incomplete. Do not invent a successful submission or replace the user's provider without agreement.

## Job-wide estimate

Before the first paid call, present:
- Scope: images, voices, shots, required lip sync and optional music.
- Proposed models and output settings from current tool contracts.
- Estimated cost range and conservative per-call maximum/reservation.
- Total cap with explicit unit, total attempt limit (including failed/quality-rejected attempts), and included revisions.
- What remains unknown and which stages cannot yet be quoted.

If a maximum charge cannot be established, do not submit under a claimed bounded budget. Obtain a bounded quote or ask for a revised arrangement. Record user approval once; it survives host changes through project state. Reconcile the final-shot estimate after image approval against the already authorized cap. Request only new scope or increased limits when needed.

## Shot execution

Build a per-shot request from approved story/action, camera, asset bindings, control clip and required events. Keep entity IDs stable. Fit the actual model schema; do not paste a universal canonical prompt. Save the request and inputs before submission. Use the state/lock protocol in project-state.md.

Poll/retrieve using the provider's returned job ID, respecting its polling guidance. Download and inspect the actual output. Link results to request and input versions. A tool reporting success does not establish visual quality. Retry only failed requirements within the agreed cap/attempt limit. Reuse successful shots; if a shot needs changed direction or appearance, reopen the relevant creative approval.

On timeout/unknown submission, search provider job history and billing using request ID/time/parameters. Never immediately resubmit from a second host. Stop when budget is exhausted and present the best actual outputs plus unresolved requirements.
