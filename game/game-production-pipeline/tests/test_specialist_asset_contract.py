from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_specialist_asset_contract as asset_validator  # noqa: E402
from pipeline_common import file_digest, load_yaml  # noqa: E402


EXAMPLE_PATH = PLUGIN_ROOT / "contracts" / "examples" / "specialist-asset-static-prop.yaml"


class SpecialistAssetContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = load_yaml(EXAMPLE_PATH)

    @property
    def contract(self):
        return self.document["specialist_asset_contract"]

    def refresh_digests(self) -> None:
        contract = self.contract
        contract["runtime_package"]["source_subject_digest"] = asset_validator.source_subject_digest(contract)
        contract["runtime_package"]["recipe_digest"] = asset_validator.recipe_digest(contract)
        subject_digest = asset_validator.asset_subject_digest(self.document)
        for review_name in asset_validator.REVIEW_FIELDS:
            contract["verification"][review_name]["subject_digest"] = subject_digest
        contract["publication"]["frozen_revision_digest"] = subject_digest
        contract["integrity"]["contract_subject_digest"] = subject_digest

    def validate(self, **kwargs):
        return asset_validator.validate_specialist_asset_contract(self.document, **kwargs)

    def assert_invalid_with(self, result, message: str) -> None:
        self.assertEqual("invalid", result["state"], result)
        self.assertIn(message, "\n".join(result["errors"]))

    def test_approved_example_passes_all_four_gates(self) -> None:
        result = self.validate()
        self.assertEqual("valid", result["state"], result)
        self.assertEqual(
            {"A0": "passed", "A1": "passed", "A2": "passed", "A3": "passed"},
            {name: value["state"] for name, value in result["gate_results"].items()},
        )

    def test_unknown_rights_fail_closed(self) -> None:
        self.contract["rights"]["commercial_use"] = "unknown"
        self.refresh_digests()
        result = self.validate()
        self.assert_invalid_with(result, "rights.commercial_use 未形成可生产结论")
        self.assertEqual("blocked", result["gate_results"]["A0"]["state"])

    def test_source_or_recipe_drift_invalidates_runtime(self) -> None:
        self.contract["import_recipe"]["engine_version"] = "4.5.0"
        subject_digest = asset_validator.asset_subject_digest(self.document)
        for review_name in asset_validator.REVIEW_FIELDS:
            self.contract["verification"][review_name]["subject_digest"] = subject_digest
        self.contract["publication"]["frozen_revision_digest"] = subject_digest
        self.contract["integrity"]["contract_subject_digest"] = subject_digest
        result = self.validate()
        self.assert_invalid_with(result, "runtime_package.recipe_digest 不匹配")
        self.assertEqual("blocked", result["gate_results"]["A2"]["state"])

    def test_performance_over_budget_blocks_runtime_gate(self) -> None:
        metric = self.contract["performance"]["metrics"][0]
        metric["measured"] = metric["limit"] + 1
        self.refresh_digests()
        result = self.validate()
        self.assert_invalid_with(result, ".result 应为 failed")
        self.assertEqual("blocked", result["gate_results"]["A2"]["state"])

    def test_stale_human_review_blocks_approval(self) -> None:
        self.contract["verification"]["intent_review"]["subject_digest"] = "0" * 64
        result = self.validate()
        self.assert_invalid_with(result, "subject_digest 已过期或不匹配")

    def test_consumer_is_read_only_and_paths_may_not_overlap(self) -> None:
        boundary = self.contract["consumer_boundary"]
        boundary["access"] = "read_write"
        boundary["generated_output_paths"] = [boundary["protected_paths"][0]]
        self.refresh_digests()
        result = self.validate()
        self.assert_invalid_with(result, "consumer_boundary.access 必须为 read_only")
        self.assert_invalid_with(result, "generated_output_paths 与 protected_paths 重叠")

    def test_rework_state_requires_an_open_routed_issue(self) -> None:
        self.contract["identity"]["lifecycle_state"] = "rework_required"
        self.refresh_digests()
        result = self.validate()
        self.assert_invalid_with(result, "rework_required 状态必须有开放返修 issue")

    def test_frozen_revision_cannot_be_modified_in_place(self) -> None:
        previous = copy.deepcopy(self.document)
        self.contract["identity"]["display_name"] = "Crate A Modified"
        self.refresh_digests()
        result = self.validate(previous=previous)
        self.assert_invalid_with(result, "冻结 revision 不得原地修改")

    def test_next_revision_must_bind_previous_subject_digest(self) -> None:
        previous = copy.deepcopy(self.document)
        self.contract["identity"]["revision"] = 2
        self.contract["identity"]["previous_revision_digest"] = "0" * 64
        self.refresh_digests()
        result = self.validate(previous=previous)
        self.assert_invalid_with(result, "previous_revision_digest 不匹配上一版本")

    def test_project_root_checks_repo_files_without_writing_ui_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ui_source = root / "game" / "scenes" / "ui" / "screen-flow.tscn"
            ui_source.parent.mkdir(parents=True)
            ui_source.write_text("[gd_scene format=3]\n", encoding="utf-8", newline="\n")
            before = file_digest(ui_source)
            result = self.validate(project_root=root)
            after = file_digest(ui_source)
        self.assert_invalid_with(result, "引用的文件不存在")
        self.assertEqual(before, after)
        self.assertTrue(any(item["state"] == "missing" for item in result["file_checks"]))


if __name__ == "__main__":
    unittest.main()
