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

## 2026-11-17 lessons from a reference-led single-take production

Source of the changes: one reference-led production (a 25 s single take, kept outside this repository). Each failure seen there became a gate check, a script option or a reference rule.

- Tests: 189 pass (`python3 -m unittest discover -s tests`, Python 3.11.7, Blender 5.3.0, ffmpeg present); 127 before. Every new check and option was written test-first and seen failing.
- Independent review of the whole change (fresh reviewer, about 70 legacy and wrong-type inputs run against the gate; option errors run under Blender): no critical finding. Five findings were fixed test-first afterwards: a split take is now an error when `gate.py reference` is run without `--max-duration`; `state.py` keeps the lock and the reservation for an `unknown` job, counts an attempt when a job is settled without `submit`, no longer crashes on a malformed job already in state, prints one error line for a missing or broken state file, and no longer drops a lock taken by someone else when a returned manual take is settled.
- New gate checks (all report malformed input instead of raising): `setup` on story and reference files, `review_notes` closed before approval, asset `kind` and shot `props`, `generation_profile` with a take-length limit, `camera_evidence` and the one-take rule on reference breakdowns, paid-only attempt limit.
- Run on the production's own files (scene of 226 proxy objects, 600 frames, 360×640):
  - `render_previs.py --audit-only`: 12.8 s. With `audit.groups` and `crop_ok` it reports 8 findings, all `center_occluded` at frames 220-241 (9.1-10.0 s), where the lead is behind the front row on purpose. The same scene without them reported an issue on most sampled frames, which had hidden a real occlusion.
  - `render_previs.py --frames` with 13 event frames: 23.7 s. During the production a review-only pass of the same scene rendered 273 stills in 3 min 47 s and each full render took about 10 minutes.
  - `media.py pair --times` with 13 times, reference crop against previs: 3.0 s, sheet 3510×960.
  - `gate.py ready` on the production's state, after filling the profile, kinds, props and notes: it reported exactly the two fields still missing there (`reference: setup …`, `reference s01: camera_evidence …`). After a reference version with a user-chosen `setup` and measured `camera_evidence` was approved through `state.py approve`, `gate.py reference --max-duration 30` and `gate.py ready` both printed `OK`.

Not verified: a new production started under these rules. The setup draft-first step, the risk review before a first take and the stills-first previs loop are documented and unit-checked, but no project has yet been run through them from the start. `crop_ok` applies to a subject for the whole shot; a long take that opens on a close-up cannot limit it to the first seconds.

## 2026-11-18 shot design, staging checks and floor plan

Source of the changes: a comparison with `scenario-blender-previs-storyboard` in scenario-labs/skills (MIT). Its shot-design rules were rewritten for this skill's idea-led route; no code was taken.

- Tests: 270 pass (`python3 -m unittest discover -s tests`, Python 3.11.7, Blender 5.3.0, ffmpeg present); 246 before. Every new check and option was written test-first and seen failing, including the runtime test for `line_crossed` under `--shot`, which was run against the previous scripts.
- Sensor-height rule: measured in Blender 5.3.0 with `sensor_width = 36` and the default sensor fit. A 360×640 frame at 40 mm has a horizontal half-angle of 0.2479 rad and a vertical one of 0.4229 rad; 1920×1080 has the reverse. The 36 mm sensor therefore lies along the longer side, which is what the distance formula in production.md and `plan_layout` use.
- Floor plan, inspected by eye on a two-shot scene (two figures, a table, cameras on opposite sides of the pair, one figure walking 3 m): both figures and the table are visible from above, each camera is a white wedge with its shot id, the action line is yellow through both figures, and the walking figure has its path, end square and id. No drawing size was changed after the inspection. Colours print lighter than the spec values (the same linear-to-display conversion as the previs renders).
- Independent review of the whole change (fresh reviewer; all six review-focus cases run under Blender; `screen_travel` compared with Blender's camera right axis in 128 camera and walk directions, `line_side` with the on-screen order of the pair in 268 random layouts): no critical finding, signs correct. Three findings were fixed test-first afterwards: `--plan ""` ran a full render and is now refused; a figure standing somewhere else in a later shot was not drawn and now gets a labelled square (inspected by eye on a scene with both figures shifted in the second shot); `"line": null` passed validation and then raised, and is now a validation error.

Not verified: no production has used the shot-design rules, the two staging checks or the floor plan yet, so their effect on generated takes is unknown. The checks read root positions on the ground plane and the action line only at the two frames either side of a cut; they do not see bodies, faces or eyelines. The floor plan was inspected on one small scene, not on a crowded set.

## 2026-11-18 lessons from a footage-led reel

Source of the changes: one production kept outside this repository (a 29.5 s reel that follows a third-party reel's format, with real footage of a partner's shop and a generated guest) and the team's feedback on it. It was made without this skill's state and gates; each safeguard its makers applied by hand became a check, a tool or a rule.

- Tests: 276 pass (`python3 -m unittest discover -s tests`, Python 3.11.7, Blender 5.3.0, ffmpeg present); 270 before. Every new check and the new tool were written test-first and seen failing.
- New gate checks: `source.rights` and `match` on a reference breakdown, a `decision` on every candidate cut, and a recorded `source.upload_agreed` before third-party reference footage is a job input (paths compared after normalising). A reference file from before this change fails `gate.py reference` until the two fields are added.
- `media.py cuts` on the production's edit (36 shots by its own timeline, nine of them 2 to 5 frames long): 34 shots detected, all nine short ones among them, and three candidates. One candidate is a real cut that the 0.3 threshold misses (24.71 s, score 0.295); two are not cuts (0.33 s and 23.67 s, scores 0.12 and 0.11). The 36th cut, between two stretches of the same clip at about 28.7 s, scored under 0.1 and is in neither list: a cut between near-identical pictures is invisible to a scene score, and only the every-frame look that production.md asks for finds it.
- `media.py sheet` on a frame of the real footage, a crop of it and the generated keyframe of the same tub: the sheet shows the generated water as a saturated olive yellow in a fuller tub against pale green in the footage, the mismatch that had been "fixed" in words.
- The reference itself was measured in a browser, frame by frame (30 steps per second, mean luma difference): 35 cuts, the nine opening cuts at 0.20 to 1.33 s as the production's final count has them. Ten cuts between 5.2 s and 14.0 s sit 2 to 3 frames later in the edit than in the reference; the production's timeline carries the same offset, written in tenths of a second.

Not verified: no production has run under these rules. The real-footage pass is a comparison aid; whether an image reads as generated stays the user's judgment. The clearance table and the facts list are prose in `brief.md` and nothing checks them. (Decided the same day after the trial below: see `no_previs`.)

## 2026-11-18 trial production under the skill

Source of the changes: the same reel as the section above, this time made under the skill on the branch, from the reference breakdown to approved keyframes (project kept outside this repository; 30 numbered findings in its `trial-notes.md`).

- What was run: a 36-shot reference breakdown from a screen recording (30 cuts detected, the other 5 found as candidates, all 35 confirmed against a frame-by-frame measurement of the original); a plan per shot (17 generated, 9 real footage, 10 reused frames); previs of the 7 shots where a figure is placed in a room, two drafts and two reviewed versions; 10 assets (3 generated character references, 7 crops of real footage); 6 start keyframes and 4 regenerations, each reviewed beside its previs guide and beside real frames; 26 credits spent by MCP, equal to the quotes; every stage approved by the user and recorded in state.
- Tests: 287 pass (`python3 -m unittest discover -s tests`, Python 3.11.7, Blender 5.3.0, ffmpeg present); 276 before the trial. Each change was written test-first and seen failing.
- Changed because of the trial: `camera_evidence` is not asked of a `format` reference; `no_previs` with a reason for close inserts and POV details (all 17 generated shots were blocked once: the 10 inserts told less than their one-line description, the 7 room shots showed camera height, facing and that three of them need a back view); a `plan` on every shot of a `format` reference, which also frees footage and reused shots from the previs check; `--low` 0.2 with neighbouring candidates merged (0.1 gave 46 candidates, 40 from one walking shot; 0.2 gave exactly the 5 missed cuts); `sheet --cell` and a printed legend; `state.py put` refuses a record without its path (the breakdown itself had been stored and approved, and the reference checks did not run until it was noticed); `state.py asset --source/--origin`; text-only handoff packs; rules for guests and staff, one role per outfit, sheets that hide hair or face, framing in words, screen recordings, and the price of short shots on a model with a minimum take length.
- Seen in the keyframes: the bath water came out the pale green of the footage (the earlier production's wording fix had overshot to olive); a towel-turban sheet alone gave brown hair and a different face twice, and the face reference as a fourth input brought both back; one close framing stayed wider than its guide in both attempts.

Not verified: video generation, edit and QA under these rules. The user, not the agent, judged whether the keyframes read as generated and whether the woman is the same person across shots. The `plan` and `no_previs` rules have been used on this one production only.

Independent review of the whole branch (fresh reviewer; 38,000 mutated states, references, specs and jobs run through the gate against `main`; every review-focus case of both plans run): no critical finding, no new exception, and no change for inputs without the new keys other than the documented `source.rights` and `match`. Fixed test-first afterwards: a `no_previs` shot must now state its `object_roles` (without them it skipped the asset, prop and continuity checks); the third-party footage check compares paths against the project root, so an absolute spelling no longer slips through; merged candidates keep the stretch they stand for (`from`, `to`) and unsorted input loses nothing; a missing spec no longer blames `no_previs` shots; the stale `decision` wording in the docs. Left as they are, all pre-existing on `main` or cosmetic: an unhashable shot `id` still raises in three places, `handoff.py pack` still raises on a malformed input entry, `put` accepts an empty path string, `sheet --cols` is not clamped, a candidate at a split boundary still asks for a decision.

## 2026-11-19 look in the story, the generation choice and the project folder

Source of the changes: a 30 s salon vlog made under the skill (project kept outside this repository) that did not read as a vlog. Measured against its reference: 7 shots of 3 to 5 s where the reference has 23 in 52 s; 6 of 7 shots from a camera nobody in the scene holds, where the reference has none; a mirror shot whose prompt kept the phone out of the reflection; lenses of 31 to 89 mm; a set emptied of people and signs; three scripted lines. The story file held the format only as a sentence in `tone`, and shot design defaulted to eye height, 40 mm, static, few shots.

- What changed: `setup.look` (twelve picks) required from version 2 story and reference files; `purpose`, `structure.id` and the `cue` optional; `serves: mood`; beat `line` and `caption`; shot design takes camera, view and cut length from the look; `view` per shot and average shot length within 30 % checked by `gate.py ready`; a reference video is always saved and measured and the user asked how closely to follow it; `generation_plan` asked with the previs review and enforced at `ready` and `submit`; `state.py init` creates the project folder.
- Tests: 330 pass (`python3 -m unittest discover -s tests`, Python 3.11.7, ffmpeg present); 297 before. Each check was written test-first and seen failing. The size limit on the workflow's SKILL.md went from 6500 to 6700 bytes for the two rules added to it.
- Existing projects: 8 project states and 15 story and reference files run through the gate and the checker on `main` and on the branch. Story and reference verdicts are unchanged. `gate.py ready` gains one line on every project, the missing `generation_plan`; two projects that passed before now stop there until the choice is recorded.
- Fresh readers: three single runs of an agent given only story-design and a one-sentence vlog concept or the project brief. First concept-only run: the look came out as the lead's own phone, handheld, no `observer`, 2.0 s shots, `speech: none`, but it inferred a purpose, added a "Save" caption and invented a price, a duration and a booking method. After the wording was tightened (purpose and cue only when stated in words; caption facts only from the brief), the second run wrote no purpose, no cue and no invented fact. The brief-led run copied the eleven measured values and wrote 13 beats at 2.3 s; its purpose and cue were removed by hand under the tightened wording.

Not verified: no previs, keyframe or take has been made under the look rules, so whether the output reads as a vlog is unknown. Each wording was tried once, not five times. The `generation_plan` and project-folder rules have not been used on a production. Left as the fresh readers found them: when the setup draft is shown against "self-review before showing anything", what `tension` measures without conflict, whether a borrowed (0) structure writes its id, what `captions: info` carries when the brief gives no facts, where cuts between views inside a beat are marked, and the language of on-screen text when the audience differs from the client.
