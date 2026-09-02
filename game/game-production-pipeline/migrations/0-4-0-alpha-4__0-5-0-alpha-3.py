#!/usr/bin/env python3
"""Plan the v0.4.0-alpha.4 to v0.5.0-alpha.3 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


FROM_VERSION = "0.4.0-alpha.4"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {"e7064c2f494a626c253a9bf725b43f3f9edfca05fe555bbef494bd38fde91e12"}


def entry():
    path = Path(__file__).with_name("_v05_alpha3_entry.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_alpha3_entry_alpha4", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移入口: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_migration(*, project_root: Path, source_root: Path, migration_at: str, from_version: str, from_lock: dict[str, Any]):
    return entry().build_alpha(project_root=project_root, source_root=source_root, migration_at=migration_at, from_version=from_version, from_lock=from_lock, expected_from_version=FROM_VERSION, supported_digests=SUPPORTED_FROM_FRAMEWORK_DIGESTS)
