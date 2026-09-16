from __future__ import annotations
import copy
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from pipeline_common import load_yaml
from validate_production_charter import (
    evaluate_authority, load_approvals, validate_charter, validate_production_charter,
)
from production_fixtures import fixture, approve_charter, write


class ProductionCharterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, self.charter, self.approvals = fixture(self.root)

    def validate(self):
        return validate_production_charter(self.charter, project_root=self.root, approvals=self.approvals)

    def test_explicit_launch_allows_bounded_production(self):
        self.assertTrue(self.validate()["launch_ready"], self.validate())
        result = evaluate_authority(self.charter, "write_workspace", project_root=self.root,
                                    approvals=self.approvals, path="outputs/item.txt")
        self.assertTrue(result["allowed"], result)

    def test_draft_never_grants_authority(self):
        self.charter["production_charter"]["review"]["status"] = "draft"
        self.assertFalse(self.validate()["launch_ready"])
        result = evaluate_authority(self.charter, "write_workspace", project_root=self.root,
                                    approvals=self.approvals, path="outputs/item.txt")
        self.assertFalse(result["allowed"])

    def test_status_alone_cannot_sign_initial_gates(self):
        self.approvals.pop("approval:fixture:D2")
        self.assertFalse(self.validate()["launch_ready"])

    def test_agent_cannot_sign_human_launch_record(self):
        self.approvals["approval:fixture:charter"]["decided_by"] = "position:sample-game:producer"
        self.assertFalse(self.validate()["launch_ready"])

    def test_approval_source_and_subject_kind_are_required(self):
        approval = self.approvals["approval:fixture:charter"]
        approval["evidence"] = {}
        self.assertFalse(self.validate()["launch_ready"])
        approval["evidence"] = {"source_ref": "fixture://owner"}
        approval["subject_kind"] = "some-other-subject"
        self.assertFalse(self.validate()["launch_ready"])

    def test_changed_budget_invalidates_approval(self):
        self.charter["production_charter"]["authority"]["execution"]["max_total_budget"] = 50
        self.assertFalse(self.validate()["launch_ready"])

    def test_changed_brief_invalidates_launch(self):
        path = self.root / "game-pipeline/project-definition/project-brief.yaml"
        doc = load_yaml(path)
        doc["project_brief"]["statements"][0]["text"] = "Changed project"
        write(self.root, str(path.relative_to(self.root)), doc)
        self.assertFalse(self.validate()["launch_ready"])

    def test_blocking_question_cannot_be_approved_away(self):
        self.charter["production_charter"]["open_questions"][0]["blocks_start"] = True
        approve_charter(self.root, self.charter, self.approvals)
        self.assertFalse(self.validate()["launch_ready"])

    def test_each_relevant_domain_must_be_covered(self):
        self.charter["production_charter"]["coverage"].pop("audio")
        approve_charter(self.root, self.charter, self.approvals)
        self.assertFalse(self.validate()["launch_ready"])

    def test_path_prefix_collision_and_parent_traversal_rejected(self):
        for path in ["outputs-evil/file", "../outputs/file", r"..\outputs\file", "C:/outputs/file"]:
            result = evaluate_authority(self.charter, "write_workspace", project_root=self.root,
                                        approvals=self.approvals, path=path)
            self.assertFalse(result["allowed"], path)

    def test_cumulative_budget_and_retry_limits(self):
        for kwargs in [{"spent_budget": 4, "estimated_cost": 2}, {"attempt": 5}, {"estimated_cost": float("nan")}]:
            self.assertFalse(evaluate_authority(self.charter, "write_workspace", project_root=self.root,
                                               approvals=self.approvals, **kwargs)["allowed"])

    def test_external_target_requires_explicit_scope(self):
        self.assertFalse(evaluate_authority(self.charter, "publish", project_root=self.root,
                            approvals=self.approvals, external=True, target="store:production")["allowed"])

    def test_duplicate_approval_id_rejected(self):
        write(self.root, "game-pipeline/approvals/copy.yaml", {"approval": self.approvals["approval:fixture:charter"]})
        _, errors = load_approvals(self.root / "game-pipeline/approvals")
        self.assertTrue(errors)

    def test_missing_external_approval_collection_cannot_enable_launch(self):
        result = validate_charter(self.root / "game-pipeline/project-definition/production-charter.yaml",
                                  project_root=self.root)
        self.assertFalse(result["launch_ready"])


if __name__ == "__main__":
    unittest.main()
