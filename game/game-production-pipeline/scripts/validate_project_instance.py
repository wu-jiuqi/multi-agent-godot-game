#!/usr/bin/env python3
"""Validate an initialized game-production-pipeline project without mutating it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from generate_codex_agents import build_generation_plan
from pipeline_common import (
    APPROVAL_SCHEMA,
    FACT_SOURCES_SCHEMA,
    PLUGIN_ID,
    PROJECT_SCHEMA,
    SKILL_BINDINGS_SCHEMA,
    load_yaml,
    plugin_root,
)
from validate_organization_registry import validate_change_set, validate_history
from validate_plugin_lock import evaluate_lock
from validate_project_brief import validate_project_brief
from validate_specialist_asset_contract import validate_specialist_asset_contract


BASE_REQUIRED_FILES = (
    "game-pipeline/project.yaml",
    "game-pipeline/plugin-lock.yaml",
    "game-pipeline/bindings/skill-bindings.yaml",
    "game-pipeline/bindings/fact-sources.yaml",
    "game-pipeline/organization/snapshot.yaml",
    "game-pipeline/organization/event-history.yaml",
)
CURRENT_REQUIRED_FILES = BASE_REQUIRED_FILES + ("game-pipeline/project-definition/project-brief.yaml",)


def nested_mapping(document: dict[str, Any], key: str, path: str, errors: list[str]) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        errors.append(f"{path} 缺少 {key} 映射")
        return {}
    return value


def validate_instance(project_root: Path, source_root: Path | None = None) -> dict[str, Any]:
    project_root = project_root.resolve()
    source_root = (source_root or plugin_root()).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checked: list[str] = []
    lock = evaluate_lock(project_root, source_root)
    errors.extend(lock["errors"])
    warnings.extend(lock["warnings"])
    required_files = CURRENT_REQUIRED_FILES if lock["state"] == "normal" else BASE_REQUIRED_FILES
    for relative_path in required_files:
        path = project_root / relative_path
        if not path.is_file():
            errors.append(f"缺少必需文件: {relative_path}")
        else:
            checked.append(relative_path)

    if errors and any(not (project_root / path).is_file() for path in required_files):
        return {
            "state": "blocked",
            "project_root": str(project_root),
            "plugin_lock": lock,
            "checked": checked,
            "errors": errors,
            "warnings": warnings,
        }

    if lock["state"] != "normal":
        warnings.append("插件锁不是 normal；只检查了跨版本公共基线，跳过当前版本项目简报、Registry 和 Agent 适配器校验")
        return {
            "state": lock["state"],
            "project_root": str(project_root),
            "plugin_lock": lock,
            "checked": checked,
            "errors": errors,
            "warnings": warnings,
        }

    try:
        project_doc = load_yaml(project_root / "game-pipeline" / "project.yaml")
        snapshot_doc = load_yaml(project_root / "game-pipeline" / "organization" / "snapshot.yaml")
        history_doc = load_yaml(project_root / "game-pipeline" / "organization" / "event-history.yaml")
        bindings_doc = load_yaml(project_root / "game-pipeline" / "bindings" / "skill-bindings.yaml")
        facts_doc = load_yaml(project_root / "game-pipeline" / "bindings" / "fact-sources.yaml")
        project_brief_doc = load_yaml(project_root / "game-pipeline" / "project-definition" / "project-brief.yaml")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        return {
            "state": "blocked",
            "project_root": str(project_root),
            "plugin_lock": lock,
            "checked": checked,
            "errors": errors,
            "warnings": warnings,
        }

    project = nested_mapping(project_doc, "game_pipeline_project", "project.yaml", errors)
    if project.get("schema_version") != PROJECT_SCHEMA:
        errors.append(f"project.yaml schema_version 必须为 {PROJECT_SCHEMA}")
    if project.get("plugin_id") != PLUGIN_ID:
        errors.append(f"project.yaml plugin_id 必须为 {PLUGIN_ID}")
    project_id = project.get("project_id")
    snapshot_id = snapshot_doc.get("organization_snapshot", {}).get("identity", {}).get("project_id")
    if not isinstance(project_id, str) or not project_id:
        errors.append("project.yaml 缺少 project_id")
    elif snapshot_id != project_id:
        errors.append("project.yaml 与 Organization Snapshot 的 project_id 不一致")

    errors.extend(f"Organization Registry: {message}" for message in validate_history(history_doc, snapshot_doc))

    skill_bindings = nested_mapping(bindings_doc, "skill_bindings", "skill-bindings.yaml", errors)
    if skill_bindings.get("schema_version") != SKILL_BINDINGS_SCHEMA:
        errors.append(f"Skill Binding schema 必须为 {SKILL_BINDINGS_SCHEMA}")
    if skill_bindings.get("project_id") != project_id:
        errors.append("Skill Binding project_id 不一致")
    if not isinstance(skill_bindings.get("bindings"), list):
        errors.append("Skill Binding bindings 必须是数组")

    fact_sources = nested_mapping(facts_doc, "fact_sources", "fact-sources.yaml", errors)
    if fact_sources.get("schema_version") != FACT_SOURCES_SCHEMA:
        errors.append(f"Fact Sources schema 必须为 {FACT_SOURCES_SCHEMA}")
    if fact_sources.get("project_id") != project_id:
        errors.append("Fact Sources project_id 不一致")
    if not isinstance(fact_sources.get("sources"), list):
        errors.append("Fact Sources sources 必须是数组")

    change_set_dir = project_root / "game-pipeline" / "organization" / "change-sets"
    for path in sorted(change_set_dir.glob("*.yaml")) if change_set_dir.is_dir() else []:
        try:
            change_set_doc = load_yaml(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        errors.extend(f"{path.name}: {message}" for message in validate_change_set(change_set_doc, snapshot_doc))
        checked.append(path.relative_to(project_root).as_posix())

    approvals_dir = project_root / "game-pipeline" / "approvals"
    approval_ids: set[str] = set()
    approval_records: dict[str, dict[str, Any]] = {}
    for path in sorted(approvals_dir.glob("*.yaml")) if approvals_dir.is_dir() else []:
        try:
            approval_doc = load_yaml(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        approval = nested_mapping(approval_doc, "approval", path.name, errors)
        if approval.get("schema_version") != APPROVAL_SCHEMA:
            errors.append(f"{path.name}: approval schema 必须为 {APPROVAL_SCHEMA}")
        approval_id = approval.get("approval_id")
        if not isinstance(approval_id, str) or not approval_id:
            errors.append(f"{path.name}: 缺少 approval_id")
        elif approval_id in approval_ids:
            errors.append(f"重复 approval_id: {approval_id}")
        else:
            approval_ids.add(approval_id)
            approval_records[approval_id] = approval
        if approval.get("decision") not in {"approved", "rejected", "revise"}:
            errors.append(f"{path.name}: decision 非法")
        for key in ("subject_kind", "subject_id", "subject_digest", "decided_by", "decided_at"):
            if not isinstance(approval.get(key), str) or not approval.get(key):
                errors.append(f"{path.name}: 缺少 {key}")
        checked.append(path.relative_to(project_root).as_posix())

    brief_result = validate_project_brief(
        project_brief_doc,
        expected_project_id=project_id if isinstance(project_id, str) else None,
        approvals=approval_records,
    )
    errors.extend(f"Project Brief: {message}" for message in brief_result["errors"])
    warnings.extend(f"Project Brief: {message}" for message in brief_result["warnings"])
    checked.append("game-pipeline/project-definition/project-brief.yaml")

    if lock["state"] == "normal":
        generation_plan, _ = build_generation_plan(project_root, source_root)
        errors.extend(f"Agent Adapter: {message}" for message in generation_plan["errors"])
        if generation_plan["can_apply"]:
            stale_actions = [item for item in generation_plan["actions"] if item["action"] != "unchanged"]
            if stale_actions:
                errors.append("存在缺失或过期的已批准 Codex Agent 适配器；先运行 generate_codex_agents.py --apply")
        warnings.extend(generation_plan["warnings"])
    else:
        warnings.append("插件锁不是 normal；未评估 Codex Agent 适配器新鲜度")

    asset_contract_dir = project_root / "game-pipeline" / "assets" / "contracts"
    asset_documents: list[tuple[Path, dict[str, Any]]] = []
    asset_revisions: dict[tuple[str, int], tuple[Path, dict[str, Any]]] = {}
    for path in sorted(asset_contract_dir.rglob("*.yaml")) if asset_contract_dir.is_dir() else []:
        try:
            document = load_yaml(path)
        except (OSError, ValueError) as exc:
            errors.append(f"Specialist Asset {path.name}: {exc}")
            continue
        asset_documents.append((path, document))
        identity = document.get("specialist_asset_contract", {}).get("identity", {})
        asset_id = identity.get("asset_id")
        revision = identity.get("revision")
        if isinstance(asset_id, str) and isinstance(revision, int) and not isinstance(revision, bool):
            key = (asset_id, revision)
            if key in asset_revisions:
                errors.append(f"Specialist Asset: 重复 asset_id/revision: {asset_id} r{revision}")
            else:
                asset_revisions[key] = (path, document)

    for path, document in asset_documents:
        identity = document.get("specialist_asset_contract", {}).get("identity", {})
        asset_id = identity.get("asset_id")
        revision = identity.get("revision")
        previous = None
        if isinstance(asset_id, str) and isinstance(revision, int) and revision > 1:
            previous_record = asset_revisions.get((asset_id, revision - 1))
            if previous_record is None:
                errors.append(f"Specialist Asset {path.name}: 缺少上一 revision 的 Contract")
            else:
                previous = previous_record[1]
        result = validate_specialist_asset_contract(document, previous=previous, project_root=project_root)
        errors.extend(f"Specialist Asset {path.name}: {message}" for message in result["errors"])
        warnings.extend(f"Specialist Asset {path.name}: {message}" for message in result["warnings"])
        checked.append(path.relative_to(project_root).as_posix())

    state = "blocked" if errors else lock["state"]
    return {
        "state": state,
        "project_root": str(project_root),
        "project_id": project_id,
        "plugin_lock": lock,
        "checked": sorted(set(checked)),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    args = parser.parse_args()
    result = validate_instance(args.project_root, args.plugin_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "normal" else 2


if __name__ == "__main__":
    raise SystemExit(main())
