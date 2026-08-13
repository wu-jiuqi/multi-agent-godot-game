from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "game" / "scripts" / "evaluate_replay_gate.py"
FIXTURE = ROOT / "game" / "tests" / "replays" / "endshift-p0a-current.json"

SPEC = importlib.util.spec_from_file_location("evaluate_replay_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ReplayGateEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_endshift_fixture_is_blocked(self) -> None:
        result = MODULE.evaluate_fixture(self.fixture)
        self.assertEqual("blocked", result["decision"])
        self.assertTrue(result["matches_expected"])
        blocker_ids = {item["id"] for item in result["blockers"]}
        self.assertIn("EVD-PROTOCOL-VERSION", blocker_ids)
        self.assertIn("EVD-HUMAN-SAMPLE", blocker_ids)
        self.assertIn("EVD-AUTO-SOLVABILITY", blocker_ids)
        self.assertEqual(
            [
                "refresh_protocol_binding",
                "rerun_automated_checks",
                "collect_human_playtest_evidence",
            ],
            result["next_actions"],
        )

    def test_complete_evidence_requires_human_review(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["expected_decision"] = "review_required"
        for item in fixture["requirements"]:
            item["status"] = "passed"
            if item["category"] == "human":
                item["source_kind"] = "human_playtest"
        result = MODULE.evaluate_fixture(fixture)
        self.assertEqual("review_required", result["decision"])
        self.assertNotEqual("approved", result["decision"])

    def test_automated_result_cannot_satisfy_human_requirement(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        for item in fixture["requirements"]:
            item["status"] = "passed"
            if item["category"] == "human":
                item["source_kind"] = "synthetic_fixture"
        result = MODULE.evaluate_fixture(fixture)
        self.assertEqual("blocked", result["decision"])
        self.assertTrue(
            any(item["code"] == "INVALID_HUMAN_SOURCE" for item in result["blockers"])
        )

    def test_failed_required_evidence_rejects_gate(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        for item in fixture["requirements"]:
            item["status"] = "passed"
            if item["category"] == "human":
                item["source_kind"] = "human_playtest"
        fixture["requirements"][0]["status"] = "failed"
        result = MODULE.evaluate_fixture(fixture)
        self.assertEqual("rejected", result["decision"])


if __name__ == "__main__":
    unittest.main()
