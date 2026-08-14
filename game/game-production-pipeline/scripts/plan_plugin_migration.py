#!/usr/bin/env python3
"""Build a deterministic, non-mutating plugin migration plan."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from bootstrap_game_pipeline import validate_timestamp
from pipeline_common import base_version, canonical_digest, load_yaml, manifest_version, plugin_root
from validate_plugin_lock import evaluate_lock


PLAN_SCHEMA = "game-production-plugin-migration-plan/v2"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def migration_slug(version: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", version).strip("-").lower()


def migration_path(source_root: Path, from_version: str, to_version: str) -> Path:
    name = f"{migration_slug(base_version(from_version))}__{migration_slug(base_version(to_version))}.py"
    return source_root / "migrations" / name


def load_migrator(path: Path) -> ModuleType:
    module_name = f"_game_pipeline_migration_{path.stem.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载迁移器: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "build_migration", None)):
        raise ValueError(f"迁移器缺少 build_migration(): {path}")
    return module


def _finalize(subject: dict[str, Any], *, can_apply: bool, desired: dict[str, str] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    plan_digest = canonical_digest(subject)
    plan = {
        **subject,
        "plan_digest": plan_digest,
        "approval_record": f"game-pipeline/approvals/migration-{plan_digest[:12]}.yaml",
        "can_apply": can_apply,
    }
    return plan, desired or {}


def prepare_migration(
    project_root: Path,
    source_root: Path | None = None,
    migration_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    project_root = project_root.resolve()
    source_root = (source_root or plugin_root()).resolve()
    lock_path = project_root / "game-pipeline" / "plugin-lock.yaml"
    if not lock_path.is_file():
        subject = {
            "schema_version": PLAN_SCHEMA,
            "project_root": str(project_root),
            "outcome": "bootstrap_required",
            "reason": "项目没有插件版本锁；这不是可自动迁移的已初始化实例",
        }
        return _finalize(subject, can_apply=False)

    try:
        document = load_yaml(lock_path)
    except (OSError, ValueError) as exc:
        subject = {
            "schema_version": PLAN_SCHEMA,
            "project_root": str(project_root),
            "outcome": "migration_blocked",
            "reason": str(exc),
        }
        return _finalize(subject, can_apply=False)

    lock = document.get("plugin_lock")
    if not isinstance(lock, dict):
        subject = {
            "schema_version": PLAN_SCHEMA,
            "project_root": str(project_root),
            "outcome": "migration_blocked",
            "reason": "plugin-lock.yaml 缺少 plugin_lock 映射",
        }
        return _finalize(subject, can_apply=False)

    lock_result = evaluate_lock(project_root, source_root)
    from_version = str(lock.get("plugin_version", "unknown"))
    to_version = manifest_version(source_root)
    common = {
        "schema_version": PLAN_SCHEMA,
        "plugin_id": "game-production-pipeline",
        "project_root": str(project_root),
        "from_version": from_version,
        "to_version": to_version,
        "from_framework_digest": lock.get("framework_digest"),
        "to_framework_digest": lock_result.get("installed_framework_digest"),
    }

    if lock_result["state"] == "normal":
        return _finalize(
            {
                **common,
                "outcome": "no_change",
                "reason": "项目锁与当前插件版本及框架摘要一致",
            },
            can_apply=False,
        )

    if lock_result["errors"]:
        return _finalize(
            {
                **common,
                "outcome": "migration_blocked",
                "reason": "项目锁无效，迁移拒绝掩盖损坏安装",
                "errors": lock_result["errors"],
            },
            can_apply=False,
        )

    if base_version(from_version) == base_version(to_version):
        return _finalize(
            {
                **common,
                "outcome": "reinstall_required",
                "reason": "版本相同但框架摘要不一致；迁移不能掩盖损坏安装或未发布修改",
            },
            can_apply=False,
        )

    candidate = migration_path(source_root, from_version, to_version)
    relative_migrator = candidate.relative_to(source_root).as_posix()
    if not candidate.is_file():
        return _finalize(
            {
                **common,
                "outcome": "migration_blocked",
                "reason": "没有从锁定版本到目标版本的显式迁移器",
                "migrator": None,
            },
            can_apply=False,
        )

    migration_at = validate_timestamp(migration_at or utc_now())
    try:
        module = load_migrator(candidate)
        details, desired = module.build_migration(
            project_root=project_root,
            source_root=source_root,
            migration_at=migration_at,
            from_version=from_version,
            from_lock=lock,
        )
    except Exception as exc:
        return _finalize(
            {
                **common,
                "migration_at": migration_at,
                "outcome": "migration_blocked",
                "reason": str(exc),
                "migrator": relative_migrator,
            },
            can_apply=False,
        )

    conflicts = details.get("conflicts", [])
    errors = details.get("errors", [])
    can_apply = not conflicts and not errors
    subject = {
        **common,
        "migration_at": migration_at,
        "outcome": "migration_ready" if can_apply else "migration_blocked",
        "reason": "找到显式迁移器且预检通过" if can_apply else "显式迁移器预检发现阻断项",
        "migrator": relative_migrator,
        "project_id": details.get("project_id"),
        "actions": details.get("actions", []),
        "conflicts": conflicts,
        "errors": errors,
        "warnings": details.get("warnings", []),
        "human_approval_required": True,
        "backup_root": "game-pipeline/.cache/migrations/<plan_digest>",
        "postconditions": details.get("postconditions", []),
        "rollback_requirement": "必须使用本计划的逐字节备份回退；禁止只回写 plugin-lock.yaml。",
    }
    return _finalize(subject, can_apply=can_apply, desired=desired)


def plan_migration(
    project_root: Path,
    source_root: Path | None = None,
    migration_at: str | None = None,
) -> dict[str, Any]:
    plan, _ = prepare_migration(project_root, source_root, migration_at)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    parser.add_argument("--migration-at", help="Apply 时必须复用 dry-run 输出中的 ISO 8601 时间")
    args = parser.parse_args()
    result = plan_migration(args.project_root, args.plugin_root, args.migration_at)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["outcome"] in {"no_change", "migration_ready"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
