import copy
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_codex_figma_plugin_is_an_explicit_agent_tool_binding(self):
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
                        "provider": "codex",
                        "name": "figma-plugin",
                        "version": "1",
                        "capabilities": [
                            "inspect-design-file",
                            "compose-visual-system",
                            "create-prototype",
                            "capture-design-evidence",
                        ],
                        "permission_scope": ["read:figma", "write:figma", "capture:figma"],
                        "deterministic": False,
                        "rollback": {
                            "supported": True,
                            "procedure_ref": "restore Figma file version",
                        },
                        "source": {"path": descriptor.relative_to(self.root).as_posix(), "sha256": file_digest(descriptor)},
                    }
                ],
            }
        }
        registry["tool_registry"]["integrity"] = {"registry_digest": registry_digest(registry)}
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


if __name__ == "__main__":
    unittest.main()
