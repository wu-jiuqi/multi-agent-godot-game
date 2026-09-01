#!/usr/bin/env python3
"""Validate Specialist Asset Loop policy and Registry bindings without mutation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any

from evaluate_specialist_asset_gate import evaluate_specialist_asset_gate
from pipeline_common import file_digest, load_yaml
from validate_specialist_asset_contract import SHA256_RE, asset_subject_digest


POLICY_SCHEMA = "game-production-specialist-asset-loop-binding/v1"
LOOP_TYPE = "specialist-asset-production"
ARTIFACT_TYPE = "specialist-asset-contract"
REQUIRED_REFERENCE_FIELDS = [
    "artifact_id",
    "artifact_type",
    "version",
    "uri",
    "digest.algorithm",
    "digest.value",
    "subject_digest",
]
GATE_BY_STATE = {"ready": "A0", "active": "A0", "review": "A2", "completed": "A3"}
INTERRUPTION_STATES = {"blocked", "paused", "waiting_approval"}


def require_mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是映射")
        return {}
    return value


def is_specialist_asset_loop(contract_document: object) -> bool:
    if not isinstance(contract_document, dict):
        return False
    contract = contract_document.get("loop_contract")
    return isinstance(contract, dict) and contract.get("loop_type") == LOOP_TYPE


def validate_asset_loop_policy(contract_document: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract_document, dict):
        return ["Loop Contract 根节点必须是映射"]
    if not is_specialist_asset_loop(contract_document):
        return errors
    policy = require_mapping(contract_document.get("asset_contract_policy"), "asset_contract_policy", errors)
    if policy.get("schema_version") != POLICY_SCHEMA:
        errors.append(f"asset_contract_policy.schema_version 必须为 {POLICY_SCHEMA}")
    if policy.get("required") is not True:
        errors.append("asset_contract_policy.required 必须为 true")
    if policy.get("artifact_type") != ARTIFACT_TYPE:
        errors.append(f"asset_contract_policy.artifact_type 必须为 {ARTIFACT_TYPE}")
    input_slot_id = policy.get("input_slot_id")
    output_id = policy.get("output_deliverable_id")
    inputs = contract_document.get("start", {}).get("required_inputs", [])
    outputs = contract_document.get("purpose", {}).get("required_deliverables", [])
    matching_inputs = [
        item for item in inputs if isinstance(item, dict) and item.get("input_slot_id") == input_slot_id
    ]
    matching_outputs = [
        item for item in outputs if isinstance(item, dict) and item.get("deliverable_id") == output_id
    ]
    if len(matching_inputs) != 1 or matching_inputs[0].get("artifact_type") != ARTIFACT_TYPE:
        errors.append("asset_contract_policy.input_slot_id 必须唯一绑定 specialist-asset-contract 输入")
    if len(matching_outputs) != 1 or matching_outputs[0].get("artifact_type") != ARTIFACT_TYPE:
        errors.append("asset_contract_policy.output_deliverable_id 必须唯一绑定 specialist-asset-contract 输出")
    if policy.get("registry_reference_required_fields") != REQUIRED_REFERENCE_FIELDS:
        errors.append("asset_contract_policy.registry_reference_required_fields 不符合 P0 引用全集")
    if policy.get("gate_requirements") != GATE_BY_STATE:
        errors.append("asset_contract_policy.gate_requirements 必须绑定 ready/active/review/completed 到 A0/A0/A2/A3")
    if policy.get("acceptance_record_kind") != "asset-gate":
        errors.append("asset_contract_policy.acceptance_record_kind 必须为 asset-gate")
    registry_policy = contract_document.get("coordination", {}).get("registry_binding", {})
    if not isinstance(registry_policy, dict) or registry_policy.get("store_asset_body_in_registry") is not False:
        errors.append("Registry 必须声明 store_asset_body_in_registry=false")
    if not isinstance(registry_policy, dict) or registry_policy.get("store_only_versioned_references_and_gate_evidence") is not True:
        errors.append("Registry 必须只保存版本化引用与 Gate 证据")
    return errors


def repo_uri_path(uri: Any, errors: list[str]) -> str | None:
    if not isinstance(uri, str) or not uri.startswith("repo://"):
        errors.append("资产 Registry 引用必须使用 repo:// URI")
        return None
    relative = uri.removeprefix("repo://").replace("\\", "/")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or ":" in relative:
        errors.append("资产 Registry URI 必须是项目内安全相对路径")
        return None
    if not relative.startswith("game-pipeline/assets/contracts/"):
        errors.append("资产 Registry URI 必须位于 game-pipeline/assets/contracts/")
        return None
    return path.as_posix()


def required_gate(snapshot: dict[str, Any]) -> str | None:
    runtime = snapshot.get("runtime") if isinstance(snapshot.get("runtime"), dict) else {}
    state = runtime.get("current_state")
    if state in INTERRUPTION_STATES:
        interruption = snapshot.get("interruption") if isinstance(snapshot.get("interruption"), dict) else {}
        state = interruption.get("resume_state")
    return GATE_BY_STATE.get(state)


def find_resource(snapshot: dict[str, Any], policy: dict[str, Any], gate: str) -> tuple[dict[str, Any], str]:
    resources = snapshot.get("resources") if isinstance(snapshot.get("resources"), dict) else {}
    if gate == "A0":
        key = "inputs"
        id_key = "input_slot_id"
        expected_id = policy.get("input_slot_id")
    else:
        key = "outputs"
        id_key = "deliverable_id"
        expected_id = policy.get("output_deliverable_id")
    values = resources.get(key) if isinstance(resources.get(key), list) else []
    matches = [item for item in values if isinstance(item, dict) and item.get(id_key) == expected_id]
    return (matches[0] if len(matches) == 1 else {}), f"resources.{key}.{expected_id}"


def validate_specialist_asset_loop(
    contract_document: object,
    snapshot_document: object,
    *,
    project_root: Path | None,
) -> dict[str, Any]:
    errors = validate_asset_loop_policy(contract_document)
    warnings: list[str] = []
    if not is_specialist_asset_loop(contract_document):
        return {"state": "not-applicable", "errors": errors, "warnings": warnings, "gate": None}
    if not isinstance(snapshot_document, dict):
        return {"state": "invalid", "errors": errors + ["Registry Snapshot 根节点必须是映射"], "warnings": warnings, "gate": None}
    snapshot = require_mapping(snapshot_document.get("registry_snapshot"), "registry_snapshot", errors)
    policy = contract_document.get("asset_contract_policy", {})
    gate = required_gate(snapshot)
    if gate is None:
        return {
            "state": "valid" if not errors else "invalid",
            "errors": errors,
            "warnings": warnings,
            "gate": None,
            "writes_performed": False,
        }
    resource, label = find_resource(snapshot, policy, gate)
    if not resource:
        errors.append(f"{label} 缺少唯一资产 Contract 引用")
        return {"state": "invalid", "errors": errors, "warnings": warnings, "gate": gate, "writes_performed": False}
    artifact = require_mapping(resource.get("artifact"), f"{label}.artifact", errors)
    if artifact.get("artifact_type") != ARTIFACT_TYPE:
        errors.append(f"{label}.artifact_type 必须为 {ARTIFACT_TYPE}")
    asset_id = artifact.get("artifact_id")
    revision = artifact.get("version")
    if not isinstance(asset_id, str) or not asset_id.startswith("asset:"):
        errors.append(f"{label}.artifact_id 必须是 asset ID")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append(f"{label}.version 必须是正整数 revision")
    subject_digest = artifact.get("subject_digest")
    if not isinstance(subject_digest, str) or not SHA256_RE.fullmatch(subject_digest):
        errors.append(f"{label}.subject_digest 必须是 64 位小写 SHA-256")
    digest = require_mapping(artifact.get("digest"), f"{label}.digest", errors)
    if digest.get("algorithm") != "sha256" or not isinstance(digest.get("value"), str) or not SHA256_RE.fullmatch(digest.get("value", "")):
        errors.append(f"{label}.digest 必须提供 sha256 和 64 位小写 value")
    relative = repo_uri_path(artifact.get("uri"), errors)
    if project_root is None:
        errors.append("专业资产 Loop 运行态校验必须提供 project_root")
        asset_document = None
    elif relative is None:
        asset_document = None
    else:
        root = project_root.resolve()
        asset_path = (root / relative).resolve()
        try:
            asset_path.relative_to(root)
        except ValueError:
            errors.append("资产 Contract 引用越出 project_root")
            asset_document = None
        else:
            if not asset_path.is_file():
                errors.append(f"资产 Contract 文件不存在: {relative}")
                asset_document = None
            elif file_digest(asset_path) != digest.get("value"):
                errors.append(f"资产 Contract 文件 digest 不匹配: {relative}")
                asset_document = None
            else:
                try:
                    asset_document = load_yaml(asset_path)
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
                    asset_document = None

    evaluation = None
    if asset_document is not None:
        asset_contract = asset_document.get("specialist_asset_contract", {})
        identity = asset_contract.get("identity", {}) if isinstance(asset_contract, dict) else {}
        if identity.get("asset_id") != asset_id:
            errors.append("Registry artifact_id 与 Asset Contract asset_id 不一致")
        if identity.get("revision") != revision:
            errors.append("Registry version 与 Asset Contract revision 不一致")
        actual_subject = asset_subject_digest(asset_document)
        if actual_subject != subject_digest:
            errors.append("Registry subject_digest 与 Asset Contract 不一致")
        evaluation = evaluate_specialist_asset_gate(
            asset_document,
            gate,
            project_root=project_root,
        )
        if evaluation.get("state") != "pass":
            errors.append(f"资产 {gate} 未通过: {evaluation.get('state')} - {evaluation.get('reason')}")

    acceptance = snapshot.get("acceptance_snapshot") if isinstance(snapshot.get("acceptance_snapshot"), dict) else {}
    gate_records = acceptance.get("asset_gates") if isinstance(acceptance.get("asset_gates"), list) else []
    matching_records = [
        item
        for item in gate_records
        if isinstance(item, dict)
        and item.get("gate_id") == gate
        and item.get("asset_id") == asset_id
        and item.get("revision") == revision
    ]
    if len(matching_records) != 1:
        errors.append(f"acceptance_snapshot.asset_gates 缺少唯一 {gate} 记录")
    else:
        record = matching_records[0]
        if record.get("result") != "passed":
            errors.append(f"acceptance_snapshot 中 {gate} 结果必须为 passed")
        if record.get("contract_subject_digest") != subject_digest:
            errors.append(f"acceptance_snapshot 中 {gate} subject digest 不匹配")
        if not isinstance(record.get("evidence_ref"), str) or not record.get("evidence_ref"):
            errors.append(f"acceptance_snapshot 中 {gate} 缺少 evidence_ref")

    return {
        "state": "valid" if not errors else "invalid",
        "gate": gate,
        "asset_id": asset_id,
        "revision": revision,
        "errors": errors,
        "warnings": warnings,
        "gate_evaluation": evaluation,
        "writes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop-contract", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_specialist_asset_loop(
            load_yaml(args.loop_contract),
            load_yaml(args.snapshot),
            project_root=args.project_root,
        )
    except (OSError, ValueError) as exc:
        result = {"state": "invalid", "errors": [str(exc)], "writes_performed": False}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("state") in {"valid", "not-applicable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
