#!/usr/bin/env python3
"""Plan the explicit v0.3.0-alpha.1 to v0.4.0-alpha.4 project migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


TARGET_VERSION = "0.4.0-alpha.4"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移基线: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_migration(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    root = Path(__file__).parent
    legacy = load_module(
        root / "0-3-0-alpha-1__0-4-0-alpha-2.py",
        "_game_pipeline_v03_migration_base_alpha4",
    )
    alpha4 = load_module(
        root / "0-4-0-alpha-3__0-4-0-alpha-4.py",
        "_game_pipeline_alpha4_control_plane",
    )
    details, desired = legacy.build_migration_to(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_target_version=TARGET_VERSION,
    )
    errors = details.get("errors", [])
    alpha4.add_control_plane_readmes(project_root, desired, errors)
    previous_paths = [
        item["path"]
        for item in details.get("actions", [])
        if item["path"] not in {"AGENTS.md", "game-pipeline/plugin-lock.yaml"}
    ]
    ordered_paths = [
        *previous_paths,
        *alpha4.ASSET_AND_LOOP_READMES,
        "AGENTS.md",
        "game-pipeline/plugin-lock.yaml",
    ]
    details["actions"] = [
        alpha4.classify_action(project_root, path, desired[path])
        for path in dict.fromkeys(ordered_paths)
        if path in desired
    ]
    history_paths = sorted(
        (project_root / "game-pipeline" / "loops" / "registry").glob("*/event-history.yaml")
    )
    details["history_digests_before"] = {
        path.relative_to(project_root).as_posix(): alpha4.sha256(path.read_bytes())
        for path in history_paths
        if path.is_file()
    }
    details.setdefault("warnings", []).append(
        "迁移不修改现有 Asset Contract、Snapshot、Event History、游戏内容或 UI 事实源"
    )
    details["postconditions"] = [
        *details.get("postconditions", []),
        "专业资产与 Loop Registry 控制面目录存在",
        "所有 Event History 的 SHA-256 与迁移前一致",
    ]
    return details, desired
