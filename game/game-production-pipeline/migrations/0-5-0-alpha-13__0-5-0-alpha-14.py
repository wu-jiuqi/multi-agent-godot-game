#!/usr/bin/env python3
"""Plan the v0.5.0-alpha.13 to v0.5.0-alpha.14 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


FROM_VERSION = "0.5.0-alpha.13"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    # Published alpha.13 artifact.
    "a525e3427c9f2f8e78a6079e2d141e37e9829f9dd4109dad2f2109b090e3fb5a",
}


def entry():
    path = Path(__file__).with_name("_v05_alpha3_entry.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_alpha14_entry", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移入口: {path}")
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
):
    return entry().build_alpha(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=FROM_VERSION,
        expected_to_version="0.5.0-alpha.14",
        supported_digests=SUPPORTED_FROM_FRAMEWORK_DIGESTS,
        metadata_only=True,
    )
