#!/usr/bin/env python3
"""Plan the v0.5.0-alpha.11 to v0.5.0-alpha.14 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


FROM_VERSION = "0.5.0-alpha.11"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    # Published alpha.11 artifact.
    "748a68f2325dc832f02c2f76e8d6c7138574bcc7015607c40805d7b678df1a23",
    # Alpha.11 development head immediately before this release.
    "e7b6fa8a8422b73c7fbfd66d2f826ac08367540dccfbf2b4ca439ecfe3876e10",
}


def entry():
    path = Path(__file__).with_name("_v05_alpha3_entry.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_alpha13_entry", path)
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
