from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bootstrap_game_pipeline as bootstrap  # noqa: E402
import build_release as release_builder  # noqa: E402
import validate_text_encoding as encoding_validator  # noqa: E402
from pipeline_common import framework_digest, manifest_version  # noqa: E402


CREATED_AT = "2026-08-15T10:00:00Z"


class TextEncodingTests(unittest.TestCase):
    def test_plugin_sources_are_strict_utf8_without_bom(self) -> None:
        result = encoding_validator.validate_plugin_tree(PLUGIN_ROOT)
        self.assertEqual("valid", result["state"], result)
        self.assertGreater(result["checked_files"], 70)
        self.assertEqual([], result["errors"])

    def test_bootstrap_chinese_survives_apply_readback_and_idempotent_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project_root = Path(temporary)
            plan, desired = bootstrap.build_plan(
                project_root,
                "encoding-game",
                "流光里的猫",
                "Godot",
                "human:owner",
                CREATED_AT,
                PLUGIN_ROOT,
            )
            self.assertFalse((project_root / "game-pipeline").exists())
            first = bootstrap.apply_plan(plan, desired, project_root, plan["approval_digest"])
            self.assertTrue(first["applied"])

            expected = {
                "game-pipeline/agents/README.md": "项目 Agent Presets",
                "game-pipeline/approvals/README.md": "人工审批记录",
                "game-pipeline/organization/change-sets/initial-organization.draft.yaml": "建立项目初始多 Agent 编制",
                "AGENTS.md": "项目管线状态位于",
            }
            before: dict[str, bytes] = {}
            for relative, marker in expected.items():
                path = project_root / relative
                before[relative] = path.read_bytes()
                text = before[relative].decode("utf-8", errors="strict")
                self.assertFalse(text.startswith("\ufeff"))
                self.assertNotIn("\ufffd", text)
                self.assertIn(marker, text)

            validation = encoding_validator.validate_project_tree(project_root, PLUGIN_ROOT)
            self.assertEqual("valid", validation["state"], validation)
            self.assertEqual("normal", validation["plugin_lock_state"])
            self.assertEqual(validation["locked_framework_digest"], validation["installed_framework_digest"])

            second_plan, second_desired = bootstrap.build_plan(
                project_root,
                "encoding-game",
                "流光里的猫",
                "Godot",
                "human:owner",
                CREATED_AT,
                PLUGIN_ROOT,
            )
            second = bootstrap.apply_plan(
                second_plan,
                second_desired,
                project_root,
                second_plan["approval_digest"],
            )
            self.assertEqual([], second["applied"])
            for relative, original_bytes in before.items():
                self.assertEqual(original_bytes, (project_root / relative).read_bytes())

    def test_validator_reports_invalid_utf8_bom_and_replacement_character_without_writing(self) -> None:
        cases = {
            "invalid.md": b"\xff",
            "bom.md": b"\xef\xbb\xbfvalid",
            "replacement.md": "bad \ufffd text".encode("utf-8"),
        }
        expected_codes = {"invalid-utf8", "unexpected-bom", "replacement-character"}
        observed: set[str] = set()
        for name, data in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / name
                path.write_bytes(data)
                before = path.read_bytes()
                _, errors = encoding_validator.decode_utf8(before, name)
                observed.update(item["code"] for item in errors)
                self.assertEqual(before, path.read_bytes())
        self.assertEqual(expected_codes, observed)

    def test_release_source_rejects_non_lf_line_endings_without_writing(self) -> None:
        data = b"first\r\nsecond\r\n"
        text, errors = encoding_validator.decode_utf8(
            data,
            "crlf.md",
            require_lf=True,
        )
        self.assertEqual("first\r\nsecond\r\n", text)
        self.assertEqual(["non-lf-line-ending"], [item["code"] for item in errors])

    def test_cli_failure_is_structured_and_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            invalid_root = Path(temporary)
            (invalid_root / "README.md").write_bytes(b"\xff")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_text_encoding.py"), "--plugin-root", str(invalid_root)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(0, completed.returncode)
            report = json.loads(completed.stdout)
            self.assertEqual("invalid", report["state"])
            self.assertTrue(any(item["code"] == "invalid-utf8" for item in report["errors"]))

    def test_release_zip_and_sha256_use_valid_utf8_source_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = release_builder.build_release(PLUGIN_ROOT, Path(temporary))
            self.assertEqual("built", report["state"], report)
            self.assertEqual(manifest_version(PLUGIN_ROOT), report["version"])
            zip_path = Path(report["zip_path"])
            sha_path = Path(report["sha256_path"])
            first_zip_bytes = zip_path.read_bytes()
            self.assertEqual(report["sha256"], hashlib.sha256(zip_path.read_bytes()).hexdigest())
            self.assertEqual(framework_digest(PLUGIN_ROOT), report["framework_digest"])
            self.assertEqual("LF", report["source_line_endings"])
            self.assertEqual(
                f"{report['sha256']}  {zip_path.name}",
                sha_path.read_text(encoding="utf-8").strip(),
            )

            validation = encoding_validator.validate_release_zip(zip_path)
            self.assertEqual("valid", validation["state"], validation)
            with zipfile.ZipFile(zip_path) as archive:
                self.assertTrue(
                    all(member.compress_type == zipfile.ZIP_STORED for member in archive.infolist())
                )
                bootstrap_source = archive.read(
                    "game-production-pipeline/scripts/bootstrap_game_pipeline.py"
                ).decode("utf-8", errors="strict")
                self.assertIn("建立项目初始多 Agent 编制", bootstrap_source)
                self.assertNotIn("\ufffd", bootstrap_source)

            second = release_builder.build_release(PLUGIN_ROOT, Path(temporary))
            self.assertEqual("built", second["state"], second)
            self.assertEqual(report["sha256"], second["sha256"])
            self.assertEqual(first_zip_bytes, zip_path.read_bytes())

    @unittest.skipUnless(shutil.which("git"), "Git is required for archive reproducibility")
    def test_git_archives_build_identically_with_autocrlf_true_and_false(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            shutil.copytree(
                PLUGIN_ROOT,
                repository,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.pyo"),
            )

            def git(*args: str) -> None:
                subprocess.run(
                    ["git", *args],
                    cwd=repository,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )

            git("init", "--quiet")
            git("config", "user.name", "Release Reproducibility Test")
            git("config", "user.email", "release-test@example.invalid")
            git("add", "--all")
            git("commit", "--quiet", "-m", "test fixture")

            reports: list[dict] = []
            for setting in ("true", "false"):
                archive_path = root / f"source-{setting}.zip"
                extracted = root / f"source-{setting}"
                output = root / f"output-{setting}"
                git(
                    "-c",
                    f"core.autocrlf={setting}",
                    "archive",
                    "--format=zip",
                    f"--output={archive_path}",
                    "HEAD",
                )
                with zipfile.ZipFile(archive_path) as archive:
                    archive.extractall(extracted)
                reports.append(release_builder.build_release(extracted, output))

            for report in reports:
                self.assertEqual("built", report["state"], report)
            self.assertEqual(reports[0]["framework_digest"], reports[1]["framework_digest"])
            self.assertEqual(reports[0]["sha256"], reports[1]["sha256"])


if __name__ == "__main__":
    unittest.main()
