#!/usr/bin/env python3
"""Validate the structural invariants of a game pipeline contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path, PurePosixPath

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment failure
    raise SystemExit("缺少 PyYAML；请先安装插件 scripts/requirements.txt") from exc


AGENTS = {"AGT-DIR", "AGT-GD", "AGT-CD", "AGT-GODOT", "AGT-QA", "SPECIALIST"}
STAGES = {"P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "X0"}
STATUSES = {"draft", "ready", "in_progress", "review", "approved", "rejected", "blocked"}
GATES = {"GATE-0", "GATE-1", "GATE-2", "GATE-3", "GATE-4"}


def require(mapping: dict, key: str, location: str, errors: list[str]):
    value = mapping.get(key)
    if value is None or value == "" or value == []:
        errors.append(f"{location}.{key} 不能为空")
    return value


def validate_repo_path(value: object, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{location} 必须是非空仓库相对路径")
        return
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in normalized:
        errors.append(f"{location} 不能越出仓库: {value}")


def validate_contract(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["根节点必须是映射"]

    contract = data.get("contract")
    if not isinstance(contract, dict):
        return ["contract 必须是映射"]

    for key in ("schema_version", "contract_id", "title", "stage", "status", "owner_agent", "project_id", "version"):
        require(contract, key, "contract", errors)
    if contract.get("stage") not in STAGES:
        errors.append("contract.stage 不是支持的阶段")
    if contract.get("status") not in STATUSES:
        errors.append("contract.status 不是支持的状态")
    if contract.get("owner_agent") not in AGENTS:
        errors.append("contract.owner_agent 不是已登记角色")

    objective = data.get("objective")
    if not isinstance(objective, dict):
        errors.append("objective 必须是映射")
    else:
        require(objective, "player_facing_outcome", "objective", errors)
        require(objective, "production_outcome", "objective", errors)

    for section in ("entry_conditions", "inputs", "steps", "outputs", "automated_checks", "exit_conditions"):
        if not isinstance(data.get(section), list) or not data[section]:
            errors.append(f"{section} 必须是非空列表")

    for index, item in enumerate(data.get("inputs", [])):
        if not isinstance(item, dict):
            errors.append(f"inputs[{index}] 必须是映射")
            continue
        validate_repo_path(item.get("path"), f"inputs[{index}].path", errors)
        if item.get("owner_agent") not in AGENTS:
            errors.append(f"inputs[{index}].owner_agent 不是已登记角色")

    for index, item in enumerate(data.get("outputs", [])):
        if not isinstance(item, dict):
            errors.append(f"outputs[{index}] 必须是映射")
            continue
        validate_repo_path(item.get("path"), f"outputs[{index}].path", errors)
        if item.get("owner_agent") not in AGENTS:
            errors.append(f"outputs[{index}].owner_agent 不是已登记角色")
        if not isinstance(item.get("acceptance"), list) or not item["acceptance"]:
            errors.append(f"outputs[{index}].acceptance 必须是非空列表")

    constraints = data.get("constraints")
    if not isinstance(constraints, dict):
        errors.append("constraints 必须是映射")
    elif constraints.get("engine_adapter") not in {"generic", "godot"}:
        errors.append("constraints.engine_adapter 必须是 generic 或 godot")

    gate = data.get("human_gate")
    if not isinstance(gate, dict):
        errors.append("human_gate 必须是映射")
    elif gate.get("required"):
        if gate.get("gate_id") not in GATES:
            errors.append("human_gate.gate_id 不是支持的人工闸门")
        if not isinstance(gate.get("questions"), list) or not gate["questions"]:
            errors.append("需要人工闸门时 questions 必须是非空列表")

    rollback = data.get("rollback")
    if not isinstance(rollback, dict):
        errors.append("rollback 必须是映射")
    else:
        if rollback.get("return_to_stage") not in STAGES:
            errors.append("rollback.return_to_stage 不是支持的阶段")
        if rollback.get("return_to_agent") not in AGENTS:
            errors.append("rollback.return_to_agent 不是已登记角色")

    handoff = data.get("handoff")
    if not isinstance(handoff, dict):
        errors.append("handoff 必须是映射")
    elif handoff.get("next_agent") not in AGENTS:
        errors.append("handoff.next_agent 不是已登记角色")

    if not isinstance(data.get("evidence"), dict):
        errors.append("evidence 必须是映射")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    args = parser.parse_args()

    try:
        data = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"无法读取 Contract: {exc}", file=sys.stderr)
        return 2

    errors = validate_contract(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {args.contract}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
