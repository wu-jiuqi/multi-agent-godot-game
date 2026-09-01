from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bootstrap_game_pipeline as bootstrap  # noqa: E402
import migrate_plugin as migrator  # noqa: E402
import plan_plugin_migration as planner  # noqa: E402
import validate_plugin_lock as lock_validator  # noqa: E402
import validate_project_instance as project_validator  # noqa: E402
from pipeline_common import dump_yaml, load_yaml  # noqa: E402


CREATED_AT = "2026-08-14T13:00:00Z"
MIGRATION_AT = "2026-08-15T10:00:00Z"
OLD_VERSION = "0.3.0-alpha.1+codex.20260814152940"
OLD_DIGEST = "04be88f71a343d0bed536d5b4ed7006778a117681cde98ded9ccd48ef144dba5"


class PluginMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name)
        plan, desired = bootstrap.build_plan(
            self.project_root,
            "test-game",
            "Test Game",
            "Godot",
            "human:owner",
            CREATED_AT,
            PLUGIN_ROOT,
        )
        bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])
        self.convert_to_v03()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def convert_to_v03(self) -> None:
        for relative_path in bootstrap.ASSET_AND_LOOP_READMES:
            path = self.project_root / relative_path
            path.unlink(missing_ok=True)
        definition = self.project_root / "game-pipeline" / "project-definition"
        for path in sorted(definition.glob("*")):
            path.unlink()
        definition.rmdir()

        facts_path = self.project_root / "game-pipeline" / "bindings" / "fact-sources.yaml"
        facts = load_yaml(facts_path)
        facts["fact_sources"]["sources"] = [
            item
            for item in facts["fact_sources"]["sources"]
            if item["fact_id"] != "fact:test-game:project-brief"
        ]
        facts_path.write_text(dump_yaml(facts), encoding="utf-8", newline="\n")

        agents_path = self.project_root / "AGENTS.md"
        agents_text = agents_path.read_text(encoding="utf-8")
        old_block = bootstrap.build_managed_blocks(OLD_VERSION, OLD_DIGEST)["AGENTS.md"]["content"]
        merged, error = bootstrap.merge_managed_block(agents_text, old_block, markdown=True)
        self.assertIsNone(error)
        agents_path.write_text(merged, encoding="utf-8", newline="\n")

        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"]["plugin_version"] = OLD_VERSION
        lock["plugin_lock"]["framework_digest"] = OLD_DIGEST
        lock["plugin_lock"]["locked_at"] = CREATED_AT
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")

    def snapshot_files(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.project_root).as_posix(): path.read_bytes()
            for path in self.project_root.rglob("*")
            if path.is_file() and "game-pipeline/.cache/" not in path.relative_to(self.project_root).as_posix()
        }

    def migration_plan(self) -> dict:
        return planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)

    def apply(self) -> tuple[dict, dict]:
        plan = self.migration_plan()
        result = migrator.apply_migration(
            self.project_root,
            PLUGIN_ROOT,
            MIGRATION_AT,
            plan["plan_digest"],
            "human:owner",
        )
        return plan, result

    def test_dry_run_is_non_mutating_and_reports_exact_actions(self) -> None:
        before = self.snapshot_files()
        plan = self.migration_plan()
        after = self.snapshot_files()
        self.assertEqual(before, after)
        self.assertEqual("migration_ready", plan["outcome"], plan)
        self.assertTrue(plan["can_apply"])
        self.assertEqual("0.4.0-alpha.4", plan["to_version"])
        self.assertEqual(
            [
                "game-pipeline/project-definition/project-brief.yaml",
                "game-pipeline/project-definition/README.md",
                "game-pipeline/bindings/fact-sources.yaml",
                *bootstrap.ASSET_AND_LOOP_READMES,
                "AGENTS.md",
                "game-pipeline/plugin-lock.yaml",
            ],
            [item["path"] for item in plan["actions"]],
        )

    def test_wrong_approval_digest_writes_nothing(self) -> None:
        before = self.snapshot_files()
        with self.assertRaisesRegex(ValueError, "approval_digest"):
            migrator.apply_migration(
                self.project_root,
                PLUGIN_ROOT,
                MIGRATION_AT,
                "0" * 64,
                "human:owner",
            )
        self.assertEqual(before, self.snapshot_files())
        self.assertFalse((self.project_root / "game-pipeline" / ".cache" / "migrations").exists())

    def test_apply_validates_and_is_idempotent(self) -> None:
        plan, result = self.apply()
        self.assertEqual("applied", result["mode"])
        self.assertEqual("normal", result["plugin_lock_state"])
        self.assertEqual("normal", result["project_state"])
        self.assertEqual("no_change", result["idempotent_outcome"])

        brief = (self.project_root / "game-pipeline" / "project-definition" / "project-brief.yaml").read_text(encoding="utf-8")
        self.assertIn("核心玩法尚待项目所有者提供", brief)
        facts = load_yaml(self.project_root / "game-pipeline" / "bindings" / "fact-sources.yaml")
        self.assertTrue(
            any(item["fact_id"] == "fact:test-game:project-brief" for item in facts["fact_sources"]["sources"])
        )
        agents = (self.project_root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("0.4.0-alpha.4", agents)
        self.assertIn("初始项目简报位于", agents)
        self.assertEqual("normal", lock_validator.evaluate_lock(self.project_root, PLUGIN_ROOT)["state"])
        self.assertEqual("normal", project_validator.validate_instance(self.project_root, PLUGIN_ROOT)["state"])
        self.assertEqual("no_change", self.migration_plan()["outcome"])

        manifest_path = Path(result["backup"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("applied", manifest["status"])
        self.assertEqual(plan["plan_digest"], manifest["plan_digest"])

    def test_rollback_restores_exact_bytes_and_removes_created_files(self) -> None:
        before = self.snapshot_files()
        plan, _ = self.apply()
        unrelated = self.project_root / "user-owned.txt"
        unrelated.write_text("preserve me\n", encoding="utf-8")
        result = migrator.rollback_migration(
            self.project_root,
            plan["plan_digest"],
            plan["plan_digest"],
        )
        self.assertEqual("rolled_back", result["mode"])
        after = self.snapshot_files()
        after.pop("user-owned.txt")
        self.assertEqual(before, after)
        self.assertEqual("preserve me\n", unrelated.read_text(encoding="utf-8"))
        self.assertFalse((self.project_root / "game-pipeline" / "project-definition").exists())
        self.assertEqual("read_only", lock_validator.evaluate_lock(self.project_root, PLUGIN_ROOT)["state"])

    def test_rollback_refuses_to_overwrite_post_migration_edit(self) -> None:
        plan, _ = self.apply()
        agents = self.project_root / "AGENTS.md"
        agents.write_text(agents.read_text(encoding="utf-8") + "\nUser edit.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "迁移后文件已变化"):
            migrator.rollback_migration(self.project_root, plan["plan_digest"], plan["plan_digest"])
        self.assertIn("User edit.", agents.read_text(encoding="utf-8"))

    def test_validation_failure_auto_rolls_back(self) -> None:
        before = self.snapshot_files()
        plan = self.migration_plan()
        with mock.patch.object(migrator, "validate_instance", return_value={"state": "blocked", "errors": ["forced"]}):
            with self.assertRaisesRegex(RuntimeError, "已自动回退"):
                migrator.apply_migration(
                    self.project_root,
                    PLUGIN_ROOT,
                    MIGRATION_AT,
                    plan["plan_digest"],
                    "human:owner",
                )
        self.assertEqual(before, self.snapshot_files())
        manifest = json.loads(
            (self.project_root / "game-pipeline" / ".cache" / "migrations" / plan["plan_digest"] / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("auto_rolled_back", manifest["status"])

    def test_unknown_v03_framework_digest_is_blocked(self) -> None:
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"]["framework_digest"] = "f" * 64
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")
        plan = self.migration_plan()
        self.assertEqual("migration_blocked", plan["outcome"])
        self.assertFalse(plan["can_apply"])
        self.assertTrue(any("白名单" in error for error in plan["errors"]))

    def test_all_published_v03_framework_digests_are_accepted(self) -> None:
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        published_digests = (
            "837c74cccfc0ac36b26dffb3571dcc10fc8d88cf41032feb18e65c5c8382be45",
            "698775c8179127be553b46b948d1b481a890a281e81b2385c59bcdf5399a0a7c",
            "04be88f71a343d0bed536d5b4ed7006778a117681cde98ded9ccd48ef144dba5",
        )
        for digest in published_digests:
            with self.subTest(digest=digest):
                lock = load_yaml(lock_path)
                lock["plugin_lock"]["framework_digest"] = digest
                lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")
                plan = self.migration_plan()
                self.assertEqual("migration_ready", plan["outcome"], plan)

    def test_existing_user_project_brief_is_not_overwritten(self) -> None:
        brief = self.project_root / "game-pipeline" / "project-definition" / "project-brief.yaml"
        brief.parent.mkdir(parents=True)
        brief.write_text("user-owned: true\n", encoding="utf-8")
        plan = self.migration_plan()
        self.assertEqual("migration_blocked", plan["outcome"])
        self.assertTrue(any(item["path"].endswith("project-brief.yaml") for item in plan["conflicts"]))
        self.assertEqual("user-owned: true\n", brief.read_text(encoding="utf-8"))


class Alpha2ToAlpha4MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name)
        plan, desired = bootstrap.build_plan(
            self.project_root,
            "test-game",
            "Test Game",
            "Godot",
            "human:owner",
            CREATED_AT,
            PLUGIN_ROOT,
        )
        bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])
        for relative_path in bootstrap.ASSET_AND_LOOP_READMES:
            (self.project_root / relative_path).unlink(missing_ok=True)
        self.old_digest = "3589bce5cf4388f91a08f12acb5d90679256191d5085e65687d06a635bbdcd32"

        agents_path = self.project_root / "AGENTS.md"
        old_block = bootstrap.build_managed_blocks(
            "0.4.0-alpha.2", self.old_digest
        )["AGENTS.md"]["content"]
        merged, error = bootstrap.merge_managed_block(
            agents_path.read_text(encoding="utf-8"), old_block, markdown=True
        )
        self.assertIsNone(error)
        agents_path.write_text(merged, encoding="utf-8", newline="\n")

        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"].update(
            {
                "plugin_version": "0.4.0-alpha.2",
                "framework_digest": self.old_digest,
                "locked_at": CREATED_AT,
            }
        )
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")

        self.history_path = (
            self.project_root
            / "game-pipeline"
            / "loops"
            / "registry"
            / "test-loop"
            / "event-history.yaml"
        )
        self.history_path.parent.mkdir(parents=True)
        self.history_path.write_bytes(b"event_history: []\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_dry_run_only_plans_managed_metadata_and_records_history_digest(self) -> None:
        before = self.history_path.read_bytes()
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_ready", plan["outcome"], plan)
        self.assertEqual("0.4.0-alpha.2", plan["from_version"])
        self.assertEqual("0.4.0-alpha.4", plan["to_version"])
        self.assertEqual(
            [*bootstrap.ASSET_AND_LOOP_READMES, "AGENTS.md", "game-pipeline/plugin-lock.yaml"],
            [item["path"] for item in plan["actions"]],
        )
        relative_history = self.history_path.relative_to(self.project_root).as_posix()
        self.assertIn(relative_history, plan["history_digests_before"])
        self.assertEqual(before, self.history_path.read_bytes())

    def test_apply_preserves_event_history_bytes(self) -> None:
        before = self.history_path.read_bytes()
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        result = migrator.apply_migration(
            self.project_root,
            PLUGIN_ROOT,
            MIGRATION_AT,
            plan["plan_digest"],
            "human:owner",
        )
        self.assertEqual("applied", result["mode"])
        self.assertEqual(before, self.history_path.read_bytes())
        self.assertEqual(
            "normal", lock_validator.evaluate_lock(self.project_root, PLUGIN_ROOT)["state"]
        )


class Alpha3ToAlpha4MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name)
        plan, desired = bootstrap.build_plan(
            self.project_root,
            "test-game",
            "Test Game",
            "Godot",
            "human:owner",
            CREATED_AT,
            PLUGIN_ROOT,
        )
        bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])
        for relative_path in bootstrap.ASSET_AND_LOOP_READMES:
            (self.project_root / relative_path).unlink(missing_ok=True)
        self.history_path = (
            self.project_root
            / "game-pipeline"
            / "loops"
            / "registry"
            / "test-loop"
            / "event-history.yaml"
        )
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_bytes(b"event_history: []\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def set_alpha3_lock(self, digest: str) -> None:
        agents_path = self.project_root / "AGENTS.md"
        old_block = bootstrap.build_managed_blocks("0.4.0-alpha.3", digest)["AGENTS.md"]["content"]
        merged, error = bootstrap.merge_managed_block(
            agents_path.read_text(encoding="utf-8"), old_block, markdown=True
        )
        self.assertIsNone(error)
        agents_path.write_text(merged, encoding="utf-8", newline="\n")
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"].update(
            {
                "plugin_version": "0.4.0-alpha.3",
                "framework_digest": digest,
                "locked_at": CREATED_AT,
            }
        )
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")

    def test_published_and_p0_baseline_alpha3_digests_are_supported(self) -> None:
        for digest in (
            "16c8b7ec74a098f9382fb1aff1af95d9557f1e4c2dbbfe4dd8caa0033a544621",
            "f7c7dedc3910401865f58a9902c5d84841998b62fc4c5b9cbfc24f5ee06d4e6f",
        ):
            with self.subTest(digest=digest):
                self.set_alpha3_lock(digest)
                plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
                self.assertEqual("migration_ready", plan["outcome"], plan)
                self.assertEqual("0.4.0-alpha.4", plan["to_version"])

    def test_apply_creates_asset_control_plane_and_preserves_history(self) -> None:
        self.set_alpha3_lock("16c8b7ec74a098f9382fb1aff1af95d9557f1e4c2dbbfe4dd8caa0033a544621")
        before = self.history_path.read_bytes()
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        result = migrator.apply_migration(
            self.project_root,
            PLUGIN_ROOT,
            MIGRATION_AT,
            plan["plan_digest"],
            "human:owner",
        )
        self.assertEqual("applied", result["mode"])
        self.assertEqual(before, self.history_path.read_bytes())
        for relative_path in bootstrap.ASSET_AND_LOOP_READMES:
            self.assertTrue((self.project_root / relative_path).is_file())

    def test_apply_preserves_existing_readme_asset_content_and_ui_bytes(self) -> None:
        self.set_alpha3_lock("16c8b7ec74a098f9382fb1aff1af95d9557f1e4c2dbbfe4dd8caa0033a544621")
        readme_path = self.project_root / "game-pipeline" / "assets" / "contracts" / "README.md"
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        readme_path.write_bytes("# 用户资产规则\n禁止覆盖。\n".encode("utf-8"))
        asset_path = self.project_root / "game" / "assets" / "ui" / "existing-theme.tres"
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(b"[gd_resource format=3]\n")
        ui_path = self.project_root / "game" / "scenes" / "ui" / "screen-flow.tscn"
        ui_path.parent.mkdir(parents=True, exist_ok=True)
        ui_path.write_bytes(b"[gd_scene format=3]\n")
        before = {
            readme_path: readme_path.read_bytes(),
            asset_path: asset_path.read_bytes(),
            ui_path: ui_path.read_bytes(),
        }

        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        result = migrator.apply_migration(
            self.project_root,
            PLUGIN_ROOT,
            MIGRATION_AT,
            plan["plan_digest"],
            "human:owner",
        )

        self.assertEqual("applied", result["mode"])
        for path, expected in before.items():
            self.assertEqual(expected, path.read_bytes(), path)

    def test_unknown_alpha3_digest_is_blocked(self) -> None:
        self.set_alpha3_lock("f" * 64)
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_blocked", plan["outcome"])
        self.assertFalse(plan["can_apply"])
        self.assertIn("白名单", "\n".join(plan["errors"]))


if __name__ == "__main__":
    unittest.main()
