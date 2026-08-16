from __future__ import annotations

import copy
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "validate_loop_registry.py"
SNAPSHOT = PLUGIN_ROOT / "contracts" / "loop-registry-record.template.yaml"
EVENT = PLUGIN_ROOT / "contracts" / "loop-registry-event.template.yaml"
CONTRACT = PLUGIN_ROOT / "contracts" / "loop-contract.template.yaml"
STATE_MACHINE = PLUGIN_ROOT / "contracts" / "loop-state-machine.default.yaml"

SPEC = importlib.util.spec_from_file_location("validate_loop_registry_history", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def make_event(
    *,
    sequence: int,
    event_type: str,
    from_state: str | None = None,
    to_state: str | None = None,
    transition_id: str | None = None,
    iteration_before: int = 0,
    iteration_after: int = 0,
    previous_digest: str | None = None,
    extra_payload: dict | None = None,
) -> dict:
    event = {
        "schema_version": "0.1",
        "event_id": f"event-{sequence}",
        "mutation_id": f"mutation-{sequence}",
        "loop_instance_id": "loop-1",
        "sequence": sequence,
        "event_type": event_type,
        "occurred_at": "2026-08-14T00:00:00Z",
        "recorded_at": "2026-08-14T00:00:00Z",
        "actor": {
            "actor_id": "actor-1",
            "role": "owner",
            "authority_id": "auth-1",
        },
        "causality": {
            "correlation_id": "correlation-1",
            "causation_event_id": None,
            "request_id": None,
        },
        "concurrency": {
            "expected_record_revision": sequence - 1,
            "resulting_record_revision": sequence,
        },
        "binding_snapshot": {
            "contract_digest": "a" * 64,
            "state_machine_digest": "b" * 64,
        },
        "payload": {},
        "evidence_refs": [],
        "integrity": {
            "canonicalization": "registry-event-canonical-json-v1",
            "digest_algorithm": "sha256",
            "previous_event_digest": previous_digest,
            "event_digest": None,
        },
    }
    if event_type == "core.loop_registered":
        event["payload"] = {
            "project_id": "project-1",
            "initial_state": "draft",
            "identity": {},
            "contract_binding": {
                "contract_id": "LOOP-CTR-<TYPE>-<NUMBER>",
                "contract_version": 1,
                "contract_digest": "a" * 64,
            },
            "state_machine_binding": {
                "state_machine_id": "LOOP-SM-DEFAULT",
                "state_machine_version": "0.2",
                "state_machine_digest": "b" * 64,
            },
            "parent_loop_id": None,
            "owner_assignment": {},
            "budget_limits": {},
        }
    else:
        event["payload"] = {
            "transition_id": transition_id,
            "from_state": from_state,
            "to_state": to_state,
            "iteration": {
                "before": iteration_before,
                "after": iteration_after,
            },
        }
        if event_type == "core.state_transitioned":
            event["payload"]["reason"] = "状态推进"
        if event_type == "core.loop_completed":
            event["payload"].update(
                {
                    "acceptance_subject_digest": "c" * 64,
                    "final_handoff_ref": "handoff-1",
                }
            )
    if extra_payload:
        event["payload"].update(extra_payload)
    event["integrity"]["event_digest"] = MODULE.canonical_event_digest(event)
    return event


class LoopRegistryHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot_doc = load_yaml(SNAPSHOT)
        self.event_contract_doc = load_yaml(EVENT)
        self.contract_doc = load_yaml(CONTRACT)
        self.state_machine_doc = load_yaml(STATE_MACHINE)

        event1 = make_event(sequence=1, event_type="core.loop_registered")
        event2 = make_event(
            sequence=2,
            event_type="core.state_transitioned",
            transition_id="TR-DRAFT-READY",
            from_state="draft",
            to_state="ready",
            previous_digest=event1["integrity"]["event_digest"],
        )
        event3 = make_event(
            sequence=3,
            event_type="core.loop_started",
            transition_id="TR-READY-ACTIVE",
            from_state="ready",
            to_state="active",
            iteration_before=0,
            iteration_after=1,
            previous_digest=event2["integrity"]["event_digest"],
        )
        self.history_doc = {"event_history": [event1, event2, event3]}

        snapshot = self.snapshot_doc["registry_snapshot"]
        snapshot["identity"]["loop_instance_id"] = "loop-1"
        snapshot["contract_binding"].update(
            {
                "contract_id": self.contract_doc["loop_contract"]["contract_id"],
                "contract_version": self.contract_doc["loop_contract"]["version"],
                "contract_digest": "a" * 64,
            }
        )
        snapshot["state_machine_binding"]["state_machine_digest"] = "b" * 64
        snapshot["runtime"].update(
            {
                "current_state": "active",
                "current_iteration": 1,
                "last_transition_id": "TR-READY-ACTIVE",
                "last_event_id": event3["event_id"],
                "last_event_digest": event3["integrity"]["event_digest"],
                "last_event_sequence": 3,
                "record_revision": 3,
            }
        )

    def run_cli(self, *, record_template: bool = False) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = {
                "snapshot": root / "snapshot.yaml",
                "history": root / "history.yaml",
                "event": root / "event.yaml",
                "contract": root / "contract.yaml",
                "state_machine": root / "state-machine.yaml",
                "record_template": root / "record-template.yaml",
            }
            documents = {
                "snapshot": self.snapshot_doc,
                "history": self.history_doc,
                "event": self.event_contract_doc,
                "contract": self.contract_doc,
                "state_machine": self.state_machine_doc,
                "record_template": load_yaml(SNAPSHOT),
            }
            for name, path in paths.items():
                path.write_text(
                    yaml.safe_dump(documents[name], allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
            arguments = [
                str(SCRIPT),
                "--snapshot",
                str(paths["snapshot"]),
                "--history",
                str(paths["history"]),
                "--event",
                str(paths["event"]),
                "--contract",
                str(paths["contract"]),
                "--state-machine",
                str(paths["state_machine"]),
            ]
            if record_template:
                arguments.extend(["--record-template", str(paths["record_template"])])
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(sys, "argv", arguments):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = MODULE.main()
            return exit_code, stdout.getvalue(), stderr.getvalue()

    def validate(self) -> list[str]:
        return MODULE.validate_history(
            self.snapshot_doc,
            self.history_doc,
            self.state_machine_doc,
            self.event_contract_doc,
            self.contract_doc,
        )

    def test_valid_history_rebuilds_snapshot_watermark(self) -> None:
        self.assertEqual([], self.validate())

    def test_active_snapshot_cli_does_not_apply_six_draft_template_rules(self) -> None:
        snapshot = self.snapshot_doc["registry_snapshot"]
        snapshot["resources"]["inputs"] = [
            {"input_slot_id": "INPUT-001", "artifact": {}}
        ]
        snapshot["resources"]["outputs"] = [
            {"deliverable_id": "DELIVERABLE-001", "artifact": {}}
        ]
        self.snapshot_doc["field_examples"]["input_binding"]["input_slot_id"] = (
            "INPUT-OTHER"
        )
        self.snapshot_doc["field_examples"]["output_registration"]["deliverable_id"] = (
            "DELIVERABLE-OTHER"
        )

        self.assertEqual([], self.validate())
        draft_errors = MODULE.validate_templates(
            self.snapshot_doc,
            self.event_contract_doc,
            self.contract_doc,
            self.state_machine_doc,
        )
        expected_false_positives = {
            "Snapshot 模板初始状态必须等于状态机 initial_state",
            "Snapshot 模板 current_iteration 必须从 0 开始",
            "注册后的 Snapshot 模板必须位于 sequence=1、record_revision=1",
            "draft 注册基线的 inputs 和 outputs 必须为空",
            "Snapshot input_slot_id 必须完整对应 Contract required_inputs",
            "Snapshot deliverable_id 必须完整对应 Contract required_deliverables",
        }
        self.assertEqual(expected_false_positives, set(draft_errors))

        exit_code, stdout, stderr = self.run_cli()
        self.assertEqual(0, exit_code, stderr)
        self.assertIn("运行态", stdout)
        for false_positive in expected_false_positives:
            self.assertNotIn(false_positive, stderr)

    def test_runtime_cli_accepts_independent_record_template(self) -> None:
        exit_code, stdout, stderr = self.run_cli(record_template=True)
        self.assertEqual(0, exit_code, stderr)
        self.assertIn("运行态", stdout)

    def test_runtime_cli_still_checks_static_event_contract(self) -> None:
        del self.event_contract_doc["payload_contracts"]["core.budget_extended"]
        exit_code, _, stderr = self.run_cli(record_template=True)
        self.assertEqual(1, exit_code)
        self.assertIn("Payload Contract", stderr)

    def test_digest_tampering_is_detected(self) -> None:
        self.history_doc["event_history"][1]["payload"]["reason"] = "被篡改"
        errors = self.validate()
        self.assertTrue(any("event_digest 不匹配" in error for error in errors))

    def test_sequence_gap_is_rejected(self) -> None:
        self.history_doc["event_history"][2]["sequence"] = 4
        self.history_doc["event_history"][2]["integrity"]["event_digest"] = (
            MODULE.canonical_event_digest(self.history_doc["event_history"][2])
        )
        errors = self.validate()
        self.assertTrue(any("sequence 必须为 3" in error for error in errors))

    def test_record_revision_mismatch_is_rejected(self) -> None:
        event3 = self.history_doc["event_history"][2]
        event3["concurrency"]["expected_record_revision"] = 99
        event3["integrity"]["event_digest"] = MODULE.canonical_event_digest(event3)
        errors = self.validate()
        self.assertTrue(any("expected_record_revision 必须为 2" in error for error in errors))

    def test_duplicate_mutation_is_rejected(self) -> None:
        self.history_doc["event_history"][2]["mutation_id"] = "mutation-2"
        self.history_doc["event_history"][2]["integrity"]["event_digest"] = (
            MODULE.canonical_event_digest(self.history_doc["event_history"][2])
        )
        errors = self.validate()
        self.assertTrue(any("mutation_id 重复" in error for error in errors))

    def test_snapshot_state_drift_is_rejected(self) -> None:
        self.snapshot_doc["registry_snapshot"]["runtime"]["current_state"] = "review"
        errors = self.validate()
        self.assertTrue(any("current_state 无法由 Event History 重建" in error for error in errors))

    def test_snapshot_tail_watermark_mismatch_is_rejected(self) -> None:
        self.snapshot_doc["registry_snapshot"]["runtime"]["last_event_sequence"] = 2
        errors = self.validate()
        self.assertTrue(any("last_event_sequence" in error for error in errors))

    def test_unknown_snapshot_input_or_deliverable_id_is_rejected(self) -> None:
        for collection, identifier, value in (
            ("inputs", "input_slot_id", "INPUT-UNKNOWN"),
            ("outputs", "deliverable_id", "DELIVERABLE-UNKNOWN"),
        ):
            with self.subTest(collection=collection):
                changed = copy.deepcopy(self.snapshot_doc)
                changed["registry_snapshot"]["resources"][collection] = [
                    {identifier: value, "artifact": {}}
                ]
                errors = MODULE.validate_runtime_snapshot(
                    changed,
                    self.contract_doc,
                    self.state_machine_doc,
                    load_yaml(SNAPSHOT),
                )
                self.assertTrue(any(value in error for error in errors), errors)

    def test_unknown_event_input_or_deliverable_id_is_rejected(self) -> None:
        for event_type, identifier, value in (
            ("core.input_bound", "input_slot_id", "INPUT-UNKNOWN"),
            ("core.output_registered", "deliverable_id", "DELIVERABLE-UNKNOWN"),
        ):
            with self.subTest(event_type=event_type):
                history_doc = copy.deepcopy(self.history_doc)
                snapshot_doc = copy.deepcopy(self.snapshot_doc)
                event3 = history_doc["event_history"][-1]
                event4 = make_event(
                    sequence=4,
                    event_type=event_type,
                    previous_digest=event3["integrity"]["event_digest"],
                    extra_payload={identifier: value, "before": None, "after": {}},
                )
                history_doc["event_history"].append(event4)
                snapshot_doc["registry_snapshot"]["runtime"].update(
                    {
                        "last_event_id": event4["event_id"],
                        "last_event_digest": event4["integrity"]["event_digest"],
                        "last_event_sequence": 4,
                        "record_revision": 4,
                    }
                )
                errors = MODULE.validate_history(
                    snapshot_doc,
                    history_doc,
                    self.state_machine_doc,
                    self.event_contract_doc,
                    self.contract_doc,
                )
                self.assertTrue(any(value in error for error in errors), errors)

    def test_illegal_transition_event_binding_is_rejected(self) -> None:
        event3 = self.history_doc["event_history"][2]
        event3["event_type"] = "core.state_transitioned"
        event3["payload"]["reason"] = "错误事件类型"
        event3["integrity"]["event_digest"] = MODULE.canonical_event_digest(event3)
        errors = self.validate()
        self.assertTrue(any("event_type 与转换绑定不一致" in error for error in errors))

    def test_missing_payload_contract_field_is_rejected(self) -> None:
        del self.history_doc["event_history"][0]["payload"]["owner_assignment"]
        self.history_doc["event_history"][0]["integrity"]["event_digest"] = (
            MODULE.canonical_event_digest(self.history_doc["event_history"][0])
        )
        errors = self.validate()
        self.assertTrue(any("owner_assignment 缺失" in error for error in errors))

    def test_resume_must_return_to_first_operational_state(self) -> None:
        event3 = self.history_doc["event_history"][-1]
        event4 = make_event(
            sequence=4,
            event_type="core.interruption_entered",
            transition_id="TR-OPERATIONAL-INTERRUPTED",
            from_state="active",
            to_state="blocked",
            iteration_before=1,
            iteration_after=1,
            previous_digest=event3["integrity"]["event_digest"],
            extra_payload={"interruption": {"resume_state": "active"}},
        )
        event5 = make_event(
            sequence=5,
            event_type="core.resume_revalidation_recorded",
            transition_id="TR-INTERRUPTED-RESUME",
            from_state="blocked",
            to_state="review",
            iteration_before=1,
            iteration_after=1,
            previous_digest=event4["integrity"]["event_digest"],
            extra_payload={
                "interruption_id": "interrupt-1",
                "revalidation": {},
            },
        )
        self.history_doc["event_history"].extend([event4, event5])
        runtime = self.snapshot_doc["registry_snapshot"]["runtime"]
        runtime.update(
            {
                "current_state": "review",
                "current_iteration": 1,
                "last_transition_id": "TR-INTERRUPTED-RESUME",
                "last_event_id": event5["event_id"],
                "last_event_digest": event5["integrity"]["event_digest"],
                "last_event_sequence": 5,
                "record_revision": 5,
            }
        )
        errors = self.validate()
        self.assertTrue(any("恢复目标不等于" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
