#!/usr/bin/env python3
"""Validate and list the reusable style-direction modules owned by direct-game-art."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from pipeline_common import canonical_digest, directory_digest, file_digest, load_yaml


SCHEMA_VERSION = "game-production-style-direction-registry/v1"
STYLE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RIGHTS_STATES = {"cleared", "conditional", "reference-only", "unknown", "blocked"}


def mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是映射")
        return {}
    return value


def strings(value: Any, label: str, errors: list[str], *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{label} 必须是数组")
        return []
    if nonempty and not value:
        errors.append(f"{label} 不能为空")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{index}] 必须是非空字符串")
        else:
            result.append(item)
    return result


def nonempty_string(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} 必须是非空字符串")
        return ""
    return value


def relative_path(value: Any, label: str, errors: list[str]) -> str:
    text = nonempty_string(value, label, errors).replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or ":" in text or ".." in path.parts or not text:
        errors.append(f"{label} 必须是仓库内相对路径: {value}")
        return ""
    return path.as_posix()


def sha256(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        errors.append(f"{label} 必须是 64 位小写 SHA-256")
        return ""
    return value


def registry_subject(registry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in registry.items() if key != "integrity"}


def registry_subject_digest(registry: dict[str, Any]) -> str:
    return canonical_digest(registry_subject(registry))


def validate_style_direction_registry(
    document: object,
    *,
    plugin_root: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    file_checks: list[dict[str, Any]] = []
    if not isinstance(document, dict):
        return {"state": "invalid", "errors": ["根节点必须是映射"], "directions": [], "file_checks": []}

    registry = mapping(document.get("style_direction_registry"), "style_direction_registry", errors)
    if registry.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须为 {SCHEMA_VERSION}")
    registry_id = nonempty_string(registry.get("registry_id"), "registry_id", errors)
    version = registry.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("version 必须是正整数")

    raw_directions = registry.get("directions")
    if not isinstance(raw_directions, list) or not raw_directions:
        errors.append("directions 必须是非空数组")
        raw_directions = []

    root = (plugin_root or Path(__file__).resolve().parents[1]).resolve()
    directions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_directions):
        label = f"directions[{index}]"
        direction = mapping(raw, label, errors)
        direction_id = nonempty_string(direction.get("id"), f"{label}.id", errors)
        if direction_id and not STYLE_ID_RE.fullmatch(direction_id):
            errors.append(f"{label}.id 必须使用小写字母、数字和连字符")
        if direction_id in seen_ids:
            errors.append(f"direction id 重复: {direction_id}")
        seen_ids.add(direction_id)
        display_name = nonempty_string(direction.get("display_name"), f"{label}.display_name", errors)
        module_path_text = relative_path(direction.get("path"), f"{label}.path", errors)
        skill_path_text = relative_path(direction.get("skill_path"), f"{label}.skill_path", errors)
        tags = strings(direction.get("tags"), f"{label}.tags", errors, nonempty=True)
        use_when = strings(direction.get("use_when"), f"{label}.use_when", errors, nonempty=True)
        avoid = strings(direction.get("avoid"), f"{label}.avoid", errors, nonempty=True)
        domains = strings(direction.get("domains"), f"{label}.domains", errors, nonempty=True)

        source = mapping(direction.get("source"), f"{label}.source", errors)
        source_kind = nonempty_string(source.get("kind"), f"{label}.source.kind", errors)
        source_uri = nonempty_string(source.get("uri"), f"{label}.source.uri", errors)
        if source_uri and not source_uri.startswith("https://"):
            errors.append(f"{label}.source.uri 必须使用 https://")
        source_revision = nonempty_string(source.get("revision"), f"{label}.source.revision", errors)
        rights_state = source.get("rights_state")
        if rights_state not in RIGHTS_STATES:
            errors.append(f"{label}.source.rights_state 非法")

        digests = mapping(direction.get("digests"), f"{label}.digests", errors)
        expected_directory_digest = sha256(digests.get("directory_sha256"), f"{label}.digests.directory_sha256", errors)
        expected_skill_digest = sha256(digests.get("skill_sha256"), f"{label}.digests.skill_sha256", errors)

        module_path = (root / module_path_text).resolve() if module_path_text else root
        skill_path = (root / skill_path_text).resolve() if skill_path_text else root
        for resolved, path_label in ((module_path, f"{label}.path"), (skill_path, f"{label}.skill_path")):
            try:
                resolved.relative_to(root)
            except ValueError:
                errors.append(f"{path_label} 越出插件根目录")
        if module_path_text and not module_path.is_dir():
            errors.append(f"{label}.path 目录不存在: {module_path_text}")
        if skill_path_text and not skill_path.is_file():
            errors.append(f"{label}.skill_path 文件不存在: {skill_path_text}")
        if module_path_text and skill_path_text and PurePosixPath(skill_path_text).parts[: len(PurePosixPath(module_path_text).parts)] != PurePosixPath(module_path_text).parts:
            errors.append(f"{label}.skill_path 必须位于 path 目录内")
        if skill_path_text and PurePosixPath(skill_path_text).name != "SKILL.md":
            errors.append(f"{label}.skill_path 必须指向 SKILL.md")

        actual_directory_digest = directory_digest(module_path) if module_path.is_dir() else None
        actual_skill_digest = file_digest(skill_path) if skill_path.is_file() else None
        file_checks.append({
            "id": direction_id,
            "path": module_path_text,
            "state": "matched" if actual_directory_digest == expected_directory_digest else "mismatch",
            "directory_sha256": actual_directory_digest,
            "skill_sha256": actual_skill_digest,
        })
        if actual_directory_digest != expected_directory_digest:
            errors.append(f"{label}.digests.directory_sha256 与目录不匹配")
        if actual_skill_digest != expected_skill_digest:
            errors.append(f"{label}.digests.skill_sha256 与 SKILL.md 不匹配")

        directions.append({
            "id": direction_id,
            "display_name": display_name,
            "path": module_path_text,
            "skill_path": skill_path_text,
            "tags": tags,
            "use_when": use_when,
            "avoid": avoid,
            "domains": domains,
            "source": {"kind": source_kind, "uri": source_uri, "revision": source_revision, "rights_state": rights_state},
            "digests": {"directory_sha256": expected_directory_digest, "skill_sha256": expected_skill_digest},
        })

    integrity = mapping(registry.get("integrity"), "integrity", errors)
    expected_registry_digest = sha256(integrity.get("registry_digest"), "integrity.registry_digest", errors)
    actual_registry_digest = registry_subject_digest(registry)
    if expected_registry_digest != actual_registry_digest:
        errors.append("integrity.registry_digest 与注册表内容不匹配")

    return {
        "state": "valid" if not errors else "invalid",
        "schema_version": SCHEMA_VERSION,
        "registry_id": registry_id,
        "version": version,
        "directions": directions,
        "integrity": {"registry_digest": actual_registry_digest, "expected_registry_digest": expected_registry_digest},
        "file_checks": file_checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--plugin-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--list", action="store_true", help="只输出已验证的方向列表")
    args = parser.parse_args()
    try:
        document = load_yaml(args.registry)
    except (OSError, ValueError) as exc:
        print(json.dumps({"state": "invalid", "errors": [str(exc)]}, ensure_ascii=True, indent=2))
        return 2
    result = validate_style_direction_registry(document, plugin_root=args.plugin_root)
    if args.list:
        result = {"state": result["state"], "registry_id": result.get("registry_id"), "version": result.get("version"), "directions": result.get("directions", []), "errors": result.get("errors", [])}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["state"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
