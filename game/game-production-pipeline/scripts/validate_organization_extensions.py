#!/usr/bin/env python3
"""Validate the fixed department-slot, P2P consultation and product handoff templates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment failure
    raise SystemExit("缺少 PyYAML；请先安装插件 scripts/requirements.txt") from exc


SLOT_IDS = {
    "slot:planning",
    "slot:art",
    "slot:programming",
    "slot:audio",
    "slot:qa",
    "slot:tools",
}
SLOT_SLUGS = {slot.removeprefix("slot:") for slot in SLOT_IDS}
EVENT_TYPES = {
    "consultation.opened",
    "peer.question",
    "peer.response",
    "peer.challenge",
    "coordinator.summary",
    "approval.requested",
    "consultation.closed",
}
HANDOFF_STATES = {"draft", "review_pending", "approved", "blocked", "superseded"}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def mapping(value: Any, location: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{location} 必须是映射")
        return {}
    return value


def sequence(value: Any, location: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{location} 必须是数组")
        return []
    return value


def require_keys(value: dict[str, Any], keys: set[str], location: str, errors: list[str]) -> None:
    for key in sorted(keys - value.keys()):
        errors.append(f"{location}.{key} 缺失")


def validate_catalog(document: Any) -> list[str]:
    errors: list[str] = []
    root = mapping(document, "document", errors)
    catalog = mapping(root.get("department_slot_catalog"), "department_slot_catalog", errors)
    require_keys(catalog, {"schema_version", "identity", "fixed_slots", "activation_contract", "manager_contract", "slots", "consistency_rules", "registry_boundary"}, "department_slot_catalog", errors)
    if catalog.get("schema_version") != "0.1-alpha":
        errors.append("department_slot_catalog.schema_version 必须为 0.1-alpha")

    identity = mapping(catalog.get("identity"), "catalog.identity", errors)
    if identity.get("status") != "framework-template":
        errors.append("catalog.identity.status 必须为 framework-template")
    fixed = mapping(catalog.get("fixed_slots"), "catalog.fixed_slots", errors)
    semantics = mapping(fixed.get("semantics"), "catalog.fixed_slots.semantics", errors)
    if semantics.get("fixed_set") is not True:
        errors.append("fixed_slots.semantics.fixed_set 必须为 true")
    if semantics.get("slot_count") != 6:
        errors.append("fixed_slots.semantics.slot_count 必须为 6")
    if semantics.get("slot_ids_are_immutable") is not True:
        errors.append("fixed_slots.semantics.slot_ids_are_immutable 必须为 true")
    if semantics.get("project_registry_materialization") != "never_by_catalog":
        errors.append("目录不得直接物化项目 Registry")
    if semantics.get("manager_activation") != "on_demand_only":
        errors.append("部门经理必须按需激活")
    if semantics.get("default_runtime_instances") != 0:
        errors.append("固定槽位默认 runtime instances 必须为 0")

    slots = sequence(catalog.get("slots"), "catalog.slots", errors)
    actual_ids: list[str] = []
    for index, raw in enumerate(slots):
        slot = mapping(raw, f"catalog.slots[{index}]", errors)
        slot_id = slot.get("slot_id")
        actual_ids.append(slot_id)
        require_keys(slot, {"slot_id", "slug", "display_name", "purpose", "manager_preset", "typical_inputs", "typical_outputs", "acceptance_owner", "independent_from", "can_merge_with", "activation_hint"}, f"catalog.slots[{index}]", errors)
        manager = mapping(slot.get("manager_preset"), f"{slot_id}.manager_preset", errors)
        require_keys(manager, {"preset_id", "preset_version", "profile_ref"}, f"{slot_id}.manager_preset", errors)
        if isinstance(slot_id, str) and slot_id in SLOT_IDS and slot.get("slug") != slot_id.removeprefix("slot:"):
            errors.append(f"{slot_id}.slug 与 slot_id 不一致")
    if set(actual_ids) != SLOT_IDS or len(actual_ids) != len(set(actual_ids)):
        errors.append(f"catalog.slots 必须恰好包含六个固定槽位: {sorted(SLOT_IDS)}")
    art = next((mapping(raw, "catalog.slots.art", errors) for raw in slots if isinstance(raw, dict) and raw.get("slot_id") == "slot:art"), {})
    skill_chain = mapping(art.get("default_skill_chain"), "slot:art.default_skill_chain", errors)
    if skill_chain.get("owner_slot") != "slot:art":
        errors.append("slot:art.default_skill_chain 必须由 slot:art 管理")
    invocation_order = sequence(skill_chain.get("invocation_order"), "slot:art.default_skill_chain.invocation_order", errors)
    expected_art_skills = ["palette-knife-impasto", "palette-knife-impasto-ui", "impasto-tween-animation"]
    actual_art_skills = [mapping(item, "slot:art.default_skill_chain.invocation_order", errors).get("skill_id") for item in invocation_order]
    if actual_art_skills != expected_art_skills:
        errors.append("slot:art.default_skill_chain 必须按 palette-knife-impasto -> palette-knife-impasto-ui -> impasto-tween-animation 调用")
    actual_art_orders = [mapping(item, "slot:art.default_skill_chain.invocation_order", errors).get("order") for item in invocation_order]
    if actual_art_orders != [1, 2, 3]:
        errors.append("slot:art.default_skill_chain.order 必须严格为 1, 2, 3")
    if not isinstance(skill_chain.get("sequencing_rule"), str) or "不得跳步" not in skill_chain["sequencing_rule"]:
        errors.append("slot:art.default_skill_chain 必须声明不得跳步的 sequencing_rule")
    boundary = mapping(skill_chain.get("programming_consumption_boundary"), "slot:art.default_skill_chain.programming_consumption_boundary", errors)
    if boundary.get("program_slot") != "slot:programming":
        errors.append("slot:art 必须声明 slot:programming 消费边界")
    if not boundary.get("cannot"):
        errors.append("slot:art.programming_consumption_boundary.cannot 不能为空")

    qa = next((mapping(raw, "catalog.slots.qa", errors) for raw in slots if isinstance(raw, dict) and raw.get("slot_id") == "slot:qa"), {})
    if qa.get("can_merge_with") != []:
        errors.append("slot:qa.can_merge_with 必须为空，保持独立验收")
    qa_independent = set(qa.get("independent_from", []))
    if not SLOT_IDS - {"slot:qa"} <= qa_independent:
        errors.append("slot:qa 必须独立于其他生产槽位")

    manager_contract = mapping(catalog.get("manager_contract"), "catalog.manager_contract", errors)
    p2p = mapping(manager_contract.get("p2p_rules"), "catalog.manager_contract.p2p_rules", errors)
    if p2p.get("topology") != "peer_to_peer_with_coordinator" or p2p.get("coordinator") != "AGT-DIR":
        errors.append("部门经理 P2P 必须由 AGT-DIR 协调")
    if p2p.get("direct_peer_contact_allowed") is not True:
        errors.append("部门经理必须允许有记录的直接 P2P 联系")
    boundary = mapping(catalog.get("registry_boundary"), "catalog.registry_boundary", errors)
    if "项目 Department、Position、Instance" not in "、".join(map(str, boundary.get("catalog_is_not_authoritative_for", []))):
        errors.append("目录必须声明不拥有项目 Department、Position、Instance")
    return errors


def validate_consultation(document: Any) -> list[str]:
    errors: list[str] = []
    root = mapping(document, "document", errors)
    contract = mapping(root.get("consultation_event"), "consultation_event", errors)
    require_keys(contract, {"schema_version", "identity", "causality", "concurrency", "topology", "governance_binding", "actor", "payload", "authority_effect", "integrity"}, "consultation_event", errors)
    if contract.get("schema_version") != "0.1-alpha":
        errors.append("consultation_event.schema_version 必须为 0.1-alpha")
    identity = mapping(contract.get("identity"), "consultation_event.identity", errors)
    event_type = identity.get("event_type")
    event_types = set(event_type.split(" | ")) if isinstance(event_type, str) and " | " in event_type else {event_type}
    if event_types != EVENT_TYPES:
        errors.append("consultation_event.identity.event_type 不在允许集合")
    concurrency = mapping(contract.get("concurrency"), "consultation_event.concurrency", errors)
    if concurrency.get("resulting_consultation_sequence") != concurrency.get("expected_consultation_sequence", -1) + 1:
        errors.append("consultation_event sequence 必须严格递增 1")
    topology = mapping(contract.get("topology"), "consultation_event.topology", errors)
    if topology.get("mode") != "peer_to_peer_with_coordinator":
        errors.append("consultation_event 必须使用 peer_to_peer_with_coordinator")
    coordinator = mapping(topology.get("coordinator"), "consultation_event.topology.coordinator", errors)
    if coordinator.get("role") != "project_manager":
        errors.append("consultation coordinator 必须是 project_manager")
    participants = sequence(topology.get("participants"), "consultation_event.topology.participants", errors)
    if not participants:
        errors.append("consultation_event 必须有参与者")
    actor = mapping(contract.get("actor"), "consultation_event.actor", errors)
    actor_roles = {"project_manager", "product_manager", "department_manager", "reviewer", "human_owner"}
    actor_role = actor.get("role")
    declared_roles = set(actor_role.split(" | ")) if isinstance(actor_role, str) and " | " in actor_role else {actor_role}
    if not declared_roles <= actor_roles:
        errors.append("consultation_event.actor.role 不在允许集合")
    authority = mapping(contract.get("authority_effect"), "consultation_event.authority_effect", errors)
    if authority.get("changes_project_fact") is not False or authority.get("writes_to_source_of_truth") != []:
        errors.append("P2P 事件默认不得写入事实源")
    application = mapping(root.get("application_contract"), "application_contract", errors)
    payload_contracts = mapping(application.get("payload_contracts"), "application_contract.payload_contracts", errors)
    if set(payload_contracts) != EVENT_TYPES:
        errors.append("P2P 事件必须为七类事件定义 Payload Contract")
    stream = sequence(application.get("event_stream"), "application_contract.event_stream", errors)
    stream_text = "\n".join(map(str, stream))
    for phrase in ("sequence", "幂等", "追加不可覆盖或删除"):
        if phrase not in stream_text:
            errors.append(f"event_stream 缺少规则: {phrase}")
    boundary = sequence(application.get("p2p_boundary"), "application_contract.p2p_boundary", errors)
    boundary_text = "\n".join(map(str, boundary))
    for phrase in ("不得直接修改其他部门事实源", "改变优先级", "人类"):
        if phrase not in boundary_text:
            errors.append(f"p2p_boundary 缺少规则: {phrase}")
    examples = mapping(root.get("field_examples"), "field_examples", errors)
    for name, example in examples.items():
        event = mapping(example, f"field_examples.{name}", errors)
        if event.get("event_type") not in EVENT_TYPES:
            errors.append(f"field_examples.{name}.event_type 无效")
    return errors


def validate_handoff(document: Any) -> list[str]:
    errors: list[str] = []
    root = mapping(document, "document", errors)
    handoff = mapping(root.get("product_prototype_handoff"), "product_prototype_handoff", errors)
    require_keys(handoff, {"schema_version", "identity", "authority", "source_document_refs", "consultation", "product_identity", "product_packet", "prototype_intent", "penpot", "human_gate", "acceptance", "rework_routes", "integrity"}, "product_prototype_handoff", errors)
    if handoff.get("schema_version") != "game-production-product-prototype-handoff/v1":
        errors.append("product_prototype_handoff.schema_version 无效")
    identity = mapping(handoff.get("identity"), "handoff.identity", errors)
    if identity.get("lifecycle_state") not in HANDOFF_STATES:
        errors.append("handoff.identity.lifecycle_state 无效")
    authority = mapping(handoff.get("authority"), "handoff.authority", errors)
    if authority.get("final_decision_owner", "").startswith("human:") is not True:
        errors.append("产品交接最终决定权必须属于人类")
    consultation = mapping(handoff.get("consultation"), "handoff.consultation", errors)
    if consultation.get("topology") != "project-manager-led-p2p":
        errors.append("产品交接必须使用 project-manager-led-p2p")
    slots = sequence(consultation.get("fixed_department_slots"), "handoff.consultation.fixed_department_slots", errors)
    handoff_slot_ids = {mapping(slot, "handoff.slot", errors).get("slot_id") for slot in slots}
    normalized_handoff_slots = {value.removeprefix("slot:") for value in handoff_slot_ids if isinstance(value, str)}
    if normalized_handoff_slots != SLOT_SLUGS:
        errors.append("产品交接的固定部门槽位必须覆盖六类 slug")
    penpot = mapping(handoff.get("penpot"), "handoff.penpot", errors)
    if penpot.get("tool_id") != "tool:penpot-mcp":
        errors.append("Penpot 交接必须绑定 tool:penpot-mcp")
    if not {"read:penpot", "write:penpot", "capture:penpot"} <= set(penpot.get("approved_scope", [])):
        errors.append("Penpot 交接必须声明读、写和捕获权限范围")
    gate = mapping(handoff.get("human_gate"), "handoff.human_gate", errors)
    if gate.get("required") is not True:
        errors.append("产品原型交接必须要求人工 Gate")
    rules = mapping(root.get("handoff_rules"), "handoff_rules", errors)
    for key in ("fixed_slot_rule", "p2p_rule", "penpot_rule", "stale_rule", "rollback_rule"):
        if not isinstance(rules.get(key), str) or not rules[key].strip():
            errors.append(f"handoff_rules.{key} 缺失")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parents[1]
    parser.add_argument("--catalog", type=Path, default=base / "contracts" / "department-slot-catalog.template.yaml")
    parser.add_argument("--consultation", type=Path, default=base / "contracts" / "consultation-event.template.yaml")
    parser.add_argument("--handoff", type=Path, default=base / "contracts" / "product-prototype-handoff.template.yaml")
    args = parser.parse_args()
    errors: list[str] = []
    try:
        errors.extend(validate_catalog(load_yaml(args.catalog)))
        errors.extend(validate_consultation(load_yaml(args.consultation)))
        errors.extend(validate_handoff(load_yaml(args.handoff)))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"无法读取组织扩展契约: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: 六部门槽位、P2P 咨询和产品原型交接契约有效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
