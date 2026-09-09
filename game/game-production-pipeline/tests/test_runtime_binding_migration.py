from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bootstrap_game_pipeline as bootstrap  # noqa: E402
import generate_codex_agents as generator  # noqa: E402
import migrate_plugin as migrator  # noqa: E402
import plan_plugin_migration as planner  # noqa: E402
import validate_project_instance as project_validator  # noqa: E402
from pipeline_common import (  # noqa: E402
    AGENT_PRESET_SCHEMA,
    APPROVAL_SCHEMA,
    SKILL_BINDING_CANONICALIZATION,
    directory_digest,
    dump_yaml,
    load_yaml,
    skill_binding_subject_digest,
)


CREATED_AT = "2026-08-24T11:40:21Z"
MIGRATION_AT = "2026-09-02T10:00:00Z"
OLD_VERSION = "0.4.0-alpha.3"
OLD_FRAMEWORK_DIGEST = "16c8b7ec74a098f9382fb1aff1af95d9557f1e4c2dbbfe4dd8caa0033a544621"
OLD_PLUGIN_DIGESTS = {
    "operate-game-production-loop": "fdfa9aeb38d00ea9c2a8ca6a3cd955a77555202450dc34bfb258bbcbd47b525d",
    "review-game-gates": "248d40ed1dbf17fd5f352ed3ec1c2cd1f785bb13aa324de4209a6fba15f84f05",
    "adapt-godot-production": "5f1a2754d7173a1cb35a469da0dd6bbf31fa2badbadff1ff7bae5fa0a1a02624",
}


class RuntimeBindingMigrationTests(unittest.TestCase):
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
        self.project_skill_path = self.project_root / ".agents" / "skills" / "vendor" / "local-art-review"
        self.project_skill_path.mkdir(parents=True)
        (self.project_skill_path / "SKILL.md").write_text(
            "# Local Art Review\n\nProject-owned review method.\n",
            encoding="utf-8",
            newline="\n",
        )
        self.project_skill_digest = directory_digest(self.project_skill_path)
        self._create_six_approved_presets_and_old_adapters()
        self._downgrade_lock_and_managed_block()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_yaml(self, relative_path: str, document: dict) -> None:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_yaml(document), encoding="utf-8", newline="\n")

    def _create_six_approved_presets_and_old_adapters(self) -> None:
        slugs = [
            "project-manager",
            "creative-lead",
            "visual-art-lead",
            "godot-lead",
            "tools-pipeline-lead",
            "quality-lead",
        ]
        binding_entries: list[dict] = []
        for index, slug in enumerate(slugs):
            if index == 0:
                skill_ids = [f"game-production-pipeline:{name}" for name in OLD_PLUGIN_DIGESTS]
                skills = [
                    {
                        "skill_id": f"game-production-pipeline:{name}",
                        "source": "plugin",
                        "path": f"skills/{name}",
                        "digest": digest,
                    }
                    for name, digest in OLD_PLUGIN_DIGESTS.items()
                ]
            elif index == 1:
                skill_ids = ["local-art-review"]
                skills = [
                    {
                        "skill_id": "local-art-review",
                        "source": "project",
                        "path": ".agents/skills/vendor/local-art-review",
                        "digest": self.project_skill_digest,
                    }
                ]
            else:
                skill_ids = []
                skills = []
            approval_id = f"approval:test-game:agent-preset:{slug}"
            metadata = {
                "schema_version": AGENT_PRESET_SCHEMA,
                "preset_id": f"preset:test-game:{slug}",
                "slug": slug,
                "name": f"Test {slug}",
                "description": f"Approved test role for {slug}.",
                "version": "0.1.0",
                "status": "approved",
                "preset_digest": None,
                "approval_id": approval_id,
                "skills": skill_ids,
                "sandbox_mode": "workspace-write",
            }
            body = f"# Role\n\nOperate only as the approved {slug}.\n"
            digest = generator.preset_digest(metadata, body)
            metadata["preset_digest"] = digest
            preset_text = "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body
            preset_path = self.project_root / "game-pipeline" / "agents" / f"{slug}.md"
            preset_path.write_text(preset_text, encoding="utf-8", newline="\n")
            self._write_yaml(
                f"game-pipeline/approvals/agent-preset-{slug}.yaml",
                {
                    "approval": {
                        "schema_version": APPROVAL_SCHEMA,
                        "approval_id": approval_id,
                        "subject_kind": "agent-preset",
                        "subject_id": metadata["preset_id"],
                        "subject_digest": digest,
                        "decision": "approved",
                        "decided_by": "human:owner",
                        "decided_at": CREATED_AT,
                        "evidence": {"source_refs": [f"preset:{slug}#sha256:{digest}"]},
                    }
                },
            )
            binding_entries.append(
                {
                    "preset_id": metadata["preset_id"],
                    "preset_digest": digest,
                    "approval_id": approval_id,
                    "skills": skills,
                }
            )
            adapter_path = self.project_root / ".codex" / "agents" / f"{slug}.toml"
            adapter_path.parent.mkdir(parents=True, exist_ok=True)
            adapter_path.write_text(
                generator.render_adapter(
                    metadata,
                    body,
                    preset_path.relative_to(self.project_root).as_posix(),
                    digest,
                    OLD_VERSION,
                ),
                encoding="utf-8",
                newline="\n",
            )

        binding_document = load_yaml(
            self.project_root / "game-pipeline" / "bindings" / "skill-bindings.yaml"
        )
        binding_document["skill_bindings"]["bindings"] = binding_entries
        old_binding_digest = skill_binding_subject_digest(binding_document["skill_bindings"])
        old_approval_id = f"approval:test-game:skill-binding:{old_binding_digest[:12]}"
        binding_document["skill_binding_proposal"] = {
            "schema_version": "test-game-skill-binding-proposal/v1",
            "proposal_id": "binding:test-game:initial-agent-skills",
            "status": "approved",
            "canonicalization": SKILL_BINDING_CANONICALIZATION,
            "digest_scope": "skill_bindings 中排除 approval_id 的全部字段",
            "subject_digest": old_binding_digest,
            "approval_id": old_approval_id,
            "preset_count": 6,
            "binding_count": 4,
            "unique_skill_count": 4,
        }
        self._write_yaml("game-pipeline/bindings/skill-bindings.yaml", binding_document)
        self._write_yaml(
            f"game-pipeline/approvals/skill-binding-{old_binding_digest[:12]}.yaml",
            {
                "approval": {
                    "schema_version": APPROVAL_SCHEMA,
                    "approval_id": old_approval_id,
                    "subject_kind": "skill-binding",
                    "subject_id": "binding:test-game:initial-agent-skills",
                    "subject_digest": old_binding_digest,
                    "decision": "approved",
                    "decided_by": "human:owner",
                    "decided_at": CREATED_AT,
                    "evidence": {"source_refs": [f"binding:test-game#sha256:{old_binding_digest}"]},
                }
            },
        )

    def _downgrade_lock_and_managed_block(self) -> None:
        agents_path = self.project_root / "AGENTS.md"
        old_block = bootstrap.build_managed_blocks(OLD_VERSION, OLD_FRAMEWORK_DIGEST)["AGENTS.md"]["content"]
        merged, error = bootstrap.merge_managed_block(
            agents_path.read_text(encoding="utf-8"), old_block, markdown=True
        )
        self.assertIsNone(error)
        agents_path.write_text(merged, encoding="utf-8", newline="\n")
        lock_path = self.project_root / "game-pipeline" / "plugin-lock.yaml"
        lock = load_yaml(lock_path)
        lock["plugin_lock"].update(
            {
                "plugin_version": OLD_VERSION,
                "framework_digest": OLD_FRAMEWORK_DIGEST,
                "locked_at": CREATED_AT,
            }
        )
        lock_path.write_text(dump_yaml(lock), encoding="utf-8", newline="\n")

    def _snapshot_without_migration_cache(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.project_root).as_posix(): path.read_bytes()
            for path in self.project_root.rglob("*")
            if path.is_file()
            and not path.relative_to(self.project_root).as_posix().startswith(
                "game-pipeline/.cache/migrations/"
            )
        }

    def test_plan_closes_skill_binding_and_six_adapter_dependencies(self) -> None:
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_ready", plan["outcome"], plan)
        self.assertEqual(3, len(plan["skill_binding_changes"]))
        self.assertTrue(plan["skill_binding_approval"]["required"])
        self.assertEqual(64, len(plan["skill_binding_approval"]["subject_digest"]))
        self.assertEqual(6, len(plan["agent_adapter_actions"]))
        self.assertEqual(
            {"update"}, {item["action"] for item in plan["agent_adapter_actions"]}
        )
        paths = {item["path"] for item in plan["actions"]}
        self.assertIn("game-pipeline/bindings/skill-bindings.yaml", paths)
        self.assertEqual(
            set(OLD_PLUGIN_DIGESTS),
            {item["skill_id"].split(":", 1)[1] for item in plan["skill_binding_changes"]},
        )

    def test_missing_separate_binding_approval_writes_nothing(self) -> None:
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        before = self._snapshot_without_migration_cache()
        with self.assertRaisesRegex(ValueError, "binding_approval_digest"):
            migrator.apply_migration(
                self.project_root,
                PLUGIN_ROOT,
                MIGRATION_AT,
                plan["plan_digest"],
                "human:owner",
            )
        self.assertEqual(before, self._snapshot_without_migration_cache())
        self.assertFalse(
            self.project_root.joinpath("game-pipeline/.cache/migrations", plan["plan_digest"]).exists()
        )

    def test_wrong_separate_binding_approval_writes_nothing(self) -> None:
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        before = self._snapshot_without_migration_cache()
        with self.assertRaisesRegex(ValueError, "binding_approval_digest"):
            migrator.apply_migration(
                self.project_root,
                PLUGIN_ROOT,
                MIGRATION_AT,
                plan["plan_digest"],
                "human:owner",
                "0" * 64,
                "human:owner",
            )
        self.assertEqual(before, self._snapshot_without_migration_cache())

    def test_apply_updates_bindings_and_adapters_and_validates(self) -> None:
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        result = migrator.apply_migration(
            self.project_root,
            PLUGIN_ROOT,
            MIGRATION_AT,
            plan["plan_digest"],
            "human:owner",
            plan["skill_binding_approval"]["subject_digest"],
            "human:owner",
        )
        self.assertEqual("normal", result["project_state"])
        self.assertEqual("no_change", result["idempotent_outcome"])
        binding_document = load_yaml(
            self.project_root / "game-pipeline" / "bindings" / "skill-bindings.yaml"
        )
        self.assertEqual(
            plan["skill_binding_approval"]["subject_digest"],
            binding_document["skill_binding_proposal"]["subject_digest"],
        )
        project_skill = binding_document["skill_bindings"]["bindings"][1]["skills"][0]
        self.assertEqual(self.project_skill_digest, project_skill["digest"])
        for action in plan["agent_adapter_actions"]:
            text = (self.project_root / action["path"]).read_text(encoding="utf-8")
            self.assertIn("# generator-version: 0.5.0-alpha.4", text)
        validation = project_validator.validate_instance(self.project_root, PLUGIN_ROOT)
        self.assertEqual("normal", validation["state"], validation)

    def test_unmanaged_adapter_conflict_blocks_before_writes(self) -> None:
        target = self.project_root / ".codex" / "agents" / "creative-lead.toml"
        target.write_text('name = "user-owned"\n', encoding="utf-8", newline="\n")
        before = self._snapshot_without_migration_cache()
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_blocked", plan["outcome"])
        self.assertIn(".codex/agents/creative-lead.toml", {item["path"] for item in plan["conflicts"]})
        self.assertEqual(before, self._snapshot_without_migration_cache())

    def test_alpha3_valid_bindings_preserved_while_six_adapters_update(self) -> None:
        # Establish a valid team with current, unchanged plugin Skill contents.
        initial = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        migrator.apply_migration(
            self.project_root, PLUGIN_ROOT, MIGRATION_AT, initial["plan_digest"],
            "human:owner", initial["skill_binding_approval"]["subject_digest"], "human:owner",
        )
        digest = "9d1e7797b7dad799317dc9bc1b710f05018bf9fe6ce144fbcb32e17ae4ad3562"
        agents_path = self.project_root / "AGENTS.md"
        old_block = bootstrap.build_managed_blocks("0.5.0-alpha.3", digest)["AGENTS.md"]["content"]
        merged, error = bootstrap.merge_managed_block(
            agents_path.read_text(encoding="utf-8"), old_block, markdown=True
        )
        self.assertIsNone(error)
        agents_path.write_text(merged, encoding="utf-8", newline="\n")
        lock = load_yaml(self.project_root / "game-pipeline/plugin-lock.yaml")
        lock["plugin_lock"].update(plugin_version="0.5.0-alpha.3", framework_digest=digest)
        self._write_yaml("game-pipeline/plugin-lock.yaml", lock)
        for path in self.project_root.glob(".codex/agents/*.toml"):
            path.write_text(path.read_text(encoding="utf-8").replace(
                "# generator-version: 0.5.0-alpha.4", "# generator-version: 0.5.0-alpha.3"
            ), encoding="utf-8", newline="\n")
        before = self._snapshot_without_migration_cache()
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        self.assertEqual("migration_ready", plan["outcome"], plan)
        self.assertEqual([], plan["skill_binding_changes"])
        self.assertFalse(plan["skill_binding_approval"]["required"])
        self.assertEqual(6, len(plan["agent_adapter_actions"]))
        self.assertEqual({"update"}, {a["action"] for a in plan["agent_adapter_actions"]})
        result = migrator.apply_migration(
            self.project_root, PLUGIN_ROOT, MIGRATION_AT, plan["plan_digest"], "human:owner"
        )
        self.assertEqual("normal", result["project_state"])
        self.assertEqual("no_change", result["idempotent_outcome"])
        changed = {a["path"] for a in plan["actions"] if a["action"] != "no_change"}
        for relative, data in before.items():
            if relative not in changed:
                self.assertEqual(data, (self.project_root / relative).read_bytes(), relative)
        migrator.rollback_migration(self.project_root, plan["plan_digest"], plan["plan_digest"])
        self.assertEqual(before, self._snapshot_without_migration_cache())

    def test_post_validation_failure_restores_every_target_and_approval(self) -> None:
        plan = planner.plan_migration(self.project_root, PLUGIN_ROOT, MIGRATION_AT)
        before = self._snapshot_without_migration_cache()
        with mock.patch.object(
            migrator,
            "validate_instance",
            return_value={"state": "blocked", "errors": ["forced postcondition failure"]},
        ):
            with self.assertRaisesRegex(RuntimeError, "已自动回退"):
                migrator.apply_migration(
                    self.project_root,
                    PLUGIN_ROOT,
                    MIGRATION_AT,
                    plan["plan_digest"],
                    "human:owner",
                    plan["skill_binding_approval"]["subject_digest"],
                    "human:owner",
                )
        self.assertEqual(before, self._snapshot_without_migration_cache())
        self.assertFalse((self.project_root / plan["approval_record"]).exists())
        self.assertFalse(
            (self.project_root / plan["skill_binding_approval"]["approval_record"]).exists()
        )
        manifest_path = self.project_root.joinpath(
            "game-pipeline/.cache/migrations", plan["plan_digest"], "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("auto_rolled_back", manifest["status"])


if __name__ == "__main__":
    unittest.main()
