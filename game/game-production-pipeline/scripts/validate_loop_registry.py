#!/usr/bin/env python3
"""Validate Loop Registry templates against their Contract and state machine."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment failure
    raise SystemExit("缺少 PyYAML；请先安装插件 scripts/requirements.txt") from exc


STATES = {
    "draft",
    "ready",
    "active",
    "review",
    "blocked",
    "paused",
    "waiting_approval",
    "completed",
    "cancelled",
}
INTERRUPTION_STATES = {"blocked", "paused", "waiting_approval"}
RESUME_STATES = {"ready", "active", "review"}
CORE_EVENTS = {
    "core.loop_registered",
    "core.loop_started",
    "core.state_transitioned",
    "core.assignment_changed",
    "core.dependency_changed",
    "core.input_bound",
    "core.output_registered",
    "core.acceptance_recorded",
    "core.interruption_entered",
    "core.interruption_rerouted",
    "core.resume_revalidation_recorded",
    "core.approval_requested",
    "core.approval_decided",
    "core.budget_extended",
    "core.contract_migrated",
    "core.state_machine_migrated",
    "core.loop_completed",
    "core.loop_cancelled",
}
STATE_CHANGING_EVENTS = {
    "core.loop_started",
    "core.state_transitioned",
    "core.interruption_entered",
    "core.interruption_rerouted",
    "core.resume_revalidation_recorded",
    "core.loop_completed",
    "core.loop_cancelled",
}
TRANSITION_EVENT_BINDINGS = {
    "TR-DRAFT-READY": "core.state_transitioned",
    "TR-READY-ACTIVE": "core.loop_started",
    "TR-ACTIVE-REVIEW": "core.state_transitioned",
    "TR-REVIEW-ACTIVE": "core.state_transitioned",
    "TR-REVIEW-COMPLETED": "core.loop_completed",
    "TR-OPERATIONAL-INTERRUPTED": "core.interruption_entered",
    "TR-INTERRUPTED-RESUME": "core.resume_revalidation_recorded",
    "TR-INTERRUPTED-REROUTE": "core.interruption_rerouted",
    "TR-NONTERMINAL-CANCELLED": "core.loop_cancelled",
}
REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "mutation_id",
    "loop_instance_id",
    "sequence",
    "event_type",
    "occurred_at",
    "recorded_at",
    "actor",
    "causality",
    "concurrency",
    "binding_snapshot",
    "payload",
    "evidence_refs",
    "integrity",
}


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def require_mapping(value: Any, location: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{location} 必须是映射")
        return {}
    return value


def require_keys(mapping: dict[str, Any], keys: set[str], location: str, errors: list[str]) -> None:
    for key in sorted(keys - mapping.keys()):
        errors.append(f"{location}.{key} 缺失")


def enum_values(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return set(value.split("|"))


def canonical_event_digest(event: dict[str, Any]) -> str:
    normalized = copy.deepcopy(event)
    integrity = normalized.get("integrity")
    if not isinstance(integrity, dict):
        raise ValueError("event.integrity 必须是映射")
    integrity["event_digest"] = None

    def reject_nonfinite(value: Any) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Event 数字禁止 NaN 和 Infinity")
        if isinstance(value, dict):
            for item in value.values():
                reject_nonfinite(item)
        elif isinstance(value, list):
            for item in value:
                reject_nonfinite(item)

    reject_nonfinite(normalized)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def transition_matches(value: Any, state: str) -> bool:
    if isinstance(value, str):
        return value == state or value == "$resume_state"
    return isinstance(value, list) and state in value


def validate_history(
    snapshot_doc: Any,
    history_doc: Any,
    state_machine_doc: Any,
    event_contract_doc: Any | None = None,
) -> list[str]:
    errors: list[str] = []
    snapshot = require_mapping(
        require_mapping(snapshot_doc, "snapshot 文档", errors).get("registry_snapshot"),
        "registry_snapshot",
        errors,
    )
    runtime = require_mapping(snapshot.get("runtime"), "registry_snapshot.runtime", errors)
    history_root = require_mapping(history_doc, "history 文档", errors)
    history = history_root.get("event_history")
    if not isinstance(history, list) or not history:
        return errors + ["event_history 必须是非空列表"]

    transitions = {
        item.get("transition_id"): item
        for item in state_machine_doc.get("transitions", [])
        if isinstance(item, dict) and item.get("transition_id")
    }
    payload_contracts = {}
    if isinstance(event_contract_doc, dict):
        payload_contracts = event_contract_doc.get("payload_contracts", {})
    seen_event_ids: set[str] = set()
    seen_mutation_ids: set[str] = set()
    expected_revision = 0
    previous_digest: str | None = None
    current_state: str | None = None
    current_iteration = 0
    last_transition_id: str | None = None
    loop_instance_id: str | None = None
    active_resume_state: str | None = None

    for index, item in enumerate(history, start=1):
        event = require_mapping(item, f"event_history[{index - 1}]", errors)
        require_keys(event, REQUIRED_EVENT_FIELDS, f"event_history[{index - 1}]", errors)
        event_id = event.get("event_id")
        mutation_id = event.get("mutation_id")
        if event_id in seen_event_ids:
            errors.append(f"event_history[{index - 1}].event_id 重复")
        if mutation_id in seen_mutation_ids:
            errors.append(f"event_history[{index - 1}].mutation_id 重复")
        seen_event_ids.add(event_id)
        seen_mutation_ids.add(mutation_id)
        if event.get("sequence") != index:
            errors.append(f"event_history[{index - 1}].sequence 必须为 {index}")

        event_loop_id = event.get("loop_instance_id")
        if loop_instance_id is None:
            loop_instance_id = event_loop_id
        elif event_loop_id != loop_instance_id:
            errors.append("Event History 中存在不同 loop_instance_id")

        concurrency = require_mapping(
            event.get("concurrency"), f"event_history[{index - 1}].concurrency", errors
        )
        if concurrency.get("expected_record_revision") != expected_revision:
            errors.append(
                f"event_history[{index - 1}].expected_record_revision 必须为 {expected_revision}"
            )
        if concurrency.get("resulting_record_revision") != expected_revision + 1:
            errors.append(
                f"event_history[{index - 1}].resulting_record_revision 必须为 {expected_revision + 1}"
            )
        expected_revision += 1

        integrity = require_mapping(
            event.get("integrity"), f"event_history[{index - 1}].integrity", errors
        )
        if integrity.get("previous_event_digest") != previous_digest:
            errors.append(f"event_history[{index - 1}] 的 previous_event_digest 断链")
        try:
            calculated = canonical_event_digest(event)
        except (TypeError, ValueError) as exc:
            errors.append(f"event_history[{index - 1}] 无法计算摘要: {exc}")
            calculated = None
        if calculated is not None and integrity.get("event_digest") != calculated:
            errors.append(f"event_history[{index - 1}].event_digest 不匹配")
        previous_digest = integrity.get("event_digest")

        event_type = event.get("event_type")
        payload = require_mapping(event.get("payload"), f"event_history[{index - 1}].payload", errors)
        payload_contract = payload_contracts.get(event_type, {})
        for field in payload_contract.get("required_fields", []):
            if field not in payload:
                errors.append(f"event_history[{index - 1}].payload.{field} 缺失")
        if index == 1:
            if event_type != "core.loop_registered":
                errors.append("第一条 Event 必须是 core.loop_registered")
            current_state = payload.get("initial_state")
            if current_state != state_machine_doc.get("state_machine", {}).get("initial_state"):
                errors.append("注册事件 initial_state 与状态机不一致")
            continue

        if event_type in STATE_CHANGING_EVENTS:
            transition_id = payload.get("transition_id")
            transition = transitions.get(transition_id)
            if transition is None:
                errors.append(f"event_history[{index - 1}] 引用了未知 transition_id")
                continue
            if transition.get("event_type") != event_type:
                errors.append(f"event_history[{index - 1}] 的 event_type 与转换绑定不一致")
            from_state = payload.get("from_state")
            to_state = payload.get("to_state")
            if from_state != current_state or not transition_matches(transition.get("from"), from_state):
                errors.append(f"event_history[{index - 1}] 的 from_state 无法从当前状态重放")
            if not transition_matches(transition.get("to"), to_state):
                errors.append(f"event_history[{index - 1}] 的 to_state 不符合状态机")
            iteration = require_mapping(
                payload.get("iteration"), f"event_history[{index - 1}].payload.iteration", errors
            )
            before = iteration.get("before")
            after = iteration.get("after")
            if before != current_iteration:
                errors.append(f"event_history[{index - 1}] 的 iteration.before 不连续")
            if transition_id == "TR-READY-ACTIVE":
                expected_after = 1
            elif transition.get("iteration_effect") == "increment":
                expected_after = current_iteration + 1
            else:
                expected_after = current_iteration
            if after != expected_after:
                errors.append(f"event_history[{index - 1}] 的 iteration.after 应为 {expected_after}")
            current_iteration = after if isinstance(after, int) else current_iteration
            if event_type == "core.interruption_entered":
                interruption = require_mapping(
                    payload.get("interruption"),
                    f"event_history[{index - 1}].payload.interruption",
                    errors,
                )
                resume_state = interruption.get("resume_state")
                if resume_state != from_state:
                    errors.append(
                        f"event_history[{index - 1}] 的 resume_state 必须等于首次中断前状态"
                    )
                active_resume_state = resume_state
            elif event_type == "core.interruption_rerouted":
                if active_resume_state is None:
                    errors.append(
                        f"event_history[{index - 1}] 重路由时不存在活动中断链"
                    )
            elif event_type == "core.resume_revalidation_recorded":
                if active_resume_state is None:
                    errors.append(
                        f"event_history[{index - 1}] 恢复时不存在活动中断链"
                    )
                elif to_state != active_resume_state:
                    errors.append(
                        f"event_history[{index - 1}] 的恢复目标不等于首次保存的 resume_state"
                    )
                active_resume_state = None
            elif event_type in {"core.loop_completed", "core.loop_cancelled"}:
                active_resume_state = None
            current_state = to_state
            last_transition_id = transition_id

    identity = require_mapping(snapshot.get("identity"), "registry_snapshot.identity", errors)
    if identity.get("loop_instance_id") != loop_instance_id:
        errors.append("Snapshot loop_instance_id 与 Event History 不一致")
    if runtime.get("last_event_sequence") != len(history):
        errors.append("Snapshot last_event_sequence 与 Event History 长度不一致")
    if runtime.get("record_revision") != expected_revision:
        errors.append("Snapshot record_revision 与 Event History 不一致")
    if runtime.get("last_event_id") != history[-1].get("event_id"):
        errors.append("Snapshot last_event_id 与 Event History 尾部不一致")
    if runtime.get("last_event_digest") != previous_digest:
        errors.append("Snapshot last_event_digest 与 Event History 尾部不一致")
    if runtime.get("current_state") != current_state:
        errors.append("Snapshot current_state 无法由 Event History 重建")
    if runtime.get("current_iteration") != current_iteration:
        errors.append("Snapshot current_iteration 无法由 Event History 重建")
    if runtime.get("last_transition_id") != last_transition_id:
        errors.append("Snapshot last_transition_id 与 Event History 不一致")
    return errors


def validate_templates(
    snapshot_doc: Any,
    event_doc: Any,
    contract_doc: Any,
    state_machine_doc: Any,
) -> list[str]:
    errors: list[str] = []
    snapshot_root = require_mapping(snapshot_doc, "snapshot 文档", errors)
    snapshot = require_mapping(snapshot_root.get("registry_snapshot"), "registry_snapshot", errors)
    event_root = require_mapping(event_doc, "event 文档", errors)
    event = require_mapping(event_root.get("event"), "event", errors)
    contract_root = require_mapping(contract_doc, "contract 文档", errors)
    contract = require_mapping(contract_root.get("loop_contract"), "loop_contract", errors)
    machine_root = require_mapping(state_machine_doc, "state machine 文档", errors)
    machine = require_mapping(machine_root.get("state_machine"), "state_machine", errors)

    require_keys(
        snapshot,
        {
            "schema_version",
            "identity",
            "contract_binding",
            "state_machine_binding",
            "topology",
            "responsibility",
            "runtime",
            "budget",
            "resources",
            "acceptance_snapshot",
            "interruption",
            "pending_approvals",
        },
        "registry_snapshot",
        errors,
    )
    require_keys(event, REQUIRED_EVENT_FIELDS, "event", errors)

    if contract.get("schema_version") != "0.2":
        errors.append("loop_contract.schema_version 必须为 0.2")
    if machine.get("version") != "0.2":
        errors.append("state_machine.version 必须为 0.2")

    state_binding = require_mapping(
        snapshot.get("state_machine_binding"), "registry_snapshot.state_machine_binding", errors
    )
    if state_binding.get("state_machine_id") != machine.get("state_machine_id"):
        errors.append("Snapshot 绑定的 state_machine_id 与状态机不一致")
    if state_binding.get("state_machine_version") != machine.get("version"):
        errors.append("Snapshot 绑定的 state_machine_version 与状态机不一致")

    runtime = require_mapping(snapshot.get("runtime"), "registry_snapshot.runtime", errors)
    require_keys(
        runtime,
        {
            "current_state",
            "state_entered_at",
            "current_iteration",
            "last_transition_id",
            "last_event_id",
            "last_event_digest",
            "last_event_sequence",
            "record_revision",
        },
        "registry_snapshot.runtime",
        errors,
    )
    if runtime.get("current_state") != machine.get("initial_state"):
        errors.append("Snapshot 模板初始状态必须等于状态机 initial_state")
    if runtime.get("current_iteration") != 0:
        errors.append("Snapshot 模板 current_iteration 必须从 0 开始")
    if runtime.get("last_event_sequence") != 1 or runtime.get("record_revision") != 1:
        errors.append("注册后的 Snapshot 模板必须位于 sequence=1、record_revision=1")

    states = set(require_mapping(state_machine_doc, "state machine 文档", errors).get("states", {}))
    if states != STATES:
        errors.append(f"状态集合不符合默认 Registry 契约: {sorted(states)}")
    if set(machine.get("interruption_states", [])) != INTERRUPTION_STATES:
        errors.append("中断状态集合不符合默认 Registry 契约")
    if set(machine.get("operational_states", [])) != RESUME_STATES:
        errors.append("可恢复 operational state 集合不符合默认 Registry 契约")

    resources = require_mapping(snapshot.get("resources"), "registry_snapshot.resources", errors)
    if resources.get("inputs") != [] or resources.get("outputs") != []:
        errors.append("draft 注册基线的 inputs 和 outputs 必须为空")
    field_examples = require_mapping(
        snapshot_root.get("field_examples"), "field_examples", errors
    )
    input_example = require_mapping(
        field_examples.get("input_binding"), "field_examples.input_binding", errors
    )
    output_example = require_mapping(
        field_examples.get("output_registration"),
        "field_examples.output_registration",
        errors,
    )
    input_ids = {input_example.get("input_slot_id")}
    output_ids = {output_example.get("deliverable_id")}
    contract_inputs = {
        item.get("input_slot_id")
        for item in contract_doc.get("start", {}).get("required_inputs", [])
        if isinstance(item, dict)
    }
    contract_outputs = {
        item.get("deliverable_id")
        for item in contract_doc.get("purpose", {}).get("required_deliverables", [])
        if isinstance(item, dict)
    }
    if not input_ids or input_ids != contract_inputs:
        errors.append("Snapshot input_slot_id 必须完整对应 Contract required_inputs")
    if not output_ids or output_ids != contract_outputs:
        errors.append("Snapshot deliverable_id 必须完整对应 Contract required_deliverables")

    topology_rules = snapshot_root.get("storage_contract", {}).get("topology_rules", [])
    topology_rules_text = "\n".join(
        item for item in topology_rules if isinstance(item, str)
    )
    for phrase in ("不得等于当前 loop_instance_id", "父 Loop 图必须无环", "blocking=true 的依赖图必须无环"):
        if phrase not in topology_rules_text:
            errors.append(f"Registry 拓扑规则缺少: {phrase}")

    if event.get("sequence") != 1 or event.get("event_type") != "core.loop_registered":
        errors.append("Event 模板必须表示 sequence=1 的 core.loop_registered")
    concurrency = require_mapping(event.get("concurrency"), "event.concurrency", errors)
    if concurrency.get("expected_record_revision") != 0:
        errors.append("注册事件 expected_record_revision 必须为 0")
    if concurrency.get("resulting_record_revision") != 1:
        errors.append("注册事件 resulting_record_revision 必须为 1")

    integrity = require_mapping(event.get("integrity"), "event.integrity", errors)
    if integrity.get("canonicalization") != "registry-event-canonical-json-v1":
        errors.append("Event 必须声明 registry-event-canonical-json-v1")
    if integrity.get("digest_algorithm") != "sha256":
        errors.append("Event 摘要算法必须为 sha256")
    if integrity.get("previous_event_digest") is not None:
        errors.append("首个 Event 的 previous_event_digest 必须为 null")
    rules = event_root.get("integrity_contract", {}).get("rules", [])
    rules_text = "\n".join(item for item in rules if isinstance(item, str))
    for phrase in ("event_digest 设为 null", "对象键", "数组保持原顺序", "UTF-8 JSON", "SHA-256"):
        if phrase not in rules_text:
            errors.append(f"Event 规范化规则缺少: {phrase}")

    core_events = set(event_root.get("event_namespace", {}).get("core", []))
    if core_events != CORE_EVENTS:
        errors.append("核心事件集合与 Registry 契约不一致")
    payload_contracts = require_mapping(
        event_root.get("payload_contracts"), "payload_contracts", errors
    )
    if set(payload_contracts) != CORE_EVENTS:
        errors.append("每个核心事件必须有且只有一个 Payload Contract")
    for event_type, contract_value in payload_contracts.items():
        payload_contract = require_mapping(
            contract_value, f"payload_contracts.{event_type}", errors
        )
        required_fields = payload_contract.get("required_fields")
        if not isinstance(required_fields, list) or not required_fields:
            errors.append(f"payload_contracts.{event_type}.required_fields 必须是非空列表")
        if not payload_contract.get("snapshot_effect"):
            errors.append(f"payload_contracts.{event_type}.snapshot_effect 不能为空")
    application_rules = "\n".join(
        item for item in event_root.get("application_contract", []) if isinstance(item, str)
    )
    for phrase in ("mutation_id", "sequence", "expected_record_revision", "原子事务", "禁止通用 JSON Patch"):
        if phrase not in application_rules:
            errors.append(f"Event 应用规则缺少: {phrase}")

    transitions = state_machine_doc.get("transitions", [])
    by_id = {
        item.get("transition_id"): item
        for item in transitions
        if isinstance(item, dict) and item.get("transition_id")
    }
    if set(by_id) != set(TRANSITION_EVENT_BINDINGS):
        errors.append("状态机转换集合与 Registry 事件绑定表不一致")
    for transition_id, expected_event in TRANSITION_EVENT_BINDINGS.items():
        actual = by_id.get(transition_id, {}).get("event_type")
        if actual != expected_event:
            errors.append(
                f"{transition_id}.event_type 应为 {expected_event}，实际为 {actual}"
            )
    if by_id.get("TR-REVIEW-ACTIVE", {}).get("iteration_effect") != "increment":
        errors.append("只有返工转换必须显式声明 iteration_effect=increment")
    for transition_id, transition in by_id.items():
        if transition_id == "TR-REVIEW-ACTIVE":
            continue
        if transition_id in {
            "TR-OPERATIONAL-INTERRUPTED",
            "TR-INTERRUPTED-RESUME",
            "TR-INTERRUPTED-REROUTE",
        } and transition.get("iteration_effect") != "preserve":
            errors.append(f"{transition_id} 必须保持 current_iteration")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--state-machine", required=True, type=Path)
    parser.add_argument("--history", type=Path)
    args = parser.parse_args()

    try:
        documents = [
            read_yaml(args.snapshot),
            read_yaml(args.event),
            read_yaml(args.contract),
            read_yaml(args.state_machine),
        ]
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"无法读取 Registry 契约: {exc}", file=sys.stderr)
        return 2

    errors = validate_templates(*documents)
    if args.history is not None:
        try:
            history_doc = read_yaml(args.history)
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            print(f"无法读取 Event History: {exc}", file=sys.stderr)
            return 2
        errors.extend(
            validate_history(documents[0], history_doc, documents[3], documents[1])
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "OK: Loop Registry Snapshot、Event、Contract 与状态机契约一致"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
