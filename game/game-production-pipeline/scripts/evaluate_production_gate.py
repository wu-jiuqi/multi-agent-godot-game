#!/usr/bin/env python3
"""Verify an actual gate review against launch authority and current file evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import file_digest, load_yaml
from validate_production_charter import (
    REQUIRED_START_GATES, load_approvals, safe_path, timestamp,
    validate_production_charter,
)


def subject_digest(root: Path, reference: dict) -> str:
    path = safe_path(root, reference.get("path"))
    if reference.get("kind", "file") == "file":
        return file_digest(path)
    if reference.get("kind") == "art-direction":
        # Semantic digest excludes the review/publication receipt itself.
        from validate_art_direction_contract import art_direction_digests
        return art_direction_digests(load_yaml(path))["contract_subject_digest"]
    raise ValueError("unknown gate subject kind")


def evaluate_production_gate(document: dict, charter_document: dict, *,
                             project_root: Path, approvals: dict) -> dict:
    errors = []
    validation = validate_production_charter(charter_document, project_root=project_root,
                                              approvals=approvals)
    if not validation.get("launch_ready"):
        return {"state": "blocked", "errors": validation["errors"] + validation.get("blockers", []),
                "writes_performed": False}
    c = charter_document["production_charter"]
    d = document.get("production_gate_decision")
    if not isinstance(d, dict):
        return {"state": "blocked", "errors": ["missing production_gate_decision"], "writes_performed": False}
    if d.get("schema_version") != "game-production-gate-decision/v1":
        errors.append("unsupported gate decision schema")
    if d.get("project_id") != validation["project_id"] or d.get("charter_digest") != validation["subject_digest"]:
        errors.append("gate decision project/charter digest mismatch")
    gid = d.get("gate_id")
    policy = next((g for g in c["gates"] if g["gate_id"] == gid), None)
    if policy is None or gid in REQUIRED_START_GATES:
        return {"state": "blocked", "errors": errors + ["production review cannot replace inception decisions"],
                "writes_performed": False}
    reviewer = policy.get("delegated_reviewer")
    if policy["owner_kind"] == "human":
        # Publication may be authorized at inception for one exact destination.
        action = d.get("external_action", {})
        grant = next((g for g in c["authority"]["external_actions"]
                      if g.get("authorized") and g["action"] == action.get("action")
                      and g.get("target") == action.get("target")), None)
        if gid != "GATE-4" or grant is None:
            return {"state": "awaiting_human", "errors": errors,
                    "reason": "this decision remains reserved for the owner", "writes_performed": False}
        reviewer = grant.get("reviewer")
        from validate_production_charter import evaluate_authority
        authority = evaluate_authority(charter_document, action.get("action"),
            project_root=project_root, approvals=approvals, external=True,
            target=action.get("target"), estimated_cost=action.get("cost"),
            spent_budget=d.get("spent_budget", 0))
        if not authority["allowed"]:
            errors.append(authority["reason"])
    if not reviewer or d.get("reviewer") != reviewer:
        errors.append("decision must be recorded by the delegated reviewer")
    if not d.get("producer") or d.get("producer") == d.get("reviewer"):
        errors.append("producer cannot be its sole reviewer")
    if not timestamp(d.get("reviewed_at")):
        errors.append("review timestamp must include timezone")
    subject = d.get("subject", {})
    try:
        if not isinstance(subject, dict) or subject_digest(project_root, subject) != subject.get("digest"):
            errors.append("gate subject digest mismatch")
    except (OSError, ValueError, KeyError) as exc:
        errors.append(f"gate subject: {exc}")
    checks = d.get("checks")
    if not isinstance(checks, list):
        checks = []
        errors.append("checks must be an array")
    seen = set()
    failed = False
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("criterion_id"), str):
            errors.append("invalid criterion record")
            continue
        cid = check["criterion_id"]
        if cid in seen:
            errors.append("duplicate criterion record")
        seen.add(cid)
        if check.get("result") not in {"passed", "failed"}:
            errors.append("criterion must record passed/failed")
        failed |= check.get("result") != "passed"
        refs = check.get("evidence")
        if not isinstance(refs, list) or not refs:
            errors.append("criterion requires actual evidence files")
            continue
        for ref in refs:
            try:
                if not isinstance(ref, dict) or file_digest(safe_path(project_root, ref.get("path"))) != ref.get("sha256"):
                    errors.append("criterion evidence digest mismatch")
            except (OSError, ValueError) as exc:
                errors.append(f"criterion evidence: {exc}")
    if seen != set(policy["acceptance_refs"]):
        errors.append("gate criteria do not match the launch acceptance baseline")
    if d.get("decision") not in {"pass", "revise"}:
        errors.append("invalid review decision")
    state = "blocked" if errors else ("revise" if failed or d["decision"] == "revise" else "pass")
    return {"state": state, "errors": errors, "gate_id": gid,
            "charter_digest": validation["subject_digest"], "reviewer": reviewer,
            "writes_performed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decision", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        approvals, errors = load_approvals(root / "game-pipeline/approvals")
        result = evaluate_production_gate(load_yaml(args.decision),
            load_yaml(root / "game-pipeline/project-definition/production-charter.yaml"),
            project_root=root, approvals=approvals)
        if errors:
            result.update(state="blocked", errors=errors + result["errors"])
    except (OSError, ValueError, TypeError) as exc:
        result = {"state": "blocked", "errors": [str(exc)], "writes_performed": False}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["state"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
