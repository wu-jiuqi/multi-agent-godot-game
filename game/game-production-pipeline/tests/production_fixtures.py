"""Synthetic project/evidence fixtures; these records never authorize a real project."""
from __future__ import annotations
import copy
from pathlib import Path
from pipeline_common import APPROVAL_SCHEMA, canonical_digest, dump_yaml, file_digest, load_yaml, project_brief_subject_digest
from validate_production_charter import production_charter_subject_digest
from validate_execution_plan import plan_digest, registry_digest
from record_execution_event import SCHEMA

PLUGIN = Path(__file__).resolve().parents[1]
NOW = "2026-09-16T08:00:00Z"


def write(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value if isinstance(value, str) else dump_yaml(value), encoding="utf-8", newline="\n")
    return target


def ref(root, path):
    return {"path": path, "sha256": file_digest(root / path)}


def approve_charter(root, charter, approvals):
    c = charter["production_charter"]
    c["review"] = {"status": "approved", "approval_id": "approval:fixture:charter",
                   "confirmed_by": "human:owner", "confirmed_at": NOW}
    c["inception"]["phase"] = "approved"
    c["inception"]["launch_blocked_until"] = []
    for gate in c["gates"]:
        if gate["required_before_start"]:
            gate.update(status="approved", approval_id="approval:fixture:" + gate["gate_id"])
    digest = production_charter_subject_digest(charter)
    c["integrity"]["subject_digest"] = digest
    subjects = [("approval:fixture:charter", c["identity"]["charter_id"], "production-charter")]
    subjects += [(g["approval_id"], c["identity"]["charter_id"] + ":" + g["gate_id"], "inception-gate")
                 for g in c["gates"] if g["required_before_start"]]
    for aid, sid, kind in subjects:
        approval = {"schema_version": APPROVAL_SCHEMA, "approval_id": aid, "subject_kind": kind,
                    "subject_id": sid, "subject_digest": digest, "decision": "approved",
                    "decided_by": "human:owner", "decided_at": NOW,
                    "evidence": {"source_ref": "fixture://explicit-owner-launch-decision"}}
        approvals[aid] = approval
        write(root, "game-pipeline/approvals/" + aid.split(":")[-1] + ".yaml", {"approval": approval})
    write(root, "game-pipeline/project-definition/production-charter.yaml", charter)
    return digest


def save_plan(root, plan):
    p = plan["execution_plan"]
    p["integrity"] = {"plan_digest": plan_digest(plan)}
    write(root, "game-pipeline/execution/plans/production.yaml", plan)


def fixture(root):
    from pipeline_common import LOCK_SCHEMA, PLUGIN_ID, framework_digest, manifest_version
    write(root, "game-pipeline/plugin-lock.yaml", {"plugin_lock": {
        "schema_version": LOCK_SCHEMA, "plugin_id": PLUGIN_ID,
        "plugin_version": manifest_version(PLUGIN), "framework_digest": framework_digest(PLUGIN),
        "locked_at": NOW}})
    brief = load_yaml(PLUGIN / "contracts/examples/sample-project-brief.yaml")
    b = brief["project_brief"]
    b["review"].update(status="confirmed", approval_id="approval:fixture:brief",
                       confirmed_by="human:owner", confirmed_at=NOW)
    bd = project_brief_subject_digest(brief)
    b["integrity"]["subject_digest"] = bd
    write(root, "game-pipeline/project-definition/project-brief.yaml", brief)
    a = {"schema_version": APPROVAL_SCHEMA, "approval_id": "approval:fixture:brief",
         "subject_kind": "project-brief", "subject_id": b["identity"]["brief_id"],
         "subject_digest": bd, "decision": "approved", "decided_by": "human:owner", "decided_at": NOW,
         "evidence": {"source_ref": "fixture://brief"}}
    approvals = {a["approval_id"]: a}
    write(root, "game-pipeline/approvals/brief.yaml", {"approval": a})
    write(root, "tools/fixture-runner.txt", "Synthetic local tool descriptor; not a real model invocation.\n")
    registry = {"tool_registry": {"schema_version": "game-production-tool-registry/v1",
        "registry_id": "tools:sample-game", "version": 1, "tools": [{
            "tool_id": "tool:fixture", "provider": "local", "name": "fixture", "version": "1",
            "capabilities": ["write-report"], "permission_scope": ["write:project"],
            "deterministic": True, "rollback": {"supported": True, "procedure_ref": "restore task snapshot"},
            "source": ref(root, "tools/fixture-runner.txt"),
        }]}}
    registry["tool_registry"]["integrity"] = {"registry_digest": registry_digest(registry)}
    write(root, "game-pipeline/execution/tools.yaml", registry)
    cdoc = load_yaml(PLUGIN / "contracts/examples/sample-production-charter.yaml")
    c = cdoc["production_charter"]
    c["brief_ref"] = {"path": "game-pipeline/project-definition/project-brief.yaml", "subject_digest": bd}
    c["authority"]["write_paths"] = ["outputs", "evidence"]
    c["authority"]["tool_registry_ref"] = ref(root, "game-pipeline/execution/tools.yaml")
    c["authority"]["allowed_models"] = ["fixture/test/1"]
    c["authority"]["execution"]["plan_budgets"] = {"plan:sample-game:production": 5}
    c["authority"]["execution"]["max_total_budget"] = 5
    c["authority"]["execution"]["budget_unit"] = "credits"
    cd = approve_charter(root, cdoc, approvals)
    write(root, "inputs/intent.md", "Fixture: produce a deterministic report.\n")
    write(root, "inputs/model.json", '{"provider":"fixture","name":"test","version":"1"}\n')
    refs = [ref(root, "inputs/intent.md")]
    task = {"task_id": "TASK-001", "title": "fixture report", "mode": "automate",
            "responsible_role": "position:sample-game:producer", "reviewer_role": "position:sample-game:qa",
            "lane_id": "main", "depends_on": [], "join": {"strategy": "all", "required_task_ids": []},
            "tool_ids": ["tool:fixture"], "write_set": ["outputs/one.txt"], "output_refs": ["outputs/one.txt"],
            "action": "produce report", "authority_action": "write_workspace", "estimated_cost": 1,
            "generated_assets": False, "asset_contract_refs": [],
            "self_check": {"required": True, "command_ref": "check:report", "max_repairs": 1}}
    plan = {"execution_plan": {"schema_version": "game-production-execution-plan/v1",
        "plan_id": "plan:sample-game:production", "project_id": "sample-game", "version": 1,
        "status": "approved", "mode": "automate",
        "production_charter_ref": {"path": "game-pipeline/project-definition/production-charter.yaml", "subject_digest": cd},
        "context": {"input_refs": refs, "context_digest": canonical_digest(refs), "captured_at": NOW},
        "model": {"provider": "fixture", "name": "test", "version": "1",
                  "source_ref": ref(root, "inputs/model.json"),
                  "source_digest": file_digest(root / "inputs/model.json")},
        "tool_registry_ref": c["authority"]["tool_registry_ref"],
        "tools": [{"tool_id": "tool:fixture", "version": "1", "capability_refs": ["write-report"],
                   "permission_scope": ["write:project"], "source_digest": file_digest(root / "tools/fixture-runner.txt")}],
        "lanes": [{"lane_id": "main", "max_parallel": 2}], "tasks": [task],
        "retry_policy": {"max_attempts": 2, "on_exhausted": "blocked"},
        "budget": {"max_cost": 5, "unit": "credits"},
        "acceptance": {"required_task_ids": ["TASK-001"]},
        "evidence_store": {"uri": "repo://game-pipeline/execution/events/production.jsonl"},
        "asset_contract_policy": {"generated_assets_require_contract": True},
    }}
    save_plan(root, plan)
    write(root, "outputs/one.txt", "synthetic produced report\n")
    write(root, "evidence/check.txt", "synthetic test passed\n")
    write(root, "evidence/review.txt", "synthetic independent review passed\n")
    return plan, cdoc, approvals


def event(plan, kind, index, *, task_id="TASK-001", attempt=1, payload=None, cost=0):
    task = next(t for t in plan["execution_plan"]["tasks"] if t["task_id"] == task_id)
    return {"schema_version": SCHEMA, "event_id": f"event:{index}",
        "plan_digest": plan_digest(plan), "task_id": task_id, "event_type": kind,
        "actor": task["reviewer_role"] if kind.startswith("review_") else task["responsible_role"],
        "attempt": attempt, "occurred_at": NOW, "cost": cost, "payload": payload or {}}


def completed_events(root, plan, *, task_id="TASK-001", attempt=1, offset=0):
    task = next(t for t in plan["execution_plan"]["tasks"] if t["task_id"] == task_id)
    outputs = [ref(root, path) for path in task["output_refs"]]
    for item in outputs:
        snapshot = f"evidence/snapshots/{item['sha256']}.bin"
        snapshot_path = root / snapshot
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes((root / item["path"]).read_bytes())
        item["snapshot_path"] = snapshot
    digest = canonical_digest(outputs)
    specs = [
        ("task_started", {}),
        ("output_recorded", {"outputs": outputs}),
        ("selfcheck_passed", {"output_digest": digest, "command_ref": task["self_check"]["command_ref"],
                             "evidence": [ref(root, "evidence/check.txt")]}),
        ("review_passed", {"output_digest": digest, "evidence": [ref(root, "evidence/review.txt")]}),
        ("task_completed", {"output_digest": digest}),
    ]
    return [event(plan, kind, offset + i + 1, task_id=task_id, attempt=attempt, payload=payload)
            for i, (kind, payload) in enumerate(specs)]
