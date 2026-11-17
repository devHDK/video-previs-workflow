"""Check a story design file: purpose and target action first, then a structure whose beats serve them."""
import argparse
import json
import sys
from pathlib import Path

# Structure id -> minimum pre-payoff beats with an active obstacle. Keep in sync with references/structures.md.
STRUCTURES = {'obstacle_payoff': 2, 'cliffhanger': 1, 'relief': 0, 'reveal': 0, 'info_list': 0, 'custom': 0}
SERVES = ('purpose', 'target_action')
SETUP_FIELDS = ('premise', 'tone', 'avoid', 'lead', 'setting')  # required; `hook` is optional. Same in video-previs-workflow gate.py
TOLERANCE = 1e-6


def text(value):
    return isinstance(value, str) and value.strip() != ''


def number(value):
    return type(value) in (int, float)


def check(story):
    if not isinstance(story, dict): return ['story must be an object']
    errors = []
    action = story.get('target_action') if isinstance(story.get('target_action'), dict) else {}
    structure = story.get('structure') if isinstance(story.get('structure'), dict) else {}
    for name, value in (('concept', story.get('concept')), ('purpose', story.get('purpose')),
                        ('audience', story.get('audience')), ('target_action.action', action.get('action')),
                        ('target_action.cue', action.get('cue')), ('structure.id', structure.get('id')),
                        ('structure.why', structure.get('why'))):
        if not text(value): errors.append(f'{name} is required')
    setup = story.get('setup') if isinstance(story.get('setup'), dict) else {}
    errors += [f'setup.{field} is required' for field in SETUP_FIELDS if not text(setup.get(field))]
    if text(structure.get('id')) and structure['id'] not in STRUCTURES:
        errors.append(f"structure.id must be one of: {', '.join(STRUCTURES)}")

    elements = story.get('elements')
    if not isinstance(elements, list) or not elements: errors.append('elements must be a nonempty list'); elements = []
    for element in elements:
        eid = element.get('id') if isinstance(element, dict) else None
        if not isinstance(element, dict) or not text(eid): errors.append('element id is required'); continue
        if element.get('serves') not in SERVES: errors.append(f'element {eid}: serves must be purpose or target_action')
        if not text(element.get('why')): errors.append(f'element {eid}: why is required')

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
        if beat.get('serves') not in SERVES: errors.append(f'{bid}: serves must be purpose or target_action')
        tension = beat.get('tension')
        if type(tension) is not int or not 0 <= tension <= 5: errors.append(f'{bid}: tension must be an integer 0-5')

    payoff = story.get('payoff_beat')
    if payoff not in ids: return errors + ['payoff_beat must name a beat']
    p = ids.index(payoff)
    if action.get('beat') not in ids: errors.append('target_action.beat must name a beat')
    elif ids.index(action['beat']) < p: errors.append('target_action.beat must not come before payoff_beat')

    needed = STRUCTURES.get(structure['id'], 0) if text(structure.get('id')) else 0
    before = [b for b in beats if isinstance(b, dict) and b.get('id') in ids[:p]]
    found = sum(1 for b in before if text(b.get('obstacle')))
    if found < needed:
        errors.append(f"{structure['id']} needs at least {needed} pre-payoff beats with an active obstacle; found {found}")
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
