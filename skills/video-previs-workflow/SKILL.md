---
name: video-previs-workflow
description: Use when producing or revising a video from an idea, script, storyboard, or reference footage using Blender previs and reference images, including Higgsfield-assisted animation, live-action concepts, and product videos.
---

# Video previs workflow

Establish direction with a reviewable previs, then approve actual appearance images before generating final shots. Deliver an edited MP4 and resumable production records. Respond in the user's language. Support new, supplied, and mixed assets; do not require source footage or another skill.

## Start or resume

Locate this installed skill's directory; resolve bundled resources relative to it, not the working directory. Run `python3 scripts/doctor.py` using that resolved path. Discover generation tools and authentication in the current host; installation does not connect MCP. Read [production.md](references/production.md) for planning and review, and [project-state.md](references/project-state.md) before creating or resuming project records.

Read existing records and user decisions before asking questions. Resume the latest valid stage. Inspect provided images early for proportions and spatial constraints. With only an idea, propose concrete action, dialogue and shots. Distinguish observed reference details from proposed changes. Establish aspect ratio, FPS, duration, audio, important events and output location. Keep project-specific brand rules in the brief.

## Production checkpoints

1. **Previs:** Block story, action, camera and timing in Blender. Use [local-tools.md](references/local-tools.md). Render and inspect actual frames/video, then show them for approval. Record the exact spec/render revision approved. If source footage is inaccessible, say what was not observed.
2. **Appearance:** Prepare actual character/person, background, prop and product image files. Generate, edit or reuse supplied images per asset. Show files for review and record approved versions separately from previs approval. A prompt list or proxy render does not satisfy this checkpoint. Retain originals. Structural changes return affected shots to previs review.
3. **Generation:** Read [generation.md](references/generation.md). Bind approved asset versions and previs to each shot, discover supported inputs, submit within the approved job budget, retrieve outputs and inspect them. Approval to author a skill or previs is not a paid-generation budget.
4. **Edit and QA:** Read [delivery.md](references/delivery.md). Conform clips to the timeline, add agreed speech, sound effects and subtitles, apply lip sync where needed, and verify the final MP4. Retain intermediate artifacts and report unresolved defects.

There are two creative checkpoints, not a new permission request per tool call. Reuse explicit approvals for unchanged versions. A changed approved decision reopens its affected checkpoint. Before the first paid image, voice, video or lip-sync call, obtain one job-wide scope, cost cap and attempt limit; continue within it without repeated authorization.

## Reliability

Persist approvals, asset versions, job status and budget in project files so another host can resume. Claim the project before paid submission; only one host may submit at a time. Unknown submission status blocks duplicate retry and retains its cost reservation. Stop at exhausted limits, missing required capabilities or unresolved cost; continue useful unpaid work.

Cut timing and frame count are controllable in editing. Generated intra-shot motion is approximate until inspected; do not promise frame-identical AI output. Report the actual frames/events examined. A spec diff is not video fidelity verification. Never mark a stage complete without its actual artifact and evidence.
