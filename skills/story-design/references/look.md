# Look

`setup.look` records how the video is shot, as picks. Every value below is required from `"version": 2`; `check_story.py` rejects a missing one or a value outside its list. A feeling stays in `setup.tone`; the look holds what a camera, an editor and a set can be held to.

```json
"look": {
  "camera": {"holder": "lead", "lens": "phone", "motion": "handheld", "views": ["pov", "mirror", "selfie", "insert"]},
  "pace": {"avg_shot_s": 2.3, "cuts": "jump"},
  "speech": "none",
  "captions": "info",
  "colour": {"light": "available", "grade": "phone_auto"},
  "world": "lived_in",
  "performance": "to_camera"
}
```

| Key | Values | Meaning |
|---|---|---|
| `camera.holder` | `lead`, `companion`, `unseen` | Who films. `lead`: the main person's own phone or camera, in their hand or set down by them. `companion`: someone who is there with them and may be heard or reflected. `unseen`: a camera with no place in the story, as in a film or an ad. |
| `camera.lens` | `phone`, `normal`, `tele` | 13–26 mm, 35–50 mm, 70 mm and up (full-frame equivalents). A phone is wide and close: faces bend near the edges and rooms look deep. |
| `camera.motion` | `handheld`, `static`, `designed` | `handheld` drifts and reframes all the time; a `propped` view stands still whatever the motion. `static` is locked off. `designed` is a planned move: a dolly, a gimbal, a crane. |
| `camera.views` | one or more of `selfie`, `pov`, `mirror`, `propped`, `insert`, `observer`, most shots first | The kinds of shot the video is cut from. `selfie`: lens toward the holder at arm's length, the arm at the frame edge. `pov`: what the holder sees: their hands, their lap, the room. `mirror`: the holder films a mirror and the camera shows in the reflection. `propped`: the camera is set down on a surface and the holder sits in front of it. `insert`: a close view of one object or detail; a recording of the holder's phone screen counts. `observer`: the subject seen from outside by a camera they do not hold. |
| `pace.avg_shot_s` | a number of seconds | Average shot length. Duration divided by it is the shot count. |
| `pace.cuts` | `hard`, `jump`, `transition` | `jump` also cuts inside one set-up to skip time. `transition` uses dissolves, wipes or effects. |
| `speech` | `none`, `voiceover`, `dialogue` | Words heard. `none` is the default: no beat has a `line`, and people seen talking say nothing the viewer has to hear or lip-read. `dialogue` is spoken in the scene, lips moving. |
| `captions` | `info`, `subtitle`, `none` | Text on screen. `info`: text on screen that carries the facts, written per beat as `caption`; every beat has one, a shot inside it may go without. `subtitle`: the spoken words, transcribed. |
| `colour.light` | `available`, `designed` | `available`: the place's own lamps and daylight, mixed colours and blown highlights included. `designed`: lit for the shot. |
| `colour.grade` | `phone_auto`, `natural`, `stylized` | `phone_auto`: straight off a phone, automatic exposure and white balance. `natural`: corrected and even. `stylized`: a look applied on purpose. |
| `world` | `lived_in`, `clean` | `lived_in`: other people, things left out, signs, clutter. `clean`: only what the story names. |
| `performance` | `to_camera`, `unaware`, `posed` | How the lead behaves; other people in a `lived_in` place get on with their work. `to_camera`: people look into and play to the lens. `unaware`: they get on with what they are doing. `posed`: held, arranged poses. |

## Filling it

- With a reference video measured in the brief (average shot length, each shot's view, who holds the camera, how many shots carry text), copy the measured values. They describe how the reference was shot, not what it shows: the story, people and place stay new.
- With a concept only, read each value off the concept and the format it names. A vlog is the lead's own phone. An unseen camera on a tripod is a different format, even with "candid" in the tone. `pace.avg_shot_s` cannot be read off a concept: propose it and show it as a shot count ("about 13 shots in 30 s") so the user can correct it.
- A value the brief marks as not measured takes its default or your reading of the concept; say which in the look table.
- `camera.holder` decides which views exist. Under `lead` or `companion` every shot is one that person could have filmed; `observer` then needs a reason shot by shot.
- A view the video uses once still goes in `camera.views`.
