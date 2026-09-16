from __future__ import annotations
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pipeline_common import file_digest, load_yaml
from evaluate_production_gate import evaluate_production_gate
from validate_art_direction_contract import art_direction_digests, validate_art_direction_contract
from production_fixtures import fixture, ref, write, approve_charter, NOW, PLUGIN


class ProductionGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.plan, self.charter, self.approvals = fixture(self.root)
        c = self.charter["production_charter"]
        policy = next(g for g in c["gates"] if g["gate_id"] == "GATE-2")
        self.document = {"production_gate_decision": {
            "schema_version": "game-production-gate-decision/v1", "project_id": "sample-game",
            "charter_digest": c["integrity"]["subject_digest"], "gate_id": "GATE-2",
            "producer": "position:sample-game:producer", "reviewer": policy["delegated_reviewer"],
            "reviewed_at": NOW, "subject": {"path": "outputs/one.txt", "kind": "file",
                                             "digest": file_digest(self.root / "outputs/one.txt")},
            "checks": [{"criterion_id": cid, "result": "passed",
                        "evidence": [ref(self.root, "evidence/review.txt")]}
                       for cid in policy["acceptance_refs"]], "decision": "pass",
        }}

    def evaluate(self):
        return evaluate_production_gate(self.document, self.charter,
                                        project_root=self.root, approvals=self.approvals)

    def test_real_independent_receipt_passes_read_only(self):
        before = copy.deepcopy(self.document)
        self.assertEqual("pass", self.evaluate()["state"])
        self.assertEqual(before, self.document)

    def test_no_self_approval_and_no_replacing_inception(self):
        d = self.document["production_gate_decision"]
        d["producer"] = d["reviewer"]
        self.assertEqual("blocked", self.evaluate()["state"])
        d["gate_id"] = "D2"
        self.assertEqual("blocked", self.evaluate()["state"])

    def test_stale_subject_evidence_charter_and_missing_criteria_block(self):
        original = copy.deepcopy(self.document)
        for field, value in [("charter_digest", "0" * 64), ("checks", [])]:
            self.document = copy.deepcopy(original)
            self.document["production_gate_decision"][field] = value
            self.assertEqual("blocked", self.evaluate()["state"])
        self.document = original
        write(self.root, "evidence/review.txt", "changed")
        self.assertEqual("blocked", self.evaluate()["state"])

    def test_failed_check_returns_revise_not_pass(self):
        self.document["production_gate_decision"]["checks"][0]["result"] = "failed"
        self.assertEqual("revise", self.evaluate()["state"])

    def test_external_release_requires_specific_launch_authority(self):
        d = self.document["production_gate_decision"]
        d["gate_id"] = "GATE-4"
        self.assertEqual("awaiting_human", self.evaluate()["state"])
        grant = {"action": "publish", "authorized": True, "scope": "one test staging build",
                 "target": "staging/example", "conditions": "all acceptance checks passed",
                 "reviewer": d["reviewer"], "max_cost": 1, "requires_gate": "GATE-4"}
        self.charter["production_charter"]["authority"]["external_actions"] = [grant]
        d["charter_digest"] = approve_charter(self.root, self.charter, self.approvals)
        d["external_action"] = {"action": "publish", "target": "staging/example", "cost": 0}
        self.assertEqual("pass", self.evaluate()["state"])
        d["external_action"]["target"] = "production/example"
        self.assertEqual("awaiting_human", self.evaluate()["state"])

    def test_delegated_art_gate_does_not_accept_missing_receipt(self):
        art = load_yaml(PLUGIN / "contracts/examples/art-direction-clockwork-garden.yaml")
        result = validate_art_direction_contract(art, project_root=self.root, target_gate="D4")
        self.assertTrue(any("gate_decision_ref" in x for x in result["gate_results"]["D4"]["issues"]))

    def test_delegated_art_gate_binds_current_semantic_subject(self):
        art = load_yaml(PLUGIN / "contracts/examples/art-direction-clockwork-garden.yaml")
        path = "game-pipeline/art-direction/contracts/example.yaml"
        write(self.root, path, art)
        d = self.document["production_gate_decision"]
        policy = next(g for g in self.charter["production_charter"]["gates"] if g["gate_id"] == "D4")
        d.update(gate_id="D4", producer=art["art_direction_contract"]["responsibility"]["owner"],
                 reviewer=policy["delegated_reviewer"])
        d["subject"] = {"path": path, "kind": "art-direction",
                        "digest": art_direction_digests(art)["contract_subject_digest"]}
        write(self.root, "evidence/d4.yaml", self.document)
        art["art_direction_contract"]["publication"]["gate_decision_ref"] = ref(self.root, "evidence/d4.yaml")
        write(self.root, path, art)
        self.assertEqual("pass", self.evaluate()["state"])
        result = validate_art_direction_contract(art, project_root=self.root, target_gate="D4")
        self.assertFalse(any("delegated D4:" in x for x in result["gate_results"]["D4"]["issues"]), result)
        # Existing physical art checks still fail; a receipt cannot waive them.
        self.assertEqual("invalid", result["state"])

    def test_agent_cannot_sign_initial_art_direction(self):
        art = load_yaml(PLUGIN / "contracts/examples/art-direction-clockwork-garden.yaml")
        art["art_direction_contract"]["verification"]["direction_approval"]["reviewer"] = "position:art-director"
        result = validate_art_direction_contract(art, target_gate="D2")
        self.assertTrue(any("human game_director" in x for x in result["errors"]))


if __name__ == "__main__":
    unittest.main()
