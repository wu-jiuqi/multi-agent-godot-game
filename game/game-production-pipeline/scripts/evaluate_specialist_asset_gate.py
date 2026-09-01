#!/usr/bin/env python3
"""Evaluate one Specialist Asset Gate without writing approval or project state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_common import canonical_digest, load_yaml
from validate_specialist_asset_contract import (
    GATE_ORDER,
    REVIEW_FIELDS,
    asset_subject_digest,
    validate_specialist_asset_contract,
)


SCHEMA_VERSION = "game-production-specialist-asset-gate-evaluation/v1"
GATE_REVIEWS = {
    "A0": ("demand_review",),
    "A1": ("demand_review", "producer_self_check", "rights_review"),
    "A2": ("demand_review", "producer_self_check", "rights_review", "technical_review"),
    "A3": REVIEW_FIELDS,
}
GATE_ACTORS = {
    "A0": ("requester",),
    "A1": ("producer", "rights_reviewer"),
    "A2": ("producer", "technical_integrator", "rights_reviewer"),
    "A3": (
        "requester",
        "producer",
        "intent_reviewer",
        "technical_integrator",
        "qa_reviewer",
        "rights_reviewer",
    ),
}


def evaluate_specialist_asset_gate(
    document: dict[str, Any],
    gate: str,
    *,
    previous: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    if gate not in GATE_ORDER:
        raise ValueError("gate 必须是 A0、A1、A2 或 A3")
    contract = document.get("specialist_asset_contract")
    if not isinstance(contract, dict):
        raise ValueError("缺少 specialist_asset_contract 映射")
    identity = contract.get("identity") if isinstance(contract.get("identity"), dict) else {}
    responsibility = (
        contract.get("responsibility") if isinstance(contract.get("responsibility"), dict) else {}
    )
    verification = contract.get("verification") if isinstance(contract.get("verification"), dict) else {}
    validation = validate_specialist_asset_contract(
        document,
        previous=previous,
        project_root=project_root,
        target_gate=gate,
    )
    gate_result = validation.get("gate_results", {}).get(gate, {"state": "blocked", "issues": []})
    non_gate_errors = [
        error
        for error in validation.get("errors", [])
        if not any(error.startswith(f"{name}:") for name in GATE_ORDER)
    ]
    issues = list(gate_result.get("issues", []))
    required_reviews = GATE_REVIEWS[gate]
    review_statuses = {
        name: verification.get(name, {}).get("status")
        if isinstance(verification.get(name), dict)
        else None
        for name in required_reviews
    }

    if non_gate_errors:
        outcome = "blocked"
        reason = "Contract 结构、引用、摘要或文件证据无效"
    elif not issues:
        outcome = "pass"
        reason = f"{gate} 的自动检查与所需专业/人工记录均已通过"
    elif any(status in {"rejected", "stale"} for status in review_statuses.values()):
        outcome = "revise"
        reason = "所需评审被拒绝或已因 Contract 变化失效"
    else:
        review_issue_names = {
            issue.removesuffix(" 尚未批准")
            for issue in issues
            if issue.endswith(" 尚未批准")
        }
        only_pending_reviews = bool(review_issue_names) and all(
            name in required_reviews and review_statuses.get(name) == "pending"
            for name in review_issue_names
        ) and len(review_issue_names) == len(issues)
        publication = contract.get("publication") if isinstance(contract.get("publication"), dict) else {}
        publication_wait = gate == "A3" and publication.get("release_state") == "candidate" and all(
            issue in {"publication.release_state 尚未 approved", "缺少 approval_refs"}
            or issue.endswith(" 尚未批准")
            for issue in issues
        )
        if only_pending_reviews or publication_wait:
            outcome = "awaiting_human"
            reason = "机器可验证部分已满足，仍等待指定评审者或发布批准"
        elif any(issue.startswith("rights.") or "授权" in issue for issue in issues):
            outcome = "blocked"
            reason = "权利链或生产授权尚未形成可执行结论"
        else:
            outcome = "revise"
            reason = "现有产物或证据未达到本 Gate 的可观察标准"

    try:
        subject_digest = asset_subject_digest(document)
    except ValueError:
        subject_digest = None
    approval_subject = {
        "schema_version": SCHEMA_VERSION,
        "asset_id": identity.get("asset_id"),
        "revision": identity.get("revision"),
        "gate": gate,
        "contract_subject_digest": subject_digest,
        "outcome": outcome,
        "issues": issues,
    }
    return {
        **approval_subject,
        "state": outcome,
        "reason": reason,
        "approval_digest": canonical_digest(approval_subject),
        "required_review_records": list(required_reviews),
        "required_actors": {
            role: responsibility.get(role) for role in GATE_ACTORS[gate]
        },
        "gate_result": gate_result,
        "validation_errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "writes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--gate", required=True, choices=GATE_ORDER)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    try:
        document = load_yaml(args.contract)
        previous = load_yaml(args.previous) if args.previous else None
        result = evaluate_specialist_asset_gate(
            document,
            args.gate,
            previous=previous,
            project_root=args.project_root,
        )
    except (OSError, ValueError) as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "state": "blocked",
            "reason": str(exc),
            "writes_performed": False,
        }
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("state") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
