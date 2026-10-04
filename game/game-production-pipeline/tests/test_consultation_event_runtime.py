from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "validate_consultation_event.py"
SPEC = importlib.util.spec_from_file_location("validate_consultation_event", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class ConsultationEventRuntimeTests(unittest.TestCase):
    def read_fixture(self, name: str) -> dict:
        return yaml.safe_load(
            (PLUGIN_ROOT / "contracts" / "examples" / name).read_text(encoding="utf-8")
        )

    def test_valid_opened_fixture_passes_and_digest_is_reproducible(self) -> None:
        event = self.read_fixture("consultation-event-valid.yaml")
        self.assertEqual([], validator.validate_consultation_event(event))
        inner = event["consultation_event"]
        self.assertEqual(inner["integrity"]["event_digest"], validator.canonical_event_digest(event))
        self.assertEqual("consultation-event-canonical-json-v1", inner["integrity"]["canonicalization"])

    def test_invalid_fixture_reports_watermark_and_canonicalization_errors(self) -> None:
        event = self.read_fixture("consultation-event-invalid.yaml")
        errors = validator.validate_consultation_event(event)
        self.assertTrue(any("sequence/resulting" in error for error in errors))
        self.assertTrue(any("canonicalization" in error for error in errors))
        self.assertTrue(any("previous_event" in error for error in errors))

    def test_external_watermark_must_match_event_concurrency(self) -> None:
        event = self.read_fixture("consultation-event-valid.yaml")
        errors = validator.validate_consultation_event(event, expected_sequence=4)
        self.assertTrue(any("外部水位" in error for error in errors))

    def test_template_uses_consultation_canonicalization_and_reuse_rule(self) -> None:
        document = yaml.safe_load(
            (PLUGIN_ROOT / "contracts" / "consultation-event.template.yaml").read_text(encoding="utf-8")
        )
        contract = document["consultation_event"]
        self.assertEqual(
            "consultation-event-canonical-json-v1",
            contract["integrity"]["canonicalization"],
        )
        self.assertIn("consultation-event-canonical-json-v1", document["canonical_event_serialization"]["canonicalization"])
        self.assertIn("registry-event-canonical-json-v1", document["canonical_event_serialization"]["algorithm_reuse"])

    def test_replay_is_read_only_and_exact_duplicate_is_idempotent(self) -> None:
        event = self.read_fixture("consultation-event-valid.yaml")
        replay = validator.replay_consultation_events([event, copy.deepcopy(event)])
        self.assertTrue(replay["valid"], replay["errors"])
        self.assertEqual(1, len(replay["events"]))
        self.assertEqual(1, replay["last_sequence"])
        self.assertEqual(event["consultation_event"]["integrity"]["event_digest"], replay["last_event_digest"])

    def test_replay_rejects_same_mutation_with_different_payload(self) -> None:
        event = self.read_fixture("consultation-event-valid.yaml")
        changed = copy.deepcopy(event)
        changed["consultation_event"]["recorded_at"] = "2026-10-04T00:00:02Z"
        changed["consultation_event"]["integrity"]["event_digest"] = validator.canonical_event_digest(changed)
        replay = validator.replay_consultation_events([event, changed])
        self.assertFalse(replay["valid"])
        self.assertTrue(any("重放载荷不一致" in error for error in replay["errors"]))

    def test_qa_cannot_claim_approved_decision(self) -> None:
        event = self.read_fixture("consultation-event-valid.yaml")
        inner = event["consultation_event"]
        qa = {
            "actor_kind": "position",
            "actor_id": "pos:sample-game:qa:manager",
            "slot_id": "slot:qa",
            "role": "department_manager",
            "participation": "consulted",
        }
        inner["topology"]["participants"].insert(0, qa)
        inner["actor"] = {
            "actor_kind": "position",
            "actor_id": "pos:sample-game:qa:manager",
            "slot_id": "slot:qa",
            "position_id": "pos:sample-game:qa:manager",
            "instance_id": None,
            "role": "department_manager",
        }
        inner["governance_binding"]["approval_refs"] = ["approval:sample-game:human-1"]
        inner["authority_effect"]["decision_status"] = "approved"
        inner["authority_effect"]["required_next_gate"] = "none"
        inner["integrity"]["event_digest"] = validator.canonical_event_digest(event)
        errors = validator.validate_consultation_event(event)
        self.assertTrue(any("QA 专业验收意见" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
