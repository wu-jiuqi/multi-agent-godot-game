#!/usr/bin/env python3
"""Plan the v0.5.0-alpha.1 to v0.5.0-alpha.4 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


FROM_VERSION = "0.5.0-alpha.1"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    "1a06826ea2faf5bde90b4473630cb955e59b3e3645982c0368cea33204c4d9ea",
    "56a98f18337eae322d24dcfc7f5a1d6c347aad8de58b35104df94980ab7ea363",
}


def entry():
    path = Path(__file__).with_name("_v05_alpha3_entry.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_alpha3_entry_v05_alpha1", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移入口: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_migration(*, project_root: Path, source_root: Path, migration_at: str, from_version: str, from_lock: dict[str, Any]):
    return entry().build_alpha(project_root=project_root, source_root=source_root, migration_at=migration_at, from_version=from_version, from_lock=from_lock, expected_from_version=FROM_VERSION, expected_to_version="0.5.0-alpha.4", supported_digests=SUPPORTED_FROM_FRAMEWORK_DIGESTS, metadata_only=True)
