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

    def test_enforced_fields_and_tools_are_documented(self):
        refs = ''.join(p.read_text() for p in (SKILLS / 'video-previs-workflow/references').glob('*.md'))
        for name in ('generation_profile', 'max_duration_s', 'duration_step_s', 'manual_takes', 'review_notes', 'props',
                     'setup', 'camera_evidence', 'continues_previous', 'split_reason', 'review_frames', 'crop_ok',
                     '--frames', '--size', '--shot', '--audit-only', '--times', 'state.py', 'blocking.py', 'previs/d01',
                     'kind `reference`', '--status cancelled'):
            self.assertTrue(name in refs, f'{name} is not documented in references/')

    def test_skill_md_stays_compact(self):
        self.assertLessEqual(len((SKILLS / 'video-previs-workflow/SKILL.md').read_bytes()), 6500)


if __name__ == '__main__':
    unittest.main()
