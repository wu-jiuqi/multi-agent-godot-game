#!/usr/bin/env python3
"""Produce a read-only migration preflight for an initialized project."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pipeline_common import base_version, canonical_digest, load_yaml, manifest_version, plugin_root
from validate_plugin_lock import evaluate_lock


def migration_slug(version: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", version).strip("-").lower()


def plan_migration(project_root: Path, source_root: Path | None = None) -> dict[str, Any]:
    project_root = project_root.resolve()
    source_root = (source_root or plugin_root()).resolve()
    lock_path = project_root / "game-pipeline" / "plugin-lock.yaml"
    if not lock_path.is_file():
        subject = {
            "schema_version": "game-production-plugin-migration-plan/v1",
            "project_root": str(project_root),
            "outcome": "bootstrap_required",
            "reason": "项目没有插件版本锁；这不是可自动迁移的已初始化实例",
        }
        return {**subject, "plan_digest": canonical_digest(subject), "can_apply": False}

    lock_result = evaluate_lock(project_root, source_root)
    document = load_yaml(lock_path)
    lock = document.get("plugin_lock", {})
    from_version = str(lock.get("plugin_version", "unknown"))
    to_version = manifest_version(source_root)
    if lock_result["state"] == "normal":
        outcome = "no_change"
        reason = "项目锁与当前插件版本及框架摘要一致"
        migrator = None
        can_apply = False
    elif base_version(from_version) == base_version(to_version):
        outcome = "reinstall_required"
        reason = "版本相同但框架摘要不一致；迁移不能掩盖损坏安装或未发布修改"
        migrator = None
        can_apply = False
    else:
        name = f"{migration_slug(base_version(from_version))}__{migration_slug(base_version(to_version))}.py"
        candidate = source_root / "migrations" / name
        migrator = candidate.relative_to(source_root).as_posix() if candidate.is_file() else None
        outcome = "migration_ready" if migrator else "migration_blocked"
        reason = "找到显式迁移器" if migrator else "没有从锁定版本到目标版本的显式迁移器"
        can_apply = bool(migrator)

    subject = {
        "schema_version": "game-production-plugin-migration-plan/v1",
        "project_root": str(project_root),
        "from_version": from_version,
        "to_version": to_version,
        "from_framework_digest": lock.get("framework_digest"),
        "to_framework_digest": lock_result.get("installed_framework_digest"),
        "outcome": outcome,
        "reason": reason,
        "migrator": migrator,
        "human_approval_required": outcome == "migration_ready",
        "dry_run_required": outcome == "migration_ready",
        "rollback_requirement": "使用经验证的 down migration，或回到迁移前 Git 提交与插件锁；禁止只回写版本号。",
    }
    return {**subject, "plan_digest": canonical_digest(subject), "can_apply": can_apply}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    args = parser.parse_args()
    result = plan_migration(args.project_root, args.plugin_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["outcome"] == "no_change" else 2


if __name__ == "__main__":
    raise SystemExit(main())
