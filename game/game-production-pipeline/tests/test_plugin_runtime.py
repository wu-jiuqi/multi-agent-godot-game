from __future__ import annotations

import copy
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bootstrap_game_pipeline as bootstrap  # noqa: E402
import generate_codex_agents as generator  # noqa: E402
import plan_plugin_migration as migration  # noqa: E402
import validate_project_instance as project_validator  # noqa: E402
import validate_plugin_lock as lock_validator  # noqa: E402
import validate_text_encoding as encoding_validator  # noqa: E402
from pipeline_common import (  # noqa: E402
    AGENT_PRESET_SCHEMA,
    APPROVAL_SCHEMA,
    SKILL_BINDINGS_SCHEMA,
    directory_digest,
    dump_yaml,
    load_yaml,
)


CREATED_AT = "2026-08-14T13:00:00Z"


class PluginRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_plan(self):
        return bootstrap.build_plan(
            self.project_root,
            "test-game",
            "Test Game",
            "Godot",
            "human:owner",
            CREATED_AT,
            PLUGIN_ROOT,
        )

    def apply_bootstrap(self):
        plan, desired = self.make_plan()
        self.assertTrue(plan["can_apply"])
        return bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])

    def write_yaml(self, relative_path: str, value) -> None:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_yaml(value), encoding="utf-8", newline="\n")

    def test_dry_run_is_non_mutating_and_apply_is_idempotent(self) -> None:
        plan, desired = self.make_plan()
        self.assertFalse((self.project_root / "game-pipeline").exists())
        result = bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])
        self.assertIn("game-pipeline/project.yaml", result["applied"])
        self.assertIn("game-pipeline/project-definition/project-brief.yaml", result["applied"])

        second_plan, second_desired = self.make_plan()
        self.assertTrue(second_plan["can_apply"])
        second = bootstrap.apply_plan(
            second_plan,
            second_desired,
            self.project_root,
            second_plan["approval_digest"],
        )
        self.assertEqual([], second["applied"])
        self.assertIn("game-pipeline/project.yaml", second["unchanged"])

    def test_wrong_approval_digest_writes_nothing(self) -> None:
        plan, desired = self.make_plan()
        with self.assertRaisesRegex(ValueError, "approval_digest"):
            bootstrap.apply_plan(plan, desired, self.project_root, "0" * 64)
        self.assertFalse((self.project_root / "game-pipeline").exists())

    def test_conflicting_existing_file_is_not_overwritten(self) -> None:
        target = self.project_root / "game-pipeline" / "project.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("owned-by-user: true\n", encoding="utf-8")
        plan, _ = self.make_plan()
        self.assertFalse(plan["can_apply"])
        self.assertEqual("owned-by-user: true\n", target.read_text(encoding="utf-8"))

    def test_managed_blocks_preserve_unmanaged_content(self) -> None:
        agents = self.project_root / "AGENTS.md"
        ignore = self.project_root / ".gitignore"
        agents.write_text("# User Rules\n\nKeep this.\n", encoding="utf-8")
        ignore.write_text("*.log\n", encoding="utf-8")
        self.apply_bootstrap()
        self.assertIn("Keep this.", agents.read_text(encoding="utf-8"))
        self.assertIn("*.log", ignore.read_text(encoding="utf-8"))
        self.assertIn("game-production-pipeline:start", agents.read_text(encoding="utf-8"))

    def test_bootstrap_registry_and_project_validate(self) -> None:
        self.apply_bootstrap()
        result = project_validator.validate_instance(self.project_root, PLUGIN_ROOT)
        self.assertEqual("normal", result["state"], result)
        self.assertEqual([], result["errors"])

    def test_version_mismatch_is_read_only_and_migration_is_blocked_without_migrator(self) -> None:
        self.apply_bootstrap()
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock_doc = load_yaml(lock_path)
        lock_doc["plugin_lock"]["plugin_version"] = "0.2.0-alpha.1"
        lock_path.write_text(dump_yaml(lock_doc), encoding="utf-8")
        lock_result = lock_validator.evaluate_lock(self.project_root, PLUGIN_ROOT)
        self.assertEqual("read_only", lock_result["state"])
        validation = project_validator.validate_instance(self.project_root, PLUGIN_ROOT)
        self.assertEqual("read_only", validation["state"], validation)
        plan = migration.plan_migration(self.project_root, PLUGIN_ROOT)
        self.assertEqual("migration_blocked", plan["outcome"])
        self.assertFalse(plan["can_apply"])

    def test_old_version_without_current_brief_remains_read_only(self) -> None:
        self.apply_bootstrap()
        brief_path = self.project_root / "game-pipeline" / "project-definition" / "project-brief.yaml"
        brief_path.unlink()
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock_doc = load_yaml(lock_path)
        lock_doc["plugin_lock"]["plugin_version"] = "0.3.0-alpha.1"
        lock_path.write_text(dump_yaml(lock_doc), encoding="utf-8")

        validation = project_validator.validate_instance(self.project_root, PLUGIN_ROOT)
        self.assertEqual("read_only", validation["state"], validation)
        self.assertEqual([], validation["errors"])
        self.assertNotIn("game-pipeline/project-definition/project-brief.yaml", validation["checked"])

    def create_agent_preset(self, *, approved: bool = True, create_approval: bool = True) -> tuple[Path, str]:
        preset_path = self.project_root / "game-pipeline" / "agents" / "milestone-reviewer.md"
        approval_id = "approval:test-game:agent:milestone-reviewer"
        metadata = {
            "schema_version": AGENT_PRESET_SCHEMA,
            "preset_id": "preset:project:test-game:milestone-reviewer",
            "slug": "milestone-reviewer",
            "name": "里程碑审查 Agent",
            "description": "Independent reviewer for approved milestone evidence and gate routing.",
            "version": "0.1.0",
            "status": "approved" if approved else "pending",
            "preset_digest": None,
            "approval_id": approval_id if approved else None,
            "skills": ["review-game-gates"],
            "sandbox_mode": "read-only",
        }
        body = "# Role\n\n独立审查已批准的里程碑证据，绝不自行批准人工门禁。\n"
        digest = generator.preset_digest(metadata, body)
        if approved:
            metadata["preset_digest"] = digest
        preset_text = "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body
        preset_path.write_text(preset_text, encoding="utf-8", newline="\n")

        if approved:
            bindings_path = self.project_root / "game-pipeline" / "bindings" / "skill-bindings.yaml"
            bindings = load_yaml(bindings_path)
            bindings["skill_bindings"]["bindings"] = [
                {
                    "preset_id": metadata["preset_id"],
                    "preset_digest": digest,
                    "approval_id": approval_id,
                    "skills": [
                        {
                            "skill_id": "review-game-gates",
                            "source": "plugin",
                            "path": "skills/review-game-gates",
                            "digest": directory_digest(PLUGIN_ROOT / "skills" / "review-game-gates"),
                        }
                    ],
                }
            ]
            bindings_path.write_text(dump_yaml(bindings), encoding="utf-8")

        if approved and create_approval:
            approval = {
                "approval": {
                    "schema_version": APPROVAL_SCHEMA,
                    "approval_id": approval_id,
                    "subject_kind": "agent-preset",
                    "subject_id": metadata["preset_id"],
                    "subject_digest": digest,
                    "decision": "approved",
                    "decided_by": "human:owner",
                    "decided_at": CREATED_AT,
                    "evidence": {"change_set_id": "chg:test-game:approved"},
                }
            }
            self.write_yaml("game-pipeline/approvals/agent-milestone-reviewer.yaml", approval)
        return preset_path, digest

    def test_pending_preset_remains_visible_but_does_not_generate(self) -> None:
        self.apply_bootstrap()
        self.create_agent_preset(approved=False)
        plan, _ = generator.build_generation_plan(self.project_root, PLUGIN_ROOT)
        self.assertTrue(plan["can_apply"], plan)
        self.assertEqual([], plan["actions"])
        self.assertTrue(any("pending" in warning for warning in plan["warnings"]))

    def test_approved_preset_generates_valid_toml_and_project_validates(self) -> None:
        self.apply_bootstrap()
        _, digest = self.create_agent_preset()
        plan, desired = generator.build_generation_plan(self.project_root, PLUGIN_ROOT)
        self.assertTrue(plan["can_apply"], plan)
        changed = generator.apply_generation(plan, desired, self.project_root)
        self.assertEqual([".codex/agents/milestone-reviewer.toml"], changed)
        adapter_path = self.project_root / changed[0]
        adapter_bytes = adapter_path.read_bytes()
        adapter_text = adapter_bytes.decode("utf-8", errors="strict")
        self.assertFalse(adapter_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn("\ufffd", adapter_text)
        parsed = tomllib.loads(adapter_text)
        self.assertEqual("里程碑审查 Agent", parsed["name"])
        self.assertEqual("read-only", parsed["sandbox_mode"])
        self.assertIn("独立审查已批准的里程碑证据", parsed["developer_instructions"])
        self.assertIn(digest, parsed["developer_instructions"])
        validation = project_validator.validate_instance(self.project_root, PLUGIN_ROOT)
        self.assertEqual("normal", validation["state"], validation)
        encoding = encoding_validator.validate_project_tree(self.project_root, PLUGIN_ROOT)
        self.assertEqual("valid", encoding["state"], encoding)

    def test_missing_approval_blocks_agent_generation(self) -> None:
        self.apply_bootstrap()
        self.create_agent_preset(create_approval=False)
        plan, _ = generator.build_generation_plan(self.project_root, PLUGIN_ROOT)
        self.assertFalse(plan["can_apply"])
        self.assertTrue(any("审批" in error for error in plan["errors"]))

    def test_non_managed_codex_agent_is_never_overwritten(self) -> None:
        self.apply_bootstrap()
        self.create_agent_preset()
        target = self.project_root / ".codex" / "agents" / "milestone-reviewer.toml"
        target.parent.mkdir(parents=True)
        target.write_text('name = "user-owned"\n', encoding="utf-8")
        plan, _ = generator.build_generation_plan(self.project_root, PLUGIN_ROOT)
        self.assertFalse(plan["can_apply"])
        self.assertIn("拒绝覆盖非托管", "\n".join(plan["errors"]))
        self.assertEqual('name = "user-owned"\n', target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
