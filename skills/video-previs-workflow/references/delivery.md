# Edit, inspect and deliver

Choose approved takes; keep source clips intact. Build an edit manifest using exact frame counts. Normalize resolution, frame rate and aspect ratio, recording any crop, retime or freeze padding. The bundled assembler letterboxes and pads short clips with their last frame; verify that any padding is acceptable. A short generated action should generally be repaired before editing rather than hidden by a frozen frame.

Prepare a mixed audio track on the final timeline: dialogue/narration, sound effects and optional music. Preserve intentional silence. Clip audio is discarded by the bundled assembler, so include any wanted generated audio in the mix. Apply lip sync using a supported tool before final edit where visible speech requires it, and inspect mouth/speech alignment. No speech means no mandatory lip-sync call.

Create timed SRT subtitles and proofread words/timing. The assembler supports selectable MP4 subtitles (`mov_text`), not burned-in text. If the requested platform requires burned-in subtitles, use an inspected FFmpeg filter command with a suitable local font and verify the rendered glyphs. Do not substitute selectable captions without reporting the difference.

## QA evidence

For each shot compare previs and selected take at cut boundaries and required-event windows. Inspect actual frame images and playback when available; expand sampling around discontinuities. Record frame numbers/timestamps and findings for:

- Identity, silhouette/clothes, props, entity counts and background continuity.
- Event order, contact/occlusion, motion direction, camera movement and entry/exit state.
- Timing drift, frozen/padded frames and unintended cuts.
- Voice intelligibility, effects, sync and subtitle text/placement.

Record uninspected intervals. A frame extraction command creates evidence to inspect; it does not inspect the images. Side-by-side comparison ends at the shorter input and is a visual aid, not a fidelity score. Spec changed-shot lists report numerical/structural edits only. Do not promise generative frame identity; exact frame choreography may require a separately scoped native animation/compositing route.

Probe and decode final MP4. Check width/height, FPS, frame count, cut order, total duration, audio presence and intended subtitles. Listen to audio if supported; otherwise state that listening was not performed. Confirm file exists and is nonempty; deliver a local link to it, the review package and a concise QA/cost summary. Mark partial delivery if required content or runtime verification remains missing.
