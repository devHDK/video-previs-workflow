---
name: story-design
description: Use when planning a short video, ad or series episode from a concept, before scripting, storyboard or previs — fixes how it is shot (camera, cut rhythm, speech, captions, light, place), the viewer action to drive and, when it has one, its purpose, then writes timed beats. Also when a finished video does not feel like its format, such as a vlog that looks like an ad.
---

# Story design

Settle how the video is shot before what happens in it, then write beats that fit both. A fun idea is not a story design until its look and target action are locked and every beat serves the purpose, the action or the mood. Respond in the user's language.

## Order

1. **Draft the setup before any plot.** From the concept, brief and references, fill the five required `setup` fields yourself: `premise` (who, where and what happens, in one sentence), `tone` (how it should feel), `avoid` (the feeling it must not have), `lead` (who they are and what they want) and `setting` (place and time). Add the optional `hook` (what is funny or surprising) only when the piece has one; a product film or a sincere ad needs none. Then fill `setup.look`, every value picked from [look.md](references/look.md): who holds the camera, its lens, movement and views; cut length and cut style; speech; captions; light and grade; how lived-in the place is; how people behave toward the camera. When the brief holds values measured from a reference video, start from them and change only what the user asked to differ; otherwise read them off the concept. `speech` is `none` unless the user asks for spoken words or the concept is built on them. Show one filled draft, the look as a table, with two alternatives for `tone` only. The user edits the draft; do not send open questions.
2. **Lock the action before any plot.** Read the concept, brief, references and feedback first.
   - `target_action`: one viewer action (save, share, follow, book…). Write the `cue` that asks for it (caption, line, end card) and the `beat` where it lands only when the brief or the user wants the ask on screen; otherwise leave both out.
   - `audience`: who watches and where.
   - `purpose`: one sentence a viewer should be able to say after one viewing, a point or an impression ("I want to go there"). Write it only when the concept, the brief or the user states it in words; otherwise leave it out. An audience and a target action are not a purpose, and a point you could infer is not one either.
   If the brief cannot decide them, propose two or three concrete options and ask. Keep brand and claim restrictions from the brief.
3. **Choose a structure only for a story with conflict**, from [structures.md](references/structures.md), and write `structure.why` as the link from purpose and action to that structure. A piece without conflict (a visit, a routine, a day) needs no `structure.id`: its `structure.why` says in one line why the beats come in this order.
4. **List elements** (characters, conflicts, jokes, reveals, props that carry meaning). Each has `serves` (`purpose`, `target_action` or `mood`) and `why`. Delete anything you cannot justify.
5. **Write timed beats** from 0 s with no gaps: visible `event`, `emotion`, `tension` 0–5 and `serves`, and name the `payoff_beat` the video builds to (in a visit, the result). Beats obey the look. A beat holds one shot or several; start its `event` with the view, in the look's words ("mirror: …"), and say where a jump cut falls. Spoken words go in the beat's `line`, never inside `event`, and only when `speech` is not `none`. With `captions: info` every beat carries its `caption`: the text on screen is where the information lives. A fact in a caption (a price, a duration, a name, how to book) comes from the brief or the user; without one the caption says what is seen or done. Where the structure needs obstacles, the `obstacle` field names who blocks and how — an antagonist must act, not just appear.
6. **Self-review** before showing anything:
   - Does any beat need what the look rules out: words spoken on screen under `speech: none`, a view the look does not list, an exchange staged for the camera under `performance: unaware`?
   - Does each beat show one visible thing with a concrete detail (an object, a step, a number)?
   - With a structure: does the antagonist act against the goal, more than once when the structure demands it? Does the hero pay a visible cost before the payoff? Does tension peak in the beat right before the payoff?
   - With a cue: does it land at or after the emotional payoff?
   - With a purpose: could a first-time viewer state it?
7. **Write `story-vNNN.json`** in the project with `"version": 2` (schema: [example-story.json](assets/example-story.json), a synthetic demo, not a creative default) and run `python3 scripts/check_story.py story-vNNN.json` from this skill's directory path until it prints `OK`. The checker covers structure, not quality; the self-review still applies.
8. **Review with the user** as the look table and a beat table (time, event, caption or line, obstacle, tension, serves) plus setup, purpose or "none", action, cue or "none", and structure. Record approval evidence. Never edit an approved version; revisions get a new file.

## Handoff

Production skills (for example video-previs-workflow) consume the approved file: path, hash and approval. They take the camera, the cut length and the views of every shot from `setup.look`. When feedback says a story "feels flat", check the structure first: a passive antagonist, missing cost or early tension peak are story-design failures, not animation fixes. When it says the video does not feel like its format, check the look first: a camera nobody in the scene holds, long locked-off shots and scripted lines are story-design failures, not prompt fixes.
