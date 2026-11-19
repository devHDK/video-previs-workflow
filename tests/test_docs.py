import importlib.util
import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / 'skills'


def load_script(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocTests(unittest.TestCase):
    def test_relative_links_resolve(self):
        for md in SKILLS.rglob('*.md'):
            for target in re.findall(r'\]\(([^)#\s]+)', md.read_text()):
                if '://' not in target:
                    self.assertTrue((md.parent / target).exists(), f'{md}: {target}')

    def test_frontmatter_name_matches_folder(self):
        for skill_md in SKILLS.glob('*/SKILL.md'):
            head = skill_md.read_text().split('---')[1]
            self.assertIn(f'name: {skill_md.parent.name}\n', head)
            self.assertRegex(head, r'description: \S')

    def test_structure_catalog_matches_checker(self):
        m = load_script(SKILLS / 'story-design/scripts/check_story.py')
        text = (SKILLS / 'story-design/references/structures.md').read_text()
        self.assertEqual(re.findall(r'^\| `([a-z_]+)` \|', text, re.M), list(m.STRUCTURES))

    def test_setup_fields_match_between_skills(self):
        self.assertEqual(load_script(SKILLS / 'story-design/scripts/check_story.py').SETUP_FIELDS,
                         load_script(SKILLS / 'video-previs-workflow/scripts/gate.py').SETUP_FIELDS)

    def test_look_values_match_between_skills(self):
        story, gate = (load_script(SKILLS / path) for path in ('story-design/scripts/check_story.py', 'video-previs-workflow/scripts/gate.py'))
        self.assertEqual((story.LOOK, story.VIEWS), (gate.LOOK, gate.VIEWS))

    def test_look_values_are_documented_in_both_skills(self):
        m = load_script(SKILLS / 'story-design/scripts/check_story.py')
        names = list(m.LOOK) + ['camera.views', 'pace.avg_shot_s'] + [v for values in m.LOOK.values() for v in values] + list(m.VIEWS)
        for doc in ('story-design/references/look.md', 'video-previs-workflow/references/production.md'):  # the workflow runs without story-design
            text = (SKILLS / doc).read_text()
            for name in names: self.assertIn(f'`{name}`', text, f'{doc}: {name}')

    def test_reference_video_is_measured_whatever_the_route(self):
        text = (SKILLS / 'video-previs-workflow/references/production.md').read_text()
        row = next(line for line in text.split('## Intake routes')[1].split('\n## ')[0].splitlines() if line.startswith('| Reference footage'))
        for name in ('inputs/', 'media.py cuts', 'brief.md', 'look', '`format`', '`shot`'): self.assertIn(name, row)

    def test_enforced_fields_and_tools_are_documented(self):
        refs = ''.join(p.read_text() for p in (SKILLS / 'video-previs-workflow/references').glob('*.md'))
        for name in ('generation_profile', 'max_duration_s', 'duration_step_s', 'manual_takes', 'review_notes', 'props',
                     'setup', 'camera_evidence', 'continues_previous', 'split_reason', 'review_frames', 'crop_ok',
                     '--frames', '--size', '--shot', '--audit-only', '--times', 'state.py', 'blocking.py', 'previs/d01',
                     'kind `reference`', '--status cancelled', 'group_motion', 'spread_s', 'measured_s', 'unlisted_motion',
                     '`travel`', 'event_results', 'gate.py qa', 'media.py dupes', 'media.py spread', 'media.py reframe',
                     'state.py asset', 'state.py keyframe', 'state.py note', 'state.py bind',
                     'state.py init', 'state.py put', 'state.py charge', 'prop_results', '`count`', '`states`',
                     'audit.line', 'line_cross_ok', 'screen_direction', 'line_crossed', 'screen_direction_reversed', '--plan', 'plan.png', 'sensor height', 'Floor plan',
                     'candidates', '--low', 'source.rights', 'upload_agreed', '`match`',
                     'media.py sheet', 'Footage-led', 'Clearance', 'no_previs',
                     '`plan`', '--source', '--origin', '--cell', '`view`', 'view_reason', 'setup.look', 'generation_plan'):
            self.assertTrue(name in refs, f'{name} is not documented in references/')

    def test_shot_design_is_scoped_to_the_idea_led_route(self):
        text = (SKILLS / 'video-previs-workflow/references/production.md').read_text()
        section = text.split('## Shot design')[1].split('\n## ')[0]
        for name in ('reference-led', '`audit.subjects`', '`audit.line`', '`line_cross_ok`', '`audit.screen_direction`', '36 mm',
                     '`camera.views`', '`holder: lead`', 'reflection', '`pace.avg_shot_s`'):
            self.assertIn(name, section)
        self.assertIn('--plan', (SKILLS / 'video-previs-workflow/SKILL.md').read_text())

    def test_footage_led_rules_keep_the_review_with_the_user(self):
        text = (SKILLS / 'video-previs-workflow/references/production.md').read_text()
        section = text.split('## Footage-led production')[1].split('\n## ')[0]
        for name in ('brief.md', 'people-free', 'third-party'): self.assertIn(name, section)
        for name in ('media.py sheet', '`review_notes`', 'first pass'): self.assertIn(name, text.split('## Shot keyframes')[1])
        self.assertIn('footage-led', (SKILLS / 'video-previs-workflow/SKILL.md').read_text())

    def test_trial_rules_are_written_down(self):
        text = (SKILLS / 'video-previs-workflow/references/production.md').read_text()
        led = text.split('## Footage-led production')[1].split('\n## ')[0]
        for name in ('guest', 'Staff', 'consent', 'people-free frame'): self.assertIn(name, led)
        for name in ('one role per outfit', 'hides the hair'): self.assertIn(name, text.split('## Appearance review')[1].split('\n## ')[0])
        self.assertIn('in words', text.split('## Shot keyframes')[1].split('\n## ')[0])
        self.assertIn('screen recording', text.split('## Reference-led route')[1].split('\n## ')[0])
        self.assertIn('shortest take', (SKILLS / 'video-previs-workflow/references/generation.md').read_text())

    def test_a_new_production_starts_in_its_own_folder(self):
        state = (SKILLS / 'video-previs-workflow/references/project-state.md').read_text().split('## State contract')[0]
        for name in ('projects/<project-id>/', 'state.py init', 'working directory', 'resume'): self.assertIn(name, state)
        self.assertIn('projects/<project-id>/', (SKILLS / 'video-previs-workflow/SKILL.md').read_text())

    def test_generation_choice_is_asked_with_the_previs(self):
        skill = (SKILLS / 'video-previs-workflow/SKILL.md').read_text()
        self.assertIn('generation_plan', skill.split('1. **Previs:**')[1].split('2. **Appearance:**')[0])
        text = (SKILLS / 'video-previs-workflow/references/generation.md').read_text()
        for name in ('state.py put', 'generation_plan', 'evidence', 'retry_of', 'gate.py submit'):
            self.assertIn(name, next(p for p in text.split('\n\n') if p.startswith('Present three choices')))

    def test_skill_md_stays_compact(self):
        self.assertLessEqual(len((SKILLS / 'video-previs-workflow/SKILL.md').read_bytes()), 6700)


if __name__ == '__main__':
    unittest.main()
