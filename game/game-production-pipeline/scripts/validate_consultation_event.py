#!/usr/bin/env python3
"""Validate concrete consultation events and replay their recorded metadata, read-only.

This checks recorded claims, not real actor identity, Registry authority, approval
authenticity, message delivery or host-tool enforcement. Replay never calls a model
or tool and never applies recommendations to a project fact source.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import yaml

from pipeline_common import PROJECT_ID_RE, canonical_digest, load_yaml


CANONICALIZATION = "consultation-event-canonical-json-v1"
EVENT_TYPES = {
    "consultation.opened", "peer.question", "peer.response", "peer.challenge",
    "coordinator.summary", "approval.requested", "consultation.closed",
}
SLOT_IDS = {f"slot:{name}" for name in ("planning", "art", "programming", "audio", "qa", "tools")}
ACTOR_ROLES = {"project_manager", "product_manager", "department_manager", "reviewer", "human_owner"}
ACTOR_KINDS = {"human", "position", "instance", "system"}
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
ULID_RE = r"[0-9A-HJKMNP-TV-Z]{26}"
PLACEHOLDER_RE = re.compile(r"<[^<>]+>")


def event_value(document: Any) -> Any:
    """Accept either a concrete event mapping or its YAML document envelope."""
    if isinstance(document, dict) and "consultation_event" in document:
        return document["consultation_event"]
    return document


def canonical_event_digest(document: Any) -> str:
    event = copy.deepcopy(event_value(document))
    if not isinstance(event, dict) or not isinstance(event.get("integrity"), dict):
        raise ValueError("consultation_event.integrity 必须是映射")
    event["integrity"]["event_digest"] = None
    return canonical_digest(event)


def _mapping(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} 必须是映射")
        return {}
    return value


def _list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{path} 必须是数组")
        return []
    return value


def _text(value: Any, path: str, errors: list[str], *, nullable: bool = False) -> bool:
    if nullable and value is None:
        return True
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} 必须是非空字符串")
        return False
    return True


def _enum(value: Any, allowed: set[str], path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{path} 不在允许集合: {sorted(allowed)}")


def _integer(value: Any, path: str, errors: list[str], *, minimum: int = 0) -> bool:
    if type(value) is not int or value < minimum:
        errors.append(f"{path} 必须是 >= {minimum} 的整数")
        return False
    return True


def _digest(value: Any, path: str, errors: list[str], *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        errors.append(f"{path} 必须是 64 位小写 SHA-256")


def _timestamp(value: Any, path: str, errors: list[str]) -> datetime | None:
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except ValueError:
        errors.append(f"{path} 必须是带时区的 ISO 8601 字符串")
        return None


def _strings(value: Any, path: str, errors: list[str], *, nonempty: bool = False) -> list[str]:
    items = _list(value, path, errors)
    result = []
    for index, item in enumerate(items):
        if _text(item, f"{path}[{index}]", errors):
            result.append(item)
    if nonempty and not items:
        errors.append(f"{path} 不能为空")
    return result


def _json_values(value: Any, path: str, errors: list[str], active: set[int] | None = None) -> None:
    active = active if active is not None else set()
    if isinstance(value, (dict, list)):
        if id(value) in active:
            errors.append(f"{path} 不允许循环引用")
            return
        active.add(id(value))
        entries = value.items() if isinstance(value, dict) else enumerate(value)
        for key, item in entries:
            if isinstance(value, dict) and not isinstance(key, str):
                errors.append(f"{path} 的对象键必须是字符串")
            _json_values(item, f"{path}.{key}", errors, active)
        active.remove(id(value))
    elif isinstance(value, str):
        if PLACEHOLDER_RE.search(value):
            errors.append(f"{path} 含未填写的模板占位符")
    elif type(value) is float:
        if not math.isfinite(value):
            errors.append(f"{path} 不允许非有限数字")
    elif value is not None and type(value) not in {bool, int}:
        errors.append(f"{path} 必须是 JSON 类型")


def _actor(value: Any, path: str, errors: list[str], *, participant: bool = False) -> dict[str, Any]:
    actor = _mapping(value, path, errors)
    kinds = ACTOR_KINDS - {"system"} if participant else ACTOR_KINDS
    _enum(actor.get("actor_kind"), kinds, f"{path}.actor_kind", errors)
    _text(actor.get("actor_id"), f"{path}.actor_id", errors)
    _enum(actor.get("role"), ACTOR_ROLES, f"{path}.role", errors)
    if actor.get("slot_id") is not None:
        _enum(actor.get("slot_id"), SLOT_IDS, f"{path}.slot_id", errors)
    if actor.get("role") == "department_manager" and actor.get("slot_id") not in SLOT_IDS:
        errors.append(f"{path} 部门经理必须声明合法 slot_id")
    if actor.get("role") == "human_owner" and actor.get("actor_kind") != "human":
        errors.append(f"{path} human_owner 必须声明 human actor_kind；真实性仍需执行层核查")
    if participant:
        _enum(actor.get("participation"), {"required", "consulted", "observer"}, f"{path}.participation", errors)
    return actor


def _validate_event(
    document: Any,
    *,
    previous_event: Any = None,
    prior_events: list[dict] | None = None,
    expected_sequence: int | None = None,
) -> list[str]:
    errors: list[str] = []
    event = _mapping(event_value(document), "consultation_event", errors)
    _json_values(event, "consultation_event", errors)
    if event.get("schema_version") != "0.1-alpha":
        errors.append("schema_version 必须为 0.1-alpha")
    identity = _mapping(event.get("identity"), "identity", errors)
    project = identity.get("project_id")
    if not isinstance(project, str) or not PROJECT_ID_RE.fullmatch(project):
        errors.append("identity.project_id 必须是有效项目 ID")
    for name, prefix in (("consultation_event_id", "conevt"), ("mutation_id", "mut"), ("consultation_id", "con")):
        value = identity.get(name)
        if not isinstance(value, str) or not re.fullmatch(rf"{prefix}:{re.escape(str(project))}:{ULID_RE}", value):
            errors.append(f"identity.{name} 必须使用 {prefix}:project_id:ULID")
    event_type = identity.get("event_type")
    extension = isinstance(event_type, str) and bool(re.fullmatch(rf"project\.{re.escape(str(project))}\.[a-z][a-z0-9_.-]*", event_type))
    if not isinstance(event_type, str) or (event_type not in EVENT_TYPES and not extension):
        errors.append("identity.event_type 必须是单个合法事件类型或本项目命名空间扩展")
    sequence_ok = _integer(identity.get("sequence"), "identity.sequence", errors, minimum=1)
    occurred = _timestamp(identity.get("occurred_at"), "identity.occurred_at", errors)
    recorded = _timestamp(identity.get("recorded_at"), "identity.recorded_at", errors)
    if occurred and recorded and recorded < occurred:
        errors.append("identity.recorded_at 不能早于 occurred_at")
    causality = _mapping(event.get("causality"), "causality", errors)
    _text(causality.get("correlation_id"), "causality.correlation_id", errors)
    for name in ("causation_event_id", "request_id"):
        _text(causality.get(name), f"causality.{name}", errors, nullable=True)
    concurrency = _mapping(event.get("concurrency"), "concurrency", errors)
    expected = concurrency.get("expected_consultation_sequence")
    resulting = concurrency.get("resulting_consultation_sequence")
    expected_ok = _integer(expected, "concurrency.expected_consultation_sequence", errors)
    resulting_ok = _integer(resulting, "concurrency.resulting_consultation_sequence", errors, minimum=1)
    if expected_sequence is not None:
        if type(expected_sequence) is not int or expected_sequence < 0:
            errors.append("expected_sequence 必须是 >= 0 的整数")
        elif expected != expected_sequence:
            errors.append("concurrency.expected_consultation_sequence 与外部水位不一致")
    if expected_ok and resulting_ok and (resulting != expected + 1 or resulting != identity.get("sequence")):
        errors.append("sequence/resulting 必须等于 expected + 1")

    topology = _mapping(event.get("topology"), "topology", errors)
    if topology.get("mode") != "peer_to_peer_with_coordinator":
        errors.append("topology.mode 必须为 peer_to_peer_with_coordinator")
    coordinator = _actor(topology.get("coordinator"), "topology.coordinator", errors)
    if coordinator.get("role") != "project_manager" or coordinator.get("actor_kind") not in {"position", "instance"}:
        errors.append("topology.coordinator 必须为 project_manager Position/Instance")
    _actor(topology.get("initiator"), "topology.initiator", errors)
    participants = {}
    participant_order = []
    for index, raw in enumerate(_list(topology.get("participants"), "topology.participants", errors)):
        item = _actor(raw, f"topology.participants[{index}]", errors, participant=True)
        actor_id = item.get("actor_id")
        if isinstance(actor_id, str):
            if actor_id in participants:
                errors.append("topology.participants actor_id 不得重复")
            participants[actor_id] = item
            participant_order.append(actor_id)
    if len(participants) < 2 or coordinator.get("actor_id") not in participants:
        errors.append("participants 必须包含 coordinator 和至少一个咨询参与者")
    if participant_order != sorted(participant_order):
        errors.append("topology.participants 必须按 actor_id 排序")
    if coordinator.get("actor_id") in participants:
        record = participants[coordinator["actor_id"]]
        if any(record.get(key) != coordinator.get(key) for key in ("actor_kind", "role")):
            errors.append("coordinator 身份与 participants 不一致")
    for index, raw in enumerate(_list(topology.get("direct_peer_links"), "topology.direct_peer_links", errors)):
        link = _mapping(raw, f"topology.direct_peer_links[{index}]", errors)
        for key in ("from_actor_id", "to_actor_id"):
            if not isinstance(link.get(key), str) or link[key] not in participants:
                errors.append(f"direct_peer_links[{index}].{key} 必须来自 participants")
        if link.get("from_actor_id") == link.get("to_actor_id"):
            errors.append("direct_peer_links 不得指向自身")
        _text(link.get("purpose"), f"direct_peer_links[{index}].purpose", errors)
        expiry = _timestamp(link.get("expires_at"), f"direct_peer_links[{index}].expires_at", errors)
        if occurred and expiry and expiry <= occurred:
            errors.append("direct_peer_links 在事件发生时已过期")
    actor = _actor(event.get("actor"), "actor", errors)
    actor_id = actor.get("actor_id")
    if not isinstance(actor_id, str) or actor_id not in participants:
        errors.append("actor 必须来自 participants")
    else:
        if any(actor.get(key) != participants[actor_id].get(key) for key in ("actor_kind", "role", "slot_id")):
            errors.append("actor 身份/槽位与 participants 不一致")
    for name in ("position_id", "instance_id"):
        _text(actor.get(name), f"actor.{name}", errors, nullable=True)
    if actor.get("actor_kind") == "position" and actor.get("position_id") != actor_id:
        errors.append("actor.position_id 必须与 Position actor_id 一致")
    if actor.get("actor_kind") == "instance" and (actor.get("instance_id") != actor_id or not actor.get("position_id")):
        errors.append("actor Instance 必须绑定相同 instance_id 和有效 position_id")
    if event_type in {"coordinator.summary", "consultation.closed"} and actor_id != coordinator.get("actor_id"):
        errors.append(f"{event_type} 必须由 coordinator 记录")

    governance = _mapping(event.get("governance_binding"), "governance_binding", errors)
    snapshot = _mapping(governance.get("organization_snapshot"), "governance_binding.organization_snapshot", errors)
    if snapshot.get("project_id") != project:
        errors.append("organization_snapshot.project_id 必须与事件项目一致")
    _integer(snapshot.get("organization_revision"), "organization_snapshot.organization_revision", errors, minimum=1)
    _digest(snapshot.get("snapshot_digest"), "organization_snapshot.snapshot_digest", errors)
    context = _mapping(governance.get("project_context"), "governance_binding.project_context", errors)
    _text(context.get("brief_ref"), "project_context.brief_ref", errors)
    for name in ("prd_ref", "gdd_ref"):
        _text(context.get(name), f"project_context.{name}", errors, nullable=True)
    _digest(context.get("context_digest"), "project_context.context_digest", errors)
    authority = _mapping(governance.get("authority_ref"), "governance_binding.authority_ref", errors)
    for name in ("id", "version"):
        _text(authority.get(name), f"authority_ref.{name}", errors)
    _digest(authority.get("digest"), "authority_ref.digest", errors)
    approvals = _strings(governance.get("approval_refs"), "governance_binding.approval_refs", errors)
    payload = _mapping(event.get("payload"), "payload", errors)
    _strings(payload.get("evidence_refs"), "payload.evidence_refs", errors)

    def recipients(value: Any, path: str) -> None:
        for recipient in _strings(value, path, errors, nonempty=True):
            if recipient not in participants:
                errors.append(f"{path} 收件人必须来自 participants")

    if event_type == "peer.question" or "question" in payload:
        question = _mapping(payload.get("question"), "payload.question", errors)
        for key in ("question_id", "text", "requested_output"):
            _text(question.get(key), f"payload.question.{key}", errors)
        if question.get("requested_by") != actor_id:
            errors.append("payload.question.requested_by 必须是当前 actor")
        recipients(question.get("recipient_actor_ids"), "payload.question.recipient_actor_ids")
        _timestamp(question.get("due_at"), "payload.question.due_at", errors)
    response = {}
    conflicts = []
    if event_type in {"peer.response", "peer.challenge", "coordinator.summary", "approval.requested", "consultation.closed"} or "response" in payload:
        response = _mapping(payload.get("response"), "payload.response", errors)
        for key in ("response_id", "summary", "requested_action"):
            _text(response.get(key), f"payload.response.{key}", errors)
        _text(response.get("in_reply_to_event_id"), "payload.response.in_reply_to_event_id", errors, nullable=True)
        if event_type in {"peer.response", "peer.challenge"} or "recipient_actor_ids" in response:
            recipients(response.get("recipient_actor_ids"), "payload.response.recipient_actor_ids")
        _enum(response.get("stance"), {"proposal", "recommendation", "objection", "clarification", "acceptance_note"}, "payload.response.stance", errors)
        option_ids = []
        for index, raw in enumerate(_list(response.get("options"), "payload.response.options", errors)):
            option = _mapping(raw, f"payload.response.options[{index}]", errors)
            if _text(option.get("option_id"), "option.option_id", errors):
                option_ids.append(option["option_id"])
            for key in ("title", "description"):
                _text(option.get(key), f"option.{key}", errors)
            for key in ("benefits", "costs", "risks", "dependencies", "evidence_refs"):
                _strings(option.get(key), f"option.{key}", errors)
        if len(set(option_ids)) != len(option_ids):
            errors.append("response.options option_id 不得重复")
        if response.get("recommended_option_id") is not None and response.get("recommended_option_id") not in option_ids:
            errors.append("recommended_option_id 必须引用 options 中的选项")
        for key in ("assumptions", "unknowns"):
            _strings(response.get(key), f"payload.response.{key}", errors)
        conflict_ids = []
        for index, raw in enumerate(_list(response.get("conflicts"), "payload.response.conflicts", errors)):
            conflict = _mapping(raw, f"payload.response.conflicts[{index}]", errors)
            conflicts.append(conflict)
            for key in ("conflict_id", "with_actor_id", "subject", "proposed_resolution"):
                _text(conflict.get(key), f"conflict.{key}", errors)
            if isinstance(conflict.get("conflict_id"), str):
                conflict_ids.append(conflict["conflict_id"])
            other = participants.get(conflict.get("with_actor_id")) if isinstance(conflict.get("with_actor_id"), str) else None
            if other is None:
                errors.append("conflict.with_actor_id 必须来自 participants")
            if type(conflict.get("escalation_required")) is not bool:
                errors.append("conflict.escalation_required 必须是布尔值")
            # This protects structured QA disputes; free text is not semantic proof.
            if (actor.get("slot_id") == "slot:qa" or (other and other.get("slot_id") == "slot:qa")) and conflict.get("escalation_required") is not True:
                errors.append("QA 独立验收冲突必须升级，不得由生产槽位覆盖或降级")
        if len(set(conflict_ids)) != len(conflict_ids):
            errors.append("response.conflicts conflict_id 不得重复")
        if event_type == "peer.challenge" and not conflicts:
            errors.append("peer.challenge 必须至少记录一项 conflict")
        handoff = _mapping(payload.get("handoff"), "payload.handoff", errors)
        for key in ("owner_actor_id", "rollback"):
            _text(handoff.get(key), f"payload.handoff.{key}", errors)
        for key in ("output_refs", "acceptance_refs"):
            _strings(handoff.get(key), f"payload.handoff.{key}", errors, nonempty=True)

    effect = _mapping(event.get("authority_effect"), "authority_effect", errors)
    status = effect.get("decision_status")
    _enum(status, {"advisory_only", "coordinator_recommendation", "pending_human_approval", "approved", "rejected"}, "authority_effect.decision_status", errors)
    _enum(effect.get("required_next_gate"), {"none", "project_manager_summary", "domain_review", "human_approval"}, "authority_effect.required_next_gate", errors)
    changed = False
    for key in ("changes_project_fact", "changes_scope_priority_budget", "changes_ownership_or_acceptance"):
        if type(effect.get(key)) is not bool:
            errors.append(f"authority_effect.{key} 必须是布尔值")
        changed = changed or effect.get(key) is True
    if effect.get("writes_to_source_of_truth") != []:
        errors.append("咨询事件不得直接写入事实源，writes_to_source_of_truth 必须为空")
    if changed and (status != "pending_human_approval" or effect.get("required_next_gate") != "human_approval"):
        errors.append("涉及事实/范围/所有权变化的提案必须 pending_human_approval 并进入 human_approval")
    if status == "pending_human_approval" and effect.get("required_next_gate") != "human_approval":
        errors.append("pending_human_approval 必须进入 human_approval")
    if status == "approved" and (actor.get("actor_kind") != "human" or actor.get("role") != "human_owner" or not approvals):
        errors.append("单事件 approved 必须声明 human_owner 和 approval_refs；不能用经理意见冒充人类批准")
    if event_type == "approval.requested" and status != "pending_human_approval":
        errors.append("approval.requested 必须保持 pending_human_approval")
    if any(item.get("escalation_required") is True for item in conflicts) and effect.get("required_next_gate") == "none":
        errors.append("存在升级冲突时 required_next_gate 不能为 none")
    if actor.get("slot_id") == "slot:qa" and status == "approved":
        errors.append("QA 专业验收意见不等于人类批准")

    integrity = _mapping(event.get("integrity"), "integrity", errors)
    if integrity.get("canonicalization") != CANONICALIZATION:
        errors.append(f"integrity.canonicalization 必须为 {CANONICALIZATION}")
    if integrity.get("digest_algorithm") != "sha256":
        errors.append("integrity.digest_algorithm 必须为 sha256")
    _digest(integrity.get("event_digest"), "integrity.event_digest", errors)
    _digest(integrity.get("previous_event_digest"), "integrity.previous_event_digest", errors, nullable=True)
    try:
        if integrity.get("event_digest") != canonical_event_digest(event):
            errors.append("integrity.event_digest 不匹配")
    except (ValueError, TypeError, RecursionError) as exc:
        errors.append(f"事件不能进行 canonical JSON 摘要: {exc}")
    previous = event_value(previous_event)
    if sequence_ok and identity["sequence"] == 1:
        if expected != 0 or integrity.get("previous_event_digest") is not None or previous is not None:
            errors.append("首事件必须从水位 0 开始，previous_event_digest 为 null 且无前驱")
        if event_type != "consultation.opened":
            errors.append("首事件必须为 consultation.opened")
    elif sequence_ok:
        if not isinstance(previous, dict):
            errors.append("后续事件必须提供 previous_event 或完整 prior_events 才能核对前驱链")
        else:
            previous_identity = _mapping(previous.get("identity"), "previous_event.identity", errors)
            previous_integrity = _mapping(previous.get("integrity"), "previous_event.integrity", errors)
            if previous_identity.get("consultation_id") != identity.get("consultation_id") or previous_identity.get("project_id") != project:
                errors.append("前驱必须属于同一 consultation/project")
            if expected != previous_identity.get("sequence"):
                errors.append("expected_consultation_sequence 与前驱水位不一致")
            if integrity.get("previous_event_digest") != previous_integrity.get("event_digest"):
                errors.append("previous_event_digest 与前驱摘要不匹配")
            try:
                if previous_integrity.get("event_digest") != canonical_event_digest(previous):
                    errors.append("previous_event.event_digest 不匹配")
            except (ValueError, TypeError, RecursionError):
                errors.append("previous_event 不能进行 canonical JSON 摘要")
            if previous_identity.get("event_type") == "consultation.closed":
                errors.append("consultation.closed 后不得追加业务事件")
            if event_type == "consultation.opened":
                errors.append("consultation.opened 只能是首事件")
            previous_governance = previous.get("governance_binding", {})
            if isinstance(previous_governance, dict):
                for key in ("organization_snapshot", "project_context"):
                    if governance.get(key) != previous_governance.get(key):
                        errors.append(f"同轮咨询 {key} 漂移，必须重新咨询")
    if event_type == "consultation.closed":
        if prior_events is None or not any(item.get("identity", {}).get("event_type") == "coordinator.summary" for item in prior_events):
            errors.append("consultation.closed 需要完整历史中的 coordinator.summary 证据")
    return errors


def validate_consultation_event(
    document: Any,
    *,
    previous_event: Any = None,
    prior_events: list[Any] | None = None,
    expected_sequence: int | None = None,
) -> list[str]:
    """Validate one event; pass history to establish a complete, validated prefix."""
    if prior_events is not None:
        result = replay_consultation_events(prior_events)
        if not result["valid"]:
            return [f"prior_events: {message}" for message in result["errors"]]
        unique = result["events"]
        return _validate_event(
            document,
            previous_event=unique[-1] if unique else None,
            prior_events=unique,
            expected_sequence=expected_sequence,
        )
    return _validate_event(document, previous_event=previous_event, expected_sequence=expected_sequence)


def replay_consultation_events(documents: Any) -> dict[str, Any]:
    """Deterministically replay recorded events; exact duplicate deliveries are no-ops."""
    if isinstance(documents, dict):
        documents = documents.get("event_history")
    if not isinstance(documents, list):
        return {"valid": False, "errors": ["event_history 必须是数组"], "events": [], "last_sequence": 0, "last_event_digest": None, "summary_event_ids": [], "closed": False}
    errors = []
    accepted = []
    mutations = {}
    event_ids = {}
    for index, document in enumerate(documents):
        event = event_value(document)
        identity = event.get("identity", {}) if isinstance(event, dict) else {}
        identity = identity if isinstance(identity, dict) else {}
        mutation = identity.get("mutation_id")
        event_id = identity.get("consultation_event_id")
        try:
            payload_digest = canonical_digest(event)
        except (ValueError, TypeError, RecursionError):
            payload_digest = None
        known = []
        for key, seen in ((mutation, mutations), (event_id, event_ids)):
            if isinstance(key, str) and key in seen:
                known.append(seen[key])
        if known:
            if payload_digest is None or any(value != payload_digest for value in known):
                errors.append(f"event_history[{index}] mutation_id/event_id 重放载荷不一致")
                break
            continue
        current_errors = _validate_event(
            event,
            previous_event=accepted[-1] if accepted else None,
            prior_events=accepted,
            expected_sequence=accepted[-1]["identity"]["sequence"] if accepted else 0,
        )
        if current_errors:
            errors.extend(f"event_history[{index}]: {message}" for message in current_errors)
            break
        mutations[mutation] = payload_digest
        event_ids[event_id] = payload_digest
        accepted.append(copy.deepcopy(event))
    last = accepted[-1] if accepted else None
    return {
        "valid": not errors, "errors": errors, "events": accepted,
        "last_sequence": last["identity"]["sequence"] if last else 0,
        "last_event_digest": last["integrity"]["event_digest"] if last else None,
        "summary_event_ids": [item["identity"]["consultation_event_id"] for item in accepted if item["identity"]["event_type"] == "coordinator.summary"],
        "closed": bool(last and last["identity"]["event_type"] == "consultation.closed"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", type=Path, help="单条实值事件 YAML，或 --replay 下的 event_history YAML")
    parser.add_argument("--previous", type=Path, help="紧邻前驱事件；不替代完整历史验证")
    parser.add_argument("--history", type=Path, help="当前事件之前的完整 event_history")
    parser.add_argument("--expected-sequence", type=int, help="外部已提交的当前咨询水位")
    parser.add_argument("--replay", action="store_true", help="只读验证并重放 event_history")
    args = parser.parse_args()
    if args.replay and (args.previous or args.history) or args.previous and args.history:
        parser.error("--replay、--previous 和 --history 不能组合使用")
    try:
        document = load_yaml(args.event)
        if args.replay:
            result = replay_consultation_events(document)
            errors = result["errors"]
        else:
            history = load_yaml(args.history) if args.history else None
            if isinstance(history, dict):
                history = history.get("event_history")
            if args.history and not isinstance(history, list):
                raise ValueError("--history 必须提供 event_history 数组")
            errors = validate_consultation_event(
                document,
                previous_event=load_yaml(args.previous) if args.previous else None,
                prior_events=history,
                expected_sequence=args.expected_sequence,
            )
            result = {"valid": not errors, "errors": errors}
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"无法读取咨询事件: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({key: value for key, value in result.items() if key != "events"}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
