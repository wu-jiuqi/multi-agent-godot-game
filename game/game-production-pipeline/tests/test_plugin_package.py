from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
SKILLS = {
    "bootstrap-game-pipeline",
    "prepare-game-project-brief",
    "design-game-organization",
    "operate-game-production-loop",
    "review-game-gates",
    "adapt-godot-production",
    "direct-game-art",
}


class PluginPackageTests(unittest.TestCase):
    def test_manifest_and_skill_entries_match_release(self) -> None:
        manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("game-production-pipeline", manifest["name"])
        self.assertRegex(manifest["version"], r"^0\.5\.0-alpha\.5(?:\+codex\.[0-9A-Za-z.-]+)?$")
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

    def test_art_direction_registers_palette_knife_as_optional_direction_module(self) -> None:
        module_root = PLUGIN_ROOT / "skills" / "direct-game-art" / "style-directions" / "palette-knife-impasto"
        self.assertTrue((module_root / "SKILL.md").is_file())
        self.assertTrue((module_root / "references" / "style-bible.md").is_file())
        self.assertTrue((module_root / "references" / "input-and-prompt-guide.md").is_file())
        self.assertTrue((module_root / "references" / "mindrift-profile.md").is_file())
        registry = (PLUGIN_ROOT / "skills" / "direct-game-art" / "style-directions" / "registry.yaml").read_text(encoding="utf-8")
        direct_skill = (PLUGIN_ROOT / "skills" / "direct-game-art" / "SKILL.md").read_text(encoding="utf-8")
        catalog = (PLUGIN_ROOT / "skills" / "direct-game-art" / "references" / "style-directions.md").read_text(encoding="utf-8")
        art_director = (PLUGIN_ROOT / "agents" / "art-director.md").read_text(encoding="utf-8")
        self.assertIn("palette-knife-impasto", direct_skill)
        self.assertIn("style_direction_registry", registry)
        self.assertIn("registry.yaml", direct_skill)
        self.assertIn("D2", direct_skill)
        self.assertIn("可选风格方向模块", art_director)
        self.assertIn("mindrift-profile.md", catalog)
        self.assertIn("097e9d4bb864ccd1ca3eef3f240bdad0ab212ac9", catalog)

    def test_installation_docs_use_the_personal_marketplace_selector(self) -> None:
        documentation = {"plugin README": PLUGIN_ROOT / "README.md"}
        repository_documentation = {
            "release notes": REPO_ROOT / "docs" / "releases" / "v0.5.0-alpha.5.md",
            "test guide": REPO_ROOT / "docs" / "releases" / "v0.5.0-alpha.5-test-guide.md",
        }
        for path in repository_documentation.values():
            self.assertTrue(path.is_file(), path)
        documentation.update(repository_documentation)
        install_command = "codex plugin add game-production-pipeline@personal"
        for label, path in documentation.items():
            with self.subTest(document=label):
                text = path.read_text(encoding="utf-8")
                self.assertIn(install_command, text)
                self.assertIn("installed, enabled", text)

        readme = documentation["plugin README"].read_text(encoding="utf-8")
        self.assertIn("UI 搜索结果", readme)

    def test_windows_encoding_guidance_is_explicit_and_safe(self) -> None:
        paths = [PLUGIN_ROOT / "README.md"]
        repository_paths = (
            REPO_ROOT / "docs" / "releases" / "v0.5.0-alpha.5.md",
            REPO_ROOT / "docs" / "releases" / "v0.5.0-alpha.5-test-guide.md",
        )
        for path in repository_paths:
            self.assertTrue(path.is_file(), path)
        paths.extend(repository_paths)
        required = (
            'Get-Content -LiteralPath "文件路径" -Encoding UTF8',
            "Windows PowerShell 5.1",
            "chcp 65001",
            "PowerShell 7",
            "managed block",
            "plugin-lock.yaml",
        )
        for path in paths:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                for marker in required:
                    self.assertIn(marker, text)

    def test_migration_release_contains_guarded_executor_and_documentation(self) -> None:
        self.assertTrue((PLUGIN_ROOT / "scripts" / "migrate_plugin.py").is_file())
        self.assertTrue((PLUGIN_ROOT / "migrations" / "0-3-0-alpha-1__0-4-0-alpha-2.py").is_file())
        self.assertTrue((PLUGIN_ROOT / "migrations" / "0-4-0-alpha-3__0-4-0-alpha-4.py").is_file())
        self.assertTrue((PLUGIN_ROOT / "migrations" / "0-4-0-alpha-4__0-5-0-alpha-1.py").is_file())
        self.assertTrue((PLUGIN_ROOT / "migrations" / "0-5-0-alpha-1__0-5-0-alpha-2.py").is_file())
        self.assertTrue((PLUGIN_ROOT / "migrations" / "0-4-0-alpha-3__0-5-0-alpha-3.py").is_file())
        self.assertTrue((PLUGIN_ROOT / "migrations" / "0-5-0-alpha-2__0-5-0-alpha-3.py").is_file())
        self.assertTrue((PLUGIN_ROOT / "migrations" / "0-5-0-alpha-3__0-5-0-alpha-4.py").is_file())
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
        for marker in (
            "migration_ready",
            "--approval-digest",
            "--binding-approval-digest",
            "--confirm-rollback",
            "game-pipeline/.cache/migrations/<plan_digest>/",
            "禁止只把 `plugin-lock.yaml` 改回旧版本",
        ):
            self.assertIn(marker, readme)


if __name__ == "__main__":
    unittest.main()
