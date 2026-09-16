from __future__ import annotations
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pipeline_common import canonical_digest
from validate_execution_plan import plan_digest, validate_execution_plan
from validate_production_run import validate_execution_authority
from record_execution_event import append_event, read_events, replay_state
from production_fixtures import fixture, completed_events, event, ref, save_plan, write


class ExecutionPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, self.charter, self.approvals = fixture(self.root)
        self.ledger = self.root / "game-pipeline/execution/events/production.jsonl"

    def append(self, value):
        return append_event(self.ledger, value, self.plan, project_root=self.root)

    def complete(self):
        result = None
        for item in completed_events(self.root, self.plan):
            result = self.append(item)
        return result["replay"]

    def test_actual_files_review_and_completion(self):
        result = validate_execution_authority(self.plan, project_root=self.root, approvals=self.approvals)
        self.assertEqual("ready", result["state"], result)
        result = self.complete()
        self.assertEqual("completed", result["state"], result)
        self.assertEqual(1, result["metrics"]["first_pass_rate"])
        self.assertEqual([], result["next_ready_tasks"])

    def test_completion_without_selfcheck_and_review_never_writes(self):
        self.append(event(self.plan, "task_started", 1))
        before = self.ledger.read_bytes()
        with self.assertRaises(ValueError):
            self.append(event(self.plan, "task_completed", 2, payload={"output_digest": "0" * 64}))
        self.assertEqual(before, self.ledger.read_bytes())

    def test_wrong_actor_cannot_supply_independent_review(self):
        events = completed_events(self.root, self.plan)
        for item in events[:3]:
            self.append(item)
        events[3]["actor"] = events[0]["actor"]
        with self.assertRaises(ValueError):
            self.append(events[3])

    def test_failure_repair_recheck_and_recovery(self):
        events = completed_events(self.root, self.plan)
        self.append(events[0])
        self.append(events[1])
        failed = copy.deepcopy(events[2])
        failed["event_type"] = "selfcheck_failed"
        failed["payload"]["reason_code"] = "CONTENT"
        self.append(failed)
        self.append(event(self.plan, "repair_requested", 4, payload={"reason_code": "CONTENT"}))
        result = replay_state(self.plan, read_events(self.ledger), project_root=self.root)
        self.assertEqual(["TASK-001"], result["next_ready_tasks"])
        write(self.root, "outputs/one.txt", "actually repaired content\n")
        for item in completed_events(self.root, self.plan, attempt=2, offset=4):
            result = self.append(item)["replay"]
        self.assertEqual("completed", result["state"], result)
        self.assertEqual(1, result["metrics"]["repair_count"])
        self.assertEqual(0, result["metrics"]["first_pass_rate"])

    def test_repair_resets_prior_selfcheck_and_review(self):
        events = completed_events(self.root, self.plan)
        for item in events[:3]:
            self.append(item)
        self.append(event(self.plan, "task_failed", 4, payload={"reason_code": "BROKEN"}))
        self.append(event(self.plan, "repair_requested", 5, payload={"reason_code": "BROKEN"}))
        self.append(event(self.plan, "task_started", 6, attempt=2))
        with self.assertRaises(ValueError):
            self.append(event(self.plan, "task_completed", 7, attempt=2,
                              payload=events[4]["payload"]))

    def test_budget_exhaustion_blocks_restart(self):
        self.append(event(self.plan, "task_started", 1))
        self.append(event(self.plan, "task_failed", 2, cost=6, payload={"reason_code": "EXPENSIVE"}))
        state = replay_state(self.plan, read_events(self.ledger), project_root=self.root)
        self.assertTrue(state["metrics"]["over_budget"])
        self.assertEqual("blocked", state["state"])
        self.append(event(self.plan, "repair_requested", 3, payload={"reason_code": "EXPENSIVE"}))
        with self.assertRaises(ValueError):
            self.append(event(self.plan, "task_started", 4, attempt=2))

    def test_duplicate_event_is_idempotent_but_changed_payload_is_rejected(self):
        value = event(self.plan, "task_started", 1)
        self.append(value)
        before = self.ledger.read_bytes()
        self.assertEqual("duplicate", self.append(value)["state"])
        self.assertEqual(before, self.ledger.read_bytes())
        value["cost"] = 1
        with self.assertRaises(ValueError):
            self.append(value)

    def test_corrupt_hash_chain_is_not_overwritten(self):
        self.append(event(self.plan, "task_started", 1))
        text = self.ledger.read_text(encoding="utf-8").replace('"cost":0', '"cost":1')
        self.ledger.write_text(text, encoding="utf-8")
        before = self.ledger.read_bytes()
        with self.assertRaises(ValueError):
            self.append(event(self.plan, "task_failed", 2, payload={"reason_code": "FAIL"}))
        self.assertEqual(before, self.ledger.read_bytes())

    def test_stale_physical_evidence_blocks_review(self):
        events = completed_events(self.root, self.plan)
        for item in events[:2]:
            self.append(item)
        write(self.root, "outputs/one.txt", "changed after production")
        with self.assertRaises(ValueError):
            self.append(events[2])

    def test_plan_drift_and_context_drift_block_resume(self):
        self.append(event(self.plan, "task_started", 1))
        write(self.root, "inputs/intent.md", "new direction")
        result = replay_state(self.plan, read_events(self.ledger), project_root=self.root)
        self.assertEqual("blocked", result["state"])

    def test_unknown_event_and_unknown_task_block(self):
        for field, value in [("event_type", "invented_pass"), ("task_id", "missing")]:
            raw = event(self.plan, "task_started", 1)
            raw[field] = value
            with self.assertRaises(ValueError):
                self.append(raw)

    def test_tool_permission_escalation_and_version_drift(self):
        for field, value in [("permission_scope", ["admin"]), ("version", "2")]:
            plan = copy.deepcopy(self.plan)
            plan["execution_plan"]["tools"][0][field] = value
            save_plan(self.root, plan)
            self.assertEqual("invalid", validate_execution_plan(plan, project_root=self.root)["state"])

    def test_generated_asset_policy_cannot_be_disabled(self):
        self.plan["execution_plan"]["asset_contract_policy"]["generated_assets_require_contract"] = False
        self.plan["execution_plan"]["tasks"][0]["generated_assets"] = True
        save_plan(self.root, self.plan)
        self.assertEqual("invalid", validate_execution_plan(self.plan)["state"])

    def test_cycles_and_unordered_same_lane_writes_rejected(self):
        task = copy.deepcopy(self.plan["execution_plan"]["tasks"][0])
        task["task_id"] = "TASK-002"
        self.plan["execution_plan"]["tasks"].append(task)
        save_plan(self.root, self.plan)
        self.assertEqual("invalid", validate_execution_plan(self.plan)["state"])
        task["depends_on"] = ["TASK-001"]
        self.plan["execution_plan"]["tasks"][0]["depends_on"] = ["TASK-002"]
        save_plan(self.root, self.plan)
        self.assertEqual("invalid", validate_execution_plan(self.plan)["state"])

    def test_lane_capacity_and_fanin_dependencies_are_real(self):
        p = self.plan["execution_plan"]
        second = copy.deepcopy(p["tasks"][0])
        second.update(task_id="TASK-002", write_set=["outputs/two.txt"], output_refs=["outputs/two.txt"])
        third = copy.deepcopy(second)
        third.update(task_id="TASK-003", write_set=["outputs/three.txt"], output_refs=["outputs/three.txt"])
        third["join"]["required_task_ids"] = ["TASK-001", "TASK-002"]
        p["tasks"] += [second, third]
        p["lanes"][0]["max_parallel"] = 1
        p["acceptance"]["required_task_ids"] = ["TASK-003"]
        save_plan(self.root, self.plan)
        self.append(event(self.plan, "task_started", 1))
        state = replay_state(self.plan, read_events(self.ledger), project_root=self.root)
        self.assertEqual([], state["next_ready_tasks"])
        with self.assertRaises(ValueError):
            self.append(event(self.plan, "task_started", 2, task_id="TASK-002"))
        with self.assertRaises(ValueError):
            self.append(event(self.plan, "task_started", 3, task_id="TASK-003"))

    def test_second_ledger_cannot_reset_budget(self):
        with self.assertRaises(ValueError):
            append_event(self.root / "another.jsonl", event(self.plan, "task_started", 1),
                         self.plan, project_root=self.root)

    def test_lock_conflict_preserves_existing_writer(self):
        self.ledger.parent.mkdir(parents=True)
        lock = self.ledger.with_suffix(".jsonl.lock")
        lock.write_text("another writer", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.append(event(self.plan, "task_started", 1))
        self.assertEqual("another writer", lock.read_text(encoding="utf-8"))


    def test_missing_plugin_lock_blocks_execution(self):
        (self.root / "game-pipeline/plugin-lock.yaml").unlink()
        with self.assertRaises(ValueError):
            self.append(event(self.plan, "task_started", 1))

    def test_model_configuration_drift_blocks_execution(self):
        write(self.root, "inputs/model.json", "changed model settings")
        self.assertEqual("invalid", validate_execution_plan(self.plan, project_root=self.root)["state"])

    def test_malformed_nested_contract_returns_invalid(self):
        for field in ["integrity", "asset_contract_policy", "acceptance"]:
            plan = copy.deepcopy(self.plan)
            plan["execution_plan"][field] = None
            self.assertEqual("invalid", validate_execution_plan(plan)["state"])

    def test_forged_asset_rights_mapping_does_not_admit_production(self):
        write(self.root, "inputs/asset.yaml", {"specialist_asset_contract": {"rights": {}}})
        task = self.plan["execution_plan"]["tasks"][0]
        task.update(generated_assets=True, asset_contract_refs=[ref(self.root, "inputs/asset.yaml")])
        save_plan(self.root, self.plan)
        self.assertEqual("invalid", validate_execution_plan(self.plan, project_root=self.root)["state"])

    def test_parallel_branches_complete_before_join_and_replay(self):
        p = self.plan["execution_plan"]
        second = copy.deepcopy(p["tasks"][0])
        second.update(task_id="TASK-002", write_set=["outputs/two.txt"], output_refs=["outputs/two.txt"])
        join = copy.deepcopy(p["tasks"][0])
        join.update(task_id="TASK-003", write_set=["outputs/three.txt"], output_refs=["outputs/three.txt"])
        join["join"]["required_task_ids"] = ["TASK-001", "TASK-002"]
        p["tasks"] += [second, join]
        p["acceptance"]["required_task_ids"] = ["TASK-003"]
        save_plan(self.root, self.plan)
        write(self.root, "outputs/two.txt", "parallel branch")
        write(self.root, "outputs/three.txt", "joined report")
        first = completed_events(self.root, self.plan)
        second_events = completed_events(self.root, self.plan, task_id="TASK-002", offset=5)
        self.append(first[0])
        self.append(second_events[0])
        for item in first[1:]:
            self.append(item)
        self.assertEqual([], replay_state(self.plan, read_events(self.ledger), project_root=self.root)["next_ready_tasks"])
        for item in second_events[1:]:
            self.append(item)
        self.assertEqual(["TASK-003"], replay_state(self.plan, read_events(self.ledger), project_root=self.root)["next_ready_tasks"])
        for item in completed_events(self.root, self.plan, task_id="TASK-003", offset=10):
            result = self.append(item)["replay"]
        self.assertEqual("completed", result["state"], result)
        self.assertEqual(3, result["metrics"]["effective_completion_count"])

    def test_historical_snapshot_tampering_blocks_replay(self):
        events = completed_events(self.root, self.plan)
        for item in events:
            self.append(item)
        snapshot = events[1]["payload"]["outputs"][0]["snapshot_path"]
        write(self.root, snapshot, "changed historical result")
        self.assertEqual("blocked", replay_state(self.plan, read_events(self.ledger), project_root=self.root)["state"])


if __name__ == "__main__":
    unittest.main()
