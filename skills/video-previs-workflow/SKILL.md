---
name: video-previs-workflow
description: Use when producing or revising a video from an idea, script, storyboard, or reference footage using Blender previs and reference images, including Higgsfield-assisted animation, live-action concepts, and product videos.
---

# Video previs workflow

Lock the story's purpose first, establish direction with a reviewable previs, approve actual appearance images and per-shot keyframes, then generate final shots. Deliver an edited MP4 and resumable production records. Respond in the user's language. Support new, supplied, and mixed assets; do not require source footage or another skill.

## Start or resume

Locate this installed skill's directory; resolve bundled resources relative to it, not the working directory. Run `python3 scripts/doctor.py` using that resolved path. Discover generation tools and authentication in the current host; installation does not connect MCP. Read [production.md](references/production.md) for planning and review, and [project-state.md](references/project-state.md) before creating or resuming project records.

Read existing records and user decisions before asking questions. Resume the latest valid stage. Inspect provided images early for proportions and spatial constraints. With only an idea, propose concrete action, dialogue and shots. Distinguish observed reference details from proposed changes. Establish aspect ratio, FPS, duration, audio, important events and output location. Before the story or reference is approved, record the `generation_profile` (model, longest take, duration step, reference slots, resolution, Unlimited eligibility) from the tool contract, the user's screen or their statement: shot structure depends on it. Keep project-specific brand rules in the brief.

## Production checkpoints

0. **Story:** Before previs, obtain an approved story design: core purpose, target viewer action and a structure chosen for both, with timed beats. Use the `story-design` skill if it is installed; otherwise meet the minimum in production.md. To reproduce a reference video's composition, action and timing, an approved reference breakdown replaces the story design: follow the reference-led route in production.md. Record path, hash and approval in state.
1. **Previs:** Block story, action, camera and timing in Blender. Use [local-tools.md](references/local-tools.md). Meet the proxy minimums in production.md. When a storyboard or reference exists, show a side-by-side sheet (panel ↔ previs frame) and list every dropped or changed panel as a decision for approval. Revise on event stills and render the full animation once; drafts are `dNN`, reviewed renders `vNNN`. Render and inspect actual frames/video, then show them for approval. Record the exact spec/render revision approved. If source footage is inaccessible, say what was not observed.
2. **Appearance:** Prepare actual image files for every role in each shot's `object_roles`: characters/people, sets, recurring props and products. Props whose structure matters get a structure view. Characters whose back or side is seen in previs get one front + back sheet; others a front view. Generate, edit or reuse supplied images per asset. Show files for review and record approved versions separately from previs approval. A prompt list or proxy render does not satisfy this checkpoint. Retain originals. Structural changes return affected shots to previs review.
3. **Shot keyframes:** Compose an approved start frame per shot (and end frame when the tool supports it) from the previs frame and approved assets; review each beside its previs frame, then review all keyframes across shots with `media.py continuity` and record one approval per shared role (the gate enforces it). Character sheets and control videos do not carry composition.
4. **Generation:** Read [generation.md](references/generation.md). Bind approved asset versions, keyframes and previs to each shot, discover supported inputs, submit within the approved job budget, retrieve outputs and inspect them. Run `scripts/gate.py ready` before the first paid video call and `scripts/gate.py submit` for every job; do not submit while it reports errors. When the user generates in a provider's web app (for example a web-only Unlimited allowance), follow the manual route in generation.md; never automate the web app. Approval to author a skill or previs is not a paid-generation budget.
5. **Edit and QA:** Read [delivery.md](references/delivery.md). Conform clips to the timeline, add agreed speech, sound effects and subtitles, apply lip sync where needed, and verify the final MP4. Compare every take with its previs using `media.py pair`. Retain intermediate artifacts and report unresolved defects.

Creative checkpoints are story, previs, appearance and keyframes; batch each into one review, not a permission request per tool call. Reuse explicit approvals for unchanged versions. A changed approved decision reopens its affected checkpoint. Before the first paid image, voice, video or lip-sync call, obtain one job-wide scope, cost cap, attempt limit and a retry reserve covering at least one retry of the most expensive shot; continue within it without repeated authorization.

## Reliability

Persist approvals, asset versions, job status and budget in project files so another host can resume; edit state with `scripts/state.py`. Claim the project before paid submission; only one host may submit at a time. Unknown submission status blocks duplicate retry and retains its cost reservation. Stop at exhausted limits, missing required capabilities or unresolved cost; continue useful unpaid work.

Cut timing and frame count are controllable in editing. Generated intra-shot motion is approximate until inspected; do not promise frame-identical AI output. Report the actual frames/events examined. A spec diff is not video fidelity verification. Never mark a stage complete without its actual artifact and evidence.
