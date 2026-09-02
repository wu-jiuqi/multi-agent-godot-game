#!/usr/bin/env python3
"""Plan the non-destructive v0.4.0-alpha.3 to v0.5.0-alpha.1 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


FROM_VERSION = "0.4.0-alpha.3"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    "16c8b7ec74a098f9382fb1aff1af95d9557f1e4c2dbbfe4dd8caa0033a544621",
    "f7c7dedc3910401865f58a9902c5d84841998b62fc4c5b9cbfc24f5ee06d4e6f",
}


def common():
    path = Path(__file__).with_name("_art_direction_v05_common.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_art_v05_from_alpha3", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载 v0.5 迁移基线: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_migration(*, project_root: Path, source_root: Path, migration_at: str, from_version: str, from_lock: dict[str, Any]):
    return common().build_from_alpha(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=FROM_VERSION,
        supported_digests=SUPPORTED_FROM_FRAMEWORK_DIGESTS,
    )
