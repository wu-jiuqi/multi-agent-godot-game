#!/usr/bin/env python3
"""Plan the non-destructive v0.4.0-alpha.3 to v0.4.0-alpha.4 migration."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from bootstrap_game_pipeline import (
    AGENTS_START_RE,
    ASSET_AND_LOOP_READMES,
    build_managed_blocks,
    merge_managed_block,
)
from pipeline_common import (
    LOCK_SCHEMA,
    PLUGIN_ID,
    base_version,
    dump_yaml,
    framework_digest,
    load_yaml,
    manifest_version,
)


FROM_VERSION = "0.4.0-alpha.3"
TO_VERSION = "0.4.0-alpha.4"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    # Published v0.4.0-alpha.3 release.
    "16c8b7ec74a098f9382fb1aff1af95d9557f1e4c2dbbfe4dd8caa0033a544621",
    # Pre-alpha.4 main revision containing the initial Specialist Asset P0 baseline.
    "f7c7dedc3910401865f58a9902c5d84841998b62fc4c5b9cbfc24f5ee06d4e6f",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_action(project_root: Path, relative_path: str, desired_text: str) -> dict[str, Any]:
    path = project_root / relative_path
    desired_bytes = desired_text.encode("utf-8")
    current_bytes = path.read_bytes() if path.is_file() else None
    return {
        "path": relative_path,
        "action": "create" if current_bytes is None else (
            "unchanged" if current_bytes == desired_bytes else "update"
        ),
        "before_sha256": sha256(current_bytes) if current_bytes is not None else None,
        "after_sha256": sha256(desired_bytes),
    }


def read_utf8(path: Path, label: str, errors: list[str]) -> str | None:
    if not path.is_file():
        errors.append(f"缺少迁移必需文件: {label}")
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


def add_control_plane_readmes(
    project_root: Path,
    desired: dict[str, str],
    errors: list[str],
) -> None:
    for relative_path, default_content in ASSET_AND_LOOP_READMES.items():
        path = project_root / relative_path
        if path.is_file():
            existing = read_utf8(path, relative_path, errors)
            if existing is not None:
                desired[relative_path] = existing
        elif path.exists():
            errors.append(f"迁移目标不是文件: {relative_path}")
        else:
            desired[relative_path] = default_content


def build_migration_from(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
    expected_from_version: str,
    supported_from_framework_digests: set[str],
    include_control_plane_readmes: bool = True,
) -> tuple[dict[str, Any], dict[str, str]]:
    errors: list[str] = []
    conflicts: list[dict[str, str]] = []
    warnings: list[str] = []
    desired: dict[str, str] = {}
    target_version = manifest_version(source_root)
    project_id: str | None = None

    if base_version(from_version) != expected_from_version:
        errors.append(f"迁移器只支持 {expected_from_version}，收到 {from_version}")
    if base_version(target_version) != TO_VERSION:
        errors.append(f"迁移器目标必须为 {TO_VERSION}，当前为 {target_version}")
    if from_lock.get("schema_version") != LOCK_SCHEMA:
        errors.append(f"lock schema 必须为 {LOCK_SCHEMA}")
    if from_lock.get("plugin_id") != PLUGIN_ID:
        errors.append(f"plugin_id 必须为 {PLUGIN_ID}")
    if from_lock.get("compatibility_mode") != "strict":
        errors.append(f"只支持 compatibility_mode=strict 的 {expected_from_version} 项目")
    if from_lock.get("framework_digest") not in supported_from_framework_digests:
        errors.append(f"{expected_from_version} framework digest 不在已发行白名单中")

    agents_path = project_root / "AGENTS.md"
    agents_text = read_utf8(agents_path, "AGENTS.md", errors)
    project_path = project_root / "game-pipeline" / "project.yaml"
    try:
        project = load_yaml(project_path).get("game_pipeline_project", {})
        project_id = project.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            errors.append("game-pipeline/project.yaml 缺少 project_id")
            project_id = None
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    history_paths = sorted(
        (project_root / "game-pipeline" / "loops" / "registry").glob("*/event-history.yaml")
    )
    history_digests = {
        path.relative_to(project_root).as_posix(): sha256(path.read_bytes())
        for path in history_paths
        if path.is_file()
    }

    if include_control_plane_readmes:
        add_control_plane_readmes(project_root, desired, errors)
    if not errors and agents_text is not None:
        if not AGENTS_START_RE.search(agents_text):
            conflicts.append(
                {"path": "AGENTS.md", "reason": "缺少受管 managed block，拒绝改写未知文件"}
            )
        else:
            target_digest = framework_digest(source_root)
            block = build_managed_blocks(target_version, target_digest)["AGENTS.md"]
            merged_agents, merge_error = merge_managed_block(
                agents_text, block["content"], markdown=True
            )
            if merge_error:
                conflicts.append({"path": "AGENTS.md", "reason": merge_error})
            else:
                desired["AGENTS.md"] = merged_agents

            target_lock = copy.deepcopy(from_lock)
            target_lock["plugin_version"] = target_version
            target_lock["framework_digest"] = target_digest
            target_lock["locked_at"] = migration_at
            desired["game-pipeline/plugin-lock.yaml"] = dump_yaml(
                {"plugin_lock": target_lock}
            )

    ordered_paths = [
        *(ASSET_AND_LOOP_READMES if include_control_plane_readmes else ()),
        "AGENTS.md",
        "game-pipeline/plugin-lock.yaml",
    ]
    actions = [
        classify_action(project_root, path, desired[path])
        for path in ordered_paths
        if path in desired
    ]
    if any(action["path"] == "game-pipeline/plugin-lock.yaml" for action in actions):
        warnings.append("plugin lock 将在控制面文件写入并验证后最后更新")
    if include_control_plane_readmes:
        warnings.append("迁移不修改现有 Asset Contract、Snapshot、Event History、游戏内容或 UI 事实源")
    else:
        warnings.append("迁移只更新受管 AGENTS.md 区块与 plugin lock，不修改项目控制面或游戏内容")

    return (
        {
            "project_id": project_id,
            "actions": actions,
            "conflicts": conflicts,
            "errors": errors,
            "warnings": warnings,
            "history_digests_before": history_digests,
            "postconditions": [
                "逐个目标文件的写入前摘要仍与计划一致",
                *(["专业资产与 Loop Registry 控制面目录存在"] if include_control_plane_readmes else []),
                "plugin lock 状态为 normal",
                "项目实例完整校验为 normal",
                "所有 Event History 的 SHA-256 与迁移前一致",
                "迁移后再次规划返回 no_change",
            ],
        },
        desired,
    )


def build_migration(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    return build_migration_from(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=FROM_VERSION,
        supported_from_framework_digests=SUPPORTED_FROM_FRAMEWORK_DIGESTS,
    )
