"""Check a story design file: the setup and its look, the target action, and beats that serve a purpose, the action or the mood."""
import argparse
import json
import sys
from pathlib import Path

# Structure id -> minimum pre-payoff beats with an active obstacle. Keep in sync with references/structures.md.
STRUCTURES = {'obstacle_payoff': 2, 'cliffhanger': 1, 'relief': 0, 'reveal': 0, 'info_list': 0, 'custom': 0}
SERVES = ('purpose', 'target_action', 'mood')
SETUP_FIELDS = ('premise', 'tone', 'avoid', 'lead', 'setting')  # required; `hook` is optional. Same in video-previs-workflow gate.py
# setup.look: how the video is shot, as picks. Required from version 2. Same in video-previs-workflow gate.py; meanings in references/look.md
LOOK = {'camera.holder': ('lead', 'companion', 'unseen'), 'camera.lens': ('phone', 'normal', 'tele'),
        'camera.motion': ('handheld', 'static', 'designed'), 'pace.cuts': ('hard', 'jump', 'transition'),
        'speech': ('none', 'voiceover', 'dialogue'), 'captions': ('info', 'subtitle', 'none'),
        'colour.light': ('available', 'designed'), 'colour.grade': ('phone_auto', 'natural', 'stylized'),
        'world': ('lived_in', 'clean'), 'performance': ('to_camera', 'unaware', 'posed')}
VIEWS = ('selfie', 'pov', 'mirror', 'propped', 'insert', 'observer')
TOLERANCE = 1e-6


def text(value):
    return isinstance(value, str) and value.strip() != ''


def number(value):
    return type(value) in (int, float)


def look_errors(look):
    if not isinstance(look, dict): return ['setup.look is required']

    def at(path):
        value = look
        for key in path.split('.'): value = value.get(key) if isinstance(value, dict) else None
        return value
    errors = [f"setup.look.{path} must be one of: {', '.join(values)}" for path, values in LOOK.items()
              if not (isinstance(at(path), str) and at(path) in values)]
    views, pace = at('camera.views'), at('pace.avg_shot_s')
    if not (isinstance(views, list) and views and all(isinstance(v, str) and v in VIEWS for v in views) and len(set(views)) == len(views)):
        errors.append(f"setup.look.camera.views must list one or more of: {', '.join(VIEWS)}")
    if not (number(pace) and pace > 0): errors.append('setup.look.pace.avg_shot_s must be a positive number')
    return errors


def check(story):
    if not isinstance(story, dict): return ['story must be an object']
    errors = []
    action = story.get('target_action') if isinstance(story.get('target_action'), dict) else {}
    structure = story.get('structure') if isinstance(story.get('structure'), dict) else {}
    for name, value in (('concept', story.get('concept')), ('audience', story.get('audience')),
                        ('target_action.action', action.get('action')), ('structure.why', structure.get('why'))):
        if not text(value): errors.append(f'{name} is required')
    setup = story.get('setup') if isinstance(story.get('setup'), dict) else {}
    errors += [f'setup.{field} is required' for field in SETUP_FIELDS if not text(setup.get(field))]
    look = setup.get('look')
    if 'look' in setup or (number(story.get('version')) and story['version'] >= 2): errors += look_errors(look)
    look = look if isinstance(look, dict) else {}
    sid = structure.get('id')  # chosen only for a story with conflict
    if sid is not None and not (isinstance(sid, str) and sid in STRUCTURES):
        errors.append(f"structure.id must be one of: {', '.join(STRUCTURES)}"); sid = None

    elements = story.get('elements')
    if not isinstance(elements, list) or not elements: errors.append('elements must be a nonempty list'); elements = []
    for element in elements:
        eid = element.get('id') if isinstance(element, dict) else None
        if not isinstance(element, dict) or not text(eid): errors.append('element id is required'); continue
        if element.get('serves') not in SERVES: errors.append(f'element {eid}: serves must be purpose, target_action or mood')
        if not text(element.get('why')): errors.append(f'element {eid}: why is required')
    served = [e.get('serves') for e in elements if isinstance(e, dict)]

    beats = story.get('beats')
    if not isinstance(beats, list) or not beats: return errors + ['beats must be a nonempty list']
    ids, previous_end = [], 0
    for beat in beats:
        bid = beat.get('id') if isinstance(beat, dict) else None
        if not isinstance(beat, dict) or not text(bid) or bid in ids:
            errors.append('beat id must be unique and nonempty'); continue
        ids.append(bid)
        start, end = beat.get('start'), beat.get('end')
        if not (number(start) and number(end) and start < end):
            errors.append(f'{bid}: start and end must be numbers with start < end'); continue
        if abs(start - previous_end) > TOLERANCE: errors.append(f'{bid}: gap or overlap with previous beat')
        previous_end = end
        if not text(beat.get('event')): errors.append(f'{bid}: event is required')
        if beat.get('serves') not in SERVES: errors.append(f'{bid}: serves must be purpose, target_action or mood')
        served.append(beat.get('serves'))
        if look.get('speech') == 'none' and text(beat.get('line')):  # spoken words live in `line`, so the look can rule them out
            errors.append(f'{bid}: line is not allowed when setup.look.speech is none')
        if look.get('captions') == 'info' and not text(beat.get('caption')):
            errors.append(f'{bid}: caption is required when setup.look.captions is info')
        tension = beat.get('tension')
        if type(tension) is not int or not 0 <= tension <= 5: errors.append(f'{bid}: tension must be an integer 0-5')

    if 'purpose' in served and not text(story.get('purpose')): errors.append('purpose is required when a beat or element serves it')
    if sid is None and any(isinstance(b, dict) and text(b.get('obstacle')) for b in beats):
        errors.append('structure.id is required when a beat has an obstacle')

    payoff = story.get('payoff_beat')
    if payoff not in ids: return errors + ['payoff_beat must name a beat']
    p = ids.index(payoff)
    if text(action.get('cue')) or action.get('beat') is not None:  # nothing asked on screen: no cue, no beat for it
        if action.get('beat') not in ids: errors.append('target_action.beat must name a beat')
        elif ids.index(action['beat']) < p: errors.append('target_action.beat must not come before payoff_beat')

    needed = STRUCTURES.get(sid, 0)
    before = [b for b in beats if isinstance(b, dict) and b.get('id') in ids[:p]]
    found = sum(1 for b in before if text(b.get('obstacle')))
    if found < needed:
        errors.append(f"{sid} needs at least {needed} pre-payoff beats with an active obstacle; found {found}")
    tensions = [b.get('tension') for b in before]
    if needed and before and all(type(t) is int for t in tensions) and tensions[-1] < max(tensions):
        errors.append('tension must peak in the beat right before payoff_beat')
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('story')
    errors = check(json.loads(Path(p.parse_args().story).read_text()))
    print('\n'.join(errors) if errors else 'OK')
    sys.exit(1 if errors else 0)


if __name__ == '__main__': main()
