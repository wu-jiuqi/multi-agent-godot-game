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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_specialist_asset_loop import (
    validate_asset_loop_policy,
    validate_specialist_asset_loop,
)

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
    contract_doc: Any | None = None,
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
        candidate_payload_contracts = event_contract_doc.get("payload_contracts", {})
        if isinstance(candidate_payload_contracts, dict):
            payload_contracts = candidate_payload_contracts
    contract_input_ids: set[Any] = set()
    contract_deliverable_ids: set[Any] = set()
    if isinstance(contract_doc, dict):
        contract_input_ids = {
            item.get("input_slot_id")
            for item in contract_doc.get("start", {}).get("required_inputs", [])
            if isinstance(item, dict)
        }
        contract_deliverable_ids = {
            item.get("deliverable_id")
            for item in contract_doc.get("purpose", {}).get("required_deliverables", [])
            if isinstance(item, dict)
        }
    seen_event_ids: set[str] = set()
    seen_mutation_ids: set[str] = set()
    expected_revision = 0
    previous_digest: str | None = None
    current_state: str | None = None
    current_iteration = 0
    last_transition_id: str | None = None
    loop_instance_id: str | None = None
    active_resume_state: str | None = None
    current_contract_binding: dict[str, Any] | None = None
    current_state_machine_binding: dict[str, Any] | None = None

    for index, item in enumerate(history, start=1):
        event = require_mapping(item, f"event_history[{index - 1}]", errors)
        require_keys(event, REQUIRED_EVENT_FIELDS, f"event_history[{index - 1}]", errors)
        event_id = event.get("event_id")
        mutation_id = event.get("mutation_id")
        if not isinstance(event_id, str) or not event_id:
            errors.append(f"event_history[{index - 1}].event_id 必须是非空字符串")
        if not isinstance(mutation_id, str) or not mutation_id:
            errors.append(f"event_history[{index - 1}].mutation_id 必须是非空字符串")
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
        if integrity.get("canonicalization") != "registry-event-canonical-json-v1":
            errors.append(
                f"event_history[{index - 1}].integrity.canonicalization 不合法"
            )
        if integrity.get("digest_algorithm") != "sha256":
            errors.append(
                f"event_history[{index - 1}].integrity.digest_algorithm 必须为 sha256"
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
        payload_contract = payload_contracts.get(event_type)
        if not isinstance(payload_contract, dict):
            errors.append(f"event_history[{index - 1}] 缺少对应的 Event Payload Contract")
            payload_contract = {}
        for field in payload_contract.get("required_fields", []):
            if field not in payload:
                errors.append(f"event_history[{index - 1}].payload.{field} 缺失")
        if event_type == "core.input_bound" and contract_doc is not None:
            input_slot_id = payload.get("input_slot_id")
            if input_slot_id not in contract_input_ids:
                errors.append(
                    f"event_history[{index - 1}] 引用了未知 input_slot_id: {input_slot_id}"
                )
        if event_type == "core.output_registered" and contract_doc is not None:
            deliverable_id = payload.get("deliverable_id")
            if deliverable_id not in contract_deliverable_ids:
                errors.append(
                    f"event_history[{index - 1}] 引用了未知 deliverable_id: {deliverable_id}"
                )
        binding_snapshot = require_mapping(
            event.get("binding_snapshot"),
            f"event_history[{index - 1}].binding_snapshot",
            errors,
        )
        if index == 1:
            if event_type != "core.loop_registered":
                errors.append("第一条 Event 必须是 core.loop_registered")
            current_state = payload.get("initial_state")
            if current_state != state_machine_doc.get("state_machine", {}).get("initial_state"):
                errors.append("注册事件 initial_state 与状态机不一致")
            current_contract_binding = require_mapping(
                payload.get("contract_binding"),
                "event_history[0].payload.contract_binding",
                errors,
            )
            current_state_machine_binding = require_mapping(
                payload.get("state_machine_binding"),
                "event_history[0].payload.state_machine_binding",
                errors,
            )
            if binding_snapshot.get("contract_digest") != current_contract_binding.get(
                "contract_digest"
            ):
                errors.append("event_history[0] 的 contract_digest 与注册绑定不一致")
            if binding_snapshot.get(
                "state_machine_digest"
            ) != current_state_machine_binding.get("state_machine_digest"):
                errors.append("event_history[0] 的 state_machine_digest 与注册绑定不一致")
            continue

        if current_contract_binding is not None and binding_snapshot.get(
            "contract_digest"
        ) != current_contract_binding.get("contract_digest"):
            errors.append(
                f"event_history[{index - 1}] 的 contract_digest 与有效绑定不一致"
            )
        if current_state_machine_binding is not None and binding_snapshot.get(
            "state_machine_digest"
        ) != current_state_machine_binding.get("state_machine_digest"):
            errors.append(
                f"event_history[{index - 1}] 的 state_machine_digest 与有效绑定不一致"
            )

        if event_type == "core.contract_migrated":
            current_contract_binding = require_mapping(
                payload.get("contract_after"),
                f"event_history[{index - 1}].payload.contract_after",
                errors,
            )
        elif event_type == "core.state_machine_migrated":
            current_state_machine_binding = require_mapping(
                payload.get("state_machine_after"),
                f"event_history[{index - 1}].payload.state_machine_after",
                errors,
            )

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
    snapshot_contract_binding = require_mapping(
        snapshot.get("contract_binding"), "registry_snapshot.contract_binding", errors
    )
    if current_contract_binding is not None:
        for key in ("contract_id", "contract_version", "contract_digest"):
            if snapshot_contract_binding.get(key) != current_contract_binding.get(key):
                errors.append(f"Snapshot {key} 与 Event History 有效绑定不一致")
    snapshot_state_machine_binding = require_mapping(
        snapshot.get("state_machine_binding"),
        "registry_snapshot.state_machine_binding",
        errors,
    )
    if current_state_machine_binding is not None:
        for key in (
            "state_machine_id",
            "state_machine_version",
            "state_machine_digest",
        ):
            if snapshot_state_machine_binding.get(key) != current_state_machine_binding.get(key):
                errors.append(f"Snapshot {key} 与 Event History 有效绑定不一致")
    return errors


def validate_static_contracts(
    event_doc: Any,
    contract_doc: Any,
    state_machine_doc: Any,
) -> list[str]:
    """Validate Event, Loop Contract, and state-machine definitions only."""
    errors: list[str] = []
    event_root = require_mapping(event_doc, "event 文档", errors)
    event = require_mapping(event_root.get("event"), "event", errors)
    contract_root = require_mapping(contract_doc, "contract 文档", errors)
    contract = require_mapping(contract_root.get("loop_contract"), "loop_contract", errors)
    machine_root = require_mapping(state_machine_doc, "state machine 文档", errors)
    machine = require_mapping(machine_root.get("state_machine"), "state_machine", errors)

    require_keys(event, REQUIRED_EVENT_FIELDS, "event", errors)
    if contract.get("schema_version") != "0.2":
        errors.append("loop_contract.schema_version 必须为 0.2")
    if not contract.get("contract_id"):
        errors.append("loop_contract.contract_id 不能为空")
    if contract.get("version") is None:
        errors.append("loop_contract.version 不能为空")
    if machine.get("version") != "0.2":
        errors.append("state_machine.version 必须为 0.2")
    errors.extend(validate_asset_loop_policy(contract_doc))

    required_inputs = contract_root.get("start", {}).get("required_inputs")
    if not isinstance(required_inputs, list):
        errors.append("start.required_inputs 必须是列表")
        required_inputs = []
    input_ids = [
        item.get("input_slot_id") for item in required_inputs if isinstance(item, dict)
    ]
    if any(not value for value in input_ids):
        errors.append("Contract required_inputs 的 input_slot_id 不能为空")
    if len(input_ids) != len(set(input_ids)):
        errors.append("Contract required_inputs 的 input_slot_id 不得重复")

    required_deliverables = contract_root.get("purpose", {}).get("required_deliverables")
    if not isinstance(required_deliverables, list):
        errors.append("purpose.required_deliverables 必须是列表")
        required_deliverables = []
    deliverable_ids = [
        item.get("deliverable_id")
        for item in required_deliverables
        if isinstance(item, dict)
    ]
    if any(not value for value in deliverable_ids):
        errors.append("Contract required_deliverables 的 deliverable_id 不能为空")
    if len(deliverable_ids) != len(set(deliverable_ids)):
        errors.append("Contract required_deliverables 的 deliverable_id 不得重复")

    states = set(machine_root.get("states", {}))
    if states != STATES:
        errors.append(f"状态集合不符合默认 Registry 契约: {sorted(states)}")
    if set(machine.get("interruption_states", [])) != INTERRUPTION_STATES:
        errors.append("中断状态集合不符合默认 Registry 契约")
    if set(machine.get("operational_states", [])) != RESUME_STATES:
        errors.append("可恢复 operational state 集合不符合默认 Registry 契约")

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


def validate_snapshot_structure(
    snapshot_doc: Any,
    state_machine_doc: Any,
    *,
    location: str = "registry_snapshot",
) -> list[str]:
    errors: list[str] = []
    snapshot_root = require_mapping(snapshot_doc, "snapshot 文档", errors)
    snapshot = require_mapping(snapshot_root.get("registry_snapshot"), location, errors)
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
        location,
        errors,
    )
    runtime = require_mapping(snapshot.get("runtime"), f"{location}.runtime", errors)
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
        f"{location}.runtime",
        errors,
    )
    resources = require_mapping(snapshot.get("resources"), f"{location}.resources", errors)
    if not isinstance(resources.get("inputs"), list):
        errors.append(f"{location}.resources.inputs 必须是列表")
    if not isinstance(resources.get("outputs"), list):
        errors.append(f"{location}.resources.outputs 必须是列表")

    machine = require_mapping(
        require_mapping(state_machine_doc, "state machine 文档", errors).get("state_machine"),
        "state_machine",
        errors,
    )
    state_binding = require_mapping(
        snapshot.get("state_machine_binding"), f"{location}.state_machine_binding", errors
    )
    if state_binding.get("state_machine_id") != machine.get("state_machine_id"):
        errors.append("Snapshot 绑定的 state_machine_id 与状态机不一致")
    if state_binding.get("state_machine_version") != machine.get("version"):
        errors.append("Snapshot 绑定的 state_machine_version 与状态机不一致")

    topology_rules = snapshot_root.get("storage_contract", {}).get("topology_rules", [])
    topology_rules_text = "\n".join(
        item for item in topology_rules if isinstance(item, str)
    )
    for phrase in ("不得等于当前 loop_instance_id", "父 Loop 图必须无环", "blocking=true 的依赖图必须无环"):
        if phrase not in topology_rules_text:
            errors.append(f"Registry 拓扑规则缺少: {phrase}")
    return errors


def validate_record_template(
    record_template_doc: Any,
    state_machine_doc: Any,
) -> list[str]:
    """Validate the independent draft record template without a project Contract."""
    errors = validate_snapshot_structure(
        record_template_doc,
        state_machine_doc,
        location="record_template.registry_snapshot",
    )
    root = require_mapping(record_template_doc, "record template 文档", errors)
    snapshot = require_mapping(
        root.get("registry_snapshot"), "record_template.registry_snapshot", errors
    )
    machine = require_mapping(
        require_mapping(state_machine_doc, "state machine 文档", errors).get("state_machine"),
        "state_machine",
        errors,
    )
    runtime = require_mapping(
        snapshot.get("runtime"), "record_template.registry_snapshot.runtime", errors
    )
    if runtime.get("current_state") != machine.get("initial_state"):
        errors.append("Record Template 初始状态必须等于状态机 initial_state")
    if runtime.get("current_iteration") != 0:
        errors.append("Record Template current_iteration 必须从 0 开始")
    if runtime.get("last_event_sequence") != 1 or runtime.get("record_revision") != 1:
        errors.append("Record Template 必须位于 sequence=1、record_revision=1")
    resources = require_mapping(
        snapshot.get("resources"), "record_template.registry_snapshot.resources", errors
    )
    if resources.get("inputs") != [] or resources.get("outputs") != []:
        errors.append("Record Template 的 draft 注册基线 inputs 和 outputs 必须为空")
    field_examples = require_mapping(root.get("field_examples"), "field_examples", errors)
    input_example = require_mapping(
        field_examples.get("input_binding"), "field_examples.input_binding", errors
    )
    output_example = require_mapping(
        field_examples.get("output_registration"), "field_examples.output_registration", errors
    )
    if not input_example.get("input_slot_id"):
        errors.append("Record Template input_binding 示例缺少 input_slot_id")
    if not output_example.get("deliverable_id"):
        errors.append("Record Template output_registration 示例缺少 deliverable_id")
    return errors


def validate_runtime_snapshot(
    snapshot_doc: Any,
    contract_doc: Any,
    state_machine_doc: Any,
    record_template_doc: Any | None = None,
    project_root: Path | None = None,
) -> list[str]:
    """Validate an active/materialized Snapshot without draft-only invariants."""
    errors = validate_snapshot_structure(snapshot_doc, state_machine_doc)
    snapshot_root = require_mapping(snapshot_doc, "snapshot 文档", errors)
    snapshot = require_mapping(snapshot_root.get("registry_snapshot"), "registry_snapshot", errors)
    contract_root = require_mapping(contract_doc, "contract 文档", errors)
    contract = require_mapping(contract_root.get("loop_contract"), "loop_contract", errors)
    contract_binding = require_mapping(
        snapshot.get("contract_binding"), "registry_snapshot.contract_binding", errors
    )
    if contract_binding.get("contract_id") != contract.get("contract_id"):
        errors.append("Snapshot 绑定的 contract_id 与 Contract 不一致")
    if contract_binding.get("contract_version") != contract.get("version"):
        errors.append("Snapshot 绑定的 contract_version 与 Contract 不一致")

    if record_template_doc is not None:
        template_root = require_mapping(record_template_doc, "record template 文档", errors)
        template_snapshot = require_mapping(
            template_root.get("registry_snapshot"),
            "record_template.registry_snapshot",
            errors,
        )
        if snapshot.get("schema_version") != template_snapshot.get("schema_version"):
            errors.append("Snapshot schema_version 与 Record Template 不一致")

    input_ids = {
        item.get("input_slot_id")
        for item in contract_root.get("start", {}).get("required_inputs", [])
        if isinstance(item, dict)
    }
    deliverable_ids = {
        item.get("deliverable_id")
        for item in contract_root.get("purpose", {}).get("required_deliverables", [])
        if isinstance(item, dict)
    }
    resources = require_mapping(snapshot.get("resources"), "registry_snapshot.resources", errors)
    snapshot_input_ids: list[Any] = []
    resource_inputs = resources.get("inputs", [])
    if not isinstance(resource_inputs, list):
        resource_inputs = []
    for index, item in enumerate(resource_inputs):
        resource = require_mapping(item, f"registry_snapshot.resources.inputs[{index}]", errors)
        input_slot_id = resource.get("input_slot_id")
        snapshot_input_ids.append(input_slot_id)
        if input_slot_id not in input_ids:
            errors.append(f"Snapshot 引用了未知 input_slot_id: {input_slot_id}")
    if len(snapshot_input_ids) != len(set(snapshot_input_ids)):
        errors.append("Snapshot resources.inputs 的 input_slot_id 不得重复")

    snapshot_output_ids: list[Any] = []
    resource_outputs = resources.get("outputs", [])
    if not isinstance(resource_outputs, list):
        resource_outputs = []
    for index, item in enumerate(resource_outputs):
        resource = require_mapping(item, f"registry_snapshot.resources.outputs[{index}]", errors)
        deliverable_id = resource.get("deliverable_id")
        snapshot_output_ids.append(deliverable_id)
        if deliverable_id not in deliverable_ids:
            errors.append(f"Snapshot 引用了未知 deliverable_id: {deliverable_id}")
    if len(snapshot_output_ids) != len(set(snapshot_output_ids)):
        errors.append("Snapshot resources.outputs 的 deliverable_id 不得重复")
    asset_result = validate_specialist_asset_loop(
        contract_doc,
        snapshot_doc,
        project_root=project_root,
    )
    errors.extend(f"Specialist Asset Loop: {message}" for message in asset_result["errors"])
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
    parser = argparse.ArgumentParser(
        description=(
            "校验 Loop Registry。未提供 --history 时为 draft 注册模板模式；"
            "提供 --history 时为运行态 Snapshot + Event History 重放模式。"
        ),
        epilog=(
            "运行态完整校验建议同时提供 --record-template；该模板只按 draft 结构校验，"
            "不会与运行态 Snapshot 混用。"
        ),
    )
    parser.add_argument(
        "--snapshot",
        required=True,
        type=Path,
        help="模板模式中的 draft Snapshot，或运行态模式中的物化 Snapshot",
    )
    parser.add_argument(
        "--event", required=True, type=Path, help="Event 与 Payload Contract 模板"
    )
    parser.add_argument("--contract", required=True, type=Path, help="Loop Contract")
    parser.add_argument(
        "--state-machine", required=True, type=Path, help="绑定的状态机定义"
    )
    parser.add_argument(
        "--history",
        type=Path,
        help="Event History；提供后进入运行态重放模式",
    )
    parser.add_argument(
        "--record-template",
        type=Path,
        help="运行态模式可选的独立 draft Record Template；不得替代 --snapshot",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="专业资产 Loop 运行态必须提供，用于核对 Contract 文件、摘要和 Gate",
    )
    args = parser.parse_args()

    if args.record_template is not None and args.history is None:
        print("--record-template 只能与 --history 一起用于运行态模式", file=sys.stderr)
        return 2

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

    mode = "template"
    if args.history is None:
        errors = validate_templates(*documents)
    else:
        mode = "runtime"
        try:
            history_doc = read_yaml(args.history)
            record_template_doc = (
                read_yaml(args.record_template) if args.record_template is not None else None
            )
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            print(f"无法读取运行态 Registry 输入: {exc}", file=sys.stderr)
            return 2
        errors = validate_static_contracts(documents[1], documents[2], documents[3])
        if record_template_doc is not None:
            errors.extend(validate_record_template(record_template_doc, documents[3]))
        errors.extend(
            validate_runtime_snapshot(
                documents[0],
                documents[2],
                documents[3],
                record_template_doc,
                args.project_root,
            )
        )
        errors.extend(
            validate_history(
                documents[0],
                history_doc,
                documents[3],
                documents[1],
                documents[2],
            )
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if mode == "template":
        print("OK: Loop Registry draft 注册模板、Event、Contract 与状态机契约一致")
    else:
        print("OK: Loop Registry 运行态 Snapshot、Event History 与静态契约一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
