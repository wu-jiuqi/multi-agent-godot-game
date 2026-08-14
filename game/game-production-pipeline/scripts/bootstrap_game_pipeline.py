#!/usr/bin/env python3
"""Plan or apply a non-destructive project instance of the game pipeline plugin."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

from pipeline_common import (
    APPROVAL_SCHEMA,
    FACT_SOURCES_SCHEMA,
    LOCK_SCHEMA,
    PLUGIN_ID,
    PROJECT_BRIEF_SCHEMA,
    PROJECT_ID_RE,
    PROJECT_SCHEMA,
    SKILL_BINDINGS_SCHEMA,
    canonical_digest,
    dump_yaml,
    ensure_within,
    file_digest,
    framework_digest,
    manifest_version,
    plugin_root,
    project_brief_subject_digest,
    stable_token,
    text_digest,
    write_new_text,
)


ORG_SCHEMA = "0.2-alpha"
MANAGED_SCHEMA = "v1"
AGENTS_START_RE = re.compile(
    r"<!-- game-production-pipeline:start schema=v1 digest=([0-9a-f]{64}) -->\n"
)
AGENTS_END = "<!-- game-production-pipeline:end -->"
IGNORE_START_RE = re.compile(
    r"# game-production-pipeline:start schema=v1 digest=([0-9a-f]{64})\n"
)
IGNORE_END = "# game-production-pipeline:end"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_timestamp(value: str) -> str:
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("--created-at 必须是 ISO 8601 时间") from exc
    return value


def binding(binding_id: str, version: str, path: Path) -> dict[str, str]:
    return {"id": binding_id, "version": version, "digest": file_digest(path)}


def canonical_event_digest(event: dict[str, Any]) -> str:
    normalized = copy.deepcopy(event)
    normalized["integrity"]["event_digest"] = None
    return canonical_digest(normalized)


def canonical_snapshot_digest(snapshot: dict[str, Any]) -> str:
    normalized = copy.deepcopy(snapshot)
    normalized["snapshot_integrity"]["snapshot_digest"] = None
    return canonical_digest(normalized)


def canonical_change_set_digest(change_set: dict[str, Any]) -> str:
    normalized = copy.deepcopy(change_set)
    normalized["integrity"]["change_set_digest"] = None
    return canonical_digest(normalized)


def decision_basis_digest(snapshot: dict[str, Any]) -> str:
    return canonical_digest(
        {
            "project_id": snapshot["identity"]["project_id"],
            "governance_bindings": snapshot["governance_bindings"],
            "formal_structure": snapshot["formal_structure"],
            "temporary_grants": snapshot["runtime"]["temporary_grants"],
            "used_identity_index": snapshot["governance"]["used_identity_index"],
            "tombstones": snapshot["governance"]["tombstones"],
        }
    )


def build_registry(project_id: str, human_id: str, created_at: str, source_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    event_token = stable_token(f"{project_id}|{created_at}|organization-initialized")
    event_id = f"evt:{event_token}"
    bindings = {
        "organization_contract": binding(
            "ORG-CONTRACT-CORE",
            ORG_SCHEMA,
            source_root / "contracts" / "organization-registry.md",
        ),
        "lifecycle_contract": binding(
            "ORG-LIFECYCLE-CORE",
            ORG_SCHEMA,
            source_root / "contracts" / "organization-lifecycle.md",
        ),
        "authority_policy": binding(
            "AUTHORITY-DELEGATION-CORE",
            ORG_SCHEMA,
            source_root / "contracts" / "authority-delegation.md",
        ),
    }
    initial = {
        "identity": {
            "project_id": project_id,
            "organization_revision": 1,
            "created_at": created_at,
            "updated_at": created_at,
        },
        "governance_bindings": bindings,
        "formal_structure": {"departments": [], "positions": []},
        "runtime": {"instances": [], "temporary_grants": []},
        "governance": {
            "used_identity_index": {
                "department_ids": [],
                "position_ids": [],
                "instance_ids": [],
                "temporary_grant_ids": [],
            },
            "tombstones": [],
            "pending_change_set_refs": [],
            "latest_applied_change_set": None,
        },
    }
    event = {
        "schema_version": ORG_SCHEMA,
        "event_id": event_id,
        "mutation_id": f"mut:{stable_token(f'{project_id}|{created_at}|bootstrap-mutation')}",
        "project_id": project_id,
        "sequence": 1,
        "event_type": "core.organization_initialized",
        "occurred_at": created_at,
        "recorded_at": created_at,
        "actor": {
            "actor_kind": "human",
            "actor_id": human_id,
            "acting_position_id": None,
            "role": "project-owner",
        },
        "authorization": {
            "authority_ref": bindings["authority_policy"],
            "approval_refs": [],
            "change_set_ref": None,
        },
        "causality": {
            "correlation_id": f"bootstrap:{project_id}:{event_token[:12]}",
            "causation_event_id": None,
            "request_id": None,
        },
        "concurrency": {
            "expected_organization_revision": 0,
            "expected_snapshot_digest": None,
            "resulting_organization_revision": 1,
        },
        "binding_snapshot": bindings,
        "payload": {"initial_organization": initial},
        "evidence_refs": [],
        "integrity": {
            "canonicalization": "registry-event-canonical-json-v1",
            "digest_algorithm": "sha256",
            "previous_event_digest": None,
            "event_digest": None,
        },
    }
    event["integrity"]["event_digest"] = canonical_event_digest(event)
    snapshot = {
        "schema_version": ORG_SCHEMA,
        **copy.deepcopy(initial),
        "event_watermark": {
            "last_event_id": event_id,
            "last_event_sequence": 1,
            "last_event_digest": event["integrity"]["event_digest"],
        },
        "snapshot_integrity": {
            "canonicalization": "organization-snapshot-canonical-json-v1",
            "digest_algorithm": "sha256",
            "snapshot_digest": None,
        },
    }
    snapshot["snapshot_integrity"]["snapshot_digest"] = canonical_snapshot_digest(snapshot)
    return {"organization_event_history": [event]}, {"organization_snapshot": snapshot}


def build_initial_change_set(project_id: str, human_id: str, created_at: str, snapshot_doc: dict[str, Any]) -> dict[str, Any]:
    snapshot = snapshot_doc["organization_snapshot"]
    token = stable_token(f"{project_id}|{created_at}|initial-organization-draft")
    change_set = {
        "schema_version": ORG_SCHEMA,
        "identity": {
            "change_set_id": f"chg:{project_id}:{token}",
            "project_id": project_id,
            "title": "建立项目初始多 Agent 编制",
            "created_at": created_at,
            "created_by": {
                "actor_kind": "human",
                "actor_id": human_id,
                "acting_position_id": None,
            },
        },
        "base": {
            "organization_revision": 1,
            "snapshot_digest": snapshot["snapshot_integrity"]["snapshot_digest"],
            "decision_basis_digest": decision_basis_digest(snapshot),
        },
        "proposal": {
            "rationale": "待项目需求分析后补充长期部门、岗位、Agent Preset 与授权边界；当前草案不创建任何 Agent。",
            "operations": [],
        },
        "impact": {
            "affected_department_ids": [],
            "affected_position_ids": [],
            "affected_grant_ids": [],
            "responsibility_coverage": ["项目管理", "项目编制设计", "后续部门责任分析"],
            "risk_level": "low",
            "reversibility": "reversible",
            "migration_refs": [],
        },
        "verification": {
            "preconditions": ["项目文档基线已由项目所有者确认", "职责覆盖与授权边界已明确"],
            "automated_checks": ["Organization Change Set 校验通过", "组织图可确定性渲染"],
            "reviewer_notes": ["这是未提交的初始草案；补全 operations 后才可进入人工审批。"],
        },
        "approval_requirement": {
            "human_approval_required": True,
            "required_approver_role": "project-owner",
            "required_authority_scope": "organization.change.apply",
            "decision_deadline": None,
        },
        "integrity": {
            "canonicalization": "organization-change-set-canonical-json-v1",
            "digest_algorithm": "sha256",
            "change_set_digest": None,
        },
    }
    change_set["integrity"]["change_set_digest"] = canonical_change_set_digest(change_set)
    return {"organization_change_set": change_set}


def build_initial_project_brief(
    project_id: str,
    project_name: str,
    engine: str,
    human_id: str,
    created_at: str,
) -> dict[str, Any]:
    source_id = f"source:{project_id}:project-identity"
    statement_specs = [
        ("project-goal", f"{project_name} 的项目目标与目标玩家体验尚待项目所有者提供。"),
        ("gameplay", "核心玩法尚待项目所有者提供。"),
        ("art-direction", "美术方向尚待项目所有者提供。"),
        ("implementation", "大致实现方案尚待项目所有者提供并标明约束强度。"),
        ("scope-constraints", "时间、成本、团队、内容量与发布约束尚待项目所有者提供。"),
    ]
    statements = [
        {
            "statement_id": f"stmt:{project_id}:{domain}",
            "domain": domain,
            "text": text,
            "status": "unknown",
            "decision_owner": human_id,
            "source_refs": [],
        }
        for domain, text in statement_specs
    ]
    platform_status = "unknown" if engine == "unknown" else "confirmed"
    statements.append(
        {
            "statement_id": f"stmt:{project_id}:platform-engine",
            "domain": "platform-engine",
            "text": "目标平台尚待确认；游戏引擎尚未识别。"
            if engine == "unknown"
            else f"游戏引擎已确认为 {engine}；目标平台尚待项目所有者确认。",
            "status": platform_status,
            "decision_owner": human_id,
            "source_refs": [] if platform_status == "unknown" else [source_id],
        }
    )
    questions = [
        {
            "question_id": f"question:{project_id}:{domain}",
            "question": f"请项目所有者确认 {domain} 的当前规划、约束或明确未知项。",
            "decision_owner": human_id,
            "blocks_staffing": True,
        }
        for domain, _ in statement_specs
    ]
    questions.append(
        {
            "question_id": f"question:{project_id}:target-platform",
            "question": "请项目所有者确认目标平台，并确认当前引擎选择是否属于已批准约束。",
            "decision_owner": human_id,
            "blocks_staffing": True,
        }
    )
    document = {
        "project_brief": {
            "schema_version": PROJECT_BRIEF_SCHEMA,
            "identity": {
                "brief_id": f"brief:{project_id}:initial",
                "project_id": project_id,
                "version": 1,
            },
            "coordination": {
                "project_owner": human_id,
                "coordinator_role_id": "AGT-DIR",
                "execution_mode": "bootstrap-workflow",
                "coordinator_position_id": None,
            },
            "sources": [
                {
                    "source_id": source_id,
                    "uri": "game-pipeline/project.yaml",
                    "version_or_digest": f"bootstrap:{created_at}",
                    "supplied_by": human_id,
                    "authority": "project.identity",
                }
            ],
            "statements": statements,
            "open_questions": questions,
            "risks": [
                {
                    "risk_id": f"risk:{project_id}:incomplete-project-brief",
                    "description": "启动资料尚不足以判断长期职责、专业边界和独立验收关系。",
                    "evidence_refs": [item["statement_id"] for item in statements if item["status"] == "unknown"],
                    "impact": "high",
                    "staffing_implication": "在项目所有者确认必要方向前禁止批准初始长期编制。",
                }
            ],
            "staffing_input": {
                "responsibility_needs": [],
                "readiness": "blocked",
                "blocker_refs": [item["question_id"] for item in questions],
            },
            "review": {
                "status": "draft",
                "approval_id": None,
                "confirmed_by": None,
                "confirmed_at": None,
            },
            "integrity": {
                "canonicalization": "project-brief-subject-canonical-json-v1",
                "digest_algorithm": "sha256",
                "subject_digest": None,
            },
        }
    }
    document["project_brief"]["integrity"]["subject_digest"] = project_brief_subject_digest(document)
    return document


def managed_block(body: str, *, markdown: bool) -> str:
    body = body.strip("\n") + "\n"
    digest = text_digest(body)
    if markdown:
        return (
            f"<!-- game-production-pipeline:start schema={MANAGED_SCHEMA} digest={digest} -->\n"
            f"{body}{AGENTS_END}\n"
        )
    return (
        f"# game-production-pipeline:start schema={MANAGED_SCHEMA} digest={digest}\n"
        f"{body}{IGNORE_END}\n"
    )


def merge_managed_block(existing: str, desired_block: str, *, markdown: bool) -> tuple[str, str | None]:
    start_re = AGENTS_START_RE if markdown else IGNORE_START_RE
    end_marker = AGENTS_END if markdown else IGNORE_END
    match = start_re.search(existing)
    if not match:
        separator = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
        return existing + separator + desired_block, None
    end_index = existing.find(end_marker, match.end())
    if end_index < 0:
        return existing, "找到起始标记但缺少结束标记"
    if start_re.search(existing, end_index + len(end_marker)):
        return existing, "存在多个托管区块"
    current_body = existing[match.end() : end_index]
    if text_digest(current_body) != match.group(1):
        return existing, "托管区块摘要不匹配，拒绝覆盖人工或损坏修改"
    block_end = end_index + len(end_marker)
    if block_end < len(existing) and existing[block_end] == "\n":
        block_end += 1
    return existing[: match.start()] + desired_block + existing[block_end:], None


def read_existing(path: Path) -> str | None:
    return path.read_text(encoding="utf-8-sig") if path.is_file() else None


def build_contents(
    project_root: Path,
    project_id: str,
    project_name: str,
    engine: str,
    human_id: str,
    created_at: str,
    source_root: Path,
) -> tuple[dict[str, str], dict[str, dict[str, Any]], list[str]]:
    history, snapshot = build_registry(project_id, human_id, created_at, source_root)
    change_set = build_initial_change_set(project_id, human_id, created_at, snapshot)
    project_brief = build_initial_project_brief(project_id, project_name, engine, human_id, created_at)
    version = manifest_version(source_root)
    digest = framework_digest(source_root)
    project_doc = {
        "game_pipeline_project": {
            "schema_version": PROJECT_SCHEMA,
            "project_id": project_id,
            "display_name": project_name,
            "engine": engine,
            "created_at": created_at,
            "plugin_id": PLUGIN_ID,
        }
    }
    lock_doc = {
        "plugin_lock": {
            "schema_version": LOCK_SCHEMA,
            "plugin_id": PLUGIN_ID,
            "plugin_version": version,
            "framework_digest": digest,
            "compatibility_mode": "strict",
            "locked_at": created_at,
        }
    }
    bindings_doc = {
        "skill_bindings": {
            "schema_version": SKILL_BINDINGS_SCHEMA,
            "project_id": project_id,
            "bindings": [],
        }
    }
    facts_doc = {
        "fact_sources": {
            "schema_version": FACT_SOURCES_SCHEMA,
            "project_id": project_id,
            "sources": [
                {
                    "fact_id": f"fact:{project_id}:project-identity",
                    "path": "game-pipeline/project.yaml",
                    "owner": human_id,
                    "authority": "project.identity",
                },
                {
                    "fact_id": f"fact:{project_id}:project-brief",
                    "path": "game-pipeline/project-definition/project-brief.yaml",
                    "owner": human_id,
                    "authority": "project.definition.draft",
                },
            ],
        }
    }
    files = {
        "game-pipeline/project.yaml": dump_yaml(project_doc),
        "game-pipeline/plugin-lock.yaml": dump_yaml(lock_doc),
        "game-pipeline/bindings/skill-bindings.yaml": dump_yaml(bindings_doc),
        "game-pipeline/bindings/fact-sources.yaml": dump_yaml(facts_doc),
        "game-pipeline/project-definition/project-brief.yaml": dump_yaml(project_brief),
        "game-pipeline/organization/snapshot.yaml": dump_yaml(snapshot),
        "game-pipeline/organization/event-history.yaml": dump_yaml(history),
        "game-pipeline/organization/change-sets/initial-organization.draft.yaml": dump_yaml(change_set),
        "game-pipeline/agents/README.md": "# 项目 Agent Presets\n\n只有经人工批准且摘要匹配的项目 Agent Preset 才能生成 `.codex/agents/*.toml`。\n",
        "game-pipeline/approvals/README.md": "# 人工审批记录\n\n审批记录必须绑定对象 ID、不可变摘要、决定者与决定时间；自动检查不能代替人工决定。\n",
        "game-pipeline/loops/README.md": "# 生产循环实例\n\n此处保存项目实际 Pipeline/Loop Contract 绑定、状态、事件与证据引用。\n",
        "game-pipeline/project-definition/README.md": "# 项目文档基线\n\n项目经理启动工作流把项目所有者已确认的方向整理到 `project-brief.yaml`。草案不得作为正式编制依据；只有摘要匹配的人工确认后才能进入组织设计。\n",
        "game-pipeline/organization/views/README.md": "# 组织视图\n\nMermaid 源文件可跟踪；生成的 SVG 仅作投影并由 `.gitignore` 忽略。\n",
        "game-pipeline/organization/validations/README.md": "# 组织校验\n\n保存可复核的校验结论与证据引用，不把自动校验结果伪装成人工审批。\n",
        ".agents/skills/README.md": "# 项目专属 Skills\n\n只保存该游戏项目特有的可执行方法；可复用框架能力仍由全局插件提供。\n",
    }
    agents_body = f"""## Game Production Pipeline

- 项目管线状态位于 `game-pipeline/`，项目专属 Skills 位于 `.agents/skills/`。
- 当前锁定插件：`{PLUGIN_ID}@{version}`，框架摘要：`{digest}`。
- 初始项目简报位于 `game-pipeline/project-definition/project-brief.yaml`；未确认前不得批准正式编制。
- 持久部门、岗位、Agent Preset 与 Skill 绑定必须先获得项目所有者人工审批。
- 临时 Agent Instance 只有在批准且未过期的 Temporary Grant 范围和额度内才可免逐实例审批，但必须先登记并保持可见。
- 管线治理审批、Codex 沙箱权限与技术验收是三个独立条件。
- 插件锁非 `normal` 时禁止修改组织和生产状态，只允许检查或迁移规划。
"""
    ignore_body = """game-pipeline/.runtime/
game-pipeline/.cache/
game-pipeline/tmp/
game-pipeline/evidence/raw-temp/
game-pipeline/organization/views/*.svg
"""
    blocks = {
        "AGENTS.md": {"content": managed_block(agents_body, markdown=True), "markdown": True},
        ".gitignore": {"content": managed_block(ignore_body, markdown=False), "markdown": False},
    }
    warnings: list[str] = []
    if engine == "unknown":
        warnings.append("未识别游戏引擎；项目已初始化，但引擎适配必须在后续确认")
    return files, blocks, warnings


def build_plan(
    project_root: Path,
    project_id: str,
    project_name: str,
    engine: str,
    human_id: str,
    created_at: str,
    source_root: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    files, blocks, warnings = build_contents(
        project_root, project_id, project_name, engine, human_id, created_at, source_root
    )
    desired: dict[str, str] = dict(files)
    actions: list[dict[str, Any]] = []
    conflicts: list[dict[str, str]] = []
    for relative_path, content in sorted(files.items()):
        target = ensure_within(project_root, project_root / relative_path)
        existing = read_existing(target)
        if existing is None:
            action = "create"
        elif existing == content:
            action = "unchanged"
        else:
            action = "conflict"
            conflicts.append({"path": relative_path, "reason": "现有文件不是本次计划内容，拒绝覆盖"})
        actions.append({"path": relative_path, "action": action, "sha256": text_digest(content)})

    for relative_path, block in sorted(blocks.items()):
        target = ensure_within(project_root, project_root / relative_path)
        existing = read_existing(target)
        if existing is None:
            merged = block["content"]
            action = "create"
        else:
            merged, error = merge_managed_block(existing, block["content"], markdown=bool(block["markdown"]))
            if error:
                action = "conflict"
                conflicts.append({"path": relative_path, "reason": error})
            elif merged == existing:
                action = "unchanged"
            elif (AGENTS_START_RE if block["markdown"] else IGNORE_START_RE).search(existing):
                action = "update_managed_block"
            else:
                action = "append_managed_block"
        desired[relative_path] = merged
        actions.append({"path": relative_path, "action": action, "sha256": text_digest(desired[relative_path])})

    approval_subject = {
        "schema_version": "game-production-bootstrap-plan/v1",
        "plugin_id": PLUGIN_ID,
        "plugin_version": manifest_version(source_root),
        "framework_digest": framework_digest(source_root),
        "project_id": project_id,
        "project_name": project_name,
        "engine": engine,
        "human_id": human_id,
        "created_at": created_at,
        "files": [{"path": item["path"], "sha256": item["sha256"]} for item in actions],
    }
    approval_digest = canonical_digest(approval_subject)
    approval_path = f"game-pipeline/approvals/bootstrap-{approval_digest[:12]}.yaml"
    plan = {
        **approval_subject,
        "actions": actions,
        "mode": "plan",
        "project_root": str(project_root),
        "approval_digest": approval_digest,
        "approval_record": approval_path,
        "conflicts": conflicts,
        "warnings": warnings,
        "can_apply": not conflicts,
    }
    return plan, desired


def atomic_replace_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.game-pipeline.tmp")
    if temp_path.exists():
        raise FileExistsError(f"临时文件已存在，拒绝覆盖: {temp_path}")
    try:
        with temp_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def apply_plan(plan: dict[str, Any], desired: dict[str, str], project_root: Path, approval_digest: str) -> dict[str, Any]:
    if not plan["can_apply"]:
        raise ValueError("计划包含冲突，不能应用")
    if approval_digest != plan["approval_digest"]:
        raise ValueError("approval_digest 与当前计划不匹配；必须重新查看并确认")
    approval_document = {
        "approval": {
            "schema_version": APPROVAL_SCHEMA,
            "approval_id": f"approval:{plan['project_id']}:bootstrap:{approval_digest[:12]}",
            "subject_kind": "bootstrap-plan",
            "subject_id": plan["project_id"],
            "subject_digest": approval_digest,
            "decision": "approved",
            "decided_by": plan["human_id"],
            "decided_at": plan["created_at"],
            "evidence": {"plugin_version": plan["plugin_version"], "framework_digest": plan["framework_digest"]},
        }
    }
    approval_path = ensure_within(project_root, project_root / plan["approval_record"])
    approval_content = dump_yaml(approval_document)
    existing_approval = read_existing(approval_path)
    if existing_approval is not None and existing_approval != approval_content:
        raise ValueError(f"审批记录冲突: {plan['approval_record']}")

    # Preflight every target before the first write so a discovered conflict cannot leave a partial bootstrap.
    for action in plan["actions"]:
        relative_path = action["path"]
        target = ensure_within(project_root, project_root / relative_path)
        current = read_existing(target)
        expected_content = desired[relative_path]
        if action["action"] == "unchanged":
            if current != expected_content:
                raise ValueError(f"计划后文件发生变化: {relative_path}")
        elif action["action"] == "create":
            if current is not None:
                raise ValueError(f"计划后路径已被创建: {relative_path}")
        elif action["action"] in {"append_managed_block", "update_managed_block"}:
            if current is None:
                raise ValueError(f"计划后路径已被删除: {relative_path}")
        else:
            raise ValueError(f"不能应用动作 {action['action']}: {relative_path}")

    applied: list[str] = []
    unchanged: list[str] = []
    for action in plan["actions"]:
        relative_path = action["path"]
        target = ensure_within(project_root, project_root / relative_path)
        expected_content = desired[relative_path]
        if action["action"] == "unchanged":
            unchanged.append(relative_path)
        elif action["action"] == "create":
            write_new_text(target, expected_content)
            applied.append(relative_path)
        else:
            atomic_replace_text(target, expected_content)
            applied.append(relative_path)

    if existing_approval is None:
        write_new_text(approval_path, approval_content)
        applied.append(plan["approval_record"])
    elif existing_approval == approval_content:
        unchanged.append(plan["approval_record"])
    return {**plan, "mode": "applied", "applied": applied, "unchanged": unchanged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--engine", default="unknown")
    parser.add_argument("--human-id", default="human:owner")
    parser.add_argument("--created-at", help="Dry-run and apply must reuse the same ISO 8601 timestamp")
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-digest")
    args = parser.parse_args()

    project_root_path = args.project_root.resolve()
    source_root = args.plugin_root.resolve()
    if not project_root_path.is_dir():
        parser.error(f"项目目录不存在: {project_root_path}")
    if not PROJECT_ID_RE.fullmatch(args.project_id):
        parser.error("--project-id 必须是小写连字符 ID")
    if args.apply and (not args.created_at or not args.approval_digest):
        parser.error("--apply 必须同时提供 --created-at 与 --approval-digest")
    created_at = validate_timestamp(args.created_at or utc_now())
    plan, desired = build_plan(
        project_root_path,
        args.project_id,
        args.project_name,
        args.engine,
        args.human_id,
        created_at,
        source_root,
    )
    if args.apply:
        try:
            result = apply_plan(plan, desired, project_root_path, args.approval_digest)
        except (OSError, ValueError) as exc:
            print(json.dumps({"mode": "blocked", "error": str(exc), "plan": plan}, ensure_ascii=False, indent=2))
            return 2
    else:
        result = plan
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("can_apply", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
