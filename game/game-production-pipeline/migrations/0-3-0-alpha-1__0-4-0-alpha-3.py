#!/usr/bin/env python3
"""Plan the explicit v0.3.0-alpha.1 to v0.4.0-alpha.3 project migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


TARGET_VERSION = "0.4.0-alpha.3"


def load_alpha2_migrator() -> ModuleType:
    path = Path(__file__).with_name("0-3-0-alpha-1__0-4-0-alpha-2.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_v03_migration_base", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载 v0.3 迁移基线: {path}")
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
    base = load_alpha2_migrator()
    return base.build_migration_to(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_target_version=TARGET_VERSION,
    )
