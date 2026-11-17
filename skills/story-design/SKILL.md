---
name: story-design
description: Use when planning a short video, ad or series episode from a concept, before scripting, storyboard or previs — fixes the core purpose, the viewer action to drive, and a structure that serves both, then writes timed beats.
---

# Story design

Design the story backwards from what the video must achieve. A fun idea is not a story design until its purpose, target action and structure are locked and every beat serves them. Respond in the user's language.

## Order

1. **Draft the setup before any plot.** From the concept, brief and references, fill the five required `setup` fields yourself: `premise` (who, where and what happens, in one sentence), `tone` (how it should feel), `avoid` (the feeling it must not have), `lead` (who they are and what they want) and `setting` (place and time). Add the optional `hook` (what is funny or surprising) only when the piece has one; a product film or a sincere ad needs none. Show one filled draft with two alternatives for `tone` only. The user edits the draft; do not send open questions.
2. **Lock three things before any plot.** Read the concept, brief, references and feedback first.
   - `purpose`: one sentence a viewer should be able to say after one viewing.
   - `target_action`: one viewer action (save, share, follow, book…), the `cue` that asks for it (caption, line, end card) and the `beat` where it lands.
   - `audience`: who watches and where.
   If the brief cannot decide them, propose two or three concrete options and ask. Keep brand and claim restrictions from the brief.
3. **Choose a structure** from [structures.md](references/structures.md) and write `structure.why` as the link from purpose and action to that structure. Conflict is not a default: add it only when the structure needs it.
4. **List elements** (characters, conflicts, jokes, reveals, props that carry meaning). Each has `serves` (`purpose` or `target_action`) and `why`. Delete anything you cannot justify.
5. **Write timed beats** from 0 s with no gaps: visible `event`, `emotion`, `tension` 0–5 and `serves`. Where the structure needs obstacles, the `obstacle` field names who blocks and how — an antagonist must act, not just appear.
6. **Self-review** before showing anything:
   - Does the antagonist act against the goal, more than once when the structure demands it?
   - Does the hero pay a visible cost before the payoff?
   - Does tension peak in the beat right before the payoff?
   - Does the action cue land at or after the emotional payoff?
   - Could a first-time viewer state the purpose?
7. **Write `story-vNNN.json`** in the project (schema: [example-story.json](assets/example-story.json), a synthetic demo, not a creative default) and run `python3 scripts/check_story.py story-vNNN.json` from this skill's directory path until it prints `OK`. The checker covers structure, not quality; the self-review still applies.
8. **Review with the user** as a beat table (time, event, obstacle, tension, serves) plus setup, purpose, action and structure. Record approval evidence. Never edit an approved version; revisions get a new file.

## Handoff

Production skills (for example video-previs-workflow) consume the approved file: path, hash and approval. When feedback says a story "feels flat", check the structure first: a passive antagonist, missing cost or early tension peak are story-design failures, not animation fixes.
