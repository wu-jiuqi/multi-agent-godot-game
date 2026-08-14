from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "validate_organization_registry.py"
SNAPSHOT = PLUGIN_ROOT / "contracts" / "examples" / "organization-alpha-snapshot.yaml"
CHANGE_SET = PLUGIN_ROOT / "contracts" / "examples" / "organization-alpha-change-set.yaml"
CONTRACTS = PLUGIN_ROOT / "contracts"

SPEC = importlib.util.spec_from_file_location("validate_organization_registry", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class OrganizationRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = load_yaml(SNAPSHOT)
        self.change_set = load_yaml(CHANGE_SET)

    def refresh_snapshot_digest(self) -> None:
        self.snapshot["organization_snapshot"]["snapshot_integrity"]["snapshot_digest"] = (
            MODULE.canonical_snapshot_digest(self.snapshot)
        )

    def refresh_change_set_digest(self) -> None:
        self.change_set["organization_change_set"]["integrity"]["change_set_digest"] = (
            MODULE.canonical_change_set_digest(self.change_set)
        )

    def test_contract_templates_and_examples_are_valid(self) -> None:
        templates = [
            load_yaml(CONTRACTS / name)
            for name in (
                "organization-snapshot.template.yaml",
                "organization-event.template.yaml",
                "organization-change-set.template.yaml",
                "organization-validation.template.yaml",
            )
        ]
        self.assertEqual([], MODULE.validate_contract_templates(*templates))
        self.assertEqual([], MODULE.validate_snapshot(self.snapshot))
        self.assertEqual([], MODULE.validate_change_set(self.change_set, self.snapshot))

    def test_snapshot_tampering_is_detected(self) -> None:
        self.snapshot["organization_snapshot"]["formal_structure"]["positions"][0]["display_name"] = "被篡改"
        errors = MODULE.validate_snapshot(self.snapshot)
        self.assertTrue(any("snapshot_digest 不匹配" in error for error in errors))

    def test_department_hierarchy_cycle_is_rejected(self) -> None:
        department = self.snapshot["organization_snapshot"]["formal_structure"]["departments"][0]
        department["parent_department_id"] = department["department_id"]
        self.refresh_snapshot_digest()
        errors = MODULE.validate_snapshot(self.snapshot)
        self.assertTrue(any("Department 层级存在环" in error for error in errors))

    def test_position_reporting_cycle_is_rejected(self) -> None:
        positions = self.snapshot["organization_snapshot"]["formal_structure"]["positions"]
        positions[-1]["reports_to_position_id"] = positions[0]["position_id"]
        self.refresh_snapshot_digest()
        errors = MODULE.validate_snapshot(self.snapshot)
        self.assertTrue(any("Position 汇报关系存在环" in error for error in errors))

    def test_manager_must_belong_to_department(self) -> None:
        department = self.snapshot["organization_snapshot"]["formal_structure"]["departments"][0]
        department["manager_position_id"] = "pos:sample-game:root:project-manager"
        self.refresh_snapshot_digest()
        errors = MODULE.validate_snapshot(self.snapshot)
        self.assertTrue(any("必须引用本部门" in error for error in errors))

    def test_instance_union_is_enforced(self) -> None:
        instance = self.snapshot["organization_snapshot"]["runtime"]["instances"][0]
        instance["temporary_binding"] = {"grant_id": "grant:sample-game:01K2M3N4P5Q6R7S8T9V0W1X2Y5"}
        self.refresh_snapshot_digest()
        errors = MODULE.validate_snapshot(self.snapshot)
        self.assertTrue(any("discriminated union" in error for error in errors))

    def test_temporary_preset_must_be_authorized(self) -> None:
        instance = self.snapshot["organization_snapshot"]["runtime"]["instances"][1]
        instance["preset_binding"]["preset_id"] = "preset:project:not-approved"
        self.refresh_snapshot_digest()
        errors = MODULE.validate_snapshot(self.snapshot)
        self.assertTrue(any("不在 Temporary Grant" in error for error in errors))

    def test_grant_usage_must_equal_current_reservations(self) -> None:
        grant = self.snapshot["organization_snapshot"]["runtime"]["temporary_grants"][0]
        grant["usage"]["reserved_cost"] = 3
        self.refresh_snapshot_digest()
        errors = MODULE.validate_snapshot(self.snapshot)
        self.assertTrue(any("预留不一致" in error for error in errors))

    def test_change_set_requires_human_approval(self) -> None:
        self.change_set["organization_change_set"]["approval_requirement"]["human_approval_required"] = False
        self.refresh_change_set_digest()
        errors = MODULE.validate_change_set(self.change_set, self.snapshot)
        self.assertTrue(any("必须要求人工审批" in error for error in errors))

    def test_governance_queue_updates_do_not_make_change_set_stale(self) -> None:
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["organization_snapshot"]["identity"]["organization_revision"] += 1
        snapshot["organization_snapshot"]["event_watermark"]["last_event_sequence"] += 1
        snapshot["organization_snapshot"]["event_watermark"]["last_event_id"] = "evt:another-governance-event"
        snapshot["organization_snapshot"]["event_watermark"]["last_event_digest"] = "1" * 64
        snapshot["organization_snapshot"]["snapshot_integrity"]["snapshot_digest"] = MODULE.canonical_snapshot_digest(snapshot)
        errors = MODULE.validate_change_set(self.change_set, snapshot)
        self.assertFalse(any("stale" in error for error in errors))

    def test_formal_structure_change_makes_change_set_stale(self) -> None:
        self.snapshot["organization_snapshot"]["formal_structure"]["positions"][0]["responsibilities"].append("新增职责")
        self.refresh_snapshot_digest()
        errors = MODULE.validate_change_set(self.change_set, self.snapshot)
        self.assertTrue(any("决策基线已 stale" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
