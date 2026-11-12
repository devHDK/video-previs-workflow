# External generation and budget

## Capability discovery

In this host, discover available Higgsfield MCP (or the user's selected provider) tools, input schemas, upload mechanism, job status/result methods, costs and authentication. Read current official documentation when needed. Tool names, models, supported resolutions, reference counts and prices are deliberately not hardcoded. A public API capability does not establish that this host's MCP exposes it.

Record the model's actual output duration for each requested duration (a request for 3 s may return about 4 s) and set previs shot lengths to fit, so editing trims rather than retimes.

Distinguish character reference, style reference, start/end frames and motion/control video. They are not interchangeable inputs. Composition comes from the approved start keyframe: motion-control and motion-transfer inputs carry motion, not set, framing or camera height, and a character sheet on a plain background leaves the model to invent the scene. A chat attachment or local path is not automatically available to a remote provider: upload using its supported method and verify resulting asset role/handle before submission. If the connected tool cannot ingest the approved previs, explain the gap and propose a supported path; do not quietly claim motion transfer using only a text prompt.

If tools/auth are absent, finish available local preparation and supply a precise handoff of files, roles, settings and pending actions. Label generation incomplete. Do not invent a successful submission or replace the user's provider without agreement.

## Job-wide estimate

Before the first paid call, present:
- Scope: images, voices, shots, required lip sync and optional music.
- Proposed models and output settings from current tool contracts.
- Estimated cost range and conservative per-call maximum/reservation.
- Total cap with explicit unit, total attempt limit (including failed/quality-rejected attempts), and included revisions.
- Keyframe images per shot and a retry reserve: `budget.retry_reserve` ≥ `budget.max_shot_quote`, so at least one retry of the most expensive shot stays affordable. First submissions may not spend the reserve; only jobs with `retry_of` may.
- What remains unknown and which stages cannot yet be quoted.

If a maximum charge cannot be established, do not submit under a claimed bounded budget. Obtain a bounded quote or ask for a revised arrangement. Record user approval once; it survives host changes through project state. Reconcile the final-shot estimate after image approval against the already authorized cap. Request only new scope or increased limits when needed.

## Shot execution

Build a per-shot request from approved story/action, camera, asset bindings, start keyframe, control clip and required events. On the reference-led route, when the tool accepts a motion/control video, use the shot's reference clip (`reference/vNNN/sNN.mp4`) for motion and the approved start keyframe for composition; otherwise use the previs render. Uploading reference footage to a provider needs the user's agreement. Keep entity IDs stable. Fit the actual model schema; do not paste a universal canonical prompt. Save the request and inputs before submission, recording the keyframe hash as `start_frame_sha256` and `retry_of` for retries. Run `python3 scripts/gate.py submit state.json job.json` and submit only when it prints `OK`. Use the state/lock protocol in project-state.md.

Poll/retrieve using the provider's returned job ID, respecting its polling guidance. Download and inspect the actual output. Link results to request and input versions. A tool reporting success does not establish visual quality. Retry only failed requirements within the agreed cap/attempt limit. Reuse successful shots; if a shot needs changed direction or appearance, reopen the relevant creative approval.

## Manual route

Some allowances apply only when a person generates in the provider's web app (Higgsfield plan Unlimited, for example: MCP, CLI and other automated generations always deduct credits). When a job could use one, show the MCP quote beside the expected web charge (0 under Unlimited) and let the user choose `route: manual` or `mcp` per job. Never automate the web app to reach a web-only allowance: no browser automation, scripted clicks or reused session cookies.

For a manual job, write `job.json` with `route: "manual"`, `provider`, `model` as the web app names it, `settings`, `inputs[]` (`path`, `slot`, `purpose`), `prompt` and `output` (`kind`, `notes`). Take slot names from the user's screen or screenshot; do not hardcode them. Video jobs pass `gate.py submit` first, as on MCP. Run `handoff.py pack job.json handoff/<request_id>` from the project directory, record the printed input hashes and set the job to `handed_off`. After the user drops one result into `output/`, run `handoff.py ingest` to the normal destination (`shots/<shot>/<attempt>/source.mp4`, the keyframe or asset path), record `sha256`, `host`, and `actual_charge` as the user confirms (unknown keeps the reservation), then inspect and approve exactly as for MCP output. A `handed_off` job is unresolved: do not resubmit the same target by another route until it is ingested or cancelled.

On timeout/unknown submission, search provider job history and billing using request ID/time/parameters. Never immediately resubmit from a second host. Stop when budget is exhausted and present the best actual outputs plus unresolved requirements.
