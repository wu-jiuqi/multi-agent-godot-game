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
            "Benchmark page and evidence contract",
            "task-definition.yaml",
            "interaction-recording",
            "motion_export",
            "offset_transform_visual_only",
            "button_down",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, reference)

    def test_plugin_role_and_workflow_define_gate_and_fallback_boundaries(self) -> None:
        agent = (PLUGIN_ROOT / "agents" / "ui-production.md").read_text(encoding="utf-8")
        workflow = (PLUGIN_ROOT / "workflows" / "ui-production.md").read_text(encoding="utf-8")
        visual_handoff = (PLUGIN_ROOT / "workflows" / "ui-visual-handoff.md").read_text(encoding="utf-8")
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
            "标杆页面门槛",
            "组件实验场只能作为辅助检查页",
            "functional",
            "motion_export",
            "offset_transform_visual_only",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)
        for marker in ("tool:figma-codex-plugin", "codex_figma_plugin", "brief/PRD/GDD"):
            with self.subTest(marker=marker):
                self.assertIn(marker, visual_handoff)

    def test_codex_figma_handoff_is_explicit_and_preserves_authored_godot_ui(self) -> None:
        skill = (REPO_ROOT / "skills" / "ui-ux-pro-max" / "SKILL.md").read_text(encoding="utf-8")
        reference_path = REPO_ROOT / "skills" / "ui-ux-pro-max" / "references" / "figma-handoff.md"
        self.assertTrue(reference_path.is_file())
        reference = reference_path.read_text(encoding="utf-8")
        for marker in (
            "references/figma-handoff.md",
            "tool:figma-codex-plugin",
            "figma:figma-use",
            "figma:figma-generate-design",
            "input_intake",
            "product_identity_and_visual_direction",
            "ux_flow",
            "figma_visual_system",
            "source_document_refs",
            "product_title",
            "slogan",
            "inherited_from_prd",
            "derived_from_inputs",
            "provider: figma",
            "integration: codex_figma_plugin",
            "frame_node_id",
            "design_system_ref",
            "file_ref",
            "serialized `.tscn`/`.tres`",
            "Do not export a Figma frame as a runtime UI",
            "do not reconstruct a fixed UI tree",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill + "\n" + reference)


if __name__ == "__main__":
    unittest.main()
