#!/usr/bin/env python3
"""Shared deterministic helpers for the game production pipeline plugin."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import yaml


PLUGIN_ID = "game-production-pipeline"
LOCK_SCHEMA = "game-production-pipeline-lock/v1"
PROJECT_SCHEMA = "game-production-project/v1"
SKILL_BINDINGS_SCHEMA = "game-production-skill-bindings/v1"
FACT_SOURCES_SCHEMA = "game-production-fact-sources/v1"
PROJECT_BRIEF_SCHEMA = "game-production-project-brief/v1"
AGENT_PRESET_SCHEMA = "game-production-agent-preset/v1"
APPROVAL_SCHEMA = "game-production-approval/v1"
MANAGED_MARKER = "game-production-pipeline:managed"
PROJECT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def project_brief_subject(document: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable subject a human approves for project-definition readiness."""
    brief = document.get("project_brief")
    if not isinstance(brief, dict):
        raise ValueError("项目简报缺少 project_brief 映射")
    return {
        "schema_version": brief.get("schema_version"),
        "identity": brief.get("identity"),
        "coordination": brief.get("coordination"),
        "sources": brief.get("sources"),
        "statements": brief.get("statements"),
        "open_questions": brief.get("open_questions"),
        "risks": brief.get("risks"),
        "staffing_input": brief.get("staffing_input"),
    }


def project_brief_subject_digest(document: dict[str, Any]) -> str:
    return canonical_digest(project_brief_subject(document))


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def directory_digest(path: Path) -> str:
    entries: list[dict[str, str]] = []
    for file_path in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        if "__pycache__" in file_path.parts or file_path.suffix in {".pyc", ".pyo"}:
            continue
        entries.append(
            {
                "path": file_path.relative_to(path).as_posix(),
                "sha256": file_digest(file_path),
            }
        )
    return canonical_digest(entries)


def framework_digest(root: Path | None = None) -> str:
    root = (root or plugin_root()).resolve()
    sources: list[Path] = []
    for directory_name in (
        "adapters",
        "agents",
        "contracts",
        "departments",
        "migrations",
        "scripts",
        "skills",
        "workflows",
    ):
        directory = root / directory_name
        if directory.exists():
            sources.extend(candidate for candidate in directory.rglob("*") if candidate.is_file())
    architecture = root / "architecture.md"
    if architecture.exists():
        sources.append(architecture)

    entries: list[dict[str, str]] = []
    for file_path in sorted(set(sources)):
        if "__pycache__" in file_path.parts or file_path.suffix in {".pyc", ".pyo"}:
            continue
        entries.append(
            {
                "path": file_path.relative_to(root).as_posix(),
                "sha256": file_digest(file_path),
            }
        )
    return canonical_digest(entries)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} 必须包含 JSON 对象")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} 必须包含 YAML 映射")
    return value


def dump_yaml(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=120)


def manifest(root: Path | None = None) -> dict[str, Any]:
    root = (root or plugin_root()).resolve()
    return load_json(root / ".codex-plugin" / "plugin.json")


def manifest_version(root: Path | None = None) -> str:
    value = manifest(root).get("version")
    if not isinstance(value, str) or not value:
        raise ValueError("插件清单缺少 version")
    return value


def base_version(version: str) -> str:
    """Ignore only Marketplace cache-buster build metadata."""
    return version.split("+", 1)[0]


def ensure_within(root: Path, target: Path) -> Path:
    root = root.resolve()
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"目标越出项目根目录: {target}") from exc
    return target


def write_new_text(path: Path, content: str) -> None:
    """Atomically create a new file without overwriting an existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def stable_token(namespace: str, length: int = 26) -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    number = int.from_bytes(hashlib.sha256(namespace.encode("utf-8")).digest(), "big")
    chars: list[str] = []
    for _ in range(length):
        number, remainder = divmod(number, 32)
        chars.append(alphabet[remainder])
    return "".join(reversed(chars))


def digest_entries(paths: Iterable[Path], relative_to: Path) -> str:
    entries = [
        {"path": path.relative_to(relative_to).as_posix(), "sha256": file_digest(path)}
        for path in sorted(paths)
    ]
    return canonical_digest(entries)
