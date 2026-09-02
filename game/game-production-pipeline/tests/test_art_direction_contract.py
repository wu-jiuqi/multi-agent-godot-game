from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_art_direction_contract as validator  # noqa: E402
from evaluate_art_direction_gate import evaluate_art_direction_gate  # noqa: E402
from pipeline_common import file_digest, load_yaml  # noqa: E402


EXAMPLE = PLUGIN_ROOT / "contracts" / "examples" / "art-direction-clockwork-garden.yaml"


class ArtDirectionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = load_yaml(EXAMPLE)

    @property
    def contract(self):
        return self.document["art_direction_contract"]

    def refresh_digests(self) -> None:
        digests = validator.art_direction_digests(self.document)
        for review_name in validator.REVIEW_FIELDS:
            review = self.contract["verification"][review_name]
            if review["status"] == "approved":
                review["subject_digest"] = digests[validator.REVIEW_DIGEST_KIND[review_name]]
        self.contract["publication"]["frozen_revision_digest"] = digests["contract_subject_digest"]
        self.contract["integrity"].update(digests)

    def validate(self, **kwargs):
        return validator.validate_art_direction_contract(self.document, **kwargs)

    def assert_invalid_with(self, result, message: str) -> None:
        self.assertEqual("invalid", result["state"], result)
        self.assertIn(message, "\n".join(result["errors"]))

    def test_production_ready_example_passes_all_gates(self) -> None:
        result = self.validate()
        self.assertEqual("valid", result["state"], result)
        self.assertEqual(
            {gate: "passed" for gate in validator.GATE_ORDER},
            {gate: value["state"] for gate, value in result["gate_results"].items()},
        )

    def test_gate_evaluator_is_read_only_and_passes(self) -> None:
        before = copy.deepcopy(self.document)
        result = evaluate_art_direction_gate(self.document, "D4")
        self.assertEqual("pass", result["state"], result)
        self.assertFalse(result["writes_performed"])
        self.assertEqual(before, self.document)

    def test_pending_human_direction_returns_awaiting_human(self) -> None:
        approval = self.contract["verification"]["direction_approval"]
        approval.update({"reviewer": None, "status": "pending", "subject_digest": None, "reviewed_at": None, "evidence_refs": []})
        result = evaluate_art_direction_gate(self.document, "D2")
        self.assertEqual("awaiting_human", result["state"], result)

    def test_exploration_requires_primary_video_and_three_real_signatures(self) -> None:
        self.contract["research"]["source_refs"] = self.contract["research"]["source_refs"][:1]
        for option in self.contract["style_exploration"]["options"]:
            option["signature"] = "same palette swap"
        self.refresh_digests()
        result = self.validate(target_gate="D1")
        self.assert_invalid_with(result, "research.source_refs 至少需要 3 项")
        self.assert_invalid_with(result, "研究必须同时包含 primary 与 video 来源")
        self.assert_invalid_with(result, "独立 signature")

    def test_direction_change_invalidates_only_direction_and_downstream_digests(self) -> None:
        before = validator.art_direction_digests(self.document)
        self.contract["style_exploration"]["selected_option_id"] = "option:inked-herbarium"
        after = validator.art_direction_digests(self.document)
        self.assertEqual(before["exploration_subject_digest"], after["exploration_subject_digest"])
        self.assertNotEqual(before["direction_subject_digest"], after["direction_subject_digest"])
        result = self.validate(target_gate="D2")
        self.assert_invalid_with(result, "direction_approval.subject_digest 已过期或不匹配")

    def test_benchmark_evidence_does_not_invalidate_direction_selection(self) -> None:
        before = validator.art_direction_digests(self.document)
        self.contract["benchmark"]["capture_refs"].append("evidence:capture:additional")
        after = validator.art_direction_digests(self.document)
        self.assertEqual(before["direction_subject_digest"], after["direction_subject_digest"])
        self.assertNotEqual(before["benchmark_subject_digest"], after["benchmark_subject_digest"])

    def test_required_ui_domain_needs_translation_and_profile(self) -> None:
        mapping_domains = self.contract["translation_matrix"]["mappings"][0]["domains"]
        self.contract["translation_matrix"]["mappings"][0]["domains"] = [item for item in mapping_domains if item["domain"] != "ui"]
        self.contract["technical_profiles"]["ui"]["enabled"] = False
        self.refresh_digests()
        result = self.validate(target_gate="D3")
        self.assert_invalid_with(result, "translation_matrix 缺少域: ['ui']")
        self.assert_invalid_with(result, "scope 包含 ui，但 UI Profile 未启用")

    def test_performance_over_budget_blocks_benchmark(self) -> None:
        metric = self.contract["performance"]["metrics"][0]
        metric["measured"] = 20
        metric["result"] = "failed"
        self.refresh_digests()
        result = self.validate(target_gate="D3")
        self.assert_invalid_with(result, "性能指标缺失或未全部通过")

    def test_rights_are_conditional_at_d0_but_must_be_cleared_at_d4(self) -> None:
        self.contract["rights"]["clearance_state"] = "conditional"
        self.refresh_digests()
        d0 = self.validate(target_gate="D0")
        self.assertEqual("passed", d0["gate_results"]["D0"]["state"])
        d4 = self.validate(target_gate="D4")
        self.assert_invalid_with(d4, "D4 要求 rights.clearance_state=cleared")

    def test_forbidden_ai_policy_rejects_ai_records(self) -> None:
        self.contract["rights"]["generative_ai_policy"] = "forbidden"
        self.contract["rights"]["ai_use_records"] = [{
            "provider": "provider",
            "model": "model",
            "version": "v1",
            "terms_snapshot_ref": "rights:terms",
            "input_asset_refs": [],
            "human_contribution_ref": "evidence:human-edit",
            "output_disposition": "discarded",
        }]
        self.refresh_digests()
        result = self.validate(target_gate="D4")
        self.assert_invalid_with(result, "generative_ai_policy=forbidden")

    def test_project_root_checks_brief_digest_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            brief = root / "game-pipeline" / "project-definition" / "project-brief.yaml"
            brief.parent.mkdir(parents=True)
            brief.write_text("project_brief: {}\n", encoding="utf-8", newline="\n")
            digest = file_digest(brief)
            self.contract["brief"]["project_brief_ref"]["sha256"] = digest
            self.refresh_digests()
            before = brief.read_bytes()
            result = self.validate(project_root=root)
            after = brief.read_bytes()
        self.assertEqual("valid", result["state"], result)
        self.assertEqual("matched", result["file_checks"][0]["state"])
        self.assertEqual(before, after)

    def test_revision_chain_binds_previous_contract_subject(self) -> None:
        previous = copy.deepcopy(self.document)
        self.contract["identity"]["revision"] = 2
        self.contract["identity"]["previous_revision_digest"] = validator.art_direction_digests(previous)["contract_subject_digest"]
        self.refresh_digests()
        result = self.validate(previous=previous)
        self.assertEqual("valid", result["state"], result)

    def test_same_revision_cannot_be_modified_in_place(self) -> None:
        previous = copy.deepcopy(self.document)
        self.contract["identity"]["display_name"] = "Changed In Place"
        self.refresh_digests()
        result = self.validate(previous=previous)
        self.assert_invalid_with(result, "同一 Art Direction revision 不得原地修改")

    def test_cli_json_is_ascii_safe_for_windows_powershell(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "evaluate_art_direction_gate.py"), str(EXAMPLE), "--gate", "D4"],
            cwd=PLUGIN_ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        completed.stdout.decode("ascii")
        payload = json.loads(completed.stdout)
        self.assertEqual("pass", payload["state"])


if __name__ == "__main__":
    unittest.main()
