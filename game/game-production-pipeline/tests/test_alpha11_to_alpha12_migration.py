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
import validate_plugin_lock as lock_validator  # noqa: E402
import validate_project_instance as project_validator  # noqa: E402
from pipeline_common import dump_yaml, framework_digest, load_yaml  # noqa: E402


CREATED_AT = "2026-10-04T10:00:00Z"
MIGRATION_AT = "2026-10-05T10:00:00Z"
FROM_VERSION = "0.5.0-alpha.11"
TO_VERSION = "0.5.0-alpha.13"
SUPPORTED_DIGESTS = (
    "748a68f2325dc832f02c2f76e8d6c7138574bcc7015607c40805d7b678df1a23",
    "e7b6fa8a8422b73c7fbfd66d2f826ac08367540dccfbf2b4ca439ecfe3876e10",
)


class Alpha11ToAlpha13MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name)
        plan, desired = bootstrap.build_plan(
            self.project_root, "test-game", "Test Game", "Godot", "human:owner",
            CREATED_AT, PLUGIN_ROOT,
        )
        bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])
        self.fact_path = self.project_root / "game" / "scenes" / "prototype.tscn"
        self.fact_path.parent.mkdir(parents=True, exist_ok=True)
        self.fact_path.write_bytes(b"[gd_scene format=3]\n")
        self.history_path = self.project_root / "game-pipeline" / "loops" / "registry" / "test-loop" / "event-history.yaml"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_bytes(b"event_history: []\n")
        self.set_alpha11_lock(SUPPORTED_DIGESTS[0])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def set_alpha11_lock(self, digest: str) -> None:
        agents_path = self.project_root / "AGENTS.md"
        old_block = bootstrap.build_managed_blocks(FROM_VERSION, digest)["AGENTS.md"]["content"]
        merged, error = bootstrap.merge_managed_block(
            agents_path.read_text(encoding="utf-8"), old_block, markdown=True,
        )
        self.assertIsNone(error)
        agents_path.write_text(merged, encoding="utf-8", newline="\n")
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"].update(
            plugin_version=FROM_VERSION, framework_digest=digest, locked_at=CREATED_AT,
        )
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")

    def snapshot_without_cache(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.project_root).as_posix(): path.read_bytes()
            for path in self.project_root.rglob("*")
            if path.is_file() and "game-pipeline/.cache/" not in path.relative_to(self.project_root).as_posix()
        }

    def test_both_known_alpha11_digests_have_non_mutating_metadata_plan(self) -> None:
        for digest in SUPPORTED_DIGESTS:
            with self.subTest(digest=digest):
                self.set_alpha11_lock(digest)
                before = self.snapshot_without_cache()
                plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
                self.assertEqual("migration_ready", plan["outcome"], plan)
                self.assertEqual(FROM_VERSION, plan["from_version"])
                self.assertEqual(TO_VERSION, plan["to_version"])
                self.assertEqual("migrations/0-5-0-alpha-11__0-5-0-alpha-13.py", plan["migrator"])
                self.assertEqual(
                    ["AGENTS.md", "game-pipeline/plugin-lock.yaml"],
                    [action["path"] for action in plan["actions"]],
                )
                self.assertFalse(plan["skill_binding_approval"]["required"])
                self.assertEqual(before, self.snapshot_without_cache())

    def test_unknown_alpha11_digest_is_blocked_without_writes(self) -> None:
        self.set_alpha11_lock("f" * 64)
        before = self.snapshot_without_cache()
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_blocked", plan["outcome"], plan)
        self.assertFalse(plan["can_apply"])
        self.assertIn("白名单", "\n".join(plan["errors"]))
        self.assertEqual(before, self.snapshot_without_cache())

    def test_apply_validates_is_idempotent_and_rolls_back_exactly(self) -> None:
        for digest in SUPPORTED_DIGESTS:
            with self.subTest(digest=digest):
                self.set_alpha11_lock(digest)
                before = self.snapshot_without_cache()
                plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
                result = migrator.apply_migration(
                    self.project_root, PLUGIN_ROOT, MIGRATION_AT,
                    plan["plan_digest"], "human:owner",
                )
                self.assertEqual("applied", result["mode"])
                self.assertEqual("normal", result["plugin_lock_state"])
                self.assertEqual("normal", result["project_state"])
                self.assertEqual("no_change", result["idempotent_outcome"])
                self.assertEqual("normal", lock_validator.evaluate_lock(self.project_root, PLUGIN_ROOT)["state"])
                self.assertEqual("normal", project_validator.validate_instance(self.project_root, PLUGIN_ROOT)["state"])
                lock = load_yaml(self.project_root / "game-pipeline" / "plugin-lock.yaml")["plugin_lock"]
                self.assertEqual(TO_VERSION, lock["plugin_version"])
                self.assertEqual(framework_digest(PLUGIN_ROOT), lock["framework_digest"])
                self.assertEqual("no_change", planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)["outcome"])
                self.assertEqual(before["game/scenes/prototype.tscn"], self.fact_path.read_bytes())
                self.assertEqual(before["game-pipeline/loops/registry/test-loop/event-history.yaml"], self.history_path.read_bytes())
                rollback = migrator.rollback_migration(
                    self.project_root, plan["plan_digest"], plan["plan_digest"],
                )
                self.assertEqual("rolled_back", rollback["mode"])
                self.assertEqual(before, self.snapshot_without_cache())


if __name__ == "__main__":
    unittest.main()
