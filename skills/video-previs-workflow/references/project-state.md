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
- `story`: path, sha256, approval status, evidence and time (`approved_at`). Required before previs, unless `reference` is approved.
- `reference`: the same fields for a reference breakdown (`reference-vNNN.json`) on the reference-led route.
- `previs`: spec_path/hash, render_path/hash, approval status, approved revision, evidence and time.
- `assets[]`: role_id, source, original_path/hash, working_path/hash, `sha256` (the working file bound to shots), version, approval status/evidence/time, shot_ids.
- `shots[]`: id, frames, `required_events` (mandatory, nonempty), `object_roles` (every previs object id → role_id or `null`), `asset_bindings` (role_id, version, sha256), `keyframes[]` (kind `start`/`end`, path, sha256, approval), previs revision, selected output, stale reason, QA status.
- `budget`: currency or credit unit, approved scope, cap, max_attempts, `retry_reserve`, `max_shot_quote`, approval evidence, settled cost, reserved cost, attempts used. State whether quote includes image, voice, video, lip-sync, and paid retries.
- `jobs[]`: local request ID, `route` (`mcp` default or `manual`), host, shot/asset target, tool/model, parameters, reference hashes, `start_frame_sha256`, `retry_of` for retries, quote with timestamp, reservation, submitted_at, provider_job_id, status, actual charge, output paths, error/recovery evidence.
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

These are orchestration instructions, not a payment firewall: bundled scripts do not submit jobs or enforce provider-side credit limits.
