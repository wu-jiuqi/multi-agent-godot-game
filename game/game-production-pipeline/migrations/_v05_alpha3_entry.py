#!/usr/bin/env python3
"""Small loader shared by explicit v0.5.0-alpha.3 migration entry points."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def load_module(name: str, filename: str) -> ModuleType:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移依赖: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_alpha(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
    expected_from_version: str,
    supported_digests: set[str],
    metadata_only: bool = False,
    expected_to_version: str = "0.5.0-alpha.3",
) -> tuple[dict[str, Any], dict[str, str]]:
    art = load_module(f"_game_pipeline_art_alpha3_{expected_from_version}", "_art_direction_v05_common.py")
    runtime = load_module(f"_game_pipeline_runtime_alpha3_{expected_from_version}", "_runtime_binding_v05_alpha3_common.py")
    builder = runtime.build_metadata_from_alpha if metadata_only else runtime.build_from_alpha
    return builder(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=expected_from_version,
        supported_digests=supported_digests,
        art_common=art,
        expected_to_version=expected_to_version,
    )


def build_v03(
    *,
    project_root: Path,
    source_root: Path,
    migration_at: str,
    from_version: str,
    from_lock: dict[str, Any],
    expected_to_version: str = "0.5.0-alpha.3",
) -> tuple[dict[str, Any], dict[str, str]]:
    art = load_module("_game_pipeline_art_alpha3_v03", "_art_direction_v05_common.py")
    runtime = load_module("_game_pipeline_runtime_alpha3_v03", "_runtime_binding_v05_alpha3_common.py")
    return runtime.build_from_v03(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        art_common=art,
        expected_to_version=expected_to_version,
    )
