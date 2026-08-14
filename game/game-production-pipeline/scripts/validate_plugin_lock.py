#!/usr/bin/env python3
"""Validate a project's strict lock against the running plugin source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_common import (
    LOCK_SCHEMA,
    PLUGIN_ID,
    base_version,
    framework_digest,
    load_yaml,
    manifest_version,
    plugin_root,
)


def evaluate_lock(project_root: Path, source_root: Path | None = None) -> dict[str, Any]:
    project_root = project_root.resolve()
    source_root = (source_root or plugin_root()).resolve()
    lock_path = project_root / "game-pipeline" / "plugin-lock.yaml"
    result: dict[str, Any] = {
        "state": "blocked",
        "project_root": str(project_root),
        "lock_path": str(lock_path),
        "plugin_root": str(source_root),
        "errors": [],
        "warnings": [],
    }
    if not lock_path.is_file():
        result["errors"].append("缺少 game-pipeline/plugin-lock.yaml")
        return result

    try:
        document = load_yaml(lock_path)
    except (OSError, ValueError) as exc:
        result["errors"].append(str(exc))
        return result

    lock = document.get("plugin_lock")
    if not isinstance(lock, dict):
        result["errors"].append("plugin-lock.yaml 缺少 plugin_lock 映射")
        return result
    if lock.get("schema_version") != LOCK_SCHEMA:
        result["errors"].append(f"不支持的 lock schema: {lock.get('schema_version')}")
    if lock.get("plugin_id") != PLUGIN_ID:
        result["errors"].append(f"plugin_id 必须为 {PLUGIN_ID}")

    installed_version = manifest_version(source_root)
    locked_version = lock.get("plugin_version")
    installed_digest = framework_digest(source_root)
    locked_digest = lock.get("framework_digest")
    result.update(
        {
            "locked_version": locked_version,
            "installed_version": installed_version,
            "locked_framework_digest": locked_digest,
            "installed_framework_digest": installed_digest,
        }
    )
    if result["errors"]:
        return result
    if not isinstance(locked_version, str):
        result["errors"].append("plugin_version 必须是字符串")
        return result
    if base_version(locked_version) != base_version(installed_version):
        result["state"] = "read_only"
        result["warnings"].append("插件版本与项目锁不一致；只允许检查和迁移规划，禁止生产写入")
        return result
    if locked_digest != installed_digest:
        result["errors"].append("插件框架摘要与项目锁不一致；可能存在未发布修改或损坏安装")
        return result

    result["state"] = "normal"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    args = parser.parse_args()
    result = evaluate_lock(args.project_root, args.plugin_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "normal" else 2


if __name__ == "__main__":
    raise SystemExit(main())
