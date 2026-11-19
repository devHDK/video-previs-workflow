# Story structures

A story with conflict picks the structure that serves its purpose and target action. The id goes in `structure.id`; the number in parentheses is the minimum count of pre-payoff beats with an active `obstacle` that `check_story.py` enforces. Conflict is a tool, not a default: a piece without it (a visit, a routine, a day) needs no id and says in `structure.why` why its beats come in this order. The rows marked (0) are shapes to borrow from, not a choice it has to make.

| id | Use when (purpose → action) | Required elements | Failure signs |
|---|---|---|---|
| `obstacle_payoff` | (2) Goal-driven comedy or drama whose catharsis should earn a save, share or booking. | A goal stated early; an antagonist who acts against it at least twice; escalating cost to the hero; payoff that releases the built tension; CTA after the payoff. | Antagonist present but passive; no cost to the hero before payoff; tension flat or peaking early; payoff happens without anyone being stopped. |
| `cliffhanger` | (1) Series episode whose action is follow or watch-next. | One open question set early; at least one active obstacle; an unresolved turn at the end that the CTA points to. | Ending resolves everything; question introduced only in the last second; CTA unrelated to the open question. |
| `relief` | (0) A familiar pain point resolved, driving inquiry or booking. | A recognisable problem shown concretely; the moment of relief; the product or service as the bridge, without claims the brief forbids. | Problem abstract or told rather than shown; relief before the problem lands; unsupported efficacy claims. |
| `reveal` | (0) Hook-and-twist content driving shares or comments. | A setup that invites a wrong assumption; fair clues; a reveal that reframes the setup. | Twist unfair or unclued; reveal so early nothing is reframed; setup too long to hold the hook. |
| `info_list` | (0) Tips or how-to content driving saves. | A promise in the first beat; distinct, ordered items; a recap or save cue at the end. | Items overlap; no promise up front; padding beats that serve neither purpose nor action. |
| `custom` | (0) None of the above fits. | State why no catalog structure fits in `structure.why`; name the beat where each required emotion lands. | Used to skip the decision; why repeats the concept instead of the purpose/action link. |
