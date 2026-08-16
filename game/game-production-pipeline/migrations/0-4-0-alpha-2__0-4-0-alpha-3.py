#!/usr/bin/env python3
"""Plan the non-destructive v0.4.0-alpha.2 to v0.4.0-alpha.3 migration."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from bootstrap_game_pipeline import AGENTS_START_RE, build_managed_blocks, merge_managed_block
from pipeline_common import (
    LOCK_SCHEMA,
    PLUGIN_ID,
    base_version,
    dump_yaml,
    framework_digest,
    load_yaml,
    manifest_version,
)


FROM_VERSION = "0.4.0-alpha.2"
TO_VERSION = "0.4.0-alpha.3"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    "3589bce5cf4388f91a08f12acb5d90679256191d5085e65687d06a635bbdcd32",
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


def build_migration(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    errors: list[str] = []
    conflicts: list[dict[str, str]] = []
    warnings: list[str] = []
    desired: dict[str, str] = {}
    target_version = manifest_version(source_root)
    project_id: str | None = None

    if base_version(from_version) != FROM_VERSION:
        errors.append(f"迁移器只支持 {FROM_VERSION}，收到 {from_version}")
    if base_version(target_version) != TO_VERSION:
        errors.append(f"迁移器目标必须为 {TO_VERSION}，当前为 {target_version}")
    if from_lock.get("schema_version") != LOCK_SCHEMA:
        errors.append(f"lock schema 必须为 {LOCK_SCHEMA}")
    if from_lock.get("plugin_id") != PLUGIN_ID:
        errors.append(f"plugin_id 必须为 {PLUGIN_ID}")
    if from_lock.get("compatibility_mode") != "strict":
        errors.append("只支持 compatibility_mode=strict 的 v0.4.0-alpha.2 项目")
    if from_lock.get("framework_digest") not in SUPPORTED_FROM_FRAMEWORK_DIGESTS:
        errors.append("v0.4.0-alpha.2 framework digest 不在已发行白名单中")

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
    history_paths = sorted((project_root / "game-pipeline" / "loops" / "registry").glob("*/event-history.yaml"))
    history_digests = {
        path.relative_to(project_root).as_posix(): sha256(path.read_bytes())
        for path in history_paths
        if path.is_file()
    }

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

    ordered_paths = ["AGENTS.md", "game-pipeline/plugin-lock.yaml"]
    actions = [
        classify_action(project_root, path, desired[path])
        for path in ordered_paths
        if path in desired
    ]
    if any(action["path"] == "game-pipeline/plugin-lock.yaml" for action in actions):
        warnings.append("plugin lock 将在 AGENTS.md 写入并验证后最后更新")
    warnings.append("此迁移不得修改 Snapshot、Event History、Contract 或游戏内容")

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
                "plugin lock 状态为 normal",
                "项目实例完整校验为 normal",
                "所有 Event History 的 SHA-256 与迁移前一致",
                "迁移后再次规划返回 no_change",
            ],
        },
        desired,
    )
