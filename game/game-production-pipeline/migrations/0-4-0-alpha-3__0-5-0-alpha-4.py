#!/usr/bin/env python3
"""Plan the v0.4.0-alpha.3 to v0.5.0-alpha.4 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


FROM_VERSION = "0.4.0-alpha.3"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    "16c8b7ec74a098f9382fb1aff1af95d9557f1e4c2dbbfe4dd8caa0033a544621",
    "f7c7dedc3910401865f58a9902c5d84841998b62fc4c5b9cbfc24f5ee06d4e6f",
}


def entry():
    path = Path(__file__).with_name("_v05_alpha3_entry.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_alpha3_entry_alpha3", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移入口: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_migration(*, project_root: Path, source_root: Path, migration_at: str, from_version: str, from_lock: dict[str, Any]):
    return entry().build_alpha(project_root=project_root, source_root=source_root, migration_at=migration_at, from_version=from_version, from_lock=from_lock, expected_from_version=FROM_VERSION, expected_to_version="0.5.0-alpha.4", supported_digests=SUPPORTED_FROM_FRAMEWORK_DIGESTS)
