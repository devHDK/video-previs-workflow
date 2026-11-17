# Direction and appearance

## Story design (minimum)

Before previs, the project needs an approved story file (`story-vNNN.json`, the `story-design` skill's format) with at least:

- `setup`: `premise`, `tone`, `avoid`, `lead` and `setting`, settled before any plot; `hook` (what is funny or surprising) is optional. Draft them yourself and let the user edit; offer alternatives for `tone` only.
- `purpose`: one sentence the viewer should take away.
- `target_action`: the viewer action (save, share, follow, book…), its `cue` (caption, line, end card) and the `beat` where it lands, at or after the payoff.
- `structure`: `id` and `why` linking purpose and action to the structure.
- `beats`: contiguous timed beats from 0 s, each with a visible `event`, `tension` 0–5 and `serves` (`purpose` or `target_action`).

Conflict only when the structure needs it. When it does, an antagonist must act, not just appear: name who blocks and how in each obstacle beat, make the hero pay a visible cost, and let tension peak right before the payoff. Shots, events and entity counts in previs derive from these beats; a previs simplification that removes an obstacle beat changes the story and reopens story approval.

## Reference-led route

Use when the user wants a reference video's composition, action and timing reproduced, with new characters, products or setting. An approved reference breakdown takes the story design's place; do not invent a purpose, target action or tension curve for it.

1. Preserve the footage as a local file in `inputs/`. With only a link or description, say what cannot be observed: timing cannot be matched without frames.
2. From the project directory run `media.py cuts inputs/reference.mp4 reference/v001`. It writes `reference-draft.json`, start/mid/end `stills` and a `clip` per detected shot. Detection is a proposal: inspect the stills and fix missed or false cuts (dissolves, flashes, whip pans) by editing shot boundaries. One source shot is one reference shot. Split it only when it is longer than the profile's `max_duration_s`: mark the later part `continues_previous: true` and give a `split_reason`; the gate rejects a split whose parts would fit one take.
3. Measure before describing the camera: at three or more times per shot, read the subject's head width and a background figure's face width (when focus blurs the background, the distance between two fixed background points) in pixels off the frames and record them as `camera_evidence` (`{t, subject_px, background_px}`; the gate needs two samples). The subject shrinking while the background holds means the subject moves away; both shrinking together means a pull-back or zoom-out; the `camera` text must agree with the numbers. Then per shot fill `camera` (shot size, angle, height, lens feel, movement, subject placement) and `action`. Time each action change as an `events` entry `{t, event}` in source seconds, read from the shot clip's frames at the source frame rate (`media.py extract reference/v001/s02.mp4 review/s02-frames --every 1/FPS` as a decimal); an event at a cut belongs to the next shot. For every figure that changes place, write the shot's `travel` entry for its role: where it ends up, the route it takes and who stands beside it ("walks straight to the empty place right of the front-row boy"); a route left unwritten gets invented in previs. For every role with five or more members, measure how far apart they change state (`media.py spread`) and note it for the shot's `group_motion`. Add a top-level `changes` list: what is replaced (performer → mascot, product, setting) and what stays. Before describing shots, add the same top-level `setup` block a story design has (the adaptation's premise, tone, what to avoid, lead and setting; a `hook` only if it has one): an adaptation inherits the source's mood unless `tone` and `avoid` say otherwise, and an eerie source reproduced faithfully gives an eerie parody.
4. Save as `reference-v001.json`; run `gate.py reference reference-v001.json --max-duration <the profile's max_duration_s>` until it prints `OK`. Review with the user as a table (id, start–end, frames at the output fps, camera, action, events) with each shot's stills, then record `reference` in state.
5. Previs shot ids equal reference shot ids. Each shot's frames = round(end × fps) − round(start × fps) at the output fps, so rounding never accumulates; key each event at frame round(t × fps) − round(start × fps) + 1 of its shot. `gate.py ready` enforces shot frames. A shot that intentionally differs (dropped, merged, retimed, reframed for another aspect ratio) gets a `decision` in a new reference version and needs re-approval.
6. Review previs with `media.py compare inputs/reference.mp4 PREVIS.mp4 review/ref-vs-previs.mp4` (synced side by side) plus the per-cut reference ↔ previs sheet below. When the delivery aspect ratio differs from the source, first make the comparison clip with `media.py reframe` (a crop window that follows the subject) and record the crop width and what the new frame gains and loses as a `decision`.
7. A turn, change of direction or stop that a figure makes in previs and the reference does not list is an added action: it will appear in the take. Put it to the user as a decision and record it in the shot's `unlisted_motion` (`{t, decision}`), or remove it. `gate.py ready` reads these moves off the scene file.

## Intake routes

| Input | Action |
|---|---|
| Reference footage | To reproduce it, follow the reference-led route. As loose inspiration: probe it, extract frames around cuts and action changes, observe camera, composition, actions and timing; list unavailable evidence. |
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
- A prop's whole path is blocked and named in the shot's `props`: where it comes from (`origin`), who holds it (`holder`) and where it ends (`exit`). Hiding a proxy inside another proxy until it is needed is a staging trick, so record the real source (a pocket, a table) there. A prop with no stated source appears from nowhere in the generated take.

Revise on stills, render once. While the blocking is still changing, run `render_previs.py --audit-only`, then render only the event frames (`--frames`) and compare them with the reference or storyboard (`media.py pair --times`). Render the full animation once, after the stills match. Drafts you revise alone go to `previs/d01`, `previs/d02`…; only a render shown for review is numbered `v001`, `v002`…, so the first version the user sees is v001. Nothing is overwritten. Share the first comparison sheet as soon as it exists, with the fixes you plan: it is information, not an approval request. When a background render starts, say how long it is expected to take.

Prepare the animatic plus key frames at cuts and required events, with shot IDs and frame numbers in the review description. Inspect the actual render before asking the user to approve. Save approval evidence and revision/hash.

Reference comparison: when a storyboard, reference footage or earlier approved version exists, build a sheet placing each reference panel beside the matching previs frame. Check pose, entity count, prop structure, shot size, camera height, start/end framing and where each frame edge cuts bodies (not at knees, mid-thigh, ankles, wrists or necks). List each dropped, merged or changed panel as an explicit decision in the approval request; an unlisted omission is a defect. Without a reference, compare against the story beats and written action requirements.

## Appearance review

Build an asset table with role ID, `kind` (`character`, `prop` or `set`), source (existing/generated/mixed), original file, working file, hash, version, approved status and dependent shot IDs. Inspect existing images and preserve the original bytes. Use a copy for crops, background removal and edits. Never manufacture missing views as if provided by the user.

Generate first what other assets wear or hold (a mask before the crowd that wears it) and pass it as a reference to the assets that depend on it. After previs approval, prepare real appearance images for each role named in any shot's `object_roles`, including sets (each distinct location) and props that recur or carry action. Existing approved images can satisfy the requirement; do not regenerate them unnecessarily. Props whose structure matters (supports, ladders, hinges, open/closed states) need a view that shows that structure. For each character or person role, list the facing seen at the start and end of every approved previs shot. A role seen only from the front gets a front view. A role whose back or side is seen anywhere, including a turn within a shot, gets one front + back sheet: both views side by side in a single image, generated in one call when the model can (otherwise combine two images). Bind that sheet file; the gate allows one file per role across shots. Add a side view only when a profile is held large on screen, and expression/pose references only when a shot or the model needs them. Background appearance must fit the approved spatial layout. Bind the same approved version to every shot where the role appears, so it cannot change between shots.

Write every defect you notice in an image as a `review_notes` entry on its record before asking for approval, and close each one as `fixed` (name the new version) or `accepted` (quote the user). A defect is never carried to the next stage to be fixed there: a flaw in an appearance image is copied into every keyframe and take made from it. The gate rejects an approved asset or keyframe with an open note.

Show the actual image files, not just filenames or prompts. Resolve feedback, then record which versions the user approved. Do not infer appearance approval from previs approval. If an early supplied photo is explicitly approved, reuse that approval and review the remaining assets.

## Shot keyframes

After appearance approval, compose one start frame per shot (plus an end frame when the video tool accepts one) from the previs frame at that point and the approved assets, so the image already carries framing, camera height, set and prop placement. Prepare each request so the model follows the previs instead of inventing:
- Guide frame: render the previs frame at the output resolution or higher (`render_previs.py --frames N --size 1080x1920`); a small gray frame loses to the composition of a set reference.
- Prompt: say what each stand-in shape becomes and that the shapes themselves must not appear (houses, not capped cylinders; a torso, not a box). Give exact counts per role as seen in the guide frame, which props belong to whom (who wears the hard hat), and a complete body and outfit for any person the frame crops.
- References: keep to four or five images. Combine several character sheets or prop views into one image, and remove stray objects from a copy of a set image before using it.
- Anchor frame: once a location's first keyframe is approved, add it as a reference for that location's other keyframes, for floor, set dressing and light only (say so, so its camera and characters are not copied). An anchor also carries whatever it shows: name anything in it that must stay hidden in the new frame (a building the crowd still covers), or pick an anchor from the same state.

A long single take also gets keyframes at its main state changes, recorded with kind `reference` and the `previs_frame` they show. They are image references ("how the scene looks at T s"), never start frames, and the gate counts only `start`. For a group whose `sync` is `ragged`, take these frames from the middle of a change, where members are in different poses: a frame of everyone in the same pose is copied as lockstep motion.

Review in two passes. First each keyframe beside its previs frame: shot size, camera height, entity positions and counts, limbs and clothing, prop structure, and where the frame edges cut bodies. Then `media.py continuity state.json review/continuity.jpg`: one row per role shared by two or more shots, so floor, light, set dressing, character design and counts can be compared across shots. Note keyframe defects in `review_notes` and close them the same way as for appearance images. Record approved keyframes in `shots[].keyframes` with path, hash and approval, and one `continuity[]` approval per shared role with the keyframe hashes reviewed. A changed keyframe reopens its shot and the continuity review of its roles. Keyframe images are paid calls inside the job budget unless generated by hand under a web-only allowance (manual route).

## Revisions

Appearance-only change: make a new asset version, reopen its image approval and mark dependent generated shots stale. Shape, scale, collision, layout or visibility change: also reopen affected previs shots. Camera/action/timing change: create a new spec revision and inspect a before/after render; check unchanged shots for accidental edits. Never silently substitute references into previously approved jobs.
