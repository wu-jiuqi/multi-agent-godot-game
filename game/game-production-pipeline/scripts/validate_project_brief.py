#!/usr/bin/env python3
"""Validate a staffing-ready project brief and its human confirmation boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_common import (
    APPROVAL_SCHEMA,
    PROJECT_BRIEF_SCHEMA,
    PROJECT_ID_RE,
    load_yaml,
    project_brief_subject_digest,
)


REQUIRED_DOMAINS = {
    "project-goal",
    "gameplay",
    "art-direction",
    "implementation",
    "platform-engine",
    "scope-constraints",
}
STATEMENT_STATUSES = {"confirmed", "preference", "hypothesis", "unknown"}
REVIEW_STATUSES = {"draft", "in_review", "confirmed", "revise", "superseded"}
READINESS_STATES = {"ready", "blocked"}
EXECUTION_MODES = {"bootstrap-workflow", "approved-position"}
IMPACTS = {"low", "medium", "high", "critical"}
ACCEPTANCE_OWNER_KINDS = {"human", "domain", "independent"}


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是映射")
        return {}
    return value


def list_value(value: Any, label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} 必须是数组")
        return []
    return value


def require_strings(value: Any, label: str, errors: list[str]) -> list[str]:
    items = list_value(value, label, errors)
    strings: list[str] = []
    for index, item in enumerate(items):
        if not nonempty_string(item):
            errors.append(f"{label}[{index}] 必须是非空字符串")
        else:
            strings.append(item)
    return strings


def load_approvals(directory: Path | None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    approvals: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if directory is None:
        return approvals, errors
    if not directory.is_dir():
        return approvals, [f"审批目录不存在: {directory}"]
    for path in sorted(directory.glob("*.yaml")):
        try:
            document = load_yaml(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        approval = document.get("approval")
        if not isinstance(approval, dict):
            continue
        approval_id = approval.get("approval_id")
        if nonempty_string(approval_id):
            approvals[str(approval_id)] = approval
    return approvals, errors


def validate_project_brief(
    document: dict[str, Any],
    *,
    expected_project_id: str | None = None,
    approvals: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    brief = mapping(document.get("project_brief"), "project_brief", errors)
    if brief.get("schema_version") != PROJECT_BRIEF_SCHEMA:
        errors.append(f"project_brief.schema_version 必须为 {PROJECT_BRIEF_SCHEMA}")

    identity = mapping(brief.get("identity"), "project_brief.identity", errors)
    brief_id = identity.get("brief_id")
    project_id = identity.get("project_id")
    if not nonempty_string(project_id) or not PROJECT_ID_RE.fullmatch(str(project_id)):
        errors.append("project_brief.identity.project_id 必须是小写连字符 ID")
    if expected_project_id is not None and project_id != expected_project_id:
        errors.append("项目简报 project_id 与项目实例不一致")
    if not nonempty_string(brief_id) or not str(brief_id).startswith(f"brief:{project_id}:"):
        errors.append("project_brief.identity.brief_id 必须使用 brief:<project-id>:<id>")
    version = identity.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("project_brief.identity.version 必须是正整数")

    coordination = mapping(brief.get("coordination"), "project_brief.coordination", errors)
    if not nonempty_string(coordination.get("project_owner")):
        errors.append("project_brief.coordination 缺少 project_owner")
    if coordination.get("coordinator_role_id") != "AGT-DIR":
        errors.append("项目简报必须由 AGT-DIR 项目经理职责协调")
    execution_mode = coordination.get("execution_mode")
    if execution_mode not in EXECUTION_MODES:
        errors.append(f"execution_mode 必须属于 {sorted(EXECUTION_MODES)}")
    coordinator_position_id = coordination.get("coordinator_position_id")
    if execution_mode == "bootstrap-workflow" and coordinator_position_id is not None:
        errors.append("bootstrap-workflow 不得伪造正式 coordinator_position_id")
    if execution_mode == "approved-position" and not nonempty_string(coordinator_position_id):
        errors.append("approved-position 必须登记 coordinator_position_id")

    source_ids: set[str] = set()
    for index, raw_source in enumerate(list_value(brief.get("sources"), "project_brief.sources", errors)):
        source = mapping(raw_source, f"sources[{index}]", errors)
        source_id = source.get("source_id")
        if not nonempty_string(source_id):
            errors.append(f"sources[{index}] 缺少 source_id")
        elif source_id in source_ids:
            errors.append(f"重复 source_id: {source_id}")
        else:
            source_ids.add(str(source_id))
        for key in ("uri", "version_or_digest", "supplied_by", "authority"):
            if not nonempty_string(source.get(key)):
                errors.append(f"sources[{index}] 缺少 {key}")

    statement_ids: set[str] = set()
    domains: dict[str, list[str]] = {}
    statements = list_value(brief.get("statements"), "project_brief.statements", errors)
    for index, raw_statement in enumerate(statements):
        statement = mapping(raw_statement, f"statements[{index}]", errors)
        statement_id = statement.get("statement_id")
        domain = statement.get("domain")
        status = statement.get("status")
        if not nonempty_string(statement_id):
            errors.append(f"statements[{index}] 缺少 statement_id")
        elif statement_id in statement_ids:
            errors.append(f"重复 statement_id: {statement_id}")
        else:
            statement_ids.add(str(statement_id))
        if not nonempty_string(domain):
            errors.append(f"statements[{index}] 缺少 domain")
        else:
            domains.setdefault(str(domain), []).append(str(status))
        if not nonempty_string(statement.get("text")):
            errors.append(f"statements[{index}] 缺少 text")
        if status not in STATEMENT_STATUSES:
            errors.append(f"statements[{index}].status 必须属于 {sorted(STATEMENT_STATUSES)}")
        if not nonempty_string(statement.get("decision_owner")):
            errors.append(f"statements[{index}] 缺少 decision_owner")
        refs = require_strings(statement.get("source_refs"), f"statements[{index}].source_refs", errors)
        if status != "unknown" and not refs:
            errors.append(f"statements[{index}] 的 {status} 结论必须引用事实源")
        for ref in refs:
            if ref not in source_ids:
                errors.append(f"statements[{index}] 引用了未知 source_id: {ref}")

    missing_domains = sorted(REQUIRED_DOMAINS - set(domains))
    if missing_domains:
        errors.append(f"项目简报必须显式覆盖必要领域，缺少: {', '.join(missing_domains)}")

    question_ids: set[str] = set()
    blocking_question_ids: set[str] = set()
    for index, raw_question in enumerate(
        list_value(brief.get("open_questions"), "project_brief.open_questions", errors)
    ):
        question = mapping(raw_question, f"open_questions[{index}]", errors)
        question_id = question.get("question_id")
        if not nonempty_string(question_id):
            errors.append(f"open_questions[{index}] 缺少 question_id")
        elif question_id in question_ids:
            errors.append(f"重复 question_id: {question_id}")
        else:
            question_ids.add(str(question_id))
        if not nonempty_string(question.get("question")):
            errors.append(f"open_questions[{index}] 缺少 question")
        if not nonempty_string(question.get("decision_owner")):
            errors.append(f"open_questions[{index}] 缺少 decision_owner")
        if not isinstance(question.get("blocks_staffing"), bool):
            errors.append(f"open_questions[{index}].blocks_staffing 必须是布尔值")
        elif question.get("blocks_staffing") and nonempty_string(question_id):
            blocking_question_ids.add(str(question_id))

    risk_ids: set[str] = set()
    for index, raw_risk in enumerate(list_value(brief.get("risks"), "project_brief.risks", errors)):
        risk = mapping(raw_risk, f"risks[{index}]", errors)
        risk_id = risk.get("risk_id")
        if not nonempty_string(risk_id):
            errors.append(f"risks[{index}] 缺少 risk_id")
        elif risk_id in risk_ids:
            errors.append(f"重复 risk_id: {risk_id}")
        else:
            risk_ids.add(str(risk_id))
        if not nonempty_string(risk.get("description")):
            errors.append(f"risks[{index}] 缺少 description")
        if risk.get("impact") not in IMPACTS:
            errors.append(f"risks[{index}].impact 必须属于 {sorted(IMPACTS)}")
        if not nonempty_string(risk.get("staffing_implication")):
            errors.append(f"risks[{index}] 缺少 staffing_implication")
        for ref in require_strings(risk.get("evidence_refs"), f"risks[{index}].evidence_refs", errors):
            if ref not in statement_ids:
                errors.append(f"risks[{index}] 引用了未知 statement_id: {ref}")

    staffing = mapping(brief.get("staffing_input"), "project_brief.staffing_input", errors)
    need_ids: set[str] = set()
    needs = list_value(staffing.get("responsibility_needs"), "staffing_input.responsibility_needs", errors)
    for index, raw_need in enumerate(needs):
        need = mapping(raw_need, f"responsibility_needs[{index}]", errors)
        need_id = need.get("need_id")
        if not nonempty_string(need_id):
            errors.append(f"responsibility_needs[{index}] 缺少 need_id")
        elif need_id in need_ids:
            errors.append(f"重复 need_id: {need_id}")
        else:
            need_ids.add(str(need_id))
        if not nonempty_string(need.get("responsibility")):
            errors.append(f"responsibility_needs[{index}] 缺少 responsibility")
        rationale_refs = require_strings(
            need.get("rationale_statement_refs"),
            f"responsibility_needs[{index}].rationale_statement_refs",
            errors,
        )
        if not rationale_refs:
            errors.append(f"responsibility_needs[{index}] 必须说明责任来源")
        for ref in rationale_refs:
            if ref not in statement_ids:
                errors.append(f"responsibility_needs[{index}] 引用了未知 statement_id: {ref}")
        if not require_strings(
            need.get("expected_artifacts"), f"responsibility_needs[{index}].expected_artifacts", errors
        ):
            errors.append(f"responsibility_needs[{index}] 必须列出预期产物")
        if need.get("acceptance_owner_kind") not in ACCEPTANCE_OWNER_KINDS:
            errors.append(
                f"responsibility_needs[{index}].acceptance_owner_kind 必须属于 {sorted(ACCEPTANCE_OWNER_KINDS)}"
            )

    readiness = staffing.get("readiness")
    if readiness not in READINESS_STATES:
        errors.append(f"staffing_input.readiness 必须属于 {sorted(READINESS_STATES)}")
    blocker_refs = set(require_strings(staffing.get("blocker_refs"), "staffing_input.blocker_refs", errors))
    known_blocker_refs = question_ids | risk_ids
    for ref in blocker_refs:
        if ref not in known_blocker_refs:
            errors.append(f"staffing_input 引用了未知 blocker_ref: {ref}")
    unresolved_required_domains = {
        domain for domain in REQUIRED_DOMAINS if domains.get(domain) and set(domains[domain]) == {"unknown"}
    }
    if readiness == "ready":
        if blocker_refs:
            errors.append("staffing_input.readiness=ready 时 blocker_refs 必须为空")
        if blocking_question_ids:
            errors.append("仍有 blocks_staffing=true 的问题，不能标记 staffing ready")
        if unresolved_required_domains:
            errors.append(
                "必要领域仍全部为 unknown，不能标记 staffing ready: "
                + ", ".join(sorted(unresolved_required_domains))
            )
        if not needs:
            errors.append("staffing ready 时至少需要一项 responsibility_need")
    if readiness == "blocked":
        expected_blockers = blocking_question_ids
        if expected_blockers - blocker_refs:
            errors.append("staffing blocked 时必须在 blocker_refs 列出所有阻断编制的问题")

    review = mapping(brief.get("review"), "project_brief.review", errors)
    review_status = review.get("status")
    if review_status not in REVIEW_STATUSES:
        errors.append(f"review.status 必须属于 {sorted(REVIEW_STATUSES)}")

    subject_digest: str | None = None
    if brief:
        try:
            subject_digest = project_brief_subject_digest(document)
        except ValueError as exc:
            errors.append(str(exc))
    integrity = mapping(brief.get("integrity"), "project_brief.integrity", errors)
    if integrity.get("canonicalization") != "project-brief-subject-canonical-json-v1":
        errors.append("project_brief.integrity.canonicalization 非法")
    if integrity.get("digest_algorithm") != "sha256":
        errors.append("project_brief.integrity.digest_algorithm 必须为 sha256")
    recorded_digest = integrity.get("subject_digest")
    if recorded_digest is not None and recorded_digest != subject_digest:
        errors.append("项目简报 subject_digest 与当前内容不匹配")

    if review_status == "confirmed":
        if readiness != "ready":
            errors.append("只有 staffing ready 的项目简报才能 confirmed")
        if recorded_digest != subject_digest:
            errors.append("confirmed 项目简报必须记录当前 subject_digest")
        approval_id = review.get("approval_id")
        for key in ("approval_id", "confirmed_by", "confirmed_at"):
            if not nonempty_string(review.get(key)):
                errors.append(f"confirmed 项目简报缺少 review.{key}")
        if approvals is None:
            warnings.append("未提供审批集合；没有验证 confirmed 项目简报的外部审批记录")
        elif nonempty_string(approval_id):
            approval = approvals.get(str(approval_id))
            if approval is None:
                errors.append(f"缺少项目简报审批记录: {approval_id}")
            else:
                if approval.get("schema_version") != APPROVAL_SCHEMA:
                    errors.append("项目简报审批记录 schema 非法")
                if approval.get("subject_kind") != "project-brief":
                    errors.append("项目简报审批记录 subject_kind 必须为 project-brief")
                if approval.get("subject_id") != brief_id:
                    errors.append("项目简报审批记录 subject_id 不匹配")
                if approval.get("subject_digest") != subject_digest:
                    errors.append("项目简报审批记录 subject_digest 不匹配")
                if approval.get("decision") != "approved":
                    errors.append("项目简报审批记录必须是 approved")
    elif recorded_digest is None:
        warnings.append("草案尚未记录 subject_digest；进入人工确认前必须刷新摘要")

    return {
        "state": "invalid" if errors else "valid",
        "project_id": project_id,
        "brief_id": brief_id,
        "review_status": review_status,
        "staffing_readiness": readiness,
        "subject_digest": subject_digest,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--project-id")
    parser.add_argument("--approval-dir", type=Path)
    args = parser.parse_args()
    try:
        document = load_yaml(args.brief)
    except (OSError, ValueError) as exc:
        print(json.dumps({"state": "invalid", "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2
    approvals, approval_errors = load_approvals(args.approval_dir)
    result = validate_project_brief(
        document,
        expected_project_id=args.project_id,
        approvals=approvals if args.approval_dir is not None else None,
    )
    result["errors"] = approval_errors + result["errors"]
    if result["errors"]:
        result["state"] = "invalid"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
