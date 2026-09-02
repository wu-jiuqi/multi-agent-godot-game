#!/usr/bin/env python3
"""Shared non-destructive migration planning for the v0.5 Art Direction control plane."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from bootstrap_game_pipeline import ART_DIRECTION_READMES


TO_VERSION = "0.5.0-alpha.1"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移基线: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_readmes(
    project_root: Path,
    desired: dict[str, str],
    errors: list[str],
    readmes: dict[str, str],
    base: ModuleType,
) -> None:
    for relative_path, default_content in readmes.items():
        path = project_root / relative_path
        if path.is_file():
            existing = base.read_utf8(path, relative_path, errors)
            if existing is not None:
                desired[relative_path] = existing
        elif path.exists():
            errors.append(f"迁移目标不是文件: {relative_path}")
        else:
            desired[relative_path] = default_content


def finalize_art_control_plane(
    *,
    project_root: Path,
    details: dict[str, Any],
    desired: dict[str, str],
    base: ModuleType,
    include_asset_readmes: bool,
) -> tuple[dict[str, Any], dict[str, str]]:
    errors = details.setdefault("errors", [])
    if include_asset_readmes:
        base.add_control_plane_readmes(project_root, desired, errors)
    add_readmes(project_root, desired, errors, ART_DIRECTION_READMES, base)
    previous_paths = [
        item["path"]
        for item in details.get("actions", [])
        if item["path"] not in {"AGENTS.md", "game-pipeline/plugin-lock.yaml"}
    ]
    ordered_paths = [
        *previous_paths,
        *(base.ASSET_AND_LOOP_READMES if include_asset_readmes else ()),
        *ART_DIRECTION_READMES,
        "AGENTS.md",
        "game-pipeline/plugin-lock.yaml",
    ]
    details["actions"] = [
        base.classify_action(project_root, path, desired[path])
        for path in dict.fromkeys(ordered_paths)
        if path in desired
    ]
    details.setdefault("warnings", []).append(
        "迁移只补充主美方向控制面并更新托管元数据；不修改现有美术/资产 Contract、风格圣经、图片、场景、UI、组织或 Event History"
    )
    details["postconditions"] = [
        *details.get("postconditions", []),
        "主美方向 contracts/research/style-bibles/benchmarks/evidence 目录存在",
        "所有 Event History 与用户内容的字节保持不变",
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
) -> tuple[dict[str, Any], dict[str, str]]:
    base = load_module(
        Path(__file__).with_name("0-4-0-alpha-3__0-4-0-alpha-4.py"),
        f"_game_pipeline_alpha4_base_for_{expected_from_version.replace('.', '_').replace('-', '_')}",
    )
    base.TO_VERSION = TO_VERSION
    details, desired = base.build_migration_from(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=expected_from_version,
        supported_from_framework_digests=supported_digests,
    )
    return finalize_art_control_plane(
        project_root=project_root,
        details=details,
        desired=desired,
        base=base,
        include_asset_readmes=False,
    )


def build_from_v03(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    root = Path(__file__).parent
    legacy = load_module(root / "0-3-0-alpha-1__0-4-0-alpha-2.py", "_game_pipeline_v03_base_for_v05")
    base = load_module(root / "0-4-0-alpha-3__0-4-0-alpha-4.py", "_game_pipeline_alpha4_control_for_v05")
    details, desired = legacy.build_migration_to(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_target_version=TO_VERSION,
    )
    return finalize_art_control_plane(
        project_root=project_root,
        details=details,
        desired=desired,
        base=base,
        include_asset_readmes=True,
    )
