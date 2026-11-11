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
