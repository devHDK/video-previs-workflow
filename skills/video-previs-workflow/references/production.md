# Direction and appearance

## Story design (minimum)

Before previs, the project needs an approved story file (`story-vNNN.json`, the `story-design` skill's format) with at least:

- `purpose`: one sentence the viewer should take away.
- `target_action`: the viewer action (save, share, follow, book…), its `cue` (caption, line, end card) and the `beat` where it lands, at or after the payoff.
- `structure`: `id` and `why` linking purpose and action to the structure.
- `beats`: contiguous timed beats from 0 s, each with a visible `event`, `tension` 0–5 and `serves` (`purpose` or `target_action`).

Conflict only when the structure needs it. When it does, an antagonist must act, not just appear: name who blocks and how in each obstacle beat, make the hero pay a visible cost, and let tension peak right before the payoff. Shots, events and entity counts in previs derive from these beats; a previs simplification that removes an obstacle beat changes the story and reopens story approval.

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

Proxy minimums:

- Story-critical props are blocked with their supporting structure, not as a bare plank or floating shape (a slide is chute + ladder/support + exit lip).
- Poses that change meaning are represented: a sleeping passenger is seated or reclined, not a standing capsule.
- Entity counts match the story beats (a swarm is several proxies, not one).
- In the delivery aspect ratio, no ground edge or empty void is visible inside the frame unless intended.
- Every proxy object id is mapped in the shot's `object_roles` to a role or to `null` (set dressing without its own asset).

Prepare the animatic plus key frames at cuts and required events, with shot IDs and frame numbers in the review description. Inspect the actual render before asking the user to approve. Save approval evidence and revision/hash.

Reference comparison: when a storyboard, reference footage or earlier approved version exists, build a sheet placing each reference panel beside the matching previs frame. Check pose, entity count, prop structure, shot size, camera height and start/end framing. List each dropped, merged or changed panel as an explicit decision in the approval request; an unlisted omission is a defect. Without a reference, compare against the story beats and written action requirements.

## Appearance review

Build an asset table with role ID, source (existing/generated/mixed), original file, working file, hash, version, approved status and dependent shot IDs. Inspect existing images and preserve the original bytes. Use a copy for crops, background removal and edits. Never manufacture missing views as if provided by the user.

After previs approval, prepare real appearance images for each role named in any shot's `object_roles`, including sets (each distinct location) and props that recur or carry action. Existing approved images can satisfy the requirement; do not regenerate them unnecessarily. Props whose structure matters (supports, ladders, hinges, open/closed states) need a view that shows that structure. Include distinct views or expression/pose references only when needed by the shot or supported model. Background appearance must fit the approved spatial layout. Bind the same approved version to every shot where the role appears, so it cannot change between shots.

Show the actual image files, not just filenames or prompts. Resolve feedback, then record which versions the user approved. Do not infer appearance approval from previs approval. If an early supplied photo is explicitly approved, reuse that approval and review the remaining assets.

## Shot keyframes

After appearance approval, compose one start frame per shot (plus an end frame when the video tool accepts one) from the previs frame at that point and the approved assets, so the image already carries framing, camera height, set and prop placement. Show each keyframe beside its previs frame; check shot size, camera height, entity positions and counts, and prop structure. Record approved keyframes in `shots[].keyframes` with path, hash and approval. A changed keyframe reopens only its shot. Keyframe images are paid calls inside the job budget.

## Revisions

Appearance-only change: make a new asset version, reopen its image approval and mark dependent generated shots stale. Shape, scale, collision, layout or visibility change: also reopen affected previs shots. Camera/action/timing change: create a new spec revision and inspect a before/after render; check unchanged shots for accidental edits. Never silently substitute references into previously approved jobs.
