from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "game" / "scripts" / "validate_loop_registry.py"
SNAPSHOT = ROOT / "game" / "contracts" / "loop-registry-record.template.yaml"
EVENT = ROOT / "game" / "contracts" / "loop-registry-event.template.yaml"
STATE_MACHINE = ROOT / "game" / "contracts" / "loop-state-machine.default.yaml"

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
            "contract_binding": {},
            "state_machine_binding": {},
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

    def validate(self) -> list[str]:
        return MODULE.validate_history(
            self.snapshot_doc,
            self.history_doc,
            self.state_machine_doc,
            self.event_contract_doc,
        )

    def test_valid_history_rebuilds_snapshot_watermark(self) -> None:
        self.assertEqual([], self.validate())

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
