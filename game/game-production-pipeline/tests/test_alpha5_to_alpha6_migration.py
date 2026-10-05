from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bootstrap_game_pipeline as bootstrap  # noqa: E402
import migrate_plugin as migrator  # noqa: E402
import plan_plugin_migration as planner  # noqa: E402
from pipeline_common import dump_yaml, framework_digest, load_yaml  # noqa: E402


CREATED_AT = "2026-09-28T09:00:00Z"
MIGRATION_AT = "2026-09-28T10:00:00Z"
ALPHA5_VERSION = "0.5.0-alpha.5"
ALPHA5_FRAMEWORK_DIGEST = "a04796a0f3d0b2fdc63237524122e24def932e4de1761367425aa60785e7018b"


class Alpha5ToAlpha6MigrationTests(unittest.TestCase):
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
        self._downgrade_to_alpha5()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _downgrade_to_alpha5(self) -> None:
        agents_path = self.project_root / "AGENTS.md"
        current_block = bootstrap.build_managed_blocks(
            bootstrap.manifest_version(PLUGIN_ROOT), framework_digest(PLUGIN_ROOT)
        )["AGENTS.md"]["content"]
        old_block = bootstrap.build_managed_blocks(
            ALPHA5_VERSION, ALPHA5_FRAMEWORK_DIGEST
        )["AGENTS.md"]["content"]
        merged, error = bootstrap.merge_managed_block(
            agents_path.read_text(encoding="utf-8"), current_block, markdown=True
        )
        self.assertIsNone(error)
        merged, error = bootstrap.merge_managed_block(merged, old_block, markdown=True)
        self.assertIsNone(error)
        agents_path.write_text(merged, encoding="utf-8", newline="\n")

        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"].update(
            {
                "plugin_version": ALPHA5_VERSION,
                "framework_digest": ALPHA5_FRAMEWORK_DIGEST,
                "locked_at": CREATED_AT,
            }
        )
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")

    def test_alpha5_digest_is_explicitly_supported(self) -> None:
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_ready", plan["outcome"], plan)
        self.assertEqual(ALPHA5_VERSION, plan["from_version"])
        self.assertEqual("0.5.0-alpha.12", plan["to_version"])
        self.assertEqual(
            ["AGENTS.md", "game-pipeline/plugin-lock.yaml"],
            [item["path"] for item in plan["actions"]],
        )

    def test_unknown_alpha5_digest_is_blocked(self) -> None:
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"]["framework_digest"] = "f" * 64
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_blocked", plan["outcome"])
        self.assertFalse(plan["can_apply"])
        self.assertIn("白名单", "\n".join(plan["errors"]))

    def test_apply_updates_managed_metadata_and_is_idempotent(self) -> None:
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        result = migrator.apply_migration(
            self.project_root,
            PLUGIN_ROOT,
            MIGRATION_AT,
            plan["plan_digest"],
            "human:owner",
        )
        self.assertEqual("applied", result["mode"])
        self.assertEqual("normal", result["plugin_lock_state"])
        self.assertEqual("normal", result["project_state"])
        self.assertEqual("no_change", result["idempotent_outcome"])
        self.assertEqual("no_change", planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)["outcome"])
        lock = load_yaml(self.project_root / "game-pipeline" / "plugin-lock.yaml")
        self.assertEqual("0.5.0-alpha.12", lock["plugin_lock"]["plugin_version"])
        self.assertEqual(framework_digest(PLUGIN_ROOT), lock["plugin_lock"]["framework_digest"])


if __name__ == "__main__":
    unittest.main()
