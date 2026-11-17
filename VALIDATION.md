# Validation status — 2026-11-11

This is a first implementation, not a claim of completed production-video validation.

## Initial version checks

- Official OpenAI skill-creator `quick_validate.py`: `Skill is valid!`.
- Python 3.11.7: seven unit tests pass. Tests first failed because helper implementations were absent, then passed after implementation.
- Tests cover scene validity, cut frame counts, invalid geometry/key frames, duplicate IDs, changed/deleted shots, global format changes, safe command argument paths, explicit frame limits, refusing existing outputs, and fatal FFmpeg decode verification flags.
- All Python scripts compile; media CLI help and example scene validation execute.
- Entire skill copied to isolated `.agents/skills` and `.claude/skills` directory layouts. All relative Markdown resources resolve and the example validator executes from both copies. No original third-party skill installation is needed.
- Independent read-only behavioral dry run: preserves unknown-job reservation (100 − 45 − 40 = 15), blocks duplicate retry, keeps previs and appearance approvals separate, requires actual new background image review, and distinguishes edit frame count from generative motion fidelity.

## Behavioral evidence and limits

Without this skill, a baseline agent already handled budget uncertainty and exactness honestly; those are not demonstrated improvements. It combined previs and appearance into one visual review, saying the package covered “character interpretation, village appearance, framing, jump timing, and landing locations.” Its record had one generic review entry rather than distinct previs/appearance approvals. The authored skill explicitly separates these records and requires actual image files; the subsequent independent dry run used both checkpoints.

The forward evaluator initially saw a partially written directory and reported a missing local-tools reference and missing assembler invocation. These resources were then completed; isolated-copy link checks and `media.py --help` confirm their presence. That observation was not an execution failure of FFmpeg. This was a small behavioral sample, not a statistical evaluation or proof against all errors.

## Not executed / not claimed

- Blender rendering: initial checks lacked Blender; the runtime verification below supersedes that initial limitation.
- FFmpeg encoding, assembly, audio/subtitle muxing and decode smoke tests: ffmpeg/ffprobe unavailable.
- Live Higgsfield authentication, uploads, paid calls, generation quality and lip sync remain unverified. Installed/enabled plugin status is verified, but read-only calls returned `Unknown tool` in this host.
- Codex skill discovery and installed-resource invocation are now verified; Claude Code live invocation remains unverified.
- `npx skills add` installer execution: documented installation route, not tested here.
- Windows/Linux runtime behavior.

The media helper still requires real FFmpeg smoke tests. Blender 5.3.0 is now tested as described below; other Blender releases remain untested. No frame-identical AI motion is promised.

## Next production smoke test

1. Run doctor after installing the local runtimes.
2. Validate and render `assets/example-scene.json` into a fresh output directory.
3. Encode its 48 PNG frames at 24 FPS, inspect actual frames/playback, and verify the 2-second MP4.
4. Assemble two synthetic clips with known frame counts, a test voice mix and SRT; inspect padding, audio and caption timing and verify decoded frame count.
5. Invoke the installed skill from each host in a new session; confirm relative resources and separate MCP connections.
6. Only with a separately approved budget, generate one shot from approved previs and images, then compare actual event frames and record deviations.

## Independent package review

One actionable QA finding was fixed: final decode now passes `-xerror` so reported decode errors fail verification. The command-contract regression test failed before the fix and passed after it; a corrupted-media runtime test remains unexecuted without FFmpeg. No other important code or workflow finding was reported.

## Blender controls update

Added deterministic linear/smooth integer-frame sampling, camera path/follow/lens keys, a foot-rooted capsule, sampled bounding-box framing and center-ray occlusion reports, declared ground-contact windows, review stills, and a cut/role handoff. GUI execution is rejected before resetting a scene. Optional-control validation rejects invalid lenses, missing follow subjects, invalid intervals and a camera coincident with its target at a sampled frame.

Nine new unit tests failed against the prior implementation, then passed with the additions (initially 16 unit tests; now 18 after review regressions). A real Blender smoke test is included in `tests/test_blender_runtime.py`; it is skipped explicitly when Blender is unavailable. It can use `BLENDER_BIN` for a nonstandard installation. It verifies review PNGs, saved scene camera/lens keys, and the audit report. Compilation/schema checks do not substitute for that test.

Behavior change: previous implicit Bezier motion becomes explicit linear by default, with opt-in smoothstep; old specs must be rerendered/reviewed. The capsule has no articulated limbs. Occlusion is a single center ray; ground contact uses a bounding-box bottom and flat plane. No mesh collision, terrain contact, advanced rigging or AI frame fidelity is claimed.

Reference reviewed: Scenario Labs' blockout skill and its MIT license. This update uses independently written helpers and introduces no Scenario package or service dependency. No upstream code is bundled.

Independent review found two camera override bugs: an unused malformed target crashed follow-camera sampling, and a base coincident target was rejected even when frame-1 keys/follow provided a valid target. Both were reproduced in tests and fixed. Final suite: 18 passed, 1 Blender integration test explicitly skipped. Omitted object rotation now holds the previous pose; the migration note documents the change.

## Blender 5.3.0 runtime verification

Actual installation reported Blender 5.3.0. The previously skipped integration test first failed because this release exposes `BLENDER_EEVEE` instead of the hardcoded `BLENDER_EEVEE_NEXT`. The renderer now selects the supported EEVEE identifier from RNA; it fails explicitly if neither exists. On restricted macOS execution, Metal initialization and thumbnail/cache writes were denied; the same test passed with host-approved GPU/cache access.

After the fix, all 19 tests pass, including real PNG renders, audit output and reopening the saved .blend to check final-frame camera position and lens. No skips. A separate full 48-frame, 24 FPS, 360×640 tracking-jump render completed. Its configured framing/center-ray/contact checks covered all 48 integer frames and returned no findings. Frames 1, 24 and 48 were visually inspected; the entire sequence has not been visually reviewed or encoded into MP4.

The user-installed Codex skill has been discovered in a live turn. Local `ffmpeg` and `ffprobe` remain unavailable, so media-helper encoding/muxing is still untested. Higgsfield is installed and enabled according to plugin discovery, but read-only profile/model calls returned `Unknown tool`; no provider account, model availability, upload or paid generation was verified and no credits were used.

## 2026-11-12 story design and fidelity gates

Trigger: review of the first generated ep01 edit (previs v004 vs selected takes, five relative points per shot) and review feedback that the story lacked conflict.

- New `story-design` skill with `check_story.py`; `video-previs-workflow` gained `gate.py` (`ready`, `submit`), clip `start`/`speed`/`dialogue` limits in `media.py assemble`, and `media.py pair` contact sheets. Every new test was run red before its implementation.
- Suite: 63 tests pass on this host (Python 3.11.7, Blender 5.3.0, local FFmpeg), including the Blender runtime test. `media.py pair` was run on real ep01 clips (s01, s04); the s04 take has audio longer than video and its last sample is still filled.
- Retrospective check: `gate.py ready` on the unchanged ep01 `state.json` exits 1 with 143 lines: no approved story; `required_events` missing for s01–s07; no approved start keyframe for s01–s07; no retry reserve; and role decisions missing for every previs object, including `slide`, `tent`, `scanner`, `suitcase`, `seat`, `plane_window` and `counter`. These match the review findings (composition drift without keyframes, slide/tent continuity without prop assets, untracked required events, a 1.5-credit remainder with no retry room). Had the gate existed, the first paid video call would have been blocked.
- Observation: shots with many set-dressing proxies (ten hair strands, five houses) need one `object_roles` entry each; mapping them to a set role or `null` is verbose but explicit.

Not verified: paid keyframe or video generation through the new gates, live invocation of `story-design` from Claude Code or Codex, and whether keyframe start frames actually hold composition in the provider's models.

## 2026-11-12 reference-led route

Trigger: a request to reproduce another video's composition, action and timing with new characters. The story gate made that impossible without an invented purpose and target action.

- `media.py cuts` (ffmpeg scene score → draft breakdown, start/mid/end stills and a clip per shot), `gate.py reference`, and an approved `reference` in state accepted in place of `story`; `ready`/`submit` then require previs shot frames = round(end × fps) − round(start × fps). Each new test was run red before its implementation; the suite has 88 passing tests.
- Baseline (skill without the route, synthetic 30 fps reference with cuts at 1.5 s and 3.5 s, target 24 fps): the agent invented a placeholder story (`structure: custom`, payoff set equal to the CTA beat) to get past checkpoint 0. It hand-built cut detection with raw ffmpeg, decided the fps rounding itself and planned to use only the previs as motion control.
- With the route, the same scenario: the agent used `media.py cuts`, wrote `reference-v001.json` that passed `gate.py reference`, derived 36/48/30 frames by the documented rule, and proposed the reference clip as motion input with upload consent. Its remaining findings were fixed: an event at a cut now belongs to the next shot (`start ≤ t < end`), and draft image paths are named `stills`, not `frames`.
- `media.py cuts` was run through the installed skill path on the same file: the stills next to each cut sample their own shot (red, test pattern, green).

Not verified: real-world footage with dissolves or fast motion (the threshold is a proposal and needs review), event timing beyond manual frame reading, and provider motion control fed with a reference clip.

## 2026-11-12 manual web handoff

Trigger: Higgsfield plan Unlimited applies only to manual generation on higgsfield.ai. Its help center says MCP, CLI and other automated generations always deduct credits, which matches ep01 (MCP, 198.5 credits) against 0-credit web generations on the same account. The skill assumed MCP submission and had no handoff format.

- `handoff.py pack` (job.json → `NN-<slot>.<ext>` uploads, `request.md`, empty `output/`, input hashes) and `ingest` (one non-hidden result, kind and decode check, refuse overwrite, hash/size/duration/fps). `gate.py` now accepts `max_shot_quote: 0` with `retry_reserve: 0` for all-web-Unlimited plans, and a job quoted above 0 is still rejected. Docs add the manual route, the `handed_off` job state and a ban on automating provider web apps. Each new test was run red before its implementation. The suite has 104 passing tests.
- While running the tests, ffprobe exited 0 on a corrupt PNG, reporting 0×0 and decoding no frames. `ingest` now requires a decoded frame and nonzero dimensions.
- Rehearsal on `../projects/ep01-v2` (s01 start keyframe job, Seedream 5.0 Lite, 5 inputs: previs v003 f1 plus the traveler, purple, amber and cabin images):
  - `pack` printed 5 hashes and a readable `request.md`.
  - `ingest` of a dropped PNG returned 360×640 with a matching hash.
  - A second `ingest` to the same destination exited 1.
  - `state.json` hash was unchanged (02372f13… before and after).

Not verified: an actual web generation and its ingest, slot names on the real provider screen, and video ingest of a provider-made MP4 (covered only by a synthetic ffmpeg clip).

## 2026-11-12 keyframe continuity

Trigger: on ep01-v2, start keyframes generated from per-shot prompts drifted between shots. Web Seedream 5.0 Lite produced wrong counts, mixed accessories, an armless bust and leaked set objects. With MCP Nano Banana Pro, the s02 floor came out as pale sand and the s03 floor as a dirt path. Each frame looked acceptable beside its previs frame. The user caught the mismatch only by viewing all keyframes side by side. Adding the approved s05 keyframe as a floor/set reference fixed both.

- `media.py continuity STATE OUT` tiles each shot's current start keyframe (approved, else latest pending) into one row per role shared by 2+ shots. Cells are 270×480 and the row legend is printed as JSON.
- `gate.py` (`ready`: all shared roles; `submit`: the job shot's roles) now requires an approved `continuity[]` record whose keyframe hashes equal the current approved keyframes. It reports a missing or stale review per role.
- `production.md` adds the practices that fixed the keyframes:
  - Output-resolution guide frames.
  - Stand-in wording ("houses, not capped cylinders"; "a torso, not a box").
  - Exact counts and accessory ownership.
  - At most 4–5 references, with combined sheets and set images cleaned of stray objects.
  - An anchor frame per location.
  - A two-pass review: each frame beside its previs, then the continuity sheet across shots.
- `delivery.md` adds a boundary check between consecutive takes that share a set role.
- Each new test was run red before its implementation. The suite passed after each task.
- ep01-v2 run (read-only, state hash unchanged):
  - The sheet has 9 rows (traveler, purple, amber, village, mint, slide, tent, inspection set, inspector).
  - `gate.py ready` reports exactly those 9 roles as needing review, and nothing else.
  - The rows show one floor, light and character design across the village shots.

Not verified: video takes against the boundary check (none generated yet). Rows also include shots where a role enters only after frame 1 (for example the stowaways in s02). That frame cannot show the role, so its consistency is checked only in the take.

## 2026-11-12 sequence takes and staged handoff folders

Trigger: on ep01-v2 the first three web takes (Seedance 2.5, 0 credits) were each generated from an independently composed keyframe. Inside the village, the s02→s03 cut jumped in camera and character positions. s03 also raised the slide and tent on the opposite sides from the previs and the approved s05/s06 keyframes, because those props rise mid-shot and nothing fixed their place. The cabin→village cut (a location change) read naturally.

- `generation.md` adds sequence takes for consecutive same-location shots:
  - Start from the first shot's approved keyframe.
  - Use later shots' keyframes as "how the scene looks at T s" references.
  - Use concatenated previs clips as the motion reference, with offset event times.
  - Name the fixed prop positions.
  - Request a duration within the model limits (web minimum 4 s).
  - `delivery.md` cuts one clip per shot from the same source by in-point.
- `gate.py submit` accepts `shots` (covered shot ids, beginning with `shot`) and checks every covered shot and its roles' continuity. Tests for an unready covered shot, an unknown shot and a wrong first shot were run red before the change, and the suite passes.
- Handoff folders are now staged (`handoff/assets|keyframes|videos/<id>`). The ep01-v2 folders were moved and `jobs[].pack_path` updated (16 folders). No unprocessed results were present.

Not verified: the sequence takes themselves (seq-s02-s03 and seq-s05-s06 are packed and waiting for web generation), including whether Seedance 2.5 keeps the 19 s discovery at 6.0 s inside an 8 s take.
