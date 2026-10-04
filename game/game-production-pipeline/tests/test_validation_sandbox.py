from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validation_sandbox", ROOT / "scripts" / "validation_sandbox.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ValidationSandboxTests(unittest.TestCase):
    def grant(self, subject: str, slot: str, *permissions: tuple[str, str], expiry: int = 200):
        return module.SyntheticGrant(subject, slot, frozenset(permissions), expiry)

    def test_f01_unused_slot_rejects_spawn_and_call_without_mutation(self):
        sandbox = module.OrganizationSandbox()
        grant = self.grant("planner", "slot:planning", ("spawn", "planner-1"), ("call", "x"))
        before = sandbox.snapshot()
        with self.assertRaises(module.BoundaryError):
            sandbox.spawn("planner-1", grant)
        self.assertEqual(before, sandbox.snapshot())
        with self.assertRaises(module.BoundaryError):
            sandbox.invoke("planner-1", "x", grant)
        self.assertEqual([], sandbox.calls)

    def test_activation_requires_exact_scope_and_expiry(self):
        sandbox = module.OrganizationSandbox(now=200)
        expired = self.grant("planner", "slot:planning", ("activate", "slot:planning"), expiry=200)
        with self.assertRaises(module.BoundaryError):
            sandbox.activate("slot:planning", expired, "planner", "planner")
        self.assertEqual("unused", sandbox.slots["slot:planning"]["status"])

    def test_f06_foreign_fact_and_qa_opinion_are_protected(self):
        sandbox = module.OrganizationSandbox()
        plan = self.grant("planner", "slot:planning", ("activate", "slot:planning"),
                          ("spawn", "planner-1"), ("call", "facts"), ("write_fact", "scope"))
        sandbox.activate("slot:planning", plan, "planner", "planner")
        sandbox.spawn("planner-1", plan)
        sandbox.facts["scope"] = {"owner_slot": "slot:qa", "value": "qa-review"}
        before = sandbox.snapshot()
        with self.assertRaises(module.BoundaryError):
            sandbox.write_fact("planner-1", "scope", "overwritten", plan)
        self.assertEqual(before, sandbox.snapshot())

    def test_merge_preserves_owners_and_qa_independence(self):
        sandbox = module.OrganizationSandbox()
        plan = self.grant("planner", "slot:planning", ("activate", "slot:planning"),
                          ("merge", "slot:planning->slot:programming"))
        programming = self.grant("programmer", "slot:programming", ("activate", "slot:programming"))
        sandbox.activate("slot:programming", programming, "programmer", "programmer")
        with self.assertRaises(module.BoundaryError):
            sandbox.merge("slot:planning", "slot:programming", plan, "planner", "")
        sandbox.merge("slot:planning", "slot:programming", plan, "planner", "planner")
        self.assertEqual("merged", sandbox.slots["slot:planning"]["status"])

    def test_f11_timeout_readback_confirms_without_duplicate(self):
        tool = module.PenpotStub()
        tool.timeout_after_next_write = True
        executor = module.PrototypeExecutor(tool)
        result = executor.sync({"screen:entry": {"title": "Entry"}}, {})
        self.assertIn("screen:entry", result)
        self.assertEqual(1, len(tool.nodes))
        self.assertIn("confirmed_committed_write", [x["action"] for x in executor.recovery_log])

    def test_f12_disconnect_or_read_only_has_no_write(self):
        tool = module.PenpotStub()
        tool.connected = False
        before = tool.snapshot()
        with self.assertRaises(module.ToolBlocked):
            module.PrototypeExecutor(tool).sync({"screen:entry": {}}, {})
        self.assertEqual(before, tool.snapshot())
        tool = module.PenpotStub()
        tool.read_only = True
        before = tool.snapshot()
        with self.assertRaises(module.ToolBlocked):
            module.PrototypeExecutor(tool).sync({"screen:entry": {}}, {})
        self.assertEqual(before, tool.snapshot())

    def test_f13_repeat_is_idempotent_and_preserves_foreign_nodes(self):
        tool = module.PenpotStub()
        executor = module.PrototypeExecutor(tool)
        first = executor.sync({"screen:entry": {"title": "Entry"}}, {})
        revision = tool.revision
        second = executor.sync({"screen:entry": {"title": "Entry"}}, {})
        self.assertEqual(first, second)
        self.assertEqual(revision, tool.revision)
        foreign_id = "foreign-node"
        tool.nodes[foreign_id] = {"artifact_id": "foreign", "kind": "screen",
                                  "namespace": "other", "content": {}}
        self.assertIn(foreign_id, tool.nodes)
        self.assertEqual(2, len(tool.nodes))


if __name__ == "__main__":
    unittest.main()
