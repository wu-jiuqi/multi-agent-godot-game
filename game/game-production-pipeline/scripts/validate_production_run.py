#!/usr/bin/env python3
"""Bind a production execution plan to the current launch, tool and cost authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import load_yaml
from validate_execution_plan import plan_body, validate_execution_plan
from validate_production_charter import (
    evaluate_authority, load_approvals, number, safe_path, validate_production_charter,
)


def validate_execution_authority(document, *, project_root: Path, approvals: dict) -> dict:
    result = validate_execution_plan(document, project_root=project_root)
    errors = list(result["errors"])
    from validate_plugin_lock import evaluate_lock
    lock = evaluate_lock(project_root)
    if lock["state"] != "normal":
        errors.append("production requires a normal current plugin lock")
    if errors:
        return {"state": "blocked", "errors": errors}
    p = plan_body(document)
    try:
        reference = p["production_charter_ref"]
        charter_path = safe_path(project_root, reference["path"])
        if charter_path != (project_root / "game-pipeline/project-definition/production-charter.yaml").resolve():
            raise ValueError("plan must use the project's current production charter")
        charter = load_yaml(charter_path)
        validation = validate_production_charter(charter, expected_project_id=p["project_id"],
                                                 project_root=project_root, approvals=approvals)
        errors.extend(validation["errors"])
        if not validation["launch_ready"]:
            errors.append("production launch is not authorized")
        if reference["subject_digest"] != validation["subject_digest"]:
            errors.append("plan references stale production charter")
        if p["status"] not in {"approved", "running", "completed", "blocked"}:
            errors.append("execution plan is not ready for production")
        c = charter["production_charter"]
        authority, execution = c["authority"], c["authority"]["execution"]
        if c["mode"] != "autonomous-after-approval" or execution["after_launch"] != "autonomous":
            errors.append("project has not enabled autonomous production")
        if p["tool_registry_ref"] != authority.get("tool_registry_ref"):
            errors.append("tool registry is outside the launch authority")
        model_key = "/".join(p["model"][key] for key in ("provider", "name", "version"))
        if model_key not in authority.get("allowed_models", []):
            errors.append("model/provider is outside the launch authority")
        allocations = execution.get("plan_budgets", {})
        if not isinstance(allocations, dict) or any(not number(x) for x in allocations.values()):
            errors.append("invalid launch plan budget allocations")
            allocations = {}
        if sum(allocations.values()) > execution["max_total_budget"]:
            errors.append("plan allocations exceed project budget")
        if p["plan_id"] not in allocations or p["budget"]["max_cost"] > allocations.get(p["plan_id"], 0):
            errors.append("plan budget exceeds its launch allocation")
        if p["budget"]["unit"] != execution["budget_unit"]:
            errors.append("plan budget unit mismatch")
        if p["retry_policy"]["max_attempts"] > execution["max_retries_per_task"] + 1:
            errors.append("plan retry limit exceeds charter")
        for tool in p["tools"]:
            if set(tool["permission_scope"]) - set(authority["tool_permissions"]):
                errors.append(f"tool permissions exceed charter: {tool['tool_id']}")
        reserved = {"change_project_direction", "sign_human_approval", "change_authority", "publish"}
        for task in p["tasks"]:
            if task["mode"] in {"decide", "takeover"} and task.get("decision_scope") in reserved:
                errors.append("task decision scope is reserved for the owner or external gate")
            for path in task["write_set"]:
                check = evaluate_authority(charter, task["authority_action"], project_root=project_root,
                    approvals=approvals, path=path, estimated_cost=task["estimated_cost"])
                if not check["allowed"]:
                    errors.append(f"{task['task_id']}: {check['reason']}")
            if task["authority_action"] not in authority["agent_actions"]["allowed"]:
                errors.append(f"task action not authorized: {task['task_id']}")
        # One durable ledger per allocated plan ID prevents a second file resetting its budget.
        candidates = []
        directory = project_root / "game-pipeline/execution/plans"
        for path in sorted(directory.glob("*.yaml")):
            other = load_yaml(path).get("execution_plan", {})
            if other.get("plan_id") == p["plan_id"]:
                candidates.append(other)
        if len(candidates) != 1 or candidates[0] != p:
            errors.append("plan must match exactly one registered execution plan file")
        for path in sorted(directory.glob("*.yaml")):
            other = load_yaml(path).get("execution_plan", {})
            if other.get("plan_id") != p["plan_id"] and other.get("evidence_store") == p["evidence_store"]:
                errors.append("execution plans cannot share an evidence ledger")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return {"state": "blocked" if errors else "ready", "errors": errors,
            "plan_digest": result.get("plan_digest")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        approvals, errors = load_approvals(args.project_root / "game-pipeline/approvals")
        result = validate_execution_authority(load_yaml(args.plan), project_root=args.project_root, approvals=approvals)
        if errors:
            result.update(state="blocked", errors=errors + result["errors"])
    except (OSError, ValueError, TypeError) as exc:
        result = {"state": "blocked", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["state"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
