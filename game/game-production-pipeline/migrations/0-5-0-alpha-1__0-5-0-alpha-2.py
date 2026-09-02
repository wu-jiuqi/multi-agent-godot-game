#!/usr/bin/env python3
"""Plan the metadata-only v0.5.0-alpha.1 to v0.5.0-alpha.2 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


FROM_VERSION = "0.5.0-alpha.1"
TO_VERSION = "0.5.0-alpha.2"
SUPPORTED_FROM_FRAMEWORK_DIGESTS = {
    # Published LF release asset and release notes.
    "1a06826ea2faf5bde90b4473630cb955e59b3e3645982c0368cea33204c4d9ea",
    # Known CRLF materialization of the same tagged source.
    "56a98f18337eae322d24dcfc7f5a1d6c347aad8de58b35104df94980ab7ea363",
}


def base():
    path = Path(__file__).with_name("0-4-0-alpha-3__0-4-0-alpha-4.py")
    spec = importlib.util.spec_from_file_location("_game_pipeline_release_repro_alpha2", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移基线: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_migration(*, project_root: Path, source_root: Path, migration_at: str, from_version: str, from_lock: dict[str, Any]):
    migration_base = base()
    migration_base.TO_VERSION = TO_VERSION
    return migration_base.build_migration_from(
        project_root=project_root,
        source_root=source_root,
        migration_at=migration_at,
        from_version=from_version,
        from_lock=from_lock,
        expected_from_version=FROM_VERSION,
        supported_from_framework_digests=SUPPORTED_FROM_FRAMEWORK_DIGESTS,
        include_control_plane_readmes=False,
    )
