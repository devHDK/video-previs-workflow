# External generation and budget

## Capability discovery

In this host, discover available Higgsfield MCP (or the user's selected provider) tools, input schemas, upload mechanism, job status/result methods, costs and authentication. Read current official documentation when needed. Tool names, models, supported resolutions, reference counts and prices are deliberately not hardcoded. A public API capability does not establish that this host's MCP exposes it.

Write what you find to `state.generation_profile` when the project starts, before the story or reference breakdown is approved: `route`, `model`, `max_duration_s`, `duration_step_s`, `image_refs`, `video_refs`, `resolution`, `unlimited` and `evidence` (the tool contract, the user's screenshot or their words). For a web app the user reads these off their screen, so ask once, early. The gate requires the model and both duration values, and rejects a shot, or a take covering several shots, that is longer than `max_duration_s`. An action the source or story plays without a cut is one take whenever it fits that limit; do not split it for convenience.

Record the model's actual output duration for each requested duration (a request for 3 s may return about 4 s) and set previs shot lengths to fit, so editing trims rather than retimes.

Distinguish character reference, style reference, start/end frames and motion/control video. They are not interchangeable inputs. Composition comes from the approved start keyframe: motion-control and motion-transfer inputs carry motion, not set, framing or camera height, and a character sheet on a plain background leaves the model to invent the scene. A chat attachment or local path is not automatically available to a remote provider: upload using its supported method and verify resulting asset role/handle before submission. Media the provider generated in this project is passed by its job ID when the tool accepts one; upload only files that exist only locally (previs guides, edited copies). If the connected tool cannot ingest the approved previs, explain the gap and propose a supported path; do not quietly claim motion transfer using only a text prompt.

If tools/auth are absent, finish available local preparation and supply a precise handoff of files, roles, settings and pending actions. Label generation incomplete. Do not invent a successful submission or replace the user's provider without agreement.

## Job-wide estimate

Before the first paid call, present:
- Scope: images, voices, shots, required lip sync and optional music.
- Proposed models and output settings from current tool contracts.
- Estimated cost range and conservative per-call maximum/reservation.
- Total cap with explicit unit, total attempt limit (including failed/quality-rejected attempts), and included revisions. `attempts_used` counts paid submissions only; zero-quote manual takes are tallied in `budget.manual_takes` and never reach the limit.
- One fix loop: one appearance image regenerated plus every keyframe once. A defect found in the first take is usually fixed there, so a budget without this loop runs out at the first retake.
- Keyframe images per shot and a retry reserve: `budget.retry_reserve` ≥ `budget.max_shot_quote`, so at least one retry of the most expensive shot stays affordable. First submissions may not spend the reserve; only jobs with `retry_of` may.
- What remains unknown and which stages cannot yet be quoted.

If a maximum charge cannot be established, do not submit under a claimed bounded budget. Obtain a bounded quote or ask for a revised arrangement. Record user approval once; it survives host changes through project state. Reconcile the final-shot estimate after image approval against the already authorized cap. Request only new scope or increased limits when needed.

## Shot execution

Build a per-shot request from approved story/action, camera, asset bindings, start keyframe, control clip and required events. On the reference-led route, when the tool accepts a motion/control video, use the shot's reference clip (`reference/vNNN/sNN.mp4`) for motion and the approved start keyframe for composition; otherwise use the previs render. Uploading reference footage to a provider needs the user's agreement. Keep entity IDs stable. Fit the actual model schema; do not paste a universal canonical prompt. Save the request and inputs before submission, recording the keyframe hash as `start_frame_sha256` and `retry_of` for retries. Run `python3 scripts/gate.py submit state.json job.json` and submit only when it prints `OK`. Use the state/lock protocol in project-state.md.

Before the first take, review its risks with the user: list what the take contains from fast crowd motion, many faces, small hand props and framing that changes mid-take, with the mitigation for each. Write the prompt to these rules, which fixed the first take of a 25 s single-take production (a mask that flew onto a face, smeared crowd faces, a missing spray):
- Take each prop's `origin`, `holder` and `exit` from the shot's `props` and narrate them in that order.
- Every action names who does it, with what, and where the object comes from ("takes a folded mask from her robe pocket, unfolds it with both hands, lays it on from the forehead down").
- A group (the shot's `group_motion`) is written by its `sync`. `unison`: pose-then-hold beats ("bow deeply and freeze; straighten and pat both cheeks three times"). `ragged`: the same beats with their times, each member up to `spread_s` earlier or later than the ones beside it, with their own depth, angle and hand position, and the poses still readable at every beat to the end of the take. Neither is written as continuous frenzy.
- One action per time window, and say what must stay visible and sharp.
Reference images do not pin mid-take framing: the model may pull back further than a mid-take keyframe shows. When it drifts, crop in the edit or retake.

Sequence takes: consecutive shots in the same location (they share a set role and no other location cuts between them) are best generated as one continuous take, because separately generated takes started from independently composed keyframes do not join inside one location: positions and camera jump at the cut (observed on ep01-v2, s02→s03). Start the take from the first shot's approved keyframe. Add each later shot's approved keyframe as an image reference ("how the scene looks at T s"), use the concatenated previs clips as the motion reference, and offset every event time by the durations of the earlier shots. Name the fixed positions of recurring props ("tent left of the fountain"), because a prop that rises mid-take is otherwise placed at random. Request a duration that covers all the covered shots within `max_duration_s` (web apps often have a 4 s minimum); when the total fits, generate them as one take. Record the job with `shots` (the covered shot ids in order, starting with `shot`); `gate.py submit` checks every covered shot. Shots at a location change stay separate takes, so cuts fall only where the location changes. This route is new: inspect the take's internal timing against the previs before relying on it.

Poll/retrieve using the provider's returned job ID, respecting its polling guidance. Download and inspect the actual output. Link results to request and input versions. A tool reporting success does not establish visual quality. Retry only failed requirements within the agreed cap/attempt limit. Reuse successful shots; if a shot needs changed direction or appearance, reopen the relevant creative approval.

## Manual route

Some allowances apply only when a person generates in the provider's web app (Higgsfield plan Unlimited, for example: MCP, CLI and other automated generations always deduct credits). When a job could use one, show the MCP quote beside the expected web charge (0 under Unlimited) and let the user choose `route: manual` or `mcp` per job. Never automate the web app to reach a web-only allowance: no browser automation, scripted clicks or reused session cookies.

For a manual job, write `job.json` with `route: "manual"`, `provider`, `model` as the web app names it, `settings`, `inputs[]` (`path`, `slot`, `purpose`), `prompt` and `output` (`kind`, `notes`). Take slot names from the user's screen or screenshot; do not hardcode them. `request.md` tells the person to check that every reference tag in the pasted prompt links to its uploaded file (a tag left as plain text means the model never saw that image) and to say how many images and videos the app accepted; record both in `generation_profile` at the first ingest. Video jobs pass `gate.py submit` first, as on MCP. Run `handoff.py pack job.json handoff/<stage>/<request_id>` from the project directory (one folder per stage: `handoff/assets/`, `handoff/keyframes/`, `handoff/videos/`, so the person sees what each batch is for), record the printed input hashes and set the job to `handed_off`. After the user drops one result into `output/`, run `handoff.py ingest` to the normal destination (`shots/<shot>/<attempt>/source.mp4`, the keyframe or asset path), record `sha256`, `host`, and `actual_charge` as the user confirms (unknown keeps the reservation), then inspect and approve exactly as for MCP output. A `handed_off` job is unresolved: do not resubmit the same target by another route until it is ingested or cancelled.

On timeout/unknown submission, search provider job history and billing using request ID/time/parameters. Never immediately resubmit from a second host. Stop when budget is exhausted and present the best actual outputs plus unresolved requirements.
