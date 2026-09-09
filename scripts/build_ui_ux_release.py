#!/usr/bin/env python3
"""Build the standalone UI/UX Skill snapshot for the repository release."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def build_release(repo_root: Path, output_dir: Path) -> dict:
    source = repo_root / "skills" / "ui-ux-pro-max"
    manifest = repo_root / "game" / "game-production-pipeline" / ".codex-plugin" / "plugin.json"
    version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    members = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink is not a release source: {path}")
        data = path.read_bytes()
        text = data.decode("utf-8")
        if text.startswith("\ufeff") or "\r" in text or "\ufffd" in text:
            raise ValueError(f"Source must be UTF-8 without BOM, replacement characters or CR: {path}")
        members[f"ui-ux-pro-max/{path.relative_to(source).as_posix()}"] = data
    if "ui-ux-pro-max/SKILL.md" not in members:
        raise ValueError("Missing Skill entry")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"ui-ux-pro-max-v{version}.zip"
    temporary = target.with_suffix(".zip.tmp")
    # Exclusive creation also prevents a competing build from being overwritten.
    with temporary.open("xb") as handle:
        try:
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_STORED) as archive:
                for name, data in members.items():
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    info.compress_type = zipfile.ZIP_STORED
                    archive.writestr(info, data)
        except Exception:
            handle.close()
            temporary.unlink()
            raise
    temporary.replace(target)
    with zipfile.ZipFile(target) as archive:
        if {name: archive.read(name) for name in archive.namelist()} != members:
            raise ValueError("Archive readback differs from source")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    sidecar = target.with_suffix(".zip.sha256")
    sidecar.write_text(f"{digest}  {target.name}\n", encoding="utf-8", newline="\n")
    return {"state": "built", "version": version, "packaged_files": len(members),
            "zip_path": str(target.resolve()), "sha256_path": str(sidecar.resolve()), "sha256": digest}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "dist")
    args = parser.parse_args()
    print(json.dumps(build_release(REPO_ROOT, args.output_dir), ensure_ascii=True, indent=2))
