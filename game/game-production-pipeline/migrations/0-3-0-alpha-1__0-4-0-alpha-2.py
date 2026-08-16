#!/usr/bin/env python3
"""Plan the explicit v0.3.0-alpha.1 to v0.4.0-alpha.2 project migration."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from bootstrap_game_pipeline import (
    AGENTS_START_RE,
    PROJECT_DEFINITION_README,
    build_initial_project_brief,
    build_managed_blocks,
    merge_managed_block,
)
from pipeline_common import (
    FACT_SOURCES_SCHEMA,
    LOCK_SCHEMA,
    PLUGIN_ID,
    PROJECT_ID_RE,
    PROJECT_SCHEMA,
    base_version,
    dump_yaml,
    framework_digest,
    load_yaml,
    manifest_version,
)


FROM_VERSION = "0.3.0-alpha.1"
TO_VERSION = "0.4.0-alpha.2"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    # Git tag v0.3.0-alpha.1 source tree.
    "837c74cccfc0ac36b26dffb3571dcc10fc8d88cf41032feb18e65c5c8382be45",
    # Published v0.3.0-alpha.1 ZIP source tree.
    "698775c8179127be553b46b948d1b481a890a281e81b2385c59bcdf5399a0a7c",
    # Marketplace cache-compatible v0.3.0-alpha.1 build used by existing projects.
    "04be88f71a343d0bed536d5b4ed7006778a117681cde98ded9ccd48ef144dba5",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_utf8(path: Path, label: str, errors: list[str]) -> str | None:
    if not path.is_file():
        errors.append(f"缺少 v0.3 必需文件: {label}")
        return None
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        errors.append(f"{label} 含 UTF-8 BOM；迁移拒绝隐式转码")
        return None
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        errors.append(f"{label} 不是严格 UTF-8: byte {exc.start}")
        return None


def classify_action(project_root: Path, relative_path: str, desired_text: str) -> dict[str, Any]:
    path = project_root / relative_path
    desired_bytes = desired_text.encode("utf-8")
    if path.is_file():
        current_bytes = path.read_bytes()
        action = "unchanged" if current_bytes == desired_bytes else "update"
        before_sha256: str | None = sha256(current_bytes)
    else:
        action = "create"
        before_sha256 = None
    return {
        "path": relative_path,
        "action": action,
        "before_sha256": before_sha256,
        "after_sha256": sha256(desired_bytes),
    }


def build_migration(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    return build_migration_to(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_target_version=TO_VERSION,
    )


def build_migration_to(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
    expected_target_version: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    errors: list[str] = []
    conflicts: list[dict[str, str]] = []
    warnings: list[str] = []
    desired: dict[str, str] = {}

    target_version = manifest_version(source_root)
    if base_version(from_version) != FROM_VERSION:
        errors.append(f"迁移器只支持 {FROM_VERSION}，收到 {from_version}")
    if base_version(target_version) != expected_target_version:
        errors.append(
            f"迁移器目标必须为 {expected_target_version}，当前为 {target_version}"
        )
    if from_lock.get("schema_version") != LOCK_SCHEMA:
        errors.append(f"lock schema 必须为 {LOCK_SCHEMA}")
    if from_lock.get("plugin_id") != PLUGIN_ID:
        errors.append(f"plugin_id 必须为 {PLUGIN_ID}")
    if from_lock.get("compatibility_mode") != "strict":
        errors.append("只支持 compatibility_mode=strict 的 v0.3 项目")
    from_digest = from_lock.get("framework_digest")
    if from_digest not in SUPPORTED_FROM_FRAMEWORK_DIGESTS:
        errors.append("v0.3 framework digest 不在已发行白名单中；拒绝迁移未知或损坏安装")

    project_path = project_root / "game-pipeline" / "project.yaml"
    facts_path = project_root / "game-pipeline" / "bindings" / "fact-sources.yaml"
    agents_path = project_root / "AGENTS.md"
    project_text = read_utf8(project_path, "game-pipeline/project.yaml", errors)
    facts_text = read_utf8(facts_path, "game-pipeline/bindings/fact-sources.yaml", errors)
    agents_text = read_utf8(agents_path, "AGENTS.md", errors)
    for required in (
        "game-pipeline/bindings/skill-bindings.yaml",
        "game-pipeline/organization/snapshot.yaml",
        "game-pipeline/organization/event-history.yaml",
    ):
        read_utf8(project_root / required, required, errors)

    project: dict[str, Any] = {}
    facts: dict[str, Any] = {}
    if project_text is not None:
        try:
            project = load_yaml(project_path).get("game_pipeline_project", {})
        except ValueError as exc:
            errors.append(str(exc))
    if facts_text is not None:
        try:
            facts = load_yaml(facts_path).get("fact_sources", {})
        except ValueError as exc:
            errors.append(str(exc))

    project_id = project.get("project_id")
    if project.get("schema_version") != PROJECT_SCHEMA:
        errors.append(f"project.yaml schema_version 必须为 {PROJECT_SCHEMA}")
    if project.get("plugin_id") != PLUGIN_ID:
        errors.append(f"project.yaml plugin_id 必须为 {PLUGIN_ID}")
    if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
        errors.append("project.yaml 缺少合法 project_id")
        project_id = None
    display_name = project.get("display_name")
    engine = project.get("engine")
    created_at = project.get("created_at")
    if not isinstance(display_name, str) or not display_name:
        errors.append("project.yaml 缺少 display_name")
    if not isinstance(engine, str) or not engine:
        errors.append("project.yaml 缺少 engine")
    if not isinstance(created_at, str) or not created_at:
        errors.append("project.yaml 缺少 created_at")

    sources = facts.get("sources")
    if facts.get("schema_version") != FACT_SOURCES_SCHEMA:
        errors.append(f"Fact Sources schema 必须为 {FACT_SOURCES_SCHEMA}")
    if project_id is not None and facts.get("project_id") != project_id:
        errors.append("Fact Sources project_id 不一致")
    if not isinstance(sources, list):
        errors.append("Fact Sources sources 必须是数组")
        sources = []

    owner: str | None = None
    if project_id is not None:
        identity_id = f"fact:{project_id}:project-identity"
        for item in sources:
            if isinstance(item, dict) and item.get("fact_id") == identity_id:
                if item.get("path") != "game-pipeline/project.yaml":
                    errors.append("项目身份事实源路径不是 game-pipeline/project.yaml")
                if isinstance(item.get("owner"), str) and item.get("owner"):
                    owner = item["owner"]
                break
        if owner is None:
            errors.append("无法从项目身份事实源确定项目所有者")

    if not errors and project_id is not None and owner is not None:
        brief_document = build_initial_project_brief(
            project_id,
            str(display_name),
            str(engine),
            owner,
            str(created_at),
        )
        brief_relative = "game-pipeline/project-definition/project-brief.yaml"
        brief_text = dump_yaml(brief_document)
        brief_path = project_root / brief_relative
        if brief_path.exists() and brief_path.read_bytes() != brief_text.encode("utf-8"):
            conflicts.append({"path": brief_relative, "reason": "已有项目简报不是迁移器生成的初始草案，拒绝覆盖"})
        else:
            desired[brief_relative] = brief_text

        readme_relative = "game-pipeline/project-definition/README.md"
        readme_path = project_root / readme_relative
        if readme_path.exists() and readme_path.read_bytes() != PROJECT_DEFINITION_README.encode("utf-8"):
            conflicts.append({"path": readme_relative, "reason": "已有项目文档说明由用户拥有，拒绝覆盖"})
        else:
            desired[readme_relative] = PROJECT_DEFINITION_README

        facts_document = {"fact_sources": copy.deepcopy(facts)}
        project_brief_fact = {
            "fact_id": f"fact:{project_id}:project-brief",
            "path": brief_relative,
            "owner": owner,
            "authority": "project.definition.draft",
        }
        matches = [item for item in sources if isinstance(item, dict) and item.get("fact_id") == project_brief_fact["fact_id"]]
        if matches and matches != [project_brief_fact]:
            conflicts.append({"path": "game-pipeline/bindings/fact-sources.yaml", "reason": "项目简报事实源 ID 已被不同内容占用"})
        elif not matches:
            facts_document["fact_sources"]["sources"].append(project_brief_fact)
        desired["game-pipeline/bindings/fact-sources.yaml"] = dump_yaml(facts_document)

        target_digest = framework_digest(source_root)
        if agents_text is not None:
            if not AGENTS_START_RE.search(agents_text):
                conflicts.append({"path": "AGENTS.md", "reason": "缺少 v0.3 managed block，拒绝把迁移内容附加到未知文件"})
            else:
                block = build_managed_blocks(target_version, target_digest)["AGENTS.md"]
                merged_agents, merge_error = merge_managed_block(agents_text, block["content"], markdown=True)
                if merge_error:
                    conflicts.append({"path": "AGENTS.md", "reason": merge_error})
                else:
                    desired["AGENTS.md"] = merged_agents

        target_lock = copy.deepcopy(from_lock)
        target_lock["plugin_version"] = target_version
        target_lock["framework_digest"] = target_digest
        target_lock["locked_at"] = migration_at
        desired["game-pipeline/plugin-lock.yaml"] = dump_yaml({"plugin_lock": target_lock})

    ordered_paths = [
        "game-pipeline/project-definition/project-brief.yaml",
        "game-pipeline/project-definition/README.md",
        "game-pipeline/bindings/fact-sources.yaml",
        "AGENTS.md",
        "game-pipeline/plugin-lock.yaml",
    ]
    actions = [classify_action(project_root, path, desired[path]) for path in ordered_paths if path in desired]
    if any(action["path"] == "game-pipeline/plugin-lock.yaml" for action in actions):
        warnings.append("plugin lock 将在其他文件写入并验证后最后更新")

    return (
        {
            "project_id": project_id,
            "actions": actions,
            "conflicts": conflicts,
            "errors": errors,
            "warnings": warnings,
            "postconditions": [
                "逐个目标文件的写入前摘要仍与计划一致",
                "plugin lock 状态为 normal",
                "项目实例完整校验为 normal",
                "迁移后再次规划返回 no_change",
            ],
        },
        desired,
    )
