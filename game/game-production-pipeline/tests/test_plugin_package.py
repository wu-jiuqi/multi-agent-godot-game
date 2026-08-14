from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "bootstrap-game-pipeline",
    "design-game-organization",
    "operate-game-production-loop",
    "review-game-gates",
    "adapt-godot-production",
}


class PluginPackageTests(unittest.TestCase):
    def test_manifest_and_skill_entries_match_release(self) -> None:
        manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("game-production-pipeline", manifest["name"])
        self.assertEqual("0.3.0-alpha.1", manifest["version"])
        self.assertEqual("./skills/", manifest["skills"])
        discovered = {path.name for path in (PLUGIN_ROOT / "skills").iterdir() if path.is_dir()}
        self.assertEqual(SKILLS, discovered)

    def test_skills_have_clean_frontmatter_and_explicit_default_prompts(self) -> None:
        for skill_name in SKILLS:
            with self.subTest(skill=skill_name):
                skill_path = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"
                text = skill_path.read_text(encoding="utf-8")
                self.assertNotIn("TODO", text)
                _, frontmatter, _ = text.split("---", 2)
                metadata = yaml.safe_load(frontmatter)
                self.assertEqual(skill_name, metadata["name"])
                openai = yaml.safe_load(
                    (PLUGIN_ROOT / "skills" / skill_name / "agents" / "openai.yaml").read_text(encoding="utf-8")
                )
                self.assertTrue(openai["interface"]["default_prompt"].startswith(f"Use ${skill_name}"))


if __name__ == "__main__":
    unittest.main()
