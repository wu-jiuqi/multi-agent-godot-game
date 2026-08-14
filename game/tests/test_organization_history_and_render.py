from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "game" / "scripts" / "validate_organization_registry.py"
RENDERER_PATH = ROOT / "game" / "scripts" / "render_organization.py"
SNAPSHOT_PATH = ROOT / "game" / "contracts" / "examples" / "organization-alpha-snapshot.yaml"
CHANGE_SET_PATH = ROOT / "game" / "contracts" / "examples" / "organization-alpha-change-set.yaml"


def import_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = import_module("organization_validator_history", VALIDATOR_PATH)
RENDERER = import_module("organization_renderer", RENDERER_PATH)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def make_envelope(*, sequence, event_id, mutation_id, event_type, recorded_at, expected_revision, expected_digest, payload, previous_digest):
    event = {
        "schema_version": "0.2-alpha",
        "event_id": event_id,
        "mutation_id": mutation_id,
        "project_id": "sample-game",
        "sequence": sequence,
        "event_type": event_type,
        "occurred_at": recorded_at,
        "recorded_at": recorded_at,
        "actor": {
            "actor_kind": "human" if sequence == 1 else "instance",
            "actor_id": "human:owner" if sequence == 1 else "inst:01K2M3N4P5Q6R7S8T9V0W1X2Y3",
            "acting_position_id": None if sequence == 1 else "pos:sample-game:root:project-agent-architect",
            "role": "project_owner" if sequence == 1 else "project_agent_architect",
        },
        "authorization": {
            "authority_ref": {"id": "AUTH-SAMPLE", "version": "1.0.0", "digest": "3" * 64},
            "approval_refs": ["approval:sample-game:initial-org"] if sequence == 1 else [],
            "change_set_ref": None,
        },
        "causality": {
            "correlation_id": "corr:sample-game:organization-alpha",
            "causation_event_id": None if sequence == 1 else "evt:01K2M3N4P5Q6R7S8T9V0W1X2Y3",
            "request_id": None,
        },
        "concurrency": {
            "expected_organization_revision": expected_revision,
            "expected_snapshot_digest": expected_digest,
            "resulting_organization_revision": sequence,
        },
        "binding_snapshot": {
            "organization_contract": {"id": "ORG-CONTRACT-CORE", "version": "0.2-alpha", "digest": "1" * 64},
            "lifecycle_contract": {"id": "ORG-LIFECYCLE-CORE", "version": "0.2-alpha", "digest": "2" * 64},
            "authority_policy": {"id": "AUTH-SAMPLE", "version": "1.0.0", "digest": "3" * 64},
        },
        "payload": payload,
        "evidence_refs": [],
        "integrity": {
            "canonicalization": "registry-event-canonical-json-v1",
            "digest_algorithm": "sha256",
            "previous_event_digest": previous_digest,
            "event_digest": None,
        },
    }
    event["integrity"]["event_digest"] = VALIDATOR.canonical_event_digest(event)
    return event


def make_history(snapshot_doc, change_set_doc):
    initial = copy.deepcopy(snapshot_doc["organization_snapshot"])
    initial["identity"]["organization_revision"] = 1
    initial["identity"]["updated_at"] = "2026-08-14T08:00:00Z"
    initial["governance"]["pending_change_set_refs"] = []
    initial.pop("event_watermark")
    initial.pop("snapshot_integrity")
    first = make_envelope(
        sequence=1,
        event_id="evt:01K2M3N4P5Q6R7S8T9V0W1X2Y3",
        mutation_id="mut:01K2M3N4P5Q6R7S8T9V0W1X2Y3",
        event_type="core.organization_initialized",
        recorded_at="2026-08-14T08:00:00Z",
        expected_revision=0,
        expected_digest=None,
        payload={"initial_organization": initial},
        previous_digest=None,
    )
    interim, errors = VALIDATOR.replay_history({"organization_event_history": [first]})
    assert not errors
    change_set = change_set_doc["organization_change_set"]
    ref = {
        "change_set_id": change_set["identity"]["change_set_id"],
        "change_set_digest": change_set["integrity"]["change_set_digest"],
        "base_organization_revision": 1,
        "base_snapshot_digest": interim["organization_snapshot"]["snapshot_integrity"]["snapshot_digest"],
        "status": "pending_review",
        "approval_ref": None,
        "submitted_by_event_id": "evt:01K2M3N4P5Q6R7S8T9V0W1X2Y4",
    }
    second = make_envelope(
        sequence=2,
        event_id="evt:01K2M3N4P5Q6R7S8T9V0W1X2Y4",
        mutation_id="mut:01K2M3N4P5Q6R7S8T9V0W1X2Y4",
        event_type="core.change_set_submitted",
        recorded_at="2026-08-14T08:10:00Z",
        expected_revision=1,
        expected_digest=interim["organization_snapshot"]["snapshot_integrity"]["snapshot_digest"],
        payload={"change_set_ref": ref},
        previous_digest=first["integrity"]["event_digest"],
    )
    return {"organization_event_history": [first, second]}


class OrganizationHistoryAndRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = load_yaml(SNAPSHOT_PATH)
        self.change_set = load_yaml(CHANGE_SET_PATH)
        self.history = make_history(self.snapshot, self.change_set)

    def test_history_rebuilds_complete_snapshot(self) -> None:
        self.assertEqual([], VALIDATOR.validate_history(self.history, self.snapshot))

    def test_history_tampering_is_detected(self) -> None:
        self.history["organization_event_history"][1]["actor"]["role"] = "tampered"
        errors = VALIDATOR.validate_history(self.history, self.snapshot)
        self.assertTrue(any("event_digest 不匹配" in error for error in errors))

    def test_mermaid_change_view_is_deterministic_and_auditable(self) -> None:
        args = RENDERER.build_graph(self.snapshot, "change", self.change_set)
        first = RENDERER.render_mermaid(*args)
        second = RENDERER.render_mermaid(*RENDERER.build_graph(self.snapshot, "change", self.change_set))
        self.assertEqual(first, second)
        self.assertIn("pending_review", first)
        self.assertIn("proposed", first)
        self.assertIn("pos:sample-game:design:ui-ux-designer", first)
        self.assertIn(self.change_set["organization_change_set"]["integrity"]["change_set_digest"], first)

    def test_runtime_view_exposes_temporary_instance_and_grant(self) -> None:
        rendered = RENDERER.render_mermaid(*RENDERER.build_graph(self.snapshot, "runtime"))
        self.assertIn("grant:sample-game:", rendered)
        self.assertIn("临时实例", rendered)
        self.assertIn("active 1/2", rendered)

    def test_svg_is_self_contained_and_escapes_text(self) -> None:
        metadata, nodes, edges = RENDERER.build_graph(self.snapshot, "formal")
        rendered = RENDERER.render_svg(metadata, nodes, edges)
        self.assertTrue(rendered.startswith("<svg"))
        self.assertIn("snapshot=", rendered)
        self.assertNotIn("<script", rendered.lower())
        self.assertNotIn("http://", rendered.replace('xmlns="http://www.w3.org/2000/svg"', ""))


if __name__ == "__main__":
    unittest.main()
