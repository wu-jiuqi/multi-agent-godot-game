from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bootstrap_game_pipeline as bootstrap  # noqa: E402
from pipeline_common import APPROVAL_SCHEMA, load_yaml, project_brief_subject_digest  # noqa: E402
from validate_project_brief import validate_project_brief  # noqa: E402


CREATED_AT = "2026-08-15T08:00:00Z"


class ProjectBriefTests(unittest.TestCase):
    def test_bootstrap_brief_is_valid_but_blocks_staffing(self) -> None:
        document = bootstrap.build_initial_project_brief(
            "test-game",
            "Test Game",
            "Godot",
            "human:owner",
            CREATED_AT,
        )
        result = validate_project_brief(document, expected_project_id="test-game", approvals={})
        self.assertEqual("valid", result["state"], result)
        self.assertEqual("draft", result["review_status"])
        self.assertEqual("blocked", result["staffing_readiness"])
        self.assertEqual([], result["errors"])

    def test_sample_brief_is_staffing_ready(self) -> None:
        document = load_yaml(PLUGIN_ROOT / "contracts" / "examples" / "sample-project-brief.yaml")
        result = validate_project_brief(document, expected_project_id="sample-game")
        self.assertEqual("valid", result["state"], result)
        self.assertEqual("ready", result["staffing_readiness"])

    def test_unknown_required_domains_cannot_be_marked_ready(self) -> None:
        document = bootstrap.build_initial_project_brief(
            "test-game",
            "Test Game",
            "Godot",
            "human:owner",
            CREATED_AT,
        )
        brief = document["project_brief"]
        brief["staffing_input"] = {
            "responsibility_needs": [
                {
                    "need_id": "need:test-game:placeholder",
                    "responsibility": "占位责任",
                    "rationale_statement_refs": ["stmt:test-game:gameplay"],
                    "expected_artifacts": ["占位产物"],
                    "acceptance_owner_kind": "human",
                }
            ],
            "readiness": "ready",
            "blocker_refs": [],
        }
        for question in brief["open_questions"]:
            question["blocks_staffing"] = False
        brief["integrity"]["subject_digest"] = project_brief_subject_digest(document)
        result = validate_project_brief(document)
        self.assertEqual("invalid", result["state"])
        self.assertTrue(any("必要领域仍全部为 unknown" in error for error in result["errors"]))

    def test_confirmed_brief_requires_matching_human_approval(self) -> None:
        document = load_yaml(PLUGIN_ROOT / "contracts" / "examples" / "sample-project-brief.yaml")
        brief = document["project_brief"]
        digest = project_brief_subject_digest(document)
        approval_id = "approval:sample-game:project-brief:initial"
        brief["integrity"]["subject_digest"] = digest
        brief["review"] = {
            "status": "confirmed",
            "approval_id": approval_id,
            "confirmed_by": "human:owner",
            "confirmed_at": CREATED_AT,
        }
        approval = {
            "schema_version": APPROVAL_SCHEMA,
            "approval_id": approval_id,
            "subject_kind": "project-brief",
            "subject_id": brief["identity"]["brief_id"],
            "subject_digest": digest,
            "decision": "approved",
            "decided_by": "human:owner",
            "decided_at": CREATED_AT,
        }
        result = validate_project_brief(document, approvals={approval_id: approval})
        self.assertEqual("valid", result["state"], result)

        stale = copy.deepcopy(document)
        stale["project_brief"]["statements"][0]["text"] = "审批后被修改的项目目标"
        stale_result = validate_project_brief(stale, approvals={approval_id: approval})
        self.assertEqual("invalid", stale_result["state"])
        self.assertTrue(any("subject_digest" in error for error in stale_result["errors"]))

    def test_non_unknown_statement_requires_registered_source(self) -> None:
        document = load_yaml(PLUGIN_ROOT / "contracts" / "examples" / "sample-project-brief.yaml")
        document["project_brief"]["statements"][0]["source_refs"] = []
        result = validate_project_brief(document)
        self.assertEqual("invalid", result["state"])
        self.assertTrue(any("必须引用事实源" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
