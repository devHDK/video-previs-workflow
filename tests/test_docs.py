import importlib.util
import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / 'skills'


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
        path = SKILLS / 'story-design/scripts/check_story.py'
        spec = importlib.util.spec_from_file_location('check_story', path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        text = (SKILLS / 'story-design/references/structures.md').read_text()
        self.assertEqual(re.findall(r'^\| `([a-z_]+)` \|', text, re.M), list(m.STRUCTURES))


if __name__ == '__main__':
    unittest.main()
