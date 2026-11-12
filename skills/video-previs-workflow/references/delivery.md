# Edit, inspect and deliver

Choose approved takes; keep source clips intact. Build an edit manifest using exact frame counts. Normalize resolution, frame rate and aspect ratio, recording any crop, retime or freeze padding. The bundled assembler letterboxes and pads short clips with their last frame; verify that any padding is acceptable. A short generated action should generally be repaired before editing rather than hidden by a frozen frame.

Fit a long take by choosing its in-point (`start`, seconds) and frame count, not by speeding it up. The assembler accepts `speed` only within 0.9–1.1 and rejects any speed change on clips marked `dialogue: true`, because a faster voice and mouth are noticeable. If the action cannot fit within those limits, regenerate or re-cut the shot instead of retiming it.

Prepare a mixed audio track on the final timeline: dialogue/narration, sound effects and optional music. Preserve intentional silence. Clip audio is discarded by the bundled assembler, so include any wanted generated audio in the mix. Apply lip sync using a supported tool before final edit where visible speech requires it, and inspect mouth/speech alignment. No speech means no mandatory lip-sync call.

Create timed SRT subtitles and proofread words/timing. The assembler supports selectable MP4 subtitles (`mov_text`), not burned-in text. If the requested platform requires burned-in subtitles, use an inspected FFmpeg filter command with a suitable local font and verify the rendered glyphs. Do not substitute selectable captions without reporting the difference.

## QA evidence

For each shot build `media.py pair PREVIS TAKE sheet.jpg` (previs row over take row at matching relative times), then compare previs, keyframe and selected take at cut boundaries and required-event windows. Inspect actual frame images and playback when available; expand sampling around discontinuities. Record a pass/fail table per shot, with frame numbers/timestamps and findings for:

- Composition against keyframe and previs: shot size, camera height, start and end framing.
- Every entry in the shot's `required_events`.
- Prop continuity across shots: the same prop keeps the same structure, material and colour wherever it appears.
- Identity, silhouette/clothes, props, entity counts and scale, and background continuity.
- Event order, contact/occlusion, motion direction, camera movement and entry/exit state.
- Timing drift, frozen/padded frames and unintended cuts.
- Voice intelligibility, effects, sync and subtitle text/placement.

On the reference-led route, also run `media.py compare` on the reference and the final edit, and report each reference event's frame offset in the final.

Record uninspected intervals. A frame extraction command creates evidence to inspect; it does not inspect the images. Side-by-side comparison ends at the shorter input and is a visual aid, not a fidelity score. Spec changed-shot lists report numerical/structural edits only. Do not promise generative frame identity; exact frame choreography may require a separately scoped native animation/compositing route.

Probe and decode final MP4. Check width/height, FPS, frame count, cut order, total duration, audio presence and intended subtitles. Listen to audio if supported; otherwise state that listening was not performed. Confirm file exists and is nonempty; deliver a local link to it, the review package and a concise QA/cost summary. Mark partial delivery if required content or runtime verification remains missing.
