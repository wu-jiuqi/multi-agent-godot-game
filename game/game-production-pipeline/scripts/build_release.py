#!/usr/bin/env python3
"""Build a byte-reproducible plugin ZIP from canonical LF source files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any

from pipeline_common import PLUGIN_ID, framework_digest, manifest_version, plugin_root
from validate_text_encoding import validate_plugin_tree, validate_release_zip


SCHEMA_VERSION = "game-production-release-build/v2"
SKIPPED_PARTS = {".git", "__pycache__"}
SKIPPED_SUFFIXES = {".pyc", ".pyo"}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def release_files(source_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(candidate for candidate in source_root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(source_root)
        if any(part in SKIPPED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in SKIPPED_SUFFIXES:
            continue
        files.append(path)
    return files


def write_deterministic_zip(target: Path, source_root: Path, files: list[Path]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    if temporary.exists():
        raise FileExistsError(f"发布临时文件已存在，拒绝覆盖: {temporary}")
    try:
        # Stored members avoid zlib-version-dependent compressed byte streams. The
        # plugin is text-heavy and small enough that byte reproducibility is more
        # valuable than transport compression at this layer.
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in files:
                relative = path.relative_to(source_root).as_posix()
                info = zipfile.ZipInfo(f"{PLUGIN_ID}/{relative}", date_time=ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = (0o100644 & 0xFFFF) << 16
                archive.writestr(info, path.read_bytes())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def write_sha256_sidecar(target: Path, zip_path: Path, digest: str) -> None:
    content = f"{digest}  {zip_path.name}\n"
    temporary = target.with_name(f".{target.name}.tmp")
    if temporary.exists():
        raise FileExistsError(f"摘要临时文件已存在，拒绝覆盖: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def build_release(source_root: Path, output_dir: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    output_dir = output_dir.resolve()
    source_validation = validate_plugin_tree(source_root)
    if source_validation["state"] != "valid":
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "blocked",
            "errors": ["插件源码编码校验失败"],
            "source_validation": source_validation,
        }

    version = manifest_version(source_root)
    files = release_files(source_root)
    zip_path = output_dir / f"{PLUGIN_ID}-v{version}.zip"
    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    write_deterministic_zip(zip_path, source_root, files)
    zip_validation = validate_release_zip(zip_path)
    if zip_validation["state"] != "valid":
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "blocked",
            "errors": ["发布 ZIP 编码校验失败"],
            "zip_path": str(zip_path),
            "zip_validation": zip_validation,
        }

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    write_sha256_sidecar(sha_path, zip_path, digest)
    recorded = sha_path.read_text(encoding="utf-8").strip()
    expected = f"{digest}  {zip_path.name}"
    if recorded != expected:
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "blocked",
            "errors": ["SHA-256 sidecar 回读不匹配"],
            "zip_path": str(zip_path),
            "sha256_path": str(sha_path),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "state": "built",
        "version": version,
        "framework_digest": framework_digest(source_root),
        "zip_path": str(zip_path),
        "sha256_path": str(sha_path),
        "sha256": digest,
        "packaged_files": len(files),
        "source_encoding": source_validation["state"],
        "source_line_endings": source_validation["line_endings"],
        "zip_encoding": zip_validation["state"],
        "errors": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    source_root = args.plugin_root.resolve()
    output_dir = args.output_dir or source_root.parents[1] / "dist"
    report = build_release(source_root, output_dir)
    # ASCII-safe JSON keeps automation output parseable under Windows PowerShell 5.1 code page 936.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["state"] == "built" else 2


if __name__ == "__main__":
    raise SystemExit(main())
