# Edit, inspect and deliver

Choose approved takes; keep source clips intact. Build an edit manifest using exact frame counts. Normalize resolution, frame rate and aspect ratio, recording any crop, retime or freeze padding. The bundled assembler letterboxes and pads short clips with their last frame; verify that any padding is acceptable. A short generated action should generally be repaired before editing rather than hidden by a frozen frame. Third-party reference footage never appears in the edit, not as a clip, a still or a background.

For a multi-cut generation, inspect the actual transitions frame by frame. Map each usable range in the shared source to its shot ID, start and target frame count. Check the framing, action and usable duration against the approved previs. Leave merged, missing or short shots open for individual pickups. Reinsert approved ranges in the original timeline alongside footage and reused shots.

Fit a long take by choosing its in-point (`start`, seconds) and frame count, not by speeding it up. Keep a continuous one-take as one uninterrupted source range. If the manifest needs one entry per planned beat, use adjacent frame ranges in source order with no gaps, overlaps or visible cuts. Review any unintended internal cut before accepting the take. The assembler accepts `speed` only within 0.9–1.1 and rejects any speed change on clips marked `dialogue: true`, because a faster voice and mouth are noticeable. If the action cannot fit within those limits, regenerate or re-cut the shot instead of retiming it.

Prepare a mixed audio track on the final timeline: dialogue/narration, sound effects and optional music. Preserve intentional silence. Clip audio is discarded by the bundled assembler, so include any wanted generated audio in the mix. Apply lip sync using a supported tool before final edit where visible speech requires it, and inspect mouth/speech alignment. No speech means no mandatory lip-sync call.

Create timed SRT subtitles and proofread words/timing. The assembler supports selectable MP4 subtitles (`mov_text`), not burned-in text. If the requested platform requires burned-in subtitles, use an inspected FFmpeg filter command with a suitable local font and verify the rendered glyphs. Do not substitute selectable captions without reporting the difference.

## QA evidence

For each shot build `media.py pair PREVIS TAKE sheet.jpg` (previs row over take row at matching relative times), then compare previs, keyframe and selected take at cut boundaries and required-event windows. Inspect actual frame images and playback when available; expand sampling around discontinuities. Write one claim per required event ("all start at once" and "each slightly off the beat" are two events), record each result in the shot's `event_results` (`{event: {result: pass|fail|accepted, evidence}}`) and run `gate.py qa state.json` before calling a take done. Record a pass/fail table per shot, with frame numbers/timestamps and findings for:

- Composition against keyframe and previs: shot size, camera height, start and end framing.
- Every entry in the shot's `required_events`.
- Prop continuity across shots: the same prop keeps the same structure, material and colour wherever it appears.
- Boundaries: for consecutive shots that share a set role, extract the last frame of one take and the first frame of the next (`ffmpeg -sseof -0.1 -i A.mp4 -update 1 a_last.png` and `ffmpeg -i B.mp4 -frames:v 1 b_first.png`; `media.py extract` samples at an interval and can miss the final second) and compare floor, light, set dressing and character positions; report differences as defects.
- Identity, silhouette/clothes, props, entity counts and scale, and background continuity.
- Real and generated side by side: where the edit cuts between footage and a generated take of the same place, lay the last real frame beside the take's first (`media.py sheet`) and compare set state: liquid colour and level, light, clothing, what is on the surfaces. A generated take is matched to the footage, never the other way round.
- Prop count: for each entry of the shot's `props`, lay stills from just before to just after every change in its `states` and count the prop in each; record `prop_results.<role>` (`pass`, or `accepted` with the user's words). A second copy in the hand while the first is still in the mouth is the usual failure.
- Event order, contact/occlusion, motion direction, camera movement and entry/exit state.
- Timing drift, frozen/padded frames and unintended cuts. Run `media.py dupes TAKE` on every take: web exports can repeat a frame every second; `--fix OUT` replaces each with the average of its neighbours (a one-frame ghost on fast motion) and the original take is kept.
- Groups: run `media.py spread` on the take over the same window and grid proportions as the reference and store it as `group_motion.<role>.measured_s`. Overall beat timing does not show whether members move together.
- Travel: for every stretch where a figure changes place, lay stills 0.2 s apart from the take beside the reference; added sidesteps and people appearing in the way show here and nowhere else.
- Voice intelligibility, effects, sync and subtitle text/placement.

On the reference-led route, also run `media.py compare` on the reference and the final edit, and report each reference event's frame offset in the final.

Record uninspected intervals. A frame extraction command creates evidence to inspect; it does not inspect the images. Side-by-side comparison ends at the shorter input and is a visual aid, not a fidelity score. Spec changed-shot lists report numerical/structural edits only. Do not promise generative frame identity; exact frame choreography may require a separately scoped native animation/compositing route.

Probe and decode final MP4. Check width/height, FPS, frame count, cut order, total duration, audio presence and intended subtitles. Listen to audio if supported; otherwise state that listening was not performed. Confirm file exists and is nonempty; deliver a local link to it, the review package and a concise QA/cost summary. Mark partial delivery if required content or runtime verification remains missing.

For a short shot, show one grouped preview with hold lengths and any missing required actions labelled. Offer use as shown, change the edit, or regenerate just the chosen shots. Record explicit acceptance of holds separately from the required-event review. A still tail is never evidence that a missing action occurred. Use the select-takes and delivery commands in project-state.md to retain the measured ranges and close the project.
