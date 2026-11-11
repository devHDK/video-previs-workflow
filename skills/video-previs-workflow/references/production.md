# Direction and appearance

## Intake routes

| Input | Action |
|---|---|
| Reference footage | Obtain accessible local footage, probe it, extract frames around cuts and action changes. Observe camera, composition, actions and timing; list unavailable evidence. |
| Idea or script | Develop a concrete beginning, change, consequence and ending; write dialogue and shot actions. Label creative proposals. |
| Approved storyboard/previs | Reuse the approved revision; fill only missing technical or production details. |

A storyboard panel may be a start, middle or end of one shot; do not equate panel count with generation calls. Preserve the user's chosen medium, tone and audience. Channel strategy and trend research are separate assignments.

Record for each shot: ID, duration in frames, subject IDs, setting, camera, start state, action, end state, required events with target frame windows, dialogue, sound cues and continuity constraints. Put voice timing into previs: measure scratch/approved voice duration and recheck timing when it changes. Scratch voice can be local or user-provided; paid scratch work needs the budget first.

## Previs review

Use simple geometry sufficient to expose composition, scale, occlusion, movement and contact. A jump requires takeoff, airborne arc and landing; rigid sliding blocks may be inadequate. Add proxy parts or custom Blender logic when needed. The bundled renderer supports primitive/capsule transforms, camera paths, target tracking and lens keys, with sampled geometry audits. It is not a full rigging system. Preserve its limitations in the review notes.

Prepare the animatic plus key frames at cuts and required events, with shot IDs and frame numbers in the review description. If a reference exists, compare it beside the previs; otherwise compare against the written action requirements. Inspect the actual render before asking the user to approve. Save approval evidence and revision/hash.

## Appearance review

Build an asset table with role ID, source (existing/generated/mixed), original file, working file, hash, version, approved status and dependent shot IDs. Inspect existing images and preserve the original bytes. Use a copy for crops, background removal and edits. Never manufacture missing views as if provided by the user.

After previs approval, prepare real appearance images for each necessary role. Existing approved images can satisfy the requirement; do not regenerate them unnecessarily. Include distinct views or expression/pose references only when needed by the shot or supported model. Background appearance must fit the approved spatial layout.

Show the actual image files, not just filenames or prompts. Resolve feedback, then record which versions the user approved. Do not infer appearance approval from previs approval. If an early supplied photo is explicitly approved, reuse that approval and review the remaining assets.

## Revisions

Appearance-only change: make a new asset version, reopen its image approval and mark dependent generated shots stale. Shape, scale, collision, layout or visibility change: also reopen affected previs shots. Camera/action/timing change: create a new spec revision and inspect a before/after render; check unchanged shots for accidental edits. Never silently substitute references into previously approved jobs.
