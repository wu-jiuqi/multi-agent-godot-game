from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bootstrap_game_pipeline as bootstrap  # noqa: E402
import validate_project_instance as project_validator  # noqa: E402
import validate_specialist_asset_contract as asset_validator  # noqa: E402
from pipeline_common import dump_yaml, file_digest, load_yaml  # noqa: E402
from validate_specialist_asset_loop import (  # noqa: E402
    validate_asset_loop_policy,
    validate_specialist_asset_loop,
)


CREATED_AT = "2026-09-02T00:00:00Z"
ASSET_EXAMPLE = PLUGIN_ROOT / "contracts" / "examples" / "specialist-asset-static-prop.yaml"
LOOP_CONTRACT = PLUGIN_ROOT / "contracts" / "specialist-asset-production.loop-contract.yaml"


class SpecialistAssetLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name)
        self.asset_document = load_yaml(ASSET_EXAMPLE)
        self.loop_contract = load_yaml(LOOP_CONTRACT)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def materialize_repo_refs(self, value: Any) -> None:
        if isinstance(value, dict):
            uri = value.get("uri")
            if isinstance(uri, str) and uri.startswith("repo://") and "sha256" in value:
                relative = uri.removeprefix("repo://")
                path = self.project_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"fixture:{relative}\n".encode("utf-8"))
                value["sha256"] = file_digest(path)
            for child in value.values():
                self.materialize_repo_refs(child)
        elif isinstance(value, list):
            for child in value:
                self.materialize_repo_refs(child)

    def write_asset_contract(self) -> tuple[Path, str]:
        self.materialize_repo_refs(self.asset_document)
        contract = self.asset_document["specialist_asset_contract"]
        contract["runtime_package"]["source_subject_digest"] = asset_validator.source_subject_digest(contract)
        contract["runtime_package"]["recipe_digest"] = asset_validator.recipe_digest(contract)
        subject_digest = asset_validator.asset_subject_digest(self.asset_document)
        for review_name in asset_validator.REVIEW_FIELDS:
            contract["verification"][review_name]["subject_digest"] = subject_digest
        contract["publication"]["frozen_revision_digest"] = subject_digest
        contract["integrity"]["contract_subject_digest"] = subject_digest
        path = self.project_root / "game-pipeline" / "assets" / "contracts" / "crate-a.r0001.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_yaml(self.asset_document), encoding="utf-8", newline="\n")
        return path, subject_digest

    def completed_snapshot(self, asset_path: Path, subject_digest: str) -> dict[str, Any]:
        return {
            "registry_snapshot": {
                "identity": {"loop_instance_id": "loop:sample-game:asset:crate-a"},
                "contract_binding": {
                    "contract_id": "LOOP-CTR-SPECIALIST-ASSET-PRODUCTION",
                    "contract_version": 1,
                    "contract_digest": "0" * 64,
                },
                "runtime": {"current_state": "completed"},
                "resources": {
                    "inputs": [],
                    "outputs": [
                        {
                            "deliverable_id": "DELIVERABLE-ASSET-CONTRACT-A3",
                            "artifact": {
                                "artifact_id": "asset:sample-game:environment:crate-a",
                                "artifact_type": "specialist-asset-contract",
                                "version": 1,
                                "uri": "repo://" + asset_path.relative_to(self.project_root).as_posix(),
                                "digest": {"algorithm": "sha256", "value": file_digest(asset_path)},
                                "subject_digest": subject_digest,
                            },
                        }
                    ],
                },
                "acceptance_snapshot": {
                    "asset_gates": [
                        {
                            "gate_id": "A3",
                            "asset_id": "asset:sample-game:environment:crate-a",
                            "revision": 1,
                            "result": "passed",
                            "contract_subject_digest": subject_digest,
                            "evidence_ref": "evidence:asset-gate:crate-a:a3",
                            "evaluated_at": "2026-09-02T04:00:00Z",
                        }
                    ]
                },
                "interruption": None,
            }
        }

    def test_standard_asset_loop_policy_is_valid(self) -> None:
        self.assertEqual([], validate_asset_loop_policy(self.loop_contract))

    def test_completed_loop_binds_a3_contract_without_writing_ui(self) -> None:
        ui_path = self.project_root / "game" / "scenes" / "ui" / "screen-flow.tscn"
        ui_path.parent.mkdir(parents=True)
        ui_path.write_text("[gd_scene format=3]\n", encoding="utf-8", newline="\n")
        before = file_digest(ui_path)
        asset_path, subject_digest = self.write_asset_contract()
        snapshot = self.completed_snapshot(asset_path, subject_digest)
        result = validate_specialist_asset_loop(
            self.loop_contract,
            snapshot,
            project_root=self.project_root,
        )
        self.assertEqual("valid", result["state"], result)
        self.assertEqual("A3", result["gate"])
        self.assertEqual(before, file_digest(ui_path))
        self.assertFalse(result["writes_performed"])

    def test_subject_digest_drift_blocks_loop(self) -> None:
        asset_path, subject_digest = self.write_asset_contract()
        snapshot = self.completed_snapshot(asset_path, subject_digest)
        snapshot["registry_snapshot"]["resources"]["outputs"][0]["artifact"]["subject_digest"] = "0" * 64
        result = validate_specialist_asset_loop(
            self.loop_contract,
            snapshot,
            project_root=self.project_root,
        )
        self.assertEqual("invalid", result["state"], result)
        self.assertIn("subject_digest", "\n".join(result["errors"]))

    def test_completed_loop_requires_a3_acceptance_record(self) -> None:
        asset_path, subject_digest = self.write_asset_contract()
        snapshot = self.completed_snapshot(asset_path, subject_digest)
        snapshot["registry_snapshot"]["acceptance_snapshot"]["asset_gates"] = []
        result = validate_specialist_asset_loop(
            self.loop_contract,
            snapshot,
            project_root=self.project_root,
        )
        self.assertEqual("invalid", result["state"], result)
        self.assertIn("缺少唯一 A3", "\n".join(result["errors"]))

    def test_project_validator_discovers_asset_loop_registry_binding(self) -> None:
        plan, desired = bootstrap.build_plan(
            self.project_root,
            "sample-game",
            "Sample Game",
            "Godot",
            "human:owner",
            CREATED_AT,
            PLUGIN_ROOT,
        )
        bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])
        asset_path, subject_digest = self.write_asset_contract()
        loop_contract_path = (
            self.project_root
            / "game-pipeline"
            / "loops"
            / "contracts"
            / "specialist-asset-production.yaml"
        )
        loop_contract_path.write_text(dump_yaml(self.loop_contract), encoding="utf-8", newline="\n")
        snapshot_path = (
            self.project_root
            / "game-pipeline"
            / "loops"
            / "registry"
            / "crate-a"
            / "snapshot.yaml"
        )
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_text(
            dump_yaml(self.completed_snapshot(asset_path, subject_digest)),
            encoding="utf-8",
            newline="\n",
        )
        result = project_validator.validate_instance(self.project_root, PLUGIN_ROOT)
        self.assertEqual("normal", result["state"], result)
        self.assertIn(
            "game-pipeline/loops/registry/crate-a/snapshot.yaml",
            result["checked"],
        )

    def test_project_validator_blocks_asset_reference_without_asset_loop_contract(self) -> None:
        plan, desired = bootstrap.build_plan(
            self.project_root,
            "sample-game",
            "Sample Game",
            "Godot",
            "human:owner",
            CREATED_AT,
            PLUGIN_ROOT,
        )
        bootstrap.apply_plan(plan, desired, self.project_root, plan["approval_digest"])
        asset_path, subject_digest = self.write_asset_contract()
        snapshot = self.completed_snapshot(asset_path, subject_digest)
        snapshot_path = (
            self.project_root
            / "game-pipeline"
            / "loops"
            / "registry"
            / "crate-a"
            / "snapshot.yaml"
        )
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_text(dump_yaml(snapshot), encoding="utf-8", newline="\n")
        result = project_validator.validate_instance(self.project_root, PLUGIN_ROOT)
        self.assertEqual("blocked", result["state"], result)
        self.assertIn("找不到绑定的 Loop Contract", "\n".join(result["errors"]))


if __name__ == "__main__":
    unittest.main()
