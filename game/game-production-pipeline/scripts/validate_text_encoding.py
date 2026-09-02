#!/usr/bin/env python3
"""Validate UTF-8 text in plugin sources, generated projects, and release ZIPs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from pipeline_common import PLUGIN_ID, plugin_root
from validate_plugin_lock import evaluate_lock


SCHEMA_VERSION = "game-production-text-encoding-validation/v1"
TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
TEXT_FILENAMES = {".gitattributes", ".gitignore"}
SKIPPED_PARTS = {".git", "__pycache__"}
UTF8_BOM = b"\xef\xbb\xbf"
REPLACEMENT_CHARACTER = "\ufffd"

PLUGIN_MARKERS = {
    "scripts/bootstrap_game_pipeline.py": (
        "项目 Agent Presets",
        "人工审批记录",
        "建立项目初始多 Agent 编制",
        "项目管线状态位于",
    ),
    "README.md": (
        "UTF-8 无 BOM",
        "Get-Content -LiteralPath \"文件路径\" -Encoding UTF8",
    ),
    ".gitattributes": ("* text=auto eol=lf",),
}
PROJECT_MARKERS = {
    "game-pipeline/agents/README.md": ("项目 Agent Presets",),
    "game-pipeline/approvals/README.md": ("人工审批记录",),
    "game-pipeline/organization/change-sets/initial-organization.draft.yaml": (
        "建立项目初始多 Agent 编制",
    ),
    "AGENTS.md": ("项目管线状态位于",),
}

AGENTS_START_RE = re.compile(
    r"<!-- game-production-pipeline:start schema=v1 digest=([0-9a-f]{64}) -->\n"
)
AGENTS_END = "<!-- game-production-pipeline:end -->"
IGNORE_START_RE = re.compile(
    r"# game-production-pipeline:start schema=v1 digest=([0-9a-f]{64})\n"
)
IGNORE_END = "# game-production-pipeline:end"


def is_target_text(path: PurePosixPath) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_FILENAMES


def error(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def decode_utf8(
    data: bytes,
    label: str,
    *,
    require_lf: bool = False,
) -> tuple[str | None, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        errors.append(error("invalid-utf8", label, str(exc)))
        return None, errors
    if data.startswith(UTF8_BOM):
        errors.append(error("unexpected-bom", label, "文本必须保持 UTF-8 无 BOM"))
    if REPLACEMENT_CHARACTER in text:
        errors.append(error("replacement-character", label, "文本包含 U+FFFD 替换字符"))
    if require_lf and b"\r" in data:
        errors.append(error("non-lf-line-ending", label, "发布源文本必须统一使用 LF 换行"))
    return text, errors


def validate_markers(
    texts: dict[str, str],
    required: dict[str, tuple[str, ...]],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for relative_path, markers in sorted(required.items()):
        text = texts.get(relative_path)
        if text is None:
            errors.append(error("missing-marker-file", relative_path, "缺少代表性中文校验目标"))
            continue
        for marker in markers:
            if marker not in text:
                errors.append(error("missing-chinese-marker", relative_path, f"缺少代表性中文: {marker}"))
    return errors


def result(kind: str, target: str, checked_files: int, errors: list[dict[str, str]], **extra: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "target": target,
        "state": "valid" if not errors else "invalid",
        "checked_files": checked_files,
        "errors": errors,
        **extra,
    }


def iter_plugin_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root)
        if any(part in SKIPPED_PARTS for part in relative.parts):
            continue
        if is_target_text(PurePosixPath(relative.as_posix())):
            yield path


def validate_plugin_tree(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    checked = 0
    for path in iter_plugin_text_files(root):
        relative = path.relative_to(root).as_posix()
        checked += 1
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(error("read-error", relative, str(exc)))
            continue
        text, file_errors = decode_utf8(data, relative, require_lf=True)
        errors.extend(file_errors)
        if text is not None:
            texts[relative] = text
    errors.extend(validate_markers(texts, PLUGIN_MARKERS))
    return result(
        "plugin-tree",
        str(root),
        checked,
        errors,
        encoding="UTF-8",
        bom="forbidden",
        line_endings="LF",
    )


def iter_project_text_files(root: Path) -> Iterable[Path]:
    candidates: list[Path] = []
    for relative_root in (Path("game-pipeline"), Path(".codex/agents"), Path(".agents/skills")):
        target_root = root / relative_root
        if target_root.is_dir():
            candidates.extend(path for path in target_root.rglob("*") if path.is_file())
    for relative_path in (Path("AGENTS.md"), Path(".gitignore")):
        path = root / relative_path
        if path.is_file():
            candidates.append(path)
    for path in sorted(set(candidates)):
        relative = path.relative_to(root)
        if any(part in SKIPPED_PARTS for part in relative.parts):
            continue
        if is_target_text(PurePosixPath(relative.as_posix())):
            yield path


def validate_managed_block(
    text: str,
    relative_path: str,
    start_re: re.Pattern[str],
    end_marker: str,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    match = start_re.search(text)
    if not match:
        return [error("missing-managed-block", relative_path, "缺少 game-production-pipeline 托管区块")]
    end_index = text.find(end_marker, match.end())
    if end_index < 0:
        return [error("incomplete-managed-block", relative_path, "托管区块缺少结束标记")]
    if start_re.search(text, end_index + len(end_marker)):
        errors.append(error("duplicate-managed-block", relative_path, "存在多个托管区块"))
    body = text[match.end() : end_index]
    actual_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if actual_digest != match.group(1):
        errors.append(error("managed-digest-mismatch", relative_path, "托管区块摘要与 UTF-8 内容不匹配"))
    return errors


def validate_project_tree(root: Path, source_root: Path) -> dict[str, Any]:
    root = root.resolve()
    source_root = source_root.resolve()
    errors: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    checked = 0
    for path in iter_project_text_files(root):
        relative = path.relative_to(root).as_posix()
        checked += 1
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(error("read-error", relative, str(exc)))
            continue
        text, file_errors = decode_utf8(data, relative)
        errors.extend(file_errors)
        if text is not None:
            texts[relative] = text
    errors.extend(validate_markers(texts, PROJECT_MARKERS))

    agents_text = texts.get("AGENTS.md")
    if agents_text is not None:
        errors.extend(validate_managed_block(agents_text, "AGENTS.md", AGENTS_START_RE, AGENTS_END))
    ignore_text = texts.get(".gitignore")
    if ignore_text is not None:
        errors.extend(validate_managed_block(ignore_text, ".gitignore", IGNORE_START_RE, IGNORE_END))

    lock = evaluate_lock(root, source_root)
    if lock["state"] != "normal":
        errors.append(
            error(
                "plugin-lock-not-normal",
                "game-pipeline/plugin-lock.yaml",
                f"plugin lock 状态为 {lock['state']}，版本或 framework digest 未通过",
            )
        )
    return result(
        "generated-project",
        str(root),
        checked,
        errors,
        encoding="UTF-8",
        bom="forbidden",
        managed_blocks_checked=2,
        plugin_lock_state=lock["state"],
        locked_version=lock.get("locked_version"),
        installed_version=lock.get("installed_version"),
        locked_framework_digest=lock.get("locked_framework_digest"),
        installed_framework_digest=lock.get("installed_framework_digest"),
    )


def validate_release_zip(path: Path) -> dict[str, Any]:
    path = path.resolve()
    errors: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    checked = 0
    member_count = 0
    try:
        with zipfile.ZipFile(path) as archive:
            members = sorted((member for member in archive.infolist() if not member.is_dir()), key=lambda item: item.filename)
            member_count = len(members)
            seen: set[str] = set()
            for member in members:
                name = member.filename
                pure = PurePosixPath(name)
                if name in seen:
                    errors.append(error("duplicate-zip-member", name, "ZIP 包含重复路径"))
                    continue
                seen.add(name)
                if pure.is_absolute() or ".." in pure.parts:
                    errors.append(error("unsafe-zip-member", name, "ZIP 路径越出插件根目录"))
                    continue
                if not pure.parts or pure.parts[0] != PLUGIN_ID:
                    errors.append(error("invalid-package-root", name, f"ZIP 文件必须位于 {PLUGIN_ID}/ 下"))
                    continue
                relative = PurePosixPath(*pure.parts[1:])
                if any(part in SKIPPED_PARTS for part in relative.parts) or not is_target_text(relative):
                    continue
                checked += 1
                text, file_errors = decode_utf8(
                    archive.read(member),
                    name,
                    require_lf=True,
                )
                errors.extend(file_errors)
                if text is not None:
                    texts[relative.as_posix()] = text
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(error("invalid-zip", str(path), str(exc)))

    errors.extend(validate_markers(texts, PLUGIN_MARKERS))
    return result(
        "release-zip",
        str(path),
        checked,
        errors,
        encoding="UTF-8",
        bom="forbidden",
        line_endings="LF",
        zip_members=member_count,
    )


def validation_report(source_root: Path, project_roots: list[Path], zip_paths: list[Path]) -> dict[str, Any]:
    checks = [validate_plugin_tree(source_root)]
    checks.extend(validate_project_tree(project, source_root) for project in project_roots)
    checks.extend(validate_release_zip(path) for path in zip_paths)
    errors = [
        {"kind": check["kind"], "target": check["target"], **item}
        for check in checks
        for item in check["errors"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "valid" if not errors else "invalid",
        "encoding": "UTF-8",
        "bom_policy": "forbidden",
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    parser.add_argument("--project-root", type=Path, action="append", default=[])
    parser.add_argument("--zip", dest="zip_paths", type=Path, action="append", default=[])
    args = parser.parse_args()
    report = validation_report(args.plugin_root, args.project_root, args.zip_paths)
    # ASCII-safe JSON survives Windows PowerShell 5.1 code page 936; JSON parsers restore Chinese text.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["state"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
