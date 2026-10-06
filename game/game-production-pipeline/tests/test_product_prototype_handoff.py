from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "validate_product_prototype_handoff",
    ROOT / "scripts" / "validate_product_prototype_handoff.py",
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class ProductPrototypeHandoffTests(unittest.TestCase):
    def write_ref(self, root: Path, relative: str, content: str, *, artifact_id: str) -> dict:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        return {
            "artifact_id": artifact_id,
            "uri": "repo://" + relative.replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def instance(self, root: Path) -> dict:
        refs = [self.write_ref(root, "inputs/brief.yaml", "brief: synthetic\n", artifact_id="brief:test")]
        prd = self.write_ref(root, "outputs/prd.md", "# PRD\n", artifact_id="prd:test")
        h = {
            "schema_version": "game-production-product-prototype-handoff/v1",
            "synthetic": True,
            "identity": {
                "handoff_id": "handoff:test-game:prototype",
                "project_id": "test-game",
                "revision": 1,
                "previous_revision_digest": None,
                "lifecycle_state": "draft",
                "owner_position_id": "pos:test-game:root:product-manager",
                "prepared_by_instance_id": "inst:synthetic",
            },
            "authority": {
                "project_manager_position_id": "pos:test-game:root:project-manager",
                "product_owner": "human:test-owner",
                "direction_gate_refs": ["GATE-0", "GATE-1"],
                "visual_gate_refs": ["D2", "UI_VISUAL"],
                "final_decision_owner": "human:test-owner",
                "approval_required_before": ["product_identity", "project_scope", "core_experience"],
            },
            "source_document_refs": [dict(refs[0], version=1, document_kind="brief",
                                           title="Synthetic brief", status="confirmed", role="requirements")],
            "consultation": {
                "topology": "project-manager-led-p2p",
                "participants": [
                    {"slot_id": slot, "activation": "not_requested", "status": "not_applicable",
                     "manager_instance_id": None, "reason": "synthetic pilot scope"}
                    for slot in sorted(validator.SLOTS)
                ],
            },
            "product_identity": {
                name: {"value": "Synthetic Product", "status": "proposed",
                       "decision_owner": "human:test-owner", "decision_ref": None}
                for name in ("product_name", "product_title", "slogan")
            },
            "product_packet": {
                "audience": "synthetic reviewer",
                "player_value": "learn the handoff contract",
                "design_pillars": ["traceability"],
                "scope": {"must": ["one screen"], "should": [], "wont": [], "status": "proposal", "decision_ref": None},
                "prd_ref": prd,
                "gdd_ref": None,
            },
            "prototype_intent": {
                "purpose": "test a traceable product handoff",
                "success_criteria": ["reviewer can follow the main flow"],
                "key_screen_ids": ["screen:entry"],
                "flow_ids": ["flow:entry"],
                "required_states": ["normal", "success", "error", "back", "cancel"],
                "review_owners": {"product": "human:test-owner", "ui_ux": "position:test-game:ui-ux", "art": "position:test-game:art-director"},
            },
            "penpot": {
                "requested": False,
                "tool_id": "tool:penpot-mcp",
                "approved_scope": [],
                "handoff_status": "not_requested",
            },
            "human_gate": {
                "required": True,
                "gate_refs": ["GATE-0", "GATE-1"],
                "status": "pending",
                "approval_ref": None,
                "approval_subject_digest": None,
                "handoff_approval_ref": None,
            },
            "acceptance": {"automated_checks": [], "professional_reviews": [], "human_experience_approval": "pending"},
            "rework_routes": {"PRODUCT_DIRECTION": ["human:test-owner"]},
            "integrity": {
                "canonicalization": "product-prototype-handoff-canonical-json-v1",
                "direction_canonicalization": "product-prototype-direction-canonical-json-v1",
                "digest_algorithm": "sha256",
            },
        }
        document = {"product_prototype_handoff": h}
        h["integrity"].update(validator.handoff_digests(document))
        return document

    def test_synthetic_instance_is_explicit_and_template_has_new_digest_fields(self):
        template = (ROOT / "contracts" / "product-prototype-handoff.template.yaml").read_text(encoding="utf-8")
        self.assertIn("direction_subject_digest", template)
        self.assertIn("evidence_subject_digest", template)
        with tempfile.TemporaryDirectory() as directory:
            result = validator.validate_product_prototype_handoff(
                self.instance(Path(directory)), project_root=Path(directory), allow_synthetic=True
            )
        self.assertEqual("valid", result["state"], result["errors"])
        self.assertTrue(result["synthetic"])
        self.assertFalse(result["remote_verified"])

    def test_direction_digest_does_not_change_when_evidence_is_added(self):
        with tempfile.TemporaryDirectory() as directory:
            base = self.instance(Path(directory))
            changed = copy.deepcopy(base)
            changed["product_prototype_handoff"]["penpot"]["file_url"] = "https://penpot.example/file"
            changed["product_prototype_handoff"]["penpot"]["operation_evidence_ref"] = {"uri": "repo://evidence/ops.yaml", "sha256": "0" * 64}
            self.assertEqual(
                validator.handoff_digests(base)["direction_subject_digest"],
                validator.handoff_digests(changed)["direction_subject_digest"],
            )
            self.assertNotEqual(
                validator.handoff_digests(base)["evidence_subject_digest"],
                validator.handoff_digests(changed)["evidence_subject_digest"],
            )

    def test_f09_direction_approval_requires_external_human_record(self):
        with tempfile.TemporaryDirectory() as directory:
            document = self.instance(Path(directory))
            h = document["product_prototype_handoff"]
            h["identity"]["lifecycle_state"] = "approved"
            h["human_gate"].update({"status": "approved", "approval_subject_digest": validator.handoff_digests(document)["direction_subject_digest"]})
            h["integrity"].update(validator.handoff_digests(document))
            result = validator.validate_product_prototype_handoff(document, project_root=Path(directory), allow_synthetic=True)
        self.assertEqual("invalid", result["state"])
        self.assertTrue(any("external human approval" in error for error in result["errors"]))

    def test_empty_referenced_document_cannot_be_a_complete_handoff(self):
        """A no-document intake must fail closed even when its empty file has a valid digest."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self.instance(root)
            source = document["product_prototype_handoff"]["source_document_refs"][0]
            path = root / "inputs" / "brief.yaml"
            path.write_text(" \n", encoding="utf-8")
            source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            document["product_prototype_handoff"]["integrity"].update(validator.handoff_digests(document))
            result = validator.validate_product_prototype_handoff(
                document, project_root=root, allow_synthetic=True
            )
        self.assertEqual("invalid", result["state"], result)
        self.assertTrue(any("must not be empty" in error for error in result["errors"]))
        self.assertFalse(result["local_evidence_ready"])

    def test_f10_repo_reference_escape_and_digest_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            document = self.instance(Path(directory))
            source = document["product_prototype_handoff"]["source_document_refs"][0]
            source["uri"] = "repo://../outside.yaml"
            result = validator.validate_product_prototype_handoff(document, project_root=Path(directory), allow_synthetic=True)
        self.assertEqual("invalid", result["state"])
        self.assertTrue(any("escapes project" in error or "does not exist" in error for error in result["errors"]))

    def test_f14_recursive_and_placeholder_input_returns_errors_without_crashing(self):
        recursive = {"product_prototype_handoff": {"schema_version": "game-production-product-prototype-handoff/v1"}}
        recursive["product_prototype_handoff"]["self"] = recursive["product_prototype_handoff"]
        with tempfile.TemporaryDirectory() as directory:
            result = validator.validate_product_prototype_handoff(recursive, project_root=Path(directory), allow_synthetic=True)
        self.assertEqual("invalid", result["state"])
        self.assertTrue(result["errors"])
        with tempfile.TemporaryDirectory() as directory:
            placeholder = self.instance(Path(directory))
            placeholder["product_prototype_handoff"]["product_packet"]["audience"] = "<replace-me>"
            result = validator.validate_product_prototype_handoff(placeholder, project_root=Path(directory), allow_synthetic=True)
        self.assertEqual("invalid", result["state"])
        self.assertTrue(any("placeholder" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
