#!/usr/bin/env python3
"""Evaluate one Art Direction Gate without writing approval or project state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_common import canonical_digest, load_yaml
from validate_art_direction_contract import (
    GATE_ORDER,
    REVIEW_BY_GATE,
    art_direction_digests,
    validate_art_direction_contract,
)


SCHEMA_VERSION = "game-production-art-direction-gate-evaluation/v1"
GATE_ACTORS = {
    "D0": ("owner", "game_designer"),
    "D1": ("owner", "game_designer"),
    "D2": ("game_director",),
    "D3": ("owner", "technical_integrator"),
    "D4": ("game_director", "qa_reviewer", "rights_reviewer"),
}


def evaluate_art_direction_gate(
    document: dict[str, Any],
    gate: str,
    *,
    previous: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    if gate not in GATE_ORDER:
        raise ValueError("gate 必须是 D0、D1、D2、D3 或 D4")
    contract = document.get("art_direction_contract")
    if not isinstance(contract, dict):
        raise ValueError("缺少 art_direction_contract 映射")
    identity = contract.get("identity") if isinstance(contract.get("identity"), dict) else {}
    responsibility = contract.get("responsibility") if isinstance(contract.get("responsibility"), dict) else {}
    verification = contract.get("verification") if isinstance(contract.get("verification"), dict) else {}
    publication = contract.get("publication") if isinstance(contract.get("publication"), dict) else {}
    result = validate_art_direction_contract(
        document,
        previous=previous,
        project_root=project_root,
        target_gate=gate,
    )
    gate_result = result.get("gate_results", {}).get(gate, {"state": "blocked", "issues": []})
    issues = list(gate_result.get("issues", []))
    non_gate_errors = [
        error for error in result.get("errors", [])
        if not any(error.startswith(f"{candidate}:") for candidate in GATE_ORDER)
    ]
    review_names = REVIEW_BY_GATE[gate]
    statuses = {
        name: verification.get(name, {}).get("status") if isinstance(verification.get(name), dict) else None
        for name in review_names
    }
    if non_gate_errors:
        state = "blocked"
        reason = "Contract 结构、阶段摘要、引用或版本链无效"
    elif not issues:
        state = "pass"
        reason = f"{gate} 的自动检查与所需评审记录均已通过"
    elif any(status in {"rejected", "stale"} for status in statuses.values()):
        state = "revise"
        reason = "所需评审已拒绝或因受控内容变化而过期"
    else:
        pending_review_issues = {
            issue.removesuffix(" 尚未批准") for issue in issues if issue.endswith(" 尚未批准")
        }
        only_pending = bool(pending_review_issues) and all(
            name in review_names and statuses.get(name) == "pending" for name in pending_review_issues
        ) and len(pending_review_issues) == len(issues)
        d4_publication_wait = gate == "D4" and publication.get("release_state") == "candidate" and all(
            issue.endswith(" 尚未批准")
            or issue in {"publication.release_state 尚未 approved", "publication.approval_refs 不能为空"}
            for issue in issues
        )
        if only_pending or d4_publication_wait:
            state = "awaiting_human"
            reason = "机器可验证部分已满足，仍等待指定的专业或人工判断"
        elif any("rights." in issue or "署名" in issue for issue in issues):
            state = "blocked"
            reason = "权利链尚未形成可生产或可发布结论"
        else:
            state = "revise"
            reason = "现有方向产物或基准证据未达到该 Gate 的可观察标准"
    if gate == "D4" and result.get("delegated_d4") and state == "awaiting_human":
        state = "revise"
        reason = "立项已委派 D4；由指定独立审核者补齐实际证据和评审记录"
    digests = art_direction_digests(document)
    approval_subject = {
        "schema_version": SCHEMA_VERSION,
        "art_direction_id": identity.get("art_direction_id"),
        "revision": identity.get("revision"),
        "gate": gate,
        "stage_digests": digests,
        "outcome": state,
        "issues": issues,
    }
    return {
        **approval_subject,
        "state": state,
        "reason": reason,
        "approval_digest": canonical_digest(approval_subject),
        "required_review_records": list(review_names),
        "required_actors": {role: responsibility.get(role) for role in GATE_ACTORS[gate]},
        "gate_result": gate_result,
        "validation_errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
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
        result = evaluate_art_direction_gate(
            load_yaml(args.contract),
            args.gate,
            previous=load_yaml(args.previous) if args.previous else None,
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
