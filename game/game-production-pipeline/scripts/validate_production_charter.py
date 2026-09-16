#!/usr/bin/env python3
"""Validate launch authority; approvals are evidence records, never generated here."""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline_common import APPROVAL_SCHEMA, PROJECT_ID_RE, canonical_digest, load_yaml
from validate_project_brief import validate_project_brief

CHARTER_SCHEMA = "game-production-production-charter/v1"
CANONICALIZATION = "production-charter-subject-canonical-json-v1"
REQUIRED_COVERAGE = {
    "project_goal", "player_experience", "audience", "gameplay", "content",
    "art_direction", "ui_ux", "audio", "platform_engine", "scope", "schedule",
    "budget", "team", "accessibility", "localization", "legal_rights",
    "distribution", "success_metrics", "risks",
}
REQUIRED_START_GATES = {"GATE-0", "GATE-1", "D2"}
ALL_GATES = REQUIRED_START_GATES | {"GATE-2", "GATE-3", "D4", "GATE-4"}
DELEGABLE_GATES = {"GATE-2", "GATE-3", "D4"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def number(value: Any, minimum: float = 0) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= minimum)


def timestamp(value: Any) -> bool:
    if not nonempty(value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def safe_path(root: Path, value: Any) -> Path:
    """Resolve repo-relative paths, including symlinks, without substring matching."""
    if not nonempty(value):
        raise ValueError("path must be a non-empty project-relative path")
    normalized = value.removeprefix("repo://").replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise ValueError(f"path escapes project: {value}")
    target = (root / normalized).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes project: {value}")
    return target


def production_charter_subject(document: dict[str, Any]) -> dict[str, Any]:
    charter = document.get("production_charter")
    if not isinstance(charter, dict):
        raise ValueError("missing production_charter mapping")
    subject = copy.deepcopy(charter)
    subject.pop("review", None)
    subject.pop("integrity", None)
    # Gate approval pointers are receipts, not authority policy.
    for gate in subject.get("gates", []):
        if isinstance(gate, dict):
            for key in ("status", "approval_id"):
                gate.pop(key, None)
    return subject


def production_charter_subject_digest(document: dict[str, Any]) -> str:
    return canonical_digest(production_charter_subject(document))


def load_approvals(directory: Path | None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    approvals, errors = {}, []
    if directory is None:
        return approvals, errors
    for path in sorted(directory.glob("*.yaml")):
        try:
            item = load_yaml(path).get("approval")
            if not isinstance(item, dict) or not nonempty(item.get("approval_id")):
                raise ValueError(f"invalid approval record: {path.name}")
            if item["approval_id"] in approvals:
                raise ValueError(f"duplicate approval_id: {item['approval_id']}")
            approvals[item["approval_id"]] = item
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return approvals, errors


def approval_matches(approval: Any, subject_id: str, digest: str, owner: str,
                     kind: str) -> bool:
    return (isinstance(approval, dict)
            and approval.get("schema_version") == APPROVAL_SCHEMA
            and approval.get("subject_kind") == kind
            and approval.get("subject_id") == subject_id
            and approval.get("subject_digest") == digest
            and approval.get("decision") == "approved"
            and approval.get("decided_by") == owner
            and isinstance(owner, str) and owner.startswith("human:")
            and timestamp(approval.get("decided_at"))
            and nonempty(approval.get("evidence", {}).get("source_ref"))
            if isinstance(approval, dict) and isinstance(approval.get("evidence"), dict)
            else False)


def _validate_production_charter(document: Any, *, expected_project_id: str | None = None,
                                approvals: dict | None = None,
                                project_root: Path | None = None) -> dict[str, Any]:
    errors, warnings, blockers = [], [], []
    if not isinstance(document, dict) or not isinstance(document.get("production_charter"), dict):
        return {"state": "invalid", "errors": ["missing production_charter mapping"],
                "warnings": [], "launch_ready": False}
    c = document["production_charter"]

    def mapping(value, label):
        if not isinstance(value, dict):
            errors.append(f"{label} must be a mapping")
            return {}
        return value

    def items(value, label):
        if not isinstance(value, list):
            errors.append(f"{label} must be an array")
            return []
        return value

    def strings(value, label, required=False):
        result = items(value, label)
        if (required and not result) or any(not nonempty(x) for x in result):
            errors.append(f"{label} must contain non-empty strings")
        if all(isinstance(x, str) for x in result) and len(set(result)) != len(result):
            errors.append(f"{label} contains duplicates")
        return [x for x in result if isinstance(x, str)]

    if c.get("schema_version") != CHARTER_SCHEMA:
        errors.append("unsupported charter schema")
    ident = mapping(c.get("identity"), "identity")
    pid, cid, owner = ident.get("project_id"), ident.get("charter_id"), ident.get("project_owner")
    if not isinstance(pid, str) or not PROJECT_ID_RE.fullmatch(pid):
        errors.append("invalid project_id")
    if expected_project_id is not None and pid != expected_project_id:
        errors.append("project_id mismatch")
    if not nonempty(cid) or not cid.startswith(f"charter:{pid}:"):
        errors.append("invalid charter_id")
    if not isinstance(owner, str) or not owner.startswith("human:"):
        errors.append("project_owner must be human")
    if type(ident.get("version")) is not int or ident["version"] < 1:
        errors.append("version must be a positive integer")
    if c.get("mode") not in {"autonomous-after-approval", "legacy", "manual", "supervised"}:
        errors.append("invalid production mode")
    inception = mapping(c.get("inception"), "inception")
    if inception.get("collaboration_required") is not True:
        errors.append("collaborative inception is required")
    if not REQUIRED_START_GATES.issubset(strings(inception.get("required_human_decisions"), "required_human_decisions")):
        errors.append("inception must retain GATE-0/GATE-1/D2 owner decisions")
    coverage = mapping(c.get("coverage"), "coverage")
    for key in sorted(REQUIRED_COVERAGE):
        if not nonempty(coverage.get(key)):
            errors.append(f"coverage missing {key}")
    decisions = items(c.get("decisions"), "decisions")
    if not decisions:
        blockers.append("no project decisions")
    ids = set()
    for raw in decisions:
        d = mapping(raw, "decision")
        did = d.get("decision_id")
        if not nonempty(did) or did in ids:
            errors.append("missing/duplicate decision_id")
        else:
            ids.add(did)
        if d.get("status") not in {"confirmed", "preference", "hypothesis", "unknown"}:
            errors.append("invalid decision status")
        for key in ("domain", "statement", "decision_owner"):
            if not nonempty(d.get(key)):
                errors.append(f"decision missing {key}")
        sources = strings(d.get("source_refs"), "decision.source_refs")
        if d.get("status") == "confirmed" and not sources:
            errors.append("confirmed decision requires source evidence")
        if type(d.get("blocks_start")) is not bool:
            errors.append("decision.blocks_start must be boolean")
        if d.get("blocks_start") and d.get("status") != "confirmed":
            blockers.append(f"unresolved decision: {did}")
    for raw in items(c.get("open_questions"), "open_questions"):
        q = mapping(raw, "question")
        for key in ("question_id", "question", "decision_owner"):
            if not nonempty(q.get(key)):
                errors.append(f"question missing {key}")
        if type(q.get("blocks_start")) is not bool:
            errors.append("question.blocks_start must be boolean")
        if q.get("blocks_start"):
            blockers.append(f"unresolved question: {q.get('question_id')}")
        elif q.get("resolution") != "out-of-scope":
            for key in ("experiment", "fallback", "stop_condition"):
                if not nonempty(q.get(key)):
                    errors.append(f"nonblocking experiment missing {key}")
            if not number(q.get("budget")):
                errors.append("nonblocking experiment requires finite budget")
    acceptance = mapping(c.get("acceptance"), "acceptance")
    criteria = items(acceptance.get("criteria"), "acceptance.criteria")
    criterion_ids = set()
    if not criteria:
        errors.append("at least one acceptance criterion is required")
    for raw in criteria:
        criterion = mapping(raw, "criterion")
        key = criterion.get("criterion_id")
        if not nonempty(key) or key in criterion_ids:
            errors.append("missing/duplicate criterion_id")
        else:
            criterion_ids.add(key)
        for field in ("description", "threshold"):
            if not nonempty(criterion.get(field)):
                errors.append(f"criterion missing {field}")
        strings(criterion.get("evidence"), "criterion.evidence", True)
        if criterion.get("verifier_kind") not in {"human", "independent", "domain"}:
            errors.append("invalid criterion verifier")
    authority = mapping(c.get("authority"), "authority")
    write_paths = strings(authority.get("write_paths"), "authority.write_paths", True)
    permissions = strings(authority.get("tool_permissions"), "authority.tool_permissions", True)
    if project_root is not None:
        for path in write_paths + [authority.get("workspace_root")]:
            try:
                safe_path(project_root, path)
            except ValueError as exc:
                errors.append(str(exc))
    execution = mapping(authority.get("execution"), "authority.execution")
    if execution.get("after_launch") not in {"autonomous", "manual", "supervised"}:
        errors.append("invalid after_launch mode")
    if execution.get("human_questions") != "boundary-events-only" or execution.get("batch_exceptions") is not True:
        errors.append("exceptions must be batched at authority boundaries")
    if type(execution.get("max_retries_per_task")) is not int or execution["max_retries_per_task"] < 0:
        errors.append("invalid retry budget")
    if not number(execution.get("max_total_budget")) or not nonempty(execution.get("budget_unit")):
        errors.append("finite total budget and budget unit required")
    actions = mapping(authority.get("agent_actions"), "authority.agent_actions")
    allowed = strings(actions.get("allowed"), "allowed actions")
    restricted = strings(actions.get("restricted"), "restricted actions")
    if set(allowed) & set(restricted) or "sign_human_approval" in allowed:
        errors.append("contradictory or forbidden agent authority")
    external = items(authority.get("external_actions"), "external_actions")
    for raw in external:
        entry = mapping(raw, "external action")
        if type(entry.get("authorized")) is not bool or not nonempty(entry.get("action")):
            errors.append("external action needs name and boolean authorization")
        if entry.get("authorized"):
            for field in ("scope", "target", "conditions", "reviewer"):
                if not nonempty(entry.get(field)):
                    errors.append(f"authorized external action missing {field}")
            if not number(entry.get("max_cost")) or entry.get("requires_gate") != "GATE-4":
                errors.append("external action requires cost bound and GATE-4")
    gate_map = {}
    for raw in items(c.get("gates"), "gates"):
        gate = mapping(raw, "gate")
        gid = gate.get("gate_id")
        if not isinstance(gid, str) or gid not in ALL_GATES or gid in gate_map:
            errors.append("missing/unknown/duplicate gate_id")
            continue
        gate_map[gid] = gate
        if gid in REQUIRED_START_GATES and (gate.get("owner_kind") != "human" or gate.get("required_before_start") is not True):
            errors.append(f"{gid} must retain inception human authority")
        if gate.get("owner_kind") not in {"human", "independent"}:
            errors.append("gate owner must be human or independent")
        if gate.get("owner_kind") == "independent":
            if gid not in DELEGABLE_GATES or not nonempty(gate.get("delegated_reviewer")):
                errors.append(f"invalid delegation: {gid}")
        if gid not in REQUIRED_START_GATES:
            refs = strings(gate.get("acceptance_refs"), f"{gid}.acceptance_refs", True)
            if set(refs) - criterion_ids:
                errors.append(f"{gid} references unknown acceptance criteria")
    if set(gate_map) != ALL_GATES:
        errors.append("missing required gates")
    notifications = mapping(c.get("notifications"), "notifications")
    if notifications.get("quiet_when_unchanged") is not True:
        errors.append("notifications must be quiet when unchanged")
    digest = production_charter_subject_digest(document)
    integrity = mapping(c.get("integrity"), "integrity")
    if integrity.get("canonicalization") != CANONICALIZATION or integrity.get("digest_algorithm") != "sha256":
        errors.append("invalid charter canonicalization")
    if integrity.get("subject_digest") not in (None, digest):
        errors.append("charter subject_digest mismatch")
    review = mapping(c.get("review"), "review")
    if review.get("status") not in {"draft", "in_review", "approved", "revise", "superseded"}:
        errors.append("invalid charter review status")
    approved = review.get("status") == "approved"
    if approved:
        if integrity.get("subject_digest") != digest:
            errors.append("approved charter requires exact subject_digest")
        if review.get("confirmed_by") != owner or not timestamp(review.get("confirmed_at")):
            errors.append("approved charter owner/timestamp mismatch")
        if approvals is None or not approval_matches(approvals.get(review.get("approval_id")), cid, digest, owner, "production-charter"):
            errors.append("missing matching human charter approval")
        for gid in REQUIRED_START_GATES:
            gate = gate_map.get(gid, {})
            if gate.get("status") != "approved" or approvals is None or not approval_matches(
                    approvals.get(gate.get("approval_id")), f"{cid}:{gid}", digest, owner, "inception-gate"):
                errors.append(f"missing matching inception approval: {gid}")
        # A launch cannot drift away from the exact approved project brief.
        brief_ref = mapping(c.get("brief_ref"), "brief_ref")
        if project_root is None:
            blockers.append("project_root required to verify launch baseline")
        else:
            try:
                brief = load_yaml(safe_path(project_root, brief_ref.get("path")))
                br = validate_project_brief(brief, expected_project_id=pid, approvals=approvals or {})
                if br["errors"] or brief["project_brief"]["review"]["status"] != "confirmed":
                    errors.append("launch brief is not confirmed and valid")
                if br["subject_digest"] != brief_ref.get("subject_digest"):
                    errors.append("launch brief digest mismatch")
            except (OSError, ValueError, KeyError) as exc:
                errors.append(f"launch brief: {exc}")
        if any("<" in str(value) for value in coverage.values()):
            errors.append("approved coverage contains placeholders")
        if blockers:
            errors.extend(blockers)
    else:
        blockers.append("charter not approved")
    return {"state": "invalid" if errors else "valid", "project_id": pid, "charter_id": cid,
            "subject_digest": digest, "review_status": review.get("status"),
            "launch_ready": approved and not errors and not blockers,
            "blockers": blockers, "errors": errors, "warnings": warnings}


def validate_charter(path: Path | str, *, project_root: Path | None = None,
                     approval_dir: Path | None = None,
                     expected_project_id: str | None = None) -> dict[str, Any]:
    try:
        document = load_yaml(Path(path))
        approvals, errors = load_approvals(approval_dir)
        result = validate_production_charter(document, project_root=project_root,
                    expected_project_id=expected_project_id,
                    approvals=approvals if approval_dir is not None else None)
        result["errors"][:0] = errors
        if errors:
            result.update(state="invalid", launch_ready=False)
        return result
    except (OSError, ValueError, TypeError) as exc:
        return {"state": "invalid", "launch_ready": False, "errors": [str(exc)], "warnings": []}


def evaluate_authority(document: dict, action: str, *, project_root: Path,
                       approvals: dict, path: str | None = None, spent_budget: float = 0,
                       estimated_cost: float = 0, attempt: int = 1,
                       external: bool = False, target: str | None = None) -> dict:
    result = validate_production_charter(document, project_root=project_root, approvals=approvals)
    if not result["launch_ready"]:
        return {"allowed": False, "reason": "launch_not_authorized"}
    c = document["production_charter"]
    a, execution = c["authority"], c["authority"]["execution"]
    if type(attempt) is not int or not 1 <= attempt <= execution["max_retries_per_task"] + 1:
        return {"allowed": False, "reason": "retry_limit_exceeded"}
    if not number(spent_budget) or not number(estimated_cost) or spent_budget + estimated_cost > execution["max_total_budget"]:
        return {"allowed": False, "reason": "budget_exceeded"}
    if action in a["agent_actions"]["restricted"]:
        return {"allowed": False, "reason": "restricted_action"}
    if path is not None:
        try:
            requested = safe_path(project_root, path)
            workspace = safe_path(project_root, a["workspace_root"])
            if not requested.is_relative_to(workspace) or not any(
                    requested.is_relative_to(safe_path(project_root, allowed)) for allowed in a["write_paths"]):
                raise ValueError("write outside charter")
        except ValueError:
            return {"allowed": False, "reason": "workspace_outside_charter"}
    if external:
        matches = [item for item in a["external_actions"] if item["action"] == action
                   and item["authorized"] and item.get("target") == target]
        if not matches or estimated_cost > matches[0]["max_cost"]:
            return {"allowed": False, "reason": "external_action_not_authorized"}
    elif action not in a["agent_actions"]["allowed"]:
        return {"allowed": False, "reason": "agent_action_not_allowed"}
    return {"allowed": True, "reason": "inside_charter", "charter_digest": result["subject_digest"]}


def validate_production_charter(document, **kwargs):
    try:
        return _validate_production_charter(document, **kwargs)
    except (AttributeError, TypeError, ValueError, KeyError) as exc:
        return {"state": "invalid", "errors": ["malformed contract: " + str(exc)], "warnings": [], "launch_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("charter", type=Path)
    parser.add_argument("--project-id")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--approval-dir", type=Path)
    parser.add_argument("--require-launch", action="store_true")
    args = parser.parse_args()
    result = validate_charter(args.charter, project_root=args.project_root,
                              approval_dir=args.approval_dir, expected_project_id=args.project_id)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["state"] == "valid" and (not args.require_launch or result["launch_ready"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
