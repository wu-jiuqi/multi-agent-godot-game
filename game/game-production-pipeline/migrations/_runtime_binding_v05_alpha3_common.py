#!/usr/bin/env python3
"""Close Skill Binding and managed Agent Adapter dependencies for v0.5.0-alpha.3."""

from __future__ import annotations

import copy
from pathlib import Path
from types import ModuleType
from typing import Any

from generate_codex_agents import build_generation_plan, load_approvals
from pipeline_common import (
    APPROVAL_SCHEMA,
    SKILL_BINDING_CANONICALIZATION,
    SKILL_BINDING_PROPOSAL_SCHEMA,
    SKILL_BINDINGS_SCHEMA,
    directory_digest,
    dump_yaml,
    ensure_within,
    file_digest,
    load_yaml,
    manifest_version,
    skill_binding_subject_digest,
)


TO_VERSION = "0.5.0-alpha.3"
BINDINGS_PATH = "game-pipeline/bindings/skill-bindings.yaml"


def _binding_counts(root: dict[str, Any]) -> tuple[int, int, int]:
    entries = root.get("bindings", [])
    skill_ids = {
        skill.get("skill_id")
        for entry in entries
        if isinstance(entry, dict)
        for skill in entry.get("skills", [])
        if isinstance(skill, dict) and isinstance(skill.get("skill_id"), str)
    }
    return len(entries), sum(
        len(entry.get("skills", []))
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("skills"), list)
    ), len(skill_ids)


def _projected_proposal(
    existing: dict[str, Any] | None,
    project_id: str,
    root: dict[str, Any],
) -> dict[str, Any]:
    digest = skill_binding_subject_digest(root)
    preset_count, binding_count, unique_skill_count = _binding_counts(root)
    proposal = copy.deepcopy(existing) if isinstance(existing, dict) else {
        "schema_version": SKILL_BINDING_PROPOSAL_SCHEMA,
        "proposal_id": f"binding:{project_id}:approved-agent-skills",
        "digest_scope": "skill_bindings 中递归排除 approval_id 的全部字段",
        "approval_requirement": {
            "human_approval_required": True,
            "required_approver_role": "project-owner",
        },
    }
    proposal_id = proposal.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        proposal_id = f"binding:{project_id}:approved-agent-skills"
        proposal["proposal_id"] = proposal_id
    proposal.update(
        {
            "status": "approved",
            "canonicalization": SKILL_BINDING_CANONICALIZATION,
            "subject_digest": digest,
            "approval_id": f"approval:{project_id}:skill-binding:{digest[:12]}",
            "preset_count": preset_count,
            "binding_count": binding_count,
            "unique_skill_count": unique_skill_count,
        }
    )
    return proposal


def _synthetic_binding_approval(proposal: dict[str, Any], migration_at: str) -> dict[str, Any]:
    return {
        "schema_version": APPROVAL_SCHEMA,
        "approval_id": proposal["approval_id"],
        "subject_kind": "skill-binding",
        "subject_id": proposal["proposal_id"],
        "subject_digest": proposal["subject_digest"],
        "decision": "approved",
        "decided_by": "human:pending-explicit-migration-approval",
        "decided_at": migration_at,
    }


def add_runtime_binding_migration(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    details: dict[str, Any],
    desired: dict[str, str],
    base: ModuleType,
) -> tuple[dict[str, Any], dict[str, str]]:
    errors = details.setdefault("errors", [])
    conflicts = details.setdefault("conflicts", [])
    warnings = details.setdefault("warnings", [])
    project_id = details.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        errors.append("无法为 Skill Binding 迁移确定 project_id")
        return details, desired

    path = project_root / BINDINGS_PATH
    try:
        original = load_yaml(path)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        return details, desired
    projected = copy.deepcopy(original)
    root = projected.get("skill_bindings")
    if not isinstance(root, dict):
        errors.append("skill-bindings.yaml 缺少 skill_bindings 映射")
        return details, desired
    if root.get("schema_version") != SKILL_BINDINGS_SCHEMA:
        errors.append(f"Skill Binding schema 必须为 {SKILL_BINDINGS_SCHEMA}")
    if root.get("project_id") != project_id:
        errors.append("Skill Binding project_id 与项目不一致")
    entries = root.get("bindings")
    if not isinstance(entries, list):
        errors.append("skill_bindings.bindings 必须是数组")
        return details, desired

    before_digest = skill_binding_subject_digest(root) if entries else None
    changes: list[dict[str, Any]] = []
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"bindings[{entry_index}] 必须是映射")
            continue
        skills = entry.get("skills")
        if not isinstance(skills, list):
            errors.append(f"bindings[{entry_index}].skills 必须是数组")
            continue
        for skill_index, skill in enumerate(skills):
            if not isinstance(skill, dict) or skill.get("source") != "plugin":
                continue
            relative_path = skill.get("path")
            if not isinstance(relative_path, str) or not relative_path:
                errors.append(f"bindings[{entry_index}].skills[{skill_index}] 缺少 path")
                continue
            try:
                skill_path = ensure_within(source_root, source_root / relative_path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if not skill_path.exists():
                errors.append(f"插件 Skill 路径不存在: {relative_path}")
                continue
            actual_digest = directory_digest(skill_path) if skill_path.is_dir() else file_digest(skill_path)
            previous_digest = skill.get("digest")
            if previous_digest != actual_digest:
                changes.append(
                    {
                        "preset_id": entry.get("preset_id"),
                        "skill_id": skill.get("skill_id"),
                        "path": relative_path,
                        "before_digest": previous_digest,
                        "after_digest": actual_digest,
                    }
                )
                skill["digest"] = actual_digest

    approvals = load_approvals(project_root)
    binding_approval: dict[str, Any] = {"required": False}
    if entries:
        existing_proposal = original.get("skill_binding_proposal")
        projected_proposal = _projected_proposal(
            existing_proposal if isinstance(existing_proposal, dict) else None,
            project_id,
            root,
        )
        after_digest = projected_proposal["subject_digest"]
        existing_approval_id = existing_proposal.get("approval_id") if isinstance(existing_proposal, dict) else None
        existing_approval = approvals.get(existing_approval_id) if isinstance(existing_approval_id, str) else None
        approval_still_valid = bool(
            isinstance(existing_proposal, dict)
            and existing_proposal.get("status") == "approved"
            and existing_proposal.get("canonicalization") == SKILL_BINDING_CANONICALIZATION
            and existing_proposal.get("subject_digest") == after_digest
            and isinstance(existing_approval, dict)
            and existing_approval.get("subject_kind") == "skill-binding"
            and existing_approval.get("subject_id") == projected_proposal["proposal_id"]
            and existing_approval.get("subject_digest") == after_digest
            and existing_approval.get("decision") == "approved"
        )
        if not approval_still_valid:
            projected["skill_binding_proposal"] = projected_proposal
            synthetic = _synthetic_binding_approval(projected_proposal, migration_at)
            approvals[projected_proposal["approval_id"]] = synthetic
            binding_approval = {
                "required": True,
                "subject_kind": "skill-binding",
                "subject_id": projected_proposal["proposal_id"],
                "before_subject_digest": before_digest,
                "subject_digest": after_digest,
                "approval_id": projected_proposal["approval_id"],
                "approval_record": f"game-pipeline/approvals/skill-binding-{after_digest[:12]}.yaml",
                "canonicalization": SKILL_BINDING_CANONICALIZATION,
                "changes": changes,
            }
        else:
            projected["skill_binding_proposal"] = copy.deepcopy(existing_proposal)
            binding_approval.update(
                {
                    "subject_id": projected_proposal["proposal_id"],
                    "subject_digest": after_digest,
                    "approval_id": existing_approval_id,
                    "changes": changes,
                }
            )
    elif changes:
        errors.append("空 Skill Binding 不应产生插件 Skill 摘要变更")

    if projected != original:
        desired[BINDINGS_PATH] = dump_yaml(projected)

    generation_plan, adapter_desired = build_generation_plan(
        project_root,
        source_root,
        bindings_document=projected,
        approvals_override=approvals,
        lock_state_override="normal",
        plugin_version_override=manifest_version(source_root),
    )
    for message in generation_plan["errors"]:
        errors.append(f"Agent Adapter 迁移: {message}")
    warnings.extend(generation_plan["warnings"])
    adapter_paths: list[str] = []
    for action in generation_plan["actions"]:
        relative_path = action["path"]
        if action["action"] == "conflict":
            conflicts.append({"path": relative_path, "reason": "现有 Codex Agent 不受插件托管"})
            continue
        adapter_paths.append(relative_path)
        desired[relative_path] = adapter_desired[relative_path]

    previous_paths = [
        item["path"]
        for item in details.get("actions", [])
        if item["path"] not in {"AGENTS.md", "game-pipeline/plugin-lock.yaml"}
    ]
    ordered_paths = [
        *previous_paths,
        *([BINDINGS_PATH] if BINDINGS_PATH in desired else []),
        *adapter_paths,
        "AGENTS.md",
        "game-pipeline/plugin-lock.yaml",
    ]
    details["actions"] = [
        base.classify_action(project_root, relative_path, desired[relative_path])
        for relative_path in dict.fromkeys(ordered_paths)
        if relative_path in desired
    ]
    details["skill_binding_approval"] = binding_approval
    details["skill_binding_changes"] = changes
    details["agent_adapter_actions"] = [
        item for item in details["actions"] if item["path"].startswith(".codex/agents/")
    ]
    warnings.append(
        "所有插件 Skill 摘要、Skill Binding 独立审批和托管 Agent Adapter 均纳入同一迁移事务"
    )
    details["postconditions"] = [
        *details.get("postconditions", []),
        "非空 Skill Binding 的提案摘要与独立人工审批记录一致",
        "所有已批准 Agent Preset 的托管 Codex Agent Adapter 均为当前生成器版本",
    ]
    return details, desired


def build_from_alpha(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
    expected_from_version: str,
    supported_digests: set[str],
    art_common: ModuleType,
    expected_to_version: str = TO_VERSION,
) -> tuple[dict[str, Any], dict[str, str]]:
    details, desired = art_common.build_from_alpha(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=expected_from_version,
        supported_digests=supported_digests,
        expected_to_version=expected_to_version,
    )
    base = art_common.load_module(
        Path(__file__).with_name("0-4-0-alpha-3__0-4-0-alpha-4.py"),
        f"_game_pipeline_alpha3_runtime_base_{expected_from_version.replace('.', '_').replace('-', '_')}",
    )
    return add_runtime_binding_migration(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        details=details,
        desired=desired,
        base=base,
    )


def build_metadata_from_alpha(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
    expected_from_version: str,
    supported_digests: set[str],
    art_common: ModuleType,
    expected_to_version: str = TO_VERSION,
) -> tuple[dict[str, Any], dict[str, str]]:
    base = art_common.load_module(
        Path(__file__).with_name("0-4-0-alpha-3__0-4-0-alpha-4.py"),
        f"_game_pipeline_alpha3_metadata_base_{expected_from_version.replace('.', '_').replace('-', '_')}",
    )
    base.TO_VERSION = expected_to_version
    details, desired = base.build_migration_from(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=expected_from_version,
        supported_from_framework_digests=supported_digests,
        include_control_plane_readmes=False,
    )
    return add_runtime_binding_migration(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        details=details,
        desired=desired,
        base=base,
    )


def build_from_v03(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
    art_common: ModuleType,
    expected_to_version: str = TO_VERSION,
) -> tuple[dict[str, Any], dict[str, str]]:
    details, desired = art_common.build_from_v03(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_to_version=expected_to_version,
    )
    base = art_common.load_module(
        Path(__file__).with_name("0-4-0-alpha-3__0-4-0-alpha-4.py"),
        "_game_pipeline_alpha3_runtime_base_v03",
    )
    return add_runtime_binding_migration(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        details=details,
        desired=desired,
        base=base,
    )
