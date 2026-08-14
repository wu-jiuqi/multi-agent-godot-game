#!/usr/bin/env python3
"""Evaluate whether replay evidence may advance to a human gate review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VALID_STATUSES = {"passed", "missing", "stale", "failed", "invalid"}
HUMAN_SOURCE_KINDS = {"human_playtest", "human_observation"}
ACTION_PRIORITY = (
    "rebuild_and_rehash",
    "refresh_protocol_binding",
    "rerun_automated_checks",
    "collect_human_playtest_evidence",
    "convene_human_gate_review",
)


def load_fixture(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("回放夹具根节点必须是对象")
    return data


def evaluate_fixture(data: dict) -> dict:
    replay_id = data.get("replay_id")
    requirements = data.get("requirements")
    if not replay_id:
        raise ValueError("replay_id 不能为空")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("requirements 必须是非空列表")

    satisfied: list[str] = []
    blockers: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    warnings: list[str] = []
    actions: list[str] = []

    seen_ids: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise ValueError("每项 requirement 必须是对象")
        requirement_id = requirement.get("id")
        if not requirement_id or requirement_id in seen_ids:
            raise ValueError("requirement.id 必须存在且唯一")
        seen_ids.add(requirement_id)

        status = requirement.get("status")
        if status not in VALID_STATUSES:
            raise ValueError(f"{requirement_id} 使用了未知状态: {status}")
        if not requirement.get("required", True):
            if status != "passed":
                warnings.append(f"{requirement_id}: 可选证据未通过，不阻塞闸门")
            continue

        category = requirement.get("category")
        source_kind = requirement.get("source_kind")
        reason = requirement.get("reason", "未提供原因")

        if category == "human" and status == "passed" and source_kind not in HUMAN_SOURCE_KINDS:
            blockers.append(
                {
                    "id": requirement_id,
                    "code": "INVALID_HUMAN_SOURCE",
                    "reason": "真人条件不能由自动化、合成夹具或 Agent 推断满足",
                }
            )
            if "collect_human_playtest_evidence" not in actions:
                actions.append("collect_human_playtest_evidence")
            continue

        if status == "passed":
            satisfied.append(requirement_id)
            continue
        if status == "failed":
            failures.append(
                {"id": requirement_id, "code": "EVIDENCE_FAILED", "reason": reason}
            )
            continue

        code = {
            "missing": "EVIDENCE_MISSING",
            "stale": "EVIDENCE_STALE",
            "invalid": "EVIDENCE_INVALID",
        }[status]
        blockers.append({"id": requirement_id, "code": code, "reason": reason})
        if category == "human" and "collect_human_playtest_evidence" not in actions:
            actions.append("collect_human_playtest_evidence")
        if category == "automated" and "rerun_automated_checks" not in actions:
            actions.append("rerun_automated_checks")
        if category == "protocol" and "refresh_protocol_binding" not in actions:
            actions.append("refresh_protocol_binding")
        if category == "build" and "rebuild_and_rehash" not in actions:
            actions.append("rebuild_and_rehash")

    snapshot = data.get("source_snapshot", {})
    if isinstance(snapshot, dict) and snapshot.get("worktree_clean") is False:
        warnings.append("目标项目工作区存在未提交变更；不得覆盖或把它们计入冻结构建证据")

    if failures:
        decision = "rejected"
    elif blockers:
        decision = "blocked"
    elif data.get("human_approval_required", True):
        decision = "review_required"
        actions.append("convene_human_gate_review")
    else:
        decision = "approved"

    expected = data.get("expected_decision")
    ordered_actions = [action for action in ACTION_PRIORITY if action in actions]

    return {
        "schema_version": "0.1",
        "replay_id": replay_id,
        "gate_id": data.get("gate_id"),
        "decision": decision,
        "expected_decision": expected,
        "matches_expected": expected is None or expected == decision,
        "satisfied": satisfied,
        "blockers": blockers,
        "failures": failures,
        "warnings": warnings,
        "next_actions": ordered_actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument(
        "--require-expected",
        action="store_true",
        help="当实际判断与夹具的 expected_decision 不同时返回非零退出码",
    )
    args = parser.parse_args()

    try:
        result = evaluate_fixture(load_fixture(args.fixture))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.require_expected and not result["matches_expected"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
