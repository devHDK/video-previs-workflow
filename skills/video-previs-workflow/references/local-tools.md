# Local helpers

Use Python 3.10+; helpers have no pip dependencies. Blender rendering requires an EEVEE-capable Blender build (4.2+ interface; 5.3.0 tested) (actual tested versions are recorded in the repository validation report). Media operations require `ffmpeg`, `ffprobe`, libx264; selectable subtitle export uses mov_text. The renderer discovers the EEVEE engine identifier from Blender RNA (`BLENDER_EEVEE_NEXT` or `BLENDER_EEVEE`) and errors if neither exists. Do not claim compatibility with untested releases. `doctor.py` reports availability, not version compatibility or provider connectivity.

Resolve `SKILL_DIR` to the installed folder; below it is a shell variable set by the agent to the actual path. Quote all paths. Project files live outside this directory.

```sh
python3 "$SKILL_DIR/scripts/doctor.py"
python3 "$SKILL_DIR/scripts/validate_spec.py" scene-v001.json
blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/render_previs.py" -- scene-v001.json previs/v001
python3 "$SKILL_DIR/scripts/media.py" encode 'previs/v001/s01/frame_%04d.png' previs/s01.mp4 --fps 24
python3 "$SKILL_DIR/scripts/media.py" extract previs/s01.mp4 review-frames --every 0.5
python3 "$SKILL_DIR/scripts/media.py" pair previs/s01.mp4 shots/s01/v001/source.mp4 qa/s01-pair.jpg --points 5
python3 "$SKILL_DIR/scripts/media.py" assemble edit.json output/final.mp4
python3 "$SKILL_DIR/scripts/media.py" probe output/final.mp4
python3 "$SKILL_DIR/scripts/media.py" cuts inputs/reference.mp4 reference/v001 --threshold 0.3
python3 "$SKILL_DIR/scripts/gate.py" reference reference-v001.json
python3 "$SKILL_DIR/scripts/gate.py" ready state.json
python3 "$SKILL_DIR/scripts/gate.py" submit state.json shots/s01/v002/job.json
```

`media.py cuts` detects cuts by ffmpeg scene score (lower `--threshold` finds softer cuts) and writes a draft breakdown, frames and per-shot clips with paths as given; run it from the project directory. `gate.py reference` checks a breakdown before approval: source, contiguous shots from 0 s, `camera`, `action`, events inside their shot (`start ≤ t < end`).

`gate.py` reads project state and never edits it. `ready` checks the whole project before the first paid video call: approved, unchanged story file or reference breakdown (with every reference shot's frames matching previs, unless it carries a `decision`); previs approval; `required_events` and an `object_roles` decision for every previs object; an approved asset bound per role, the same version in every shot; exactly one approved, unchanged start keyframe per shot (mark superseded keyframes and assets as such); `retry_reserve ≥ max_shot_quote`. `submit` checks one job (`shot`, numeric `quote`, `start_frame_sha256`, optional `retry_of`) against its shot and the remaining budget, and rejects a quote above `max_shot_quote` because the reserve is sized from it. Both print `OK` (exit 0) or one error per line (exit 1).

On restricted macOS hosts, EEVEE needs access to Metal GPU and Blender cache/thumbnail directories; a sandbox may deny these. Use the host approval mechanism for this render rather than treating a Metal initialization failure as a scene error.

On macOS the Blender executable may be `/Applications/Blender.app/Contents/MacOS/Blender`. Use the discovered path. Render/extract destinations must not exist; media outputs reject overwrites. Use a new revision for edits. If a command fails after writing partial output, inspect it and choose a new revision rather than pretending it succeeded.

## Scene format v1

See [example-scene.json](../assets/example-scene.json). It is a synthetic jump demo, not a global creative default.

- `version`: 1; `fps`, `width`, `height`: positive integers; dimensions even.
- `shots[]`: unique path-safe `id`, positive integer `frames`, `camera`, `objects`.
- `camera`: base `position` and either `target` (XYZ, Z up) or `follow` (an object ID) with optional world-space `offset`. Optional positive `lens` in mm (default 40). Optional `keys` beginning at frame 1 can animate `position`, `target`, and `lens`; omitted properties retain the previous value. `follow` overrides target keys and tracks the subject root, not its surface. Add an offset for head/body framing. Camera position is an independent world-space path; tracking aims the camera without moving it automatically.
- Objects: unique `id`, `shape` (`cube`, `sphere`, `cylinder`, `capsule`), RGB `color` in 0..1, positive XYZ `scale`, `keys`.
- Each key: shot-local integer `frame`, XYZ `position`, optional XYZ Euler `rotation` in radians. Keys increase from frame 1 through the shot's last frame. Scale is relative to Blender primitives, not absolute dimensions. Object and camera `interpolation` is `linear` by default or `smooth` (smoothstep per segment, easing to rest at each key). Every integer frame is baked from the same sampler used for tracking. This changes the previous implicit Bezier default: rerender/review existing specs before reusing approvals. Omitted rotation now retains the previous keyed pose (the old renderer reset it to zero); specify an explicit zero rotation when a reset is intended. Euler rotation interpolates numerically; use unwrapped radians when crossing ±π. Subframe motion blur is not validated.
- Blender render frames are inclusive 1..N. Edit timeline intervals are zero-based, end-exclusive: a 48-frame first shot is [0,48); the next begins at 48.

The helper saves one .blend, `audit.json`, review stills and a PNG sequence per shot, plus a top-level `handoff.json` with cut intervals and role colors. Encode each sequence, then assemble clips. No audio is generated. For fast review, add `--review-only`: it saves the scene, runs audits and renders key stills without a full sequence. A still-only run is not an approved animatic.

Run only in a separate background Blender process; GUI execution is rejected before any scene reset. The renderer starts a fresh scene per shot in that process and saves only into the new output directory. It is not an editor for an existing user's .blend. Cubes/spheres/cylinders are center-rooted Blender primitives. The new capsule is foot-rooted, 2 m tall and .7 m wide before scale; its root stays on ground at z=0. Its silhouette has no limbs or facing marker; use project-specific geometry when gait, gesture, facing or contact must be explicit.

See [tracking-jump.json](../assets/tracking-jump.json) for a moving-camera example. Do not turn it into a global style default.

## Geometry audit

A shot can specify `audit: {"subjects": ["hero"], "step": 1, "margin": 0.03, "ground_z": 0, "tolerance": 0.03}`. Objects can declare `ground_contact: [[1,12],[36,48]]` using inclusive shot-local intervals. Only those intervals require contact; an airborne jump is not automatically flagged as floating.

Checks project each subject's world bounding-box corners into the camera, test a center ray for occlusion, and compare declared contact objects' lowest bounding-box point with ground height. Sampling defaults to every frame and always adds final/key/contact-boundary frames. Reports list sampled frames and findings. No configured checks produces `not_configured`, not a pass. Empty findings mean only the configured sampled checks passed.

These are conservative geometry indicators: bounding boxes may flag rotated shapes unnecessarily; a center ray cannot establish full visibility and treats transparent occluders geometrically. Ground height is a flat reference plane, not arbitrary terrain. There is no general mesh-intersection or limb-contact solver. Inspect rendered frames and fix geometry or intentionally document exceptions before approval. Audits do not silently reframe the shot or block saving review artifacts.

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
