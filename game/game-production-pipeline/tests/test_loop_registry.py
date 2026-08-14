from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "validate_loop_registry.py"
SNAPSHOT = PLUGIN_ROOT / "contracts" / "loop-registry-record.template.yaml"
EVENT = PLUGIN_ROOT / "contracts" / "loop-registry-event.template.yaml"
CONTRACT = PLUGIN_ROOT / "contracts" / "loop-contract.template.yaml"
STATE_MACHINE = PLUGIN_ROOT / "contracts" / "loop-state-machine.default.yaml"

SPEC = importlib.util.spec_from_file_location("validate_loop_registry", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class LoopRegistryValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = load_yaml(SNAPSHOT)
        self.event = load_yaml(EVENT)
        self.contract = load_yaml(CONTRACT)
        self.state_machine = load_yaml(STATE_MACHINE)

    def validate(self) -> list[str]:
        return MODULE.validate_templates(
            self.snapshot,
            self.event,
            self.contract,
            self.state_machine,
        )

    def test_current_templates_are_consistent(self) -> None:
        self.assertEqual([], self.validate())

    def test_every_core_event_has_payload_contract(self) -> None:
        del self.event["payload_contracts"]["core.budget_extended"]
        errors = self.validate()
        self.assertTrue(any("Payload Contract" in error for error in errors))

    def test_contract_input_id_must_match_snapshot(self) -> None:
        self.snapshot["field_examples"]["input_binding"]["input_slot_id"] = "INPUT-OTHER"
        errors = self.validate()
        self.assertTrue(any("input_slot_id" in error for error in errors))

    def test_state_machine_binding_version_must_match(self) -> None:
        self.snapshot["registry_snapshot"]["state_machine_binding"][
            "state_machine_version"
        ] = "0.1"
        errors = self.validate()
        self.assertTrue(any("state_machine_version" in error for error in errors))

    def test_registration_revision_must_be_atomic(self) -> None:
        self.event["event"]["concurrency"]["resulting_record_revision"] = 2
        errors = self.validate()
        self.assertTrue(any("resulting_record_revision" in error for error in errors))

    def test_terminal_transition_uses_specialized_event(self) -> None:
        for transition in self.state_machine["transitions"]:
            if transition["transition_id"] == "TR-REVIEW-COMPLETED":
                transition["event_type"] = "core.state_transitioned"
        errors = self.validate()
        self.assertTrue(any("TR-REVIEW-COMPLETED.event_type" in error for error in errors))

    def test_interruption_transition_cannot_increment_iteration(self) -> None:
        for transition in self.state_machine["transitions"]:
            if transition["transition_id"] == "TR-INTERRUPTED-RESUME":
                transition["iteration_effect"] = "increment"
        errors = self.validate()
        self.assertTrue(any("TR-INTERRUPTED-RESUME" in error for error in errors))

    def test_event_canonicalization_contract_is_required(self) -> None:
        self.event["integrity_contract"]["rules"] = [
            rule
            for rule in self.event["integrity_contract"]["rules"]
            if "event_digest 设为 null" not in rule
        ]
        errors = self.validate()
        self.assertTrue(any("event_digest 设为 null" in error for error in errors))

    def test_draft_registration_has_no_runtime_artifacts(self) -> None:
        self.snapshot["registry_snapshot"]["resources"]["inputs"].append(
            copy.deepcopy(self.snapshot["field_examples"]["input_binding"])
        )
        errors = self.validate()
        self.assertTrue(any("draft 注册基线" in error for error in errors))

    def test_topology_cycle_policy_is_required(self) -> None:
        self.snapshot["storage_contract"]["topology_rules"] = []
        errors = self.validate()
        self.assertTrue(any("拓扑规则缺少" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
