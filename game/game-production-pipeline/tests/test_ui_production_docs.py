from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = REPO_ROOT / "game" / "game-production-pipeline"


class UiProductionDocumentationTests(unittest.TestCase):
    def test_godot_skill_reference_is_linked_and_covers_required_contract(self) -> None:
        skill = (REPO_ROOT / "skills" / "ui-ux-pro-max" / "SKILL.md").read_text(encoding="utf-8")
        reference_path = REPO_ROOT / "skills" / "ui-ux-pro-max" / "references" / "godot-production.md"
        self.assertTrue(reference_path.is_file())
        reference = reference_path.read_text(encoding="utf-8")
        self.assertIn("references/godot-production.md", skill)
        for marker in (
            "prototype",
            "greybox",
            "style-pass",
            "final",
            "no more than **five** questions",
            "Screen/Flow Contract",
            "UI Visual Contract",
            "source_uri",
            "runtime_uri",
            "slice_or_nine_patch",
            "reduced_motion",
            "UI_READABILITY",
            "Fixed handoff output",
            "implementation_ready",
            "review_pending",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, reference)

    def test_plugin_role_and_workflow_define_gate_and_fallback_boundaries(self) -> None:
        agent = (PLUGIN_ROOT / "agents" / "ui-production.md").read_text(encoding="utf-8")
        workflow = (PLUGIN_ROOT / "workflows" / "ui-production.md").read_text(encoding="utf-8")
        for marker in (
            "AGT-UI-PRODUCTION-TEMPLATE",
            "@export",
            "normal",
            "hover",
            "pressed",
            "focus",
            "disabled",
            "error",
            "UI_VISUAL",
            "UI_STRUCTURE",
            "UI_TECH",
            "UI_READABILITY",
            "目标构建",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, agent)
        for marker in (
            "0. 项目状态",
            "Asset Manifest",
            "预置",
            "`.tscn`/`.tres`",
            "十段",
            "review_pending",
            "blocked",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)


if __name__ == "__main__":
    unittest.main()
