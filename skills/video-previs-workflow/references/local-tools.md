# Local helpers

Use Python 3.10+; helpers have no pip dependencies. Blender rendering requires an EEVEE-capable Blender build (4.2+ interface; 5.3.0 tested) (actual tested versions are recorded in the repository validation report). Media operations require `ffmpeg`, `ffprobe`, libx264; selectable subtitle export uses mov_text. The renderer discovers the EEVEE engine identifier from Blender RNA (`BLENDER_EEVEE_NEXT` or `BLENDER_EEVEE`) and errors if neither exists. Do not claim compatibility with untested releases. `doctor.py` reports availability, not version compatibility or provider connectivity.

Resolve `SKILL_DIR` to the installed folder; below it is a shell variable set by the agent to the actual path. Quote all paths. Project files live outside this directory.

```sh
python3 "$SKILL_DIR/scripts/doctor.py"
python3 "$SKILL_DIR/scripts/validate_spec.py" scene-v001.json
blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/render_previs.py" -- scene-v001.json previs/v001
blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/render_previs.py" -- scene-v001.json previs/d01 --frames 7,203,451
blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/render_previs.py" -- scene-v001.json previs/d01-audit --audit-only
blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/render_previs.py" -- scene-v001.json previs/d01-plan --plan s01,s02,s03
blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/render_previs.py" -- scene-v001.json previs/guides-v001 --shot s01 --frames 1 --size 1080x1920
python3 "$SKILL_DIR/scripts/media.py" encode 'previs/v001/s01/frame_%04d.png' previs/s01.mp4 --fps 24
python3 "$SKILL_DIR/scripts/media.py" extract previs/s01.mp4 review-frames --every 0.5
python3 "$SKILL_DIR/scripts/media.py" pair previs/s01.mp4 shots/s01/v001/source.mp4 qa/s01-pair.jpg --points 5
python3 "$SKILL_DIR/scripts/media.py" pair inputs/reference.mp4 previs/d01.mp4 review/ref-vs-d01.jpg --times 0.24,7.4,12.0
python3 "$SKILL_DIR/scripts/media.py" continuity state.json review/continuity.jpg
python3 "$SKILL_DIR/scripts/media.py" sheet review/real-vs-k03.jpg source/frame.jpg shots/s03/keyframes/k03-v001.png
python3 "$SKILL_DIR/scripts/media.py" assemble edit.json output/final.mp4
python3 "$SKILL_DIR/scripts/media.py" probe output/final.mp4
python3 "$SKILL_DIR/scripts/media.py" cuts inputs/reference.mp4 reference/v001 --threshold 0.3
python3 "$SKILL_DIR/scripts/media.py" reframe inputs/reference.mp4 review/ref-9x16.mp4 --size 360x640 --crop-width 1056 --centres 0:780,3.04:1178 --fps 24
python3 "$SKILL_DIR/scripts/media.py" spread inputs/reference.mp4 --start 21 --end 29.4 --grid 24x12
python3 "$SKILL_DIR/scripts/media.py" dupes shots/s01/v001/source.mp4 --fix shots/s01/v001/fix/source.mp4
python3 "$SKILL_DIR/scripts/gate.py" qa state.json
python3 "$SKILL_DIR/scripts/gate.py" reference reference-v001.json --max-duration 30
python3 "$SKILL_DIR/scripts/gate.py" ready state.json
python3 "$SKILL_DIR/scripts/gate.py" submit state.json shots/s01/v002/job.json
python3 "$SKILL_DIR/scripts/state.py" init state.json --project-id my-video
python3 "$SKILL_DIR/scripts/state.py" put state.json generation_profile profile.json
python3 "$SKILL_DIR/scripts/state.py" put state.json shot shots/s01/shot.json
python3 "$SKILL_DIR/scripts/state.py" lock state.json --owner claude-local --purpose "keyframes s01-s03"
python3 "$SKILL_DIR/scripts/state.py" reserve state.json shots/s01/keyframes/k01-v002-job.json
python3 "$SKILL_DIR/scripts/state.py" submit state.json k01-s01-v002 --provider-job-id PROVIDER_ID
python3 "$SKILL_DIR/scripts/state.py" settle state.json k01-s01-v002 --charge 1 --output shots/s01/keyframes/k01-v002.png
python3 "$SKILL_DIR/scripts/state.py" asset state.json hero@v002 --kind character --path assets/hero/v002/hero.png
python3 "$SKILL_DIR/scripts/state.py" keyframe state.json s01 shots/s01/keyframes/k00-v001.png --kind start --previs-frame 1
python3 "$SKILL_DIR/scripts/state.py" note state.json asset hero@v002 --note "cap is on in both views"
python3 "$SKILL_DIR/scripts/state.py" note state.json asset hero@v002 --resolve accepted --evidence 'User: "fine"'
python3 "$SKILL_DIR/scripts/state.py" approve state.json asset hero@v002 --evidence 'User: "ok"'
python3 "$SKILL_DIR/scripts/state.py" approve state.json reference reference-v001.json --evidence 'User: "ok"'
python3 "$SKILL_DIR/scripts/state.py" charge state.json k01-s01-v002 --charge 2 --evidence 'provider transactions 2026-11-18'
python3 "$SKILL_DIR/scripts/state.py" bind state.json
python3 "$SKILL_DIR/scripts/handoff.py" pack shots/s01/v002/job.json handoff/videos/s01-v002
python3 "$SKILL_DIR/scripts/handoff.py" ingest handoff/videos/s01-v002 shots/s01/v002/source.mp4 --kind video
```

`media.py cuts` detects cuts by ffmpeg scene score (lower `--threshold` finds softer cuts) and writes a draft breakdown, frames and per-shot clips with paths as given; run it from the project directory. Scene changes scored between `--low` (default 0.2) and the threshold are not cut on; they are written to `candidates` with their time and score, neighbouring ones (0.1 s apart or less: one shaky shot) merged into the strongest, and `gate.py reference` rejects a candidate without a `decision`. `gate.py reference` checks a breakdown before approval: source with `source.rights`, `match`, a `plan` on every shot of a `format` reference, `setup`, contiguous shots from 0 s, `camera`, `camera_evidence` (two or more measured samples per shot, not required when `match` is `format`), `action`, events inside their shot (`start ≤ t < end`), and a `split_reason` on every shot marked `continues_previous`. With `--max-duration SECONDS` (the profile's `max_duration_s`; `ready` passes it itself) it also rejects a split take that would fit one generation.

`gate.py` reads project state and never edits it. `ready` and `submit` read each figure's path from the scene file (a figure is a capsule-rooted object; `id_part` objects belong to `id`): a role with five or more figures needs `group_motion`, and on the reference-led route every turn of 45° or more, change of direction or stop of half a second needs a reference event or an `unlisted_motion` decision within 0.75 s, and a figure that moves more than a metre needs a `travel` entry in its reference shot. `gate.py qa` checks takes after generation: a `selected_output` file per shot, a `pass` or `accepted` `prop_results` entry with evidence for every prop of the shot, a `pass` or `accepted` result with evidence in `event_results` for every required event, and `measured_s` for every group (a ragged group outside 0.5-2× its `spread_s` blocks unless accepted with evidence). `ready` and `submit` also require: the `setup` sheet in the story or reference file, a `generation_profile` and no shot or covered take longer than its `max_duration_s`, a `kind` on every approved asset, `props` (origin, holder, exit, a positive `count` and `states`) for each prop role of a shot, and no open `review_notes` on an approved asset or keyframe; the attempt limit applies to paid jobs only. A shot that is not in the previs spec passes only with a `no_previs` reason, its own `frames` and its `object_roles` (checked against the take limit and, on the reference-led route, the reference cut). `ready` checks the whole project before the first paid video call: approved, unchanged story file or reference breakdown (with every reference shot's frames matching previs, unless it carries a `decision` or its `plan` is `footage` or `reuse`); previs approval; `required_events` and an `object_roles` decision for every previs object; an approved asset bound per role, the same version in every shot; exactly one approved, unchanged start keyframe per shot (mark superseded keyframes and assets as such); for every role used by two or more shots, an approved `continuity` record whose keyframe hashes match the current approved keyframes (`submit` checks the roles of its shot); `retry_reserve ≥ max_shot_quote`. `submit` checks one job (`shot`, numeric `quote`, `start_frame_sha256`, optional `retry_of`, optional `shots` for a sequence take, every one of which must be ready) against its shot and the remaining budget, and rejects a quote above `max_shot_quote` because the reserve is sized from it. Both print `OK` (exit 0) or one error per line (exit 1). A budget of `max_shot_quote: 0` and `retry_reserve: 0` is valid when all video is generated by hand under a web-only Unlimited allowance; any job quoted above 0 is then rejected. `submit` also requires a numeric `cap` and accepts a quote of 0 only for a job with `route: "manual"`, because MCP generation always bills.

`state.py` is the one script that edits `state.json`; each command prints `OK` or one error line (exit 1) and writes atomically. `put` takes the record (`{"path": "reference-v001.json"}`), not the file it points to, and refuses a `story` or `reference` without `path` or a `previs` without `spec_path`. `state.py asset --source footage --origin 'IMG_0549 0.5 s, top 30 %'` records where a crop of real footage came from (`generated` by default, `existing` for a supplied file). `state.py init projects/<project-id>/state.json --project-id <project-id>` creates the project folder and the file. `state.py put SECTION FILE` merges a JSON object into `output`, `generation_profile`, `generation_plan`, `budget`, `handoff` or, as `shot`, into the shot with that `id` (added when new); for `story`, `reference` and `previs` it replaces the record, hashes the file and sets it `pending`. It never approves and never changes the budget counters (`settled`, `reserved`, `attempts_used`, `manual_takes`). `approve` takes the record kind and an identifier: `role@version` for an asset, the path for a keyframe, the role for continuity, any text (the file name) for story, reference and previs. `state.py charge` corrects a settled job's charge and `budget.settled` with evidence: read charges from the provider's transaction list, since a balance difference includes whatever else the account spent meanwhile. Records: `state.py asset` and `state.py keyframe` add a pending record with the file's hash; `state.py note` writes a defect or closes every open one as `fixed`/`accepted` with evidence; approving an asset or a start keyframe marks the older approved version `superseded`; `state.py bind` ties each role's approved asset to the shots that use it. A paid or manual job goes through it in this order:

1. `lock`: take the submission lock.
2. `gate.py submit state.json job.json`: check the job before it is reserved (after `reserve` its own quote counts against the budget).
3. `reserve`: add the job file (`request_id`, `route`, numeric `quote`, target and inputs) as `reserved` and hold its quote. A job already in state under that id is refused.
4. Call the provider, or pack the handoff folder for a manual job.
5. `submit`: mark it `running`, or `handed_off` for `route: manual`, and count a paid attempt or a manual take.
6. `settle`: record the charge and the result files with their hashes and free the reservation. `settle ID --charge 0 --status cancelled` gives up a reservation that was never sent; a job settled straight from `reserved` with any other status still counts as an attempt. A job marked `unknown` by hand after an interrupted submission keeps its reservation and the lock until it is settled.

`submit` and `settle` give the lock back once no job is reserved, submitting, running or unknown; a handed-off manual job never holds it, and settling one leaves a lock taken since alone. `unlock` removes a lock that has no such job behind it. `approve` records the user's words on a story, reference, previs, asset (`role@version`), keyframe (path) or continuity (role) record, and refuses one with an open review note.

`media.py pair` puts one source above the other in 270×480 cells: `--points N` samples both evenly, `--times` samples both at the same seconds, so the reference events can be compared with the previs, or the previs with a take, exactly where they matter. A time past a source's end gives its last frame.

`media.py sheet OUTPUT IMAGE IMAGE…` tiles still images in cells, `--cols` per row (default 2), for comparing a real frame with a keyframe or laying out a mapping of reference stills and planned frames. It prints which image is in which cell, because the picture carries no labels. `--cell 540x960` makes the cells large enough to see hair colour or the thickness of a mask (the default 270x480 is an overview); `--cell 1080x1920` combines reference views at working size.

`media.py dupes` lists frames that repeat the previous one while the picture moves (exit 1 when any remain); `--fix` writes the repaired copy. `media.py spread` cuts the window into a grid of about one group member per cell (`--crop w:h:x:y` to the area the group fills) and returns `spread_s`, half the 10-90 % width of the cells' offsets from the common beat: about 0.1 reads as lockstep, the value of the reference is the target. `media.py reframe` crops a window of `--crop-width` source pixels whose centre follows `--centres` (`t:x` pairs) and pads it to `--size`, for comparing a reference in another aspect ratio at the previs scale.

`media.py continuity` reads state and tiles each shot's current start keyframe (approved, else the latest pending) into one row per role shared by two or more shots, 270×480 per cell, and prints the row legend as JSON with each row's `keyframe_sha256` (the hashes shown, ready to copy into a `continuity` record); the image has no labels. A shared role whose shot has no approved keyframe cannot be reviewed; the gate names those shots.

`handoff.py` serves the manual route in generation.md. A job without inputs is packed as a text-only request. Run it from the project directory. `pack` copies a job's inputs in upload order as `NN-<slot>.<ext>`, writes `request.md` (model, settings, input table, prompt, expected result) and an empty `output/`, and prints the input hashes. `ingest` takes the single non-hidden file in `output/`, rejects a wrong kind or an undecodable file, copies it to the destination and prints its hash, size and, for video, duration and fps. Neither edits state, and both refuse to overwrite.

On restricted macOS hosts, EEVEE needs access to Metal GPU and Blender cache/thumbnail directories; a sandbox may deny these. Use the host approval mechanism for this render rather than treating a Metal initialization failure as a scene error.

On macOS the Blender executable may be `/Applications/Blender.app/Contents/MacOS/Blender`. Use the discovered path. Render/extract destinations must not exist; media outputs reject overwrites. Use a new revision for edits. If a command fails after writing partial output, inspect it and choose a new revision rather than pretending it succeeded.

## Scene format v1

See [example-scene.json](../assets/example-scene.json). It is a synthetic jump demo, not a global creative default.

- `version`: 1; `fps`, `width`, `height`: positive integers; dimensions even.
- `shots[]`: unique path-safe `id`, positive integer `frames`, `camera`, `objects`.
- `camera`: base `position` and either `target` (XYZ, Z up) or `follow` (an object ID) with optional world-space `offset`. Optional positive `lens` in mm (default 40). Optional `keys` beginning at frame 1 can animate `position`, `target`, and `lens`; omitted properties retain the previous value. `follow` overrides target keys and tracks the subject root, not its surface. Add an offset for head/body framing. Camera position is an independent world-space path; tracking aims the camera without moving it automatically.
- Objects: unique `id`, `shape` (`cube`, `sphere`, `cylinder`, `capsule`), RGB `color` in 0..1, positive XYZ `scale`, `keys`.
- Optional per shot: `review_frames`, shot-local frames that get a review still besides the first, middle and last (event frames worth comparing with the reference).
- Each key: shot-local integer `frame`, XYZ `position`, optional XYZ Euler `rotation` in radians. Keys increase from frame 1 through the shot's last frame. Scale is relative to Blender primitives, not absolute dimensions. Object and camera `interpolation` is `linear` by default or `smooth` (smoothstep per segment, easing to rest at each key). Every integer frame is baked from the same sampler used for tracking. This changes the previous implicit Bezier default: rerender/review existing specs before reusing approvals. Omitted rotation now retains the previous keyed pose (the old renderer reset it to zero); specify an explicit zero rotation when a reset is intended. Euler rotation interpolates numerically; use unwrapped radians when crossing ±π. Subframe motion blur is not validated.
- Blender render frames are inclusive 1..N. Edit timeline intervals are zero-based, end-exclusive: a 48-frame first shot is [0,48); the next begins at 48.

The helper saves one .blend, `audit.json`, review stills and a PNG sequence per shot, plus a top-level `handoff.json` with cut intervals and role colors. Encode each sequence, then assemble clips. No audio is generated. Review stills are the first, middle and last frame of each shot plus its `review_frames`. Six options shorten the loop:

- `--review-only`: the scene, audits and review stills, without the full sequence.
- `--frames 7,203,451`: stills at exactly these shot-local frames and nothing else. Use it with the event frames while matching a reference.
- `--size 1080x1920`: this run's resolution, without copying the spec. With `--frames` it renders keyframe guides.
- `--shot s02`: one shot only.
- `--audit-only`: `audit.json` per shot and one JSON line of status each; no scene file, no images. Run it before rendering to catch a hidden face or a subject out of frame.
- `--plan s01,s02,s03`: one floor plan for shots that share a location, and nothing else: `plan.png` (1080×1080, seen from above) and `plan.json` (the positions drawn). The set and the figures are the first listed shot's at frame 1. Per shot it draws the camera as a white wedge with the shot id (its position and horizontal view angle at frame 1, plus its path when it moves), the path of every figure root that travels more than 0.5 m in the figure's colour with its id at the end, and a declared `audit.line` in yellow. A root that starts a later shot somewhere else than in the first listed shot, or exists only in the later shot, gets a square in its colour labelled with its id and that shot (`hero s02`): a figure that jumps between shots shows as a proxy and a square apart. It cannot be combined with the other options. Later shots' objects are drawn only as these squares and paths, never as shapes, and anything above 50 m hides the overlays.

A wrong frame, size or shot id fails before anything is written. A still-only run is not an approved animatic.

Run only in a separate background Blender process; GUI execution is rejected before any scene reset. The renderer starts a fresh scene per shot in that process and saves only into the new output directory. It is not an editor for an existing user's .blend. Cubes/spheres/cylinders are center-rooted Blender primitives. The new capsule is foot-rooted, 2 m tall and .7 m wide before scale; its root stays on ground at z=0. Its silhouette has no limbs or facing marker; use project-specific geometry when gait, gesture, facing or contact must be explicit.

See [tracking-jump.json](../assets/tracking-jump.json) for a moving-camera example. Do not turn it into a global style default.

## Scene generators

A scene with more than a few objects is written by a short project script that prints the spec JSON (keep it in the project, not here). It can import `scripts/blocking.py` for the parts every project repeats: `frame_of` (seconds to a shot-local frame, with the gate's rounding), `track` (a value over time from keys), `local_to_world` (a point given relative to a figure and its facing) and `person` (body, head and a face marker, so a turn is visible; a bare capsule has no front). Crowds, folds and props stay in the project script.

## Geometry audit

A shot can specify `audit: {"subjects": ["hero"], "step": 1, "margin": 0.03, "ground_z": 0, "tolerance": 0.03}`. Two optional lists keep the findings meaningful: `groups` (lists of object ids; members of one list never count as occluding each other, for a face marker or mask in front of a head) and `crop_ok` (subjects allowed to leave the frame, for a close-up that crops them on purpose). Objects can declare `ground_contact: [[1,12],[36,48]]` using inclusive shot-local intervals. Only those intervals require contact; an airborne jump is not automatically flagged as floating.

Checks project each subject's world bounding-box corners into the camera, test a center ray for occlusion, and compare declared contact objects' lowest bounding-box point with ground height. Sampling defaults to every frame and always adds final/key/contact-boundary frames. Reports list sampled frames and findings. No configured checks produces `not_configured`, not a pass. Empty findings mean only the configured sampled checks passed.

These are conservative geometry indicators: bounding boxes may flag rotated shapes unnecessarily; a center ray cannot establish full visibility and treats transparent occluders geometrically. Ground height is a flat reference plane, not arbitrary terrain. There is no general mesh-intersection or limb-contact solver. Inspect rendered frames and fix geometry or intentionally document exceptions before approval. Audits do not silently reframe the shot or block saving review artifacts.

Two staging checks need no rendering and are read from the whole spec, so they also run with `--shot`. `audit.line` (`"line": ["hero", "rival"]`, two object ids) names the pair an action line runs through: when a shot and the shot right before it declare the same pair, the camera's side of the line at the earlier shot's last frame is compared with its side at this shot's first frame, and a change is reported as `line_crossed` at frame 1. A camera within about 6° of the line counts as on it and is never reported. Set `line_cross_ok: true` on the later shot once the crossing is a recorded decision. `audit.screen_direction` (`{"hero": "right"}`) names the way a figure should travel across the screen in that shot: its root path is projected on the camera's right-hand axis frame by frame, and more than 0.5 m of net travel the other way is reported as `screen_direction_reversed` at the last frame. Travel toward or away from the camera is neither. Both use root positions on the ground plane; they do not know what a body or a face is doing.

```sh
python3 "$SKILL_DIR/scripts/validate_spec.py" scene-v002.json --previous scene-v001.json
python3 "$SKILL_DIR/scripts/media.py" compare old.mp4 new.mp4 review-side-by-side.mp4
```

The diff identifies changed or removed shots; global format or shot-order changes mark all affected shots. It does not judge images.

## Edit manifest

Paths are relative to the manifest. Clip order is the edit order, and each duration is a frame count at the output FPS.

```json
{
  "fps": 24, "width": 360, "height": 640,
  "clips": [{"path": "shots/s01.mp4", "frames": 48},
            {"path": "shots/s02.mp4", "frames": 72, "start": 0.5, "speed": 1.05},
            {"path": "shots/s03.mp4", "frames": 48, "dialogue": true}],
  "audio": "audio/mix.wav",
  "subtitles": "edit/captions.srt"
}
```

Optional clip keys: `start` (seconds into the source, ≥ 0), `speed` (0.9–1.1, default 1) and `dialogue` (true forbids any speed change). The assembler rejects values outside these limits before encoding. Omit `audio`/`subtitles` if not requested. The helper normalizes/re-encodes clips, removes their audio, pads short clips, adds a prepared audio mix and selectable captions, verifies output frame count and decodes the MP4. It is a finishing helper, not an automatic dialogue/SFX mixer or lip-sync system. Inspect/approve padding and prepare the mix separately. `media.py --help` lists subcommands.
