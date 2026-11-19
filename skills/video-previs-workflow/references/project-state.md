# Resumable project records

Keep production data in a user-selected project directory, outside the installed skill. Suggested layout:

```
brief.md
state.json
scene-v001.json
inputs/                  # preserved originals
previs/v001/             # blend, PNG, MP4
assets/<role>/<version>/
shots/<shot>/<attempt>/
audio/
edit/                    # manifest, subtitles, mixed audio
output/
qa.md
```

Use project-relative paths and content hashes. Do not write secrets into records. A provider asset handle is not a replacement for the local original. When moving hosts, verify files and permissions, then refresh expired provider uploads.

## State contract

Maintain these fields (JSON or equivalent structured text):

- `project_id`, `revision`, `stage`, `updated_at`, `active_host`.
- `output`: width, height, fps, total_frames, audio/subtitle requirements.
- `generation_profile`: route, model, `max_duration_s`, `duration_step_s`, image_refs, video_refs, resolution, unlimited, evidence. Recorded before the story or reference is approved.
- `story`: path, sha256, approval status, evidence and time (`approved_at`). Required before previs, unless `reference` is approved.
- `reference`: the same fields for a reference breakdown (`reference-vNNN.json`) on the reference-led route.
- `previs`: spec_path/hash, render_path/hash, approval status, approved revision, evidence and time.
- `assets[]`: role_id, `kind` (`character`, `prop` or `set`), source (`generated`, `existing` or `footage`, with `origin` for a footage crop: clip, time, area), original_path/hash, working_path/hash, `sha256` (the working file bound to shots), version, approval status/evidence/time, shot_ids.
- `shots[]`: id, frames, `view` (one of the look's `camera.views`; `view_reason` when it is outside them), `no_previs` (the reason, for a close insert or POV detail that is not in the previs spec; it then needs `frames`), `required_events` (mandatory, nonempty), `object_roles` (every previs object id → role_id or `null`), `props` (each prop role → `origin`, `holder`, `exit`, `count`: how many exist in the whole take, `states`: `{t, where}` for each place it is held from the first frame), `prop_results` (prop role → `result`, `evidence`: its count read off the take), `group_motion` (each role with five or more figures → `sync` `unison`/`ragged`, `spread_s` for ragged: seconds a member may lead or lag, half the measured 10-90 % width; after generation `measured_s`), `unlisted_motion` (`{t, decision}` for a previs turn, direction change or stop the reference does not list), `event_results` (required event → `result`, `evidence`), `asset_bindings` (role_id, version, sha256), `keyframes[]` (kind `start`/`end`, or kind `reference` with `previs_frame` for a mid-take state image; path, sha256, approval), previs revision, selected output, stale reason, QA status.
- `review_notes[]` on an asset or keyframe: `note`, `resolution` (`fixed` or `accepted`) and `evidence` (the new version, or the user's words). An approved record may not hold an open note.
- `continuity[]`: role_id, `keyframe_sha256` (shot → hash of the approved start keyframe reviewed), approval, evidence. Required for every role used by two or more shots.
- `budget`: currency or credit unit, approved scope, cap, max_attempts, `retry_reserve`, `max_shot_quote`, approval evidence, settled cost, reserved cost, attempts used (paid submissions only) and `manual_takes` (zero-quote manual jobs, not limited). State whether quote includes image, voice, video, lip-sync, and paid retries.
- `jobs[]`: local request ID, `route` (`mcp` default or `manual`), host, shot/asset target, `shots` for a sequence take (covered shot ids in order, beginning with its shot), tool/model, parameters, reference hashes, `start_frame_sha256`, `retry_of` for retries, quote with timestamp, reservation, submitted_at, provider_job_id, status, actual charge, output paths, error/recovery evidence.
- `handoff`: blockers, next unpaid action, next paid action, unresolved jobs, unverified outputs.

Budget approvals and creative approvals are separate. Never fill an approval record on behalf of the user without conversation evidence.

## Submission state machine

`prepared -> reserved -> submitting -> running -> succeeded | failed | cancelled`

Manual route: `prepared -> reserved -> handed_off -> succeeded | failed | cancelled`. A `handed_off` job is unresolved like a running one.

Any interruption after submission may become `unknown`; it is not a terminal failure. Persist a unique local request ID and reserve the maximum credible charge **before** submission. Store provider job ID as soon as returned. A failed or rejected attempt still consumes an attempt and may consume credits. Resolve actual billing before releasing a reservation.

`available = cap - settled - unresolved reservations`. Move a reservation into settled cost when reconciled; do not count it twice. If exact billing is unavailable, keep a conservative reservation. Do not estimate unknown charges as zero.

Example: cap 100, settled 45, unknown job reservation 40 leaves 15 available. A 40-credit retry is out of budget and a duplicate risk. Recover through provider history/request metadata; if unresolved, hold paid submissions and continue unpaid preparation. An absent job ID alone is not evidence of failure.

## Single writer and handoff

Only one agent/host may submit jobs for a project at a time. Before modifying state for submission, create a `submission.lock` directory atomically (`mkdir` without `exist_ok=True`), write owner/time/request ID, then reread current state. An existing lock requires inspecting its owner and pending jobs; do not remove it merely because it is old. On confirmed safe handoff, reconcile jobs and explicitly transfer ownership. Write state to a temporary file beside it and atomically replace it. Release the lock after the submission and state update are known; interruption leaves it for recovery.

Do these steps with `state.py` (`lock`, `reserve`, `submit`, `settle`, `approve`, `unlock`; see local-tools.md) instead of editing the file by hand: it takes and releases the lock, keeps `reserved` and `settled` in step with the jobs and writes atomically. Hand edits remain for recovery. `gate.py` still only reads.

These are orchestration instructions, not a payment firewall: bundled scripts do not submit jobs or enforce provider-side credit limits.

### Generation modes and verified delivery

New video jobs store `generation_mode` (`per_shot`, `multi_cut`, or `one_take`), `shot`, ordered `shots`, and the actual requested `duration_s`. Old jobs still open without these fields. For a manual multi-cut job the first input is the combined previs with its editor `tag`. Subsequent inputs each carry a unique image tag and a matching `shot`. Put the previs mention in the base prompt and supply ordered `beats`, e.g. `{"shot":"s02","start_s":2,"action":"She enters the bath."}`. Start at zero. The packer inserts each photo mention and derives the end from the next beat or job duration. Use the validated duration in the web settings.

After ingest and settlement, run `state.py select-takes STATE SELECTION.json`. The file is a list of rows, e.g. `{"shot":"s02","request_id":"v001","source":"takes/v001/source.mp4","start":48,"end":69,"take":"shots/s02/edit.mp4","target_frames":24,"hold_frames":3,"hold_acceptance":"user accepted the grouped preview"}`. The end is exclusive. Keep selections and edit takes at the same fps for this command. Use an exact contiguous source range before padding, retain full source separately, and record event results after choosing the take. Resume from selected_output and open event results.

Before reporting completion run `gate.py delivery STATE MANIFEST MP4`, then `state.py deliver STATE MANIFEST MP4` to record verified file hashes and the delivered stage. Both commands use the assembler's clips/frames manifest and compare it with the approved output and the encoded media. Record an approved target change with its evidence before updating the target. Missing evidence remains open.

For delivery, identify each manifest clip with its timeline `shot` ID (including footage and opening reuse IDs). Keep paths relative to the manifest. The delivery check compares the reference shot order when available, and verifies each selected edit take's path, hash and unaltered frame range.
