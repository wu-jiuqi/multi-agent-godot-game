from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "validate_organization_extensions.py"
SPEC = importlib.util.spec_from_file_location("validate_organization_extensions", SCRIPT_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class OrganizationExtensionTests(unittest.TestCase):
    def read_contract(self, name: str) -> dict:
        return yaml.safe_load((PLUGIN_ROOT / "contracts" / name).read_text(encoding="utf-8"))

    def test_extension_templates_pass_deterministic_validator(self) -> None:
        catalog = self.read_contract("department-slot-catalog.template.yaml")
        consultation = self.read_contract("consultation-event.template.yaml")
        handoff = self.read_contract("product-prototype-handoff.template.yaml")
        self.assertEqual([], validator.validate_catalog(catalog))
        self.assertEqual([], validator.validate_consultation(consultation))
        self.assertEqual([], validator.validate_handoff(handoff))

    def test_catalog_has_six_lazy_slots_and_keeps_qa_independent(self) -> None:
        catalog = self.read_contract("department-slot-catalog.template.yaml")["department_slot_catalog"]
        semantics = catalog["fixed_slots"]["semantics"]
        self.assertEqual(6, semantics["slot_count"])
        self.assertEqual(0, semantics["default_runtime_instances"])
        self.assertEqual("on_demand_only", semantics["manager_activation"])
        self.assertEqual(
            validator.SLOT_IDS,
            {slot["slot_id"] for slot in catalog["slots"]},
        )
        qa = next(slot for slot in catalog["slots"] if slot["slot_id"] == "slot:qa")
        self.assertEqual([], qa["can_merge_with"])
        self.assertTrue(set(validator.SLOT_IDS) - {"slot:qa"} <= set(qa["independent_from"]))

    def test_consultation_contract_is_advisory_and_append_only(self) -> None:
        document = self.read_contract("consultation-event.template.yaml")
        contract = document["consultation_event"]
        self.assertEqual("peer_to_peer_with_coordinator", contract["topology"]["mode"])
        self.assertFalse(contract["authority_effect"]["changes_project_fact"])
        self.assertEqual([], contract["authority_effect"]["writes_to_source_of_truth"])
        stream = "\n".join(document["application_contract"]["event_stream"])
        self.assertIn("幂等", stream)
        self.assertIn("追加不可覆盖或删除", stream)

    def test_no_document_product_discovery_precedes_prototype_handoff(self) -> None:
        skill = (PLUGIN_ROOT / "skills" / "product-discovery" / "SKILL.md").read_text(encoding="utf-8")
        workflow = (PLUGIN_ROOT / "workflows" / "product-discovery.md").read_text(encoding="utf-8")
        for text in (skill, workflow):
            self.assertIn("proposal", text)
            self.assertIn("unknown", text)
            self.assertIn("GATE-0", text)
            self.assertIn("GATE-1", text)
            self.assertIn("product-prototype-handoff", text)
        self.assertIn("空输入", workflow)
        self.assertIn("initial brief", skill)
        self.assertIn("initial PRD", skill)

    def test_product_and_penpot_boundaries_are_explicit(self) -> None:
        product_skill = (PLUGIN_ROOT / "skills" / "product-brief-and-identity" / "SKILL.md").read_text(encoding="utf-8")
        penpot_skill = (PLUGIN_ROOT / "skills" / "penpot-prototype-orchestration" / "SKILL.md").read_text(encoding="utf-8")
        product_agent = (PLUGIN_ROOT / "agents" / "product-manager.md").read_text(encoding="utf-8")
        workflow = (PLUGIN_ROOT / "workflows" / "product-prototyping.md").read_text(encoding="utf-8")
        for text in (product_skill, product_agent, workflow):
            self.assertIn("GATE-0", text)
            self.assertIn("GATE-1", text)
            self.assertIn("P2P", text)
        self.assertIn("tool:penpot-mcp", penpot_skill)
        self.assertIn("Read before writing", penpot_skill)
        self.assertIn("UI_VISUAL", penpot_skill)
        self.assertIn("UI_STRUCTURE", penpot_skill)
        self.assertIn("implementation_ready", penpot_skill)
        self.assertIn("不等于 Godot", workflow)


if __name__ == "__main__":
    unittest.main()
