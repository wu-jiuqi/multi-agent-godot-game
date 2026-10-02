from __future__ import annotations

import copy
import hashlib
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_art_direction_contract as validator  # noqa: E402
from evaluate_art_direction_gate import evaluate_art_direction_gate  # noqa: E402
from pipeline_common import load_yaml  # noqa: E402


REF = "0" * 64


def artifact(name: str) -> dict[str, object]:
    return {"artifact_id": f"ui:{name}", "version": 1, "uri": f"repo://ui/{name}.tres", "sha256": REF}


def document_ref(kind: str, slug: str) -> dict[str, object]:
    return {
        "artifact_id": f"product-doc:demo:{slug}",
        "version": 1,
        "document_kind": kind,
        "title": f"Demo {kind.upper()}",
        "uri": f"repo://product-docs/{slug}.md",
        "sha256": REF,
        "content_digest": REF,
        "role": {"brief": "product-goal", "prd": "requirements", "gdd": "game-design"}[kind],
    }


class UIVisualContractTests(unittest.TestCase):
    def test_template_declares_four_stage_product_to_penpot_handoff(self) -> None:
        template = load_yaml(PLUGIN_ROOT / "contracts" / "ui-visual-contract.template.yaml")
        contract = template["ui_visual_contract"]
        self.assertEqual(
            ["input_intake", "product_identity_and_visual_direction", "ux_flow", "penpot_visual_system"],
            contract["workflow"]["stage_order"],
        )
        for field in ("source_document_refs", "product_identity", "visual_direction", "ux_flow", "penpot_prototype"):
            with self.subTest(field=field):
                self.assertIn(field, contract)
        self.assertEqual("penpot", contract["penpot_prototype"]["provider"])
        self.assertEqual("penpot_mcp", contract["penpot_prototype"]["integration"])

    def make_document(self) -> dict[str, object]:
        states = {
            state: {"applicable": True, "visual_rule": f"{state} treatment", "resource_refs": [artifact("button")]} 
            for state in validator.UI_STATE_NAMES
        }
        contract: dict[str, object] = {
            "schema_version": validator.UI_VISUAL_SCHEMA_VERSION,
            "identity": {"ui_visual_id": "uivis:demo", "revision": 1, "previous_revision_digest": None, "lifecycle_state": "production_ready"},
            "art_direction_ref": {"artifact_id": "artdir:demo", "version": 1, "uri": "repo://art-direction.yaml", "sha256": REF, "subject_digest": REF},
            "screen_flow_ref": artifact("screen-flow"),
            "workflow": {
                "stage_order": [
                    "input_intake",
                    "product_identity_and_visual_direction",
                    "ux_flow",
                    "figma_visual_system",
                ],
                "current_stage": "figma_visual_system",
                "stages": {
                    "input_intake": {"status": "complete"},
                    "product_identity_and_visual_direction": {"status": "complete"},
                    "ux_flow": {"status": "complete"},
                    "figma_visual_system": {"status": "complete"},
                },
            },
            "source_document_refs": [document_ref("brief", "demo-brief"), document_ref("prd", "demo-prd"), document_ref("gdd", "demo-gdd")],
            "product_identity": {
                "product_name": "Demo Atelier",
                "product_title": "Demo Atelier: Garden Console",
                "slogan": "Make every signal feel hand-crafted.",
                "decision_ref": artifact("product-identity-decision"),
                "decision_rationale": "The title and slogan connect the product promise to the player-facing workshop fantasy.",
            },
            "visual_direction": {
                "style_requirements": [
                    "Warm editorial craft with measured technical controls.",
                    "Use a quiet canvas, clear hierarchy, and non-color state redundancy.",
                ],
                "decision_ref": artifact("visual-direction-decision"),
                "decision_rationale": "The direction makes dense control state calm and legible.",
            },
            "ux_flow": {
                "resolution": "inherited_from_prd",
                "authoring_skipped": True,
                "source_document_refs": ["product-doc:demo:demo-prd"],
                "decision_ref": artifact("ux-flow-decision"),
                "skip_reason": "The PRD already specifies the screen sequence, entry points, and return path.",
                "unresolved_questions": [],
            },
            "figma_prototype": {
                "provider": "figma",
                "integration": "codex_figma_plugin",
                "file_ref": {
                    "artifact_id": "figma-file:demo:1",
                    "version": 1,
                    "uri": "repo://ui/figma/demo-file.json",
                    "sha256": REF,
                },
                "file_key": "demo",
                "file_url": "https://www.figma.com/file/demo/demo-atelier",
                "prototype_url": "https://www.figma.com/proto/demo/demo-atelier",
                "version": "1.0",
                "screen_refs": [
                    {
                        "screen_id": "main",
                        "frame_node_id": "1:2",
                        "frame_url": "https://www.figma.com/design/demo?node-id=1-2",
                    }
                ],
                "design_system_ref": {
                    "artifact_id": "figma-design-system:demo:1",
                    "version": 1,
                    "uri": "repo://ui/figma/demo-design-system.json",
                    "sha256": REF,
                },
                "design_system_url": "https://www.figma.com/design/demo?node-id=2-3",
                "handoff_status": "implementation_ready",
                "handoff_evidence_refs": [artifact("figma-handoff")],
                "review_evidence_refs": [artifact("figma-review")],
            },
            "visual_identity": "Botanical brass atelier controls",
            "shape_language": "Leaf arcs interlock with measured ratchets",
            "material_surface_rules": "Pigment paper with restrained brass glints",
            "color_token_ref": artifact("tokens"),
            "typography_ref": artifact("type"),
            "iconography_ref": artifact("icons"),
            "ornament_decoration_rules": "Corner herbarium marks only at section boundaries",
            "component_state_matrix": [{"component_id": "button.primary", "node_type": "Button", "states": states}],
            "motion_language": "Short eased ink reveal and spring return",
            "theme_resource_refs": [artifact("theme")],
            "style_frame_refs": [dict(artifact("frame"), screen_id="main")],
            "positive_example_refs": [artifact("positive")],
            "negative_example_refs": [artifact("negative")],
            "key_screen_ids": ["main"],
            "required_interaction_states": list(validator.UI_STATE_NAMES),
            "benchmark_capture_refs": [dict(artifact("capture"), screen_id="main", states=list(validator.UI_STATE_NAMES), media_type="screenshot", build_ref="build:demo", viewport=[1280, 720], ui_visual_digest="")],
            "accessibility_constraints": ["Text contrast 4.5:1", "State is never color-only"],
            "owner": "position:demo:art-director",
            "reviewers": {"art_director": "position:demo:art-director", "ui_ux": "position:demo:ui-ux", "godot_implementer": "position:demo:godot"},
            "rework_routes": {code: [f"position:demo:{code.lower()}"] for code in ("UI_VISUAL", "UI_STRUCTURE", "UI_TECH", "UI_READABILITY")},
            "visual_review": {"status": "approved", "reviewer": "position:demo:art-director", "subject_digest": "", "reviewed_at": "2026-09-28T00:00:00Z", "evidence_refs": ["evidence:ui-review"], "ui_body_reviewed": True},
            "integrity": {"ui_visual_digest": ""},
        }
        document = {"ui_visual_contract": contract}
        digest = validator.ui_visual_digests(document)["ui_visual_digest"]
        contract["integrity"]["ui_visual_digest"] = digest
        contract["visual_review"]["subject_digest"] = digest
        contract["benchmark_capture_refs"][0]["ui_visual_digest"] = digest
        return document

    def make_penpot_document(self) -> dict[str, object]:
        """Convert the complete legacy fixture into the canonical Penpot shape."""
        document = self.make_document()
        contract = document["ui_visual_contract"]
        legacy = contract.pop("figma_prototype")
        contract["workflow"]["stage_order"][-1] = "penpot_visual_system"
        contract["workflow"]["current_stage"] = "penpot_visual_system"
        contract["workflow"]["stages"]["penpot_visual_system"] = contract["workflow"]["stages"].pop("figma_visual_system")
        contract["penpot_prototype"] = {
            "provider": "penpot",
            "integration": "penpot_mcp",
            "file_ref": {**legacy["file_ref"], "artifact_id": "penpot-file:demo:1", "uri": "repo://ui/penpot/demo-file.json"},
            "file_id": "demo-file",
            "page_id": "demo-page",
            "file_url": "https://design.penpot.app/#/workspace/demo/project/demo/file/demo-file",
            "prototype_url": "https://design.penpot.app/#/view/demo-file?page-id=demo-page",
            "version": "1.0",
            "screen_refs": [{
                "screen_id": "main",
                "page_id": "demo-page",
                "shape_id": "main-shape",
                "frame_url": "https://design.penpot.app/#/view/demo-file?page-id=demo-page&shape-id=main-shape",
            }],
            "design_system_ref": {**legacy["design_system_ref"], "artifact_id": "penpot-design-system:demo:1", "uri": "repo://ui/penpot/demo-design-system.json"},
            "design_system_url": "https://design.penpot.app/#/view/demo-file?page-id=demo-page",
            "handoff_status": "implementation_ready",
            "handoff_evidence_refs": [{**artifact("penpot-handoff")}],
            "review_evidence_refs": [{**artifact("penpot-review")}],
        }
        digest = validator.ui_visual_digests(document)["ui_visual_digest"]
        contract["integrity"]["ui_visual_digest"] = digest
        contract["visual_review"]["subject_digest"] = digest
        contract["benchmark_capture_refs"][0]["ui_visual_digest"] = digest
        return document

    def test_penpot_handoff_is_ready_and_checks_stable_ids(self) -> None:
        document = self.make_penpot_document()
        result = validator.validate_ui_figma_handoff(document)
        self.assertEqual("valid", result["state"], result)
        self.assertTrue(result["penpot_ready"])
        full_result = validator.validate_ui_visual_contract(document)
        self.assertEqual("valid", full_result["state"], full_result)
        self.assertEqual("valid", full_result["penpot_handoff"]["state"])
        document["ui_visual_contract"]["penpot_prototype"]["screen_refs"][0]["shape_id"] = ""
        invalid = validator.validate_ui_figma_handoff(document)
        self.assertIn("shape_id", "\n".join(invalid["errors"]))

    def test_penpot_only_cli_accepts_canonical_contract(self) -> None:
        document = self.make_penpot_document()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "penpot.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_art_direction_contract.py"), str(path), "--ui-penpot-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["penpot_ready"])

    def materialize_repo_refs(self, document: dict[str, object], root: Path) -> None:
        def visit(value: object) -> None:
            if isinstance(value, dict):
                uri = value.get("uri")
                if isinstance(uri, str) and uri.startswith("repo://"):
                    relative = uri.removeprefix("repo://")
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    payload = f"fixture snapshot: {relative}\n".encode("utf-8")
                    path.write_bytes(payload)
                    value["sha256"] = hashlib.sha256(payload).hexdigest()
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(document)

    def test_figma_handoff_requires_local_snapshots_and_matching_urls(self) -> None:
        document = self.make_document()
        figma = document["ui_visual_contract"]["figma_prototype"]
        figma["file_ref"]["uri"] = figma["file_url"]
        result = validator.validate_ui_figma_handoff(document)
        self.assertIn("本地 SHA-256", "\n".join(result["errors"]))

        document = self.make_document()
        document["ui_visual_contract"]["figma_prototype"]["design_system_url"] = (
            "https://www.figma.com/design/other-file?node-id=2-3"
        )
        result = validator.validate_ui_figma_handoff(document)
        self.assertIn("design_system_url", "\n".join(result["errors"]))

    def test_malformed_figma_references_return_errors_without_crashing(self) -> None:
        for field, value in (("file_ref", None), ("design_system_ref", []), ("screen_refs", [None])):
            with self.subTest(field=field):
                document = self.make_document()
                document["ui_visual_contract"]["figma_prototype"][field] = value
                result = validator.validate_ui_figma_handoff(document)
                self.assertEqual("invalid", result["state"])
                self.assertTrue(result["errors"])

    def test_figma_local_snapshot_drift_is_reported(self) -> None:
        document = self.make_document()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.materialize_repo_refs(document, root)
            valid = validator.validate_ui_figma_handoff(document, project_root=root)
            self.assertEqual("valid", valid["state"], valid)
            snapshot = root / "ui" / "figma" / "demo-file.json"
            snapshot.write_text("changed\n", encoding="utf-8")
            drifted = validator.validate_ui_figma_handoff(document, project_root=root)
            self.assertIn("SHA-256 不匹配", "\n".join(drifted["errors"]))

    def test_inherited_prd_and_stage_skip_cannot_be_bypassed(self) -> None:
        document = self.make_document()
        ux = document["ui_visual_contract"]["ux_flow"]
        ux["source_document_refs"] = ["product-doc:demo:demo-brief"]
        result = validator.validate_ui_figma_handoff(document)
        self.assertIn("inherited_from_prd 必须绑定 document_kind=prd", "\n".join(result["errors"]))

        document = self.make_document()
        document["ui_visual_contract"]["workflow"]["stages"]["ux_flow"]["status"] = "pending"
        result = validator.validate_ui_figma_handoff(document)
        self.assertIn("workflow.stages.ux_flow.status=complete", "\n".join(result["errors"]))

    def test_figma_only_readiness_does_not_require_godot_theme_or_build(self) -> None:
        document = self.make_document()
        contract = document["ui_visual_contract"]
        contract.pop("theme_resource_refs")
        contract.pop("benchmark_capture_refs")
        result = validator.validate_ui_figma_handoff(document)
        self.assertEqual("valid", result["state"], result)

    def test_normal_draft_can_record_unfinished_figma_work(self) -> None:
        document = self.make_document()
        contract = document["ui_visual_contract"]
        contract["identity"]["lifecycle_state"] = "draft"
        contract["figma_prototype"] = {"handoff_status": "draft"}
        digest = validator.ui_visual_digests(document)["ui_visual_digest"]
        contract["integrity"]["ui_visual_digest"] = digest
        contract["visual_review"]["subject_digest"] = digest
        contract["benchmark_capture_refs"][0]["ui_visual_digest"] = digest
        result = validator.validate_ui_visual_contract(document)
        self.assertEqual("valid", result["state"], result)
        self.assertEqual("draft_not_evaluated", result["figma_handoff"]["state"])

    def test_legacy_figma_only_check_is_not_evaluated_as_a_pass(self) -> None:
        document = {"ui_visual_contract": {"schema_version": validator.UI_VISUAL_SCHEMA_VERSION}}
        result = validator.validate_ui_figma_handoff(document)
        self.assertEqual("legacy_not_evaluated", result["state"])
        self.assertFalse(result["figma_ready"])

    def test_ui_figma_only_cli_is_a_readiness_checker(self) -> None:
        document = self.make_document()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ui.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_art_direction_contract.py"), str(path), "--ui-figma-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["figma_ready"])

            legacy = Path(temp) / "legacy.yaml"
            legacy.write_text(yaml.safe_dump({"ui_visual_contract": {"schema_version": validator.UI_VISUAL_SCHEMA_VERSION}}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_art_direction_contract.py"), str(legacy), "--ui-figma-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual("legacy_not_evaluated", json.loads(completed.stdout)["state"])

    def test_four_stage_product_to_figma_handoff_is_explicit(self) -> None:
        contract = self.make_document()["ui_visual_contract"]
        workflow = contract["workflow"]
        self.assertEqual(
            ["input_intake", "product_identity_and_visual_direction", "ux_flow", "figma_visual_system"],
            workflow["stage_order"],
        )
        self.assertTrue(all(stage["status"] == "complete" for stage in workflow["stages"].values()))

        kinds = {ref["document_kind"] for ref in contract["source_document_refs"]}
        self.assertIn("brief", kinds)
        self.assertTrue({"prd", "gdd"}.intersection(kinds))

        identity = contract["product_identity"]
        for field in ("product_name", "product_title", "slogan"):
            self.assertTrue(identity[field])
        self.assertTrue(contract["visual_direction"]["style_requirements"])

        ux_flow = contract["ux_flow"]
        self.assertEqual("inherited_from_prd", ux_flow["resolution"])
        self.assertTrue(ux_flow["authoring_skipped"])
        self.assertTrue(ux_flow["skip_reason"])

        figma = contract["figma_prototype"]
        self.assertEqual("figma", figma["provider"])
        self.assertEqual("codex_figma_plugin", figma["integration"])
        for field in ("file_ref", "file_url", "prototype_url", "screen_refs", "design_system_ref", "handoff_evidence_refs"):
            self.assertTrue(figma[field])
        self.assertEqual("implementation_ready", figma["handoff_status"])

    def test_product_decision_change_stales_visual_evidence(self) -> None:
        document = self.make_document()
        document["ui_visual_contract"]["product_identity"]["slogan"] = "A changed promise."
        result = validator.validate_ui_visual_contract(document)
        errors = "\n".join(result["errors"])
        self.assertIn("integrity.ui_visual_digest 不匹配", errors)
        self.assertIn("benchmark_capture_refs[0].ui_visual_digest 已过期", errors)
        self.assertIn("visual_review.subject_digest 已过期或不匹配", errors)

    def test_complete_visual_contract_passes_structure_checks(self) -> None:
        result = validator.validate_ui_visual_contract(self.make_document())
        self.assertEqual("valid", result["state"], result)

    def test_missing_style_frame_fails(self) -> None:
        document = self.make_document()
        document["ui_visual_contract"]["style_frame_refs"] = []
        result = validator.validate_ui_visual_contract(document)
        self.assertIn("style_frame_refs 不能为空", "\n".join(result["errors"]))

    def test_missing_visual_deliverables_fail_deterministically(self) -> None:
        for field, message in (
            ("typography_ref", "typography_ref"),
            ("iconography_ref", "iconography_ref"),
            ("theme_resource_refs", "theme_resource_refs 不能为空"),
            ("component_state_matrix", "component_state_matrix 不能为空"),
        ):
            with self.subTest(field=field):
                document = self.make_document()
                document["ui_visual_contract"][field] = [] if field.endswith("refs") or field == "component_state_matrix" else None
                result = validator.validate_ui_visual_contract(document)
                self.assertIn(message, "\n".join(result["errors"]))

    def test_missing_visual_deliverables_fail_individually(self) -> None:
        for field, expected in (
            ("typography_ref", "typography_ref"),
            ("iconography_ref", "iconography_ref"),
            ("component_state_matrix", "component_state_matrix 不能为空"),
            ("theme_resource_refs", "theme_resource_refs 不能为空"),
        ):
            with self.subTest(field=field):
                document = self.make_document()
                document["ui_visual_contract"][field] = []
                result = validator.validate_ui_visual_contract(document)
                self.assertIn(expected, "\n".join(result["errors"]))

    def test_visual_digest_change_stales_capture_and_review(self) -> None:
        document = self.make_document()
        document["ui_visual_contract"]["shape_language"] = "Changed visual language"
        result = validator.validate_ui_visual_contract(document)
        errors = "\n".join(result["errors"])
        self.assertIn("integrity.ui_visual_digest 不匹配", errors)
        self.assertIn("benchmark_capture_refs[0].ui_visual_digest 已过期", errors)
        self.assertIn("visual_review.subject_digest 已过期或不匹配", errors)

    def test_non_ui_art_direction_does_not_require_ui_contract(self) -> None:
        art = load_yaml(PLUGIN_ROOT / "contracts" / "examples" / "art-direction-clockwork-garden.yaml")
        scope = art["art_direction_contract"]["scope"]
        scope["required_domains"] = [domain for domain in scope["required_domains"] if domain != "ui"]
        art["art_direction_contract"]["rework"]["allowed_reason_codes"] = validator.REASON_CODES
        result = validator.validate_art_direction_contract(art, target_gate="D3")
        self.assertNotIn("UI Visual Contract", "\n".join(result["gate_results"]["D3"]["issues"]))

    def test_ui_required_art_direction_without_ref_fails_d3(self) -> None:
        art = load_yaml(PLUGIN_ROOT / "contracts" / "examples" / "art-direction-clockwork-garden.yaml")
        art["art_direction_contract"]["technical_profiles"]["ui"].pop("ui_visual_contract_ref", None)
        art["art_direction_contract"]["rework"]["allowed_reason_codes"] = validator.REASON_CODES
        result = validator.validate_art_direction_contract(art, target_gate="D3")
        issues = "\n".join(result["gate_results"]["D3"]["issues"])
        self.assertEqual("invalid", result["state"])
        self.assertIn("technical_profiles.ui.ui_visual_contract_ref 缺失", "\n".join(result["errors"]))

    def test_visual_and_structure_failures_route_to_different_owners(self) -> None:
        visual = load_yaml(PLUGIN_ROOT / "contracts" / "examples" / "art-direction-clockwork-garden.yaml")
        visual["ui_visual_contract"]["shape_language"] = []
        visual_result = evaluate_art_direction_gate(visual, "D3")
        self.assertIn("UI_VISUAL", visual_result["rework"]["reason_codes"])
        self.assertIn("position:clockwork-garden:art-director", visual_result["rework"]["routes"]["UI_VISUAL"])

        structure = load_yaml(PLUGIN_ROOT / "contracts" / "examples" / "art-direction-clockwork-garden.yaml")
        structure["ui_visual_contract"]["screen_flow_ref"] = None
        structure_result = evaluate_art_direction_gate(structure, "D3")
        self.assertIn("UI_STRUCTURE", structure_result["rework"]["reason_codes"])
        self.assertIn("position:clockwork-garden:ui-ux", structure_result["rework"]["routes"]["UI_STRUCTURE"])


if __name__ == "__main__":
    unittest.main()
