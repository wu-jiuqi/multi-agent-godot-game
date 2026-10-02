import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_codex_agents import validate_tool_binding, preset_digest, render_adapter
from pipeline_common import file_digest
from validate_execution_plan import registry_digest
from production_fixtures import fixture, write


class AgentToolBindingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        plan, _, _ = fixture(self.root)
        self.metadata = {"tool_registry_ref": plan["execution_plan"]["tool_registry_ref"],
                         "tool_ids": ["tool:fixture"]}

    def test_known_tools_and_legacy_compatibility(self):
        self.assertEqual([], validate_tool_binding(self.metadata, self.root))
        self.assertEqual([], validate_tool_binding({}, self.root))

    def test_unknown_tool_and_registry_source_drift_block(self):
        m = copy.deepcopy(self.metadata)
        m["tool_ids"] = ["tool:unknown"]
        self.assertTrue(validate_tool_binding(m, self.root))
        write(self.root, "tools/fixture-runner.txt", "unexpected runner")
        self.assertTrue(validate_tool_binding(self.metadata, self.root))

    def test_binding_changes_invalidate_preset_approval(self):
        before = preset_digest(self.metadata, "Produce a report.")
        self.metadata["tool_ids"].append("tool:new")
        self.assertNotEqual(before, preset_digest(self.metadata, "Produce a report."))

    def test_adapter_carries_approved_scope(self):
        self.metadata.update(name="Producer", description="Produce reports", skills=[])
        result = render_adapter(self.metadata, "Produce a report.", "preset.md", "0" * 64, "test")
        self.assertIn("tool:fixture", result)
        self.assertIn("does not grant host tool permissions", result)

    def test_optional_figma_binding_uses_project_snapshot_without_fake_version_or_rollback(self):
        descriptor = write(
            self.root,
            "tools/codex-figma-plugin.adapter.yaml",
            "provider: codex\nname: figma-plugin\nversion: '1'\n",
        )
        registry = {
            "tool_registry": {
                "schema_version": "game-production-tool-registry/v1",
                "registry_id": "tools:figma-ui",
                "version": 1,
                "tools": [
                    {
                        "tool_id": "tool:figma-codex-plugin",
                        "provider": "codex-app-host",
                        "name": "figma",
                        "version": "project-recorded-host-version",
                        "capabilities": [
                            "inspect-design-file",
                            "create-or-update-visual-system",
                            "create-prototype",
                            "capture-design-evidence",
                        ],
                        "permission_scope": ["read:figma", "write:figma", "capture:figma"],
                        "deterministic": False,
                        "rollback": {"supported": False, "procedure_ref": None},
                        "source": {"path": descriptor.relative_to(self.root).as_posix(), "sha256": file_digest(descriptor)},
                        "capability_verification": {
                            "status": "pending",
                            "verified_against": "project-local host schema snapshot",
                            "evidence_refs": [],
                        },
                    }
                ],
            }
        }
        registry["tool_registry"]["integrity"] = {"registry_digest": registry_digest(registry)}
        self.assertFalse(registry["tool_registry"]["tools"][0]["rollback"]["supported"])
        registry_path = write(self.root, "game-pipeline/execution/figma-tools.yaml", registry)
        metadata = {
            "tool_registry_ref": {
                "path": registry_path.relative_to(self.root).as_posix(),
                "sha256": file_digest(registry_path),
            },
            "tool_ids": ["tool:figma-codex-plugin"],
        }
        self.assertEqual([], validate_tool_binding(metadata, self.root))
        metadata.update(name="UI Producer", description="Build Figma visual systems", skills=[])
        rendered = render_adapter(metadata, "Produce the UI visual prototype.", "preset.md", "0" * 64, "test")
        self.assertIn("tool:figma-codex-plugin", rendered)
        self.assertIn("Approved tool registry", rendered)
        self.assertNotIn('"version": "1"', rendered)

    def test_optional_penpot_binding_uses_project_snapshot_without_secret_url(self):
        descriptor = write(
            self.root,
            "tools/penpot-mcp.adapter.yaml",
            "provider: penpot-mcp\nname: penpot-mcp\nversion: 'project-recorded'\n",
        )
        registry = {
            "tool_registry": {
                "schema_version": "game-production-tool-registry/v1",
                "registry_id": "tools:penpot-ui",
                "version": 1,
                "tools": [{
                    "tool_id": "tool:penpot-mcp",
                    "provider": "codex-app-host",
                    "name": "penpot-mcp",
                    "version": "project-recorded-host-version",
                    "capabilities": ["inspect-design-file", "create-or-update-visual-system", "capture-design-evidence"],
                    "permission_scope": ["read:penpot", "write:penpot", "capture:penpot"],
                    "deterministic": False,
                    "rollback": {"supported": False, "procedure_ref": None},
                    "source": {"path": descriptor.relative_to(self.root).as_posix(), "sha256": file_digest(descriptor)},
                    "capability_verification": {"status": "pending", "verified_against": "project-local host schema snapshot", "evidence_refs": []},
                }],
            }
        }
        registry["tool_registry"]["integrity"] = {"registry_digest": registry_digest(registry)}
        registry_path = write(self.root, "game-pipeline/execution/penpot-tools.yaml", yaml.safe_dump(registry, sort_keys=False))
        metadata = {
            "tool_registry_ref": {"path": registry_path.relative_to(self.root).as_posix(), "sha256": file_digest(registry_path)},
            "tool_ids": ["tool:penpot-mcp"],
        }
        self.assertEqual([], validate_tool_binding(metadata, self.root))
        metadata.update(name="UI Producer", description="Build Penpot visual systems", skills=[])
        rendered = render_adapter(metadata, "Produce the UI visual prototype.", "preset.md", "0" * 64, "test")
        self.assertIn("tool:penpot-mcp", rendered)
        self.assertNotIn("userToken=", rendered)


if __name__ == "__main__":
    unittest.main()
