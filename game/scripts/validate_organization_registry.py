#!/usr/bin/env python3
"""Validate Organization Registry snapshots, events and change sets."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment failure
    raise SystemExit("缺少 PyYAML；请先安装 game/scripts/requirements.txt") from exc


SCHEMA_VERSION = "0.2-alpha"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PROJECT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DEPARTMENT_RE = re.compile(r"^dept:([a-z0-9]+(?:-[a-z0-9]+)*):([a-z0-9]+(?:-[a-z0-9]+)*)$")
POSITION_RE = re.compile(r"^pos:([a-z0-9]+(?:-[a-z0-9]+)*):([a-z0-9]+(?:-[a-z0-9]+)*|root):([a-z0-9]+(?:-[a-z0-9]+)*)$")
PRESET_RE = re.compile(r"^preset:[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$")
INSTANCE_RE = re.compile(r"^inst:[0-9A-HJKMNP-TV-Z]{26}$")
GRANT_RE = re.compile(r"^grant:([a-z0-9]+(?:-[a-z0-9]+)*):[0-9A-HJKMNP-TV-Z]{26}$")
CHANGE_SET_RE = re.compile(r"^chg:([a-z0-9]+(?:-[a-z0-9]+)*):[0-9A-HJKMNP-TV-Z]{26}$")

LONG_LIVED_STATES = {"active", "suspended", "retiring"}
INSTANCE_STATES = {"starting", "active", "draining"}
PENDING_STATUSES = {"pending_review", "approved_pending_apply", "stale"}
OPERATION_TYPES = {
    "create_department",
    "update_department",
    "create_position",
    "update_position",
    "issue_temporary_grant",
    "revoke_temporary_grant",
    "transition_department",
    "transition_position",
    "migrate_governance_binding",
}
MATERIALIZATION_TOKENS = {
    "$apply.event_id",
    "$apply.recorded_at",
    "$approval.decision_ref",
    "$change_set.digest",
}
CORE_EVENTS = {
    "core.organization_initialized",
    "core.change_set_submitted",
    "core.change_set_decided",
    "core.change_set_applied",
    "core.department_lifecycle_transitioned",
    "core.position_lifecycle_transitioned",
    "core.instance_registered",
    "core.instance_lifecycle_transitioned",
    "core.temporary_grant_usage_changed",
    "core.governance_binding_migrated",
}
EVENT_REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "mutation_id",
    "project_id",
    "sequence",
    "event_type",
    "occurred_at",
    "recorded_at",
    "actor",
    "authorization",
    "causality",
    "concurrency",
    "binding_snapshot",
    "payload",
    "evidence_refs",
    "integrity",
}
EVENT_PAYLOAD_FIELDS = {
    "core.organization_initialized": {"initial_organization"},
    "core.change_set_submitted": {"change_set_ref"},
    "core.change_set_decided": {"change_set_id", "change_set_digest", "decision", "decision_ref"},
    "core.change_set_applied": {"change_set_ref", "approval_ref", "operations"},
    "core.department_lifecycle_transitioned": {"department_id", "from_state", "to_state", "reason", "approval_ref"},
    "core.position_lifecycle_transitioned": {"position_id", "from_state", "to_state", "reason", "approval_ref"},
    "core.instance_registered": {"instance", "reservation"},
    "core.instance_lifecycle_transitioned": {"instance_id", "from_state", "to_state", "reason", "release_reservation"},
    "core.temporary_grant_usage_changed": {"grant_id", "usage_before", "usage_after", "reason"},
    "core.governance_binding_migrated": {"binding_kind", "before", "after", "migration_check_ref", "approval_ref"},
}


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> bytes:
    def reject_constants(constant: str) -> None:
        raise ValueError(f"不允许非有限数字: {constant}")

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
        default=reject_constants,
    )
    return encoded.encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def canonical_event_digest(event: dict[str, Any]) -> str:
    normalized = copy.deepcopy(event)
    normalized.setdefault("integrity", {})["event_digest"] = None
    return canonical_digest(normalized)


def canonical_snapshot_digest(snapshot_doc: dict[str, Any]) -> str:
    normalized = copy.deepcopy(snapshot_doc["organization_snapshot"])
    normalized.setdefault("snapshot_integrity", {})["snapshot_digest"] = None
    return canonical_digest(normalized)


def canonical_change_set_digest(change_set_doc: dict[str, Any]) -> str:
    normalized = copy.deepcopy(change_set_doc["organization_change_set"])
    normalized.setdefault("integrity", {})["change_set_digest"] = None
    return canonical_digest(normalized)


def canonical_decision_basis_digest(snapshot_doc: dict[str, Any]) -> str:
    snapshot = snapshot_doc["organization_snapshot"]
    basis = {
        "project_id": snapshot["identity"]["project_id"],
        "governance_bindings": snapshot["governance_bindings"],
        "formal_structure": snapshot["formal_structure"],
        "temporary_grants": snapshot["runtime"]["temporary_grants"],
        "used_identity_index": snapshot["governance"]["used_identity_index"],
        "tombstones": snapshot["governance"]["tombstones"],
    }
    return canonical_digest(basis)


def require_mapping(value: Any, location: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{location} 必须是映射")
        return {}
    return value


def require_list(value: Any, location: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{location} 必须是数组")
        return []
    return value


def require_keys(mapping: dict[str, Any], keys: Iterable[str], location: str, errors: list[str]) -> None:
    for key in sorted(set(keys) - mapping.keys()):
        errors.append(f"{location}.{key} 缺失")


def check_digest(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
        errors.append(f"{location} 必须是 64 位小写 SHA-256")


def check_binding(value: Any, location: str, errors: list[str], *, preset: bool = False) -> None:
    binding = require_mapping(value, location, errors)
    required = {"preset_id", "version", "digest"} if preset else {"id", "version", "digest"}
    require_keys(binding, required, location, errors)
    if preset and not PRESET_RE.fullmatch(str(binding.get("preset_id", ""))):
        errors.append(f"{location}.preset_id 格式无效")
    check_digest(binding.get("digest"), f"{location}.digest", errors)


def check_materialization_tokens(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            check_materialization_tokens(child, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_materialization_tokens(child, f"{location}[{index}]", errors)
    elif isinstance(value, str):
        if value.startswith("$") and value not in MATERIALIZATION_TOKENS:
            errors.append(f"{location} 使用未知物化令牌: {value}")
        if "<" in value or ">" in value:
            errors.append(f"{location} 禁止自然语言占位符")


def sorted_unique(items: list[Any], key: str, location: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    seen_order: list[str] = []
    for index, raw in enumerate(items):
        item = require_mapping(raw, f"{location}[{index}]", errors)
        stable_id = item.get(key)
        if not isinstance(stable_id, str) or not stable_id:
            errors.append(f"{location}[{index}].{key} 缺失")
            continue
        if stable_id in result:
            errors.append(f"{location}.{key} 重复: {stable_id}")
        result[stable_id] = item
        seen_order.append(stable_id)
    if seen_order != sorted(seen_order):
        errors.append(f"{location} 必须按 {key} 升序排列")
    return result


def find_cycle(nodes: Iterable[str], parent_of: dict[str, str | None]) -> list[str] | None:
    visited: set[str] = set()
    for start in nodes:
        if start in visited:
            continue
        path: list[str] = []
        at: str | None = start
        while at is not None and at not in visited:
            if at in path:
                return path[path.index(at):] + [at]
            path.append(at)
            at = parent_of.get(at)
        visited.update(path)
    return None


def validate_snapshot(snapshot_doc: Any, *, verify_digest: bool = True) -> list[str]:
    errors: list[str] = []
    root = require_mapping(snapshot_doc, "document", errors)
    snapshot = require_mapping(root.get("organization_snapshot"), "organization_snapshot", errors)
    require_keys(snapshot, {"schema_version", "identity", "governance_bindings", "event_watermark", "formal_structure", "runtime", "governance", "snapshot_integrity"}, "organization_snapshot", errors)
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"organization_snapshot.schema_version 必须为 {SCHEMA_VERSION}")

    identity = require_mapping(snapshot.get("identity"), "identity", errors)
    require_keys(identity, {"project_id", "organization_revision", "created_at", "updated_at"}, "identity", errors)
    project_id = identity.get("project_id")
    if not isinstance(project_id, str) or not PROJECT_RE.fullmatch(project_id):
        errors.append("identity.project_id 必须是小写连字符 ID")
    revision = identity.get("organization_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("identity.organization_revision 必须是正整数")

    bindings = require_mapping(snapshot.get("governance_bindings"), "governance_bindings", errors)
    for binding_name in ("organization_contract", "lifecycle_contract", "authority_policy"):
        check_binding(bindings.get(binding_name), f"governance_bindings.{binding_name}", errors)

    watermark = require_mapping(snapshot.get("event_watermark"), "event_watermark", errors)
    require_keys(watermark, {"last_event_id", "last_event_sequence", "last_event_digest"}, "event_watermark", errors)
    if watermark.get("last_event_sequence") != revision:
        errors.append("last_event_sequence 必须等于 organization_revision")
    check_digest(watermark.get("last_event_digest"), "event_watermark.last_event_digest", errors)

    formal = require_mapping(snapshot.get("formal_structure"), "formal_structure", errors)
    departments = sorted_unique(require_list(formal.get("departments"), "formal_structure.departments", errors), "department_id", "formal_structure.departments", errors)
    positions = sorted_unique(require_list(formal.get("positions"), "formal_structure.positions", errors), "position_id", "formal_structure.positions", errors)

    for dept_id, department in departments.items():
        match = DEPARTMENT_RE.fullmatch(dept_id)
        if not match or match.group(1) != project_id:
            errors.append(f"Department ID 与 project_id 不匹配: {dept_id}")
        require_keys(department, {"display_name", "purpose", "parent_department_id", "manager_position_id", "responsibilities", "ownership_refs", "authority_binding", "temporary_workforce_policy", "lifecycle", "approval_binding", "audit"}, dept_id, errors)
        parent_id = department.get("parent_department_id")
        if parent_id is not None and parent_id not in departments:
            errors.append(f"{dept_id}.parent_department_id 未引用当前 Department")
        lifecycle = require_mapping(department.get("lifecycle"), f"{dept_id}.lifecycle", errors)
        if lifecycle.get("state") not in LONG_LIVED_STATES:
            errors.append(f"{dept_id}.lifecycle.state 非法")
        approval = require_mapping(department.get("approval_binding"), f"{dept_id}.approval_binding", errors)
        check_digest(approval.get("subject_digest"), f"{dept_id}.approval_binding.subject_digest", errors)
        check_binding(department.get("authority_binding"), f"{dept_id}.authority_binding", errors)

    cycle = find_cycle(departments, {key: value.get("parent_department_id") for key, value in departments.items()})
    if cycle:
        errors.append("Department 层级存在环: " + " -> ".join(cycle))

    for position_id, position in positions.items():
        match = POSITION_RE.fullmatch(position_id)
        if not match or match.group(1) != project_id:
            errors.append(f"Position ID 与 project_id 不匹配: {position_id}")
        require_keys(position, {"display_name", "organization_scope", "department_id", "reports_to_position_id", "preset_binding", "responsibilities", "ownership_refs", "authority_binding", "concurrency_policy", "handoff_policy", "independence_policy", "lifecycle", "approval_binding", "audit"}, position_id, errors)
        scope = position.get("organization_scope")
        department_id = position.get("department_id")
        if scope == "root" and department_id is not None:
            errors.append(f"{position_id} 是 root 岗位，department_id 必须为 null")
        elif scope == "department" and department_id not in departments:
            errors.append(f"{position_id}.department_id 未引用当前 Department")
        elif scope not in {"root", "department"}:
            errors.append(f"{position_id}.organization_scope 非法")
        reports_to = position.get("reports_to_position_id")
        if reports_to is not None and reports_to not in positions:
            errors.append(f"{position_id}.reports_to_position_id 未引用当前 Position")
        check_binding(position.get("preset_binding"), f"{position_id}.preset_binding", errors, preset=True)
        check_binding(position.get("authority_binding"), f"{position_id}.authority_binding", errors)
        lifecycle = require_mapping(position.get("lifecycle"), f"{position_id}.lifecycle", errors)
        if lifecycle.get("state") not in LONG_LIVED_STATES:
            errors.append(f"{position_id}.lifecycle.state 非法")
        approval = require_mapping(position.get("approval_binding"), f"{position_id}.approval_binding", errors)
        check_digest(approval.get("subject_digest"), f"{position_id}.approval_binding.subject_digest", errors)

    cycle = find_cycle(positions, {key: value.get("reports_to_position_id") for key, value in positions.items()})
    if cycle:
        errors.append("Position 汇报关系存在环: " + " -> ".join(cycle))
    for dept_id, department in departments.items():
        manager_id = department.get("manager_position_id")
        manager = positions.get(manager_id)
        if manager is None:
            errors.append(f"{dept_id}.manager_position_id 未引用当前 Position")
        elif manager.get("department_id") != dept_id or manager.get("lifecycle", {}).get("state") == "retiring":
            errors.append(f"{dept_id}.manager_position_id 必须引用本部门非 retiring 岗位")

    runtime = require_mapping(snapshot.get("runtime"), "runtime", errors)
    instances = sorted_unique(require_list(runtime.get("instances"), "runtime.instances", errors), "instance_id", "runtime.instances", errors)
    grants = sorted_unique(require_list(runtime.get("temporary_grants"), "runtime.temporary_grants", errors), "grant_id", "runtime.temporary_grants", errors)

    for grant_id, grant in grants.items():
        match = GRANT_RE.fullmatch(grant_id)
        if not match or match.group(1) != project_id:
            errors.append(f"Temporary Grant ID 与 project_id 不匹配: {grant_id}")
        require_keys(grant, {"grantee", "issuer", "parent_grant_id", "allowed_presets", "scope", "limits", "permission_policy", "obligations", "valid_from", "expires_at", "revoked_at", "usage", "approval_binding", "audit"}, grant_id, errors)
        parent_id = grant.get("parent_grant_id")
        if parent_id is not None and parent_id not in grants:
            errors.append(f"{grant_id}.parent_grant_id 未引用当前 Grant")
        grantee = require_mapping(grant.get("grantee"), f"{grant_id}.grantee", errors)
        if grantee.get("kind") == "position" and grantee.get("id") not in positions:
            errors.append(f"{grant_id}.grantee 未引用当前 Position")
        if grantee.get("kind") == "instance" and grantee.get("id") not in instances:
            errors.append(f"{grant_id}.grantee 未引用当前 Instance")
        if grantee.get("kind") not in {"position", "instance"}:
            errors.append(f"{grant_id}.grantee.kind 非法")
        limits = require_mapping(grant.get("limits"), f"{grant_id}.limits", errors)
        required_limits = {"maximum_active_instances", "maximum_total_instances", "maximum_cost", "maximum_duration_seconds", "maximum_creation_depth"}
        require_keys(limits, required_limits, f"{grant_id}.limits", errors)
        if parent_id is None:
            for name in required_limits:
                value = limits.get(name)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                    errors.append(f"{grant_id}.limits.{name} 根授权必须是显式有限非负数")
        usage = require_mapping(grant.get("usage"), f"{grant_id}.usage", errors)
        for used, limit in (("reserved_active_instances", "maximum_active_instances"), ("created_instances", "maximum_total_instances"), ("reserved_cost", "maximum_cost"), ("reserved_duration_seconds", "maximum_duration_seconds")):
            value = usage.get(used)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                errors.append(f"{grant_id}.usage.{used} 必须是非负数")
            elif isinstance(limits.get(limit), (int, float)) and value > limits[limit]:
                errors.append(f"{grant_id}.usage.{used} 超过 {limit}")
        for index, preset_binding in enumerate(require_list(grant.get("allowed_presets"), f"{grant_id}.allowed_presets", errors)):
            check_binding(preset_binding, f"{grant_id}.allowed_presets[{index}]", errors, preset=True)
        check_binding(grant.get("permission_policy"), f"{grant_id}.permission_policy", errors)
        approval = require_mapping(grant.get("approval_binding"), f"{grant_id}.approval_binding", errors)
        check_digest(approval.get("subject_digest"), f"{grant_id}.approval_binding.subject_digest", errors)

    cycle = find_cycle(grants, {key: value.get("parent_grant_id") for key, value in grants.items()})
    if cycle:
        errors.append("Temporary Grant 委托链存在环: " + " -> ".join(cycle))

    grant_reservations: dict[str, dict[str, float]] = {
        grant_id: {"active": 0, "cost": 0, "duration": 0} for grant_id in grants
    }
    for instance_id, instance in instances.items():
        if not INSTANCE_RE.fullmatch(instance_id):
            errors.append(f"Instance ID 格式无效: {instance_id}")
        require_keys(instance, {"instance_kind", "preset_binding", "position_binding", "temporary_binding", "lifecycle", "started_at", "expires_at", "audit"}, instance_id, errors)
        check_binding(instance.get("preset_binding"), f"{instance_id}.preset_binding", errors, preset=True)
        kind = instance.get("instance_kind")
        position_binding = instance.get("position_binding")
        temporary_binding = instance.get("temporary_binding")
        if kind == "position":
            binding = require_mapping(position_binding, f"{instance_id}.position_binding", errors)
            if binding.get("position_id") not in positions or temporary_binding is not None:
                errors.append(f"{instance_id} 的 position/temporary discriminated union 无效")
            elif instance.get("preset_binding") != positions[binding["position_id"]].get("preset_binding"):
                errors.append(f"{instance_id}.preset_binding 与 Position 当前绑定不一致")
        elif kind == "temporary":
            binding = require_mapping(temporary_binding, f"{instance_id}.temporary_binding", errors)
            if binding.get("grant_id") not in grants or position_binding is not None:
                errors.append(f"{instance_id} 的 temporary/position discriminated union 无效")
            else:
                grant = grants[binding["grant_id"]]
                if instance.get("preset_binding") not in grant.get("allowed_presets", []):
                    errors.append(f"{instance_id}.preset_binding 不在 Temporary Grant 允许集合中")
                if binding.get("created_by_instance_id") not in instances:
                    errors.append(f"{instance_id}.created_by_instance_id 未引用当前 Instance")
                depth = binding.get("creation_depth")
                if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1 or depth > grant["limits"]["maximum_creation_depth"]:
                    errors.append(f"{instance_id}.creation_depth 超过授权上限")
                reservation = require_mapping(binding.get("reservation"), f"{instance_id}.temporary_binding.reservation", errors)
                cost = reservation.get("cost")
                duration = reservation.get("duration_seconds")
                if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
                    errors.append(f"{instance_id}.reservation.cost 必须是非负数")
                    cost = 0
                if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
                    errors.append(f"{instance_id}.reservation.duration_seconds 必须是非负数")
                    duration = 0
                grant_reservations[binding["grant_id"]]["active"] += 1
                grant_reservations[binding["grant_id"]]["cost"] += cost
                grant_reservations[binding["grant_id"]]["duration"] += duration
        else:
            errors.append(f"{instance_id}.instance_kind 非法")
        lifecycle = require_mapping(instance.get("lifecycle"), f"{instance_id}.lifecycle", errors)
        if lifecycle.get("state") not in INSTANCE_STATES:
            errors.append(f"{instance_id}.lifecycle.state 非法")

    for grant_id, totals in grant_reservations.items():
        usage = grants[grant_id]["usage"]
        expected = {
            "reserved_active_instances": totals["active"],
            "reserved_cost": totals["cost"],
            "reserved_duration_seconds": totals["duration"],
        }
        for field, value in expected.items():
            if usage.get(field) != value:
                errors.append(f"{grant_id}.usage.{field} 与当前 Temporary Instance 预留不一致")

    governance = require_mapping(snapshot.get("governance"), "governance", errors)
    index = require_mapping(governance.get("used_identity_index"), "governance.used_identity_index", errors)
    current_ids = {
        "department_ids": set(departments),
        "position_ids": set(positions),
        "instance_ids": set(instances),
        "temporary_grant_ids": set(grants),
    }
    for index_name, ids in current_ids.items():
        values = require_list(index.get(index_name), f"used_identity_index.{index_name}", errors)
        if values != sorted(set(values)):
            errors.append(f"used_identity_index.{index_name} 必须升序且唯一")
        missing = ids - set(values)
        if missing:
            errors.append(f"used_identity_index.{index_name} 缺少当前 ID: {sorted(missing)}")
    pending_refs = sorted_unique(require_list(governance.get("pending_change_set_refs"), "governance.pending_change_set_refs", errors), "change_set_id", "governance.pending_change_set_refs", errors)
    for change_set_id, ref in pending_refs.items():
        match = CHANGE_SET_RE.fullmatch(change_set_id)
        if not match or match.group(1) != project_id:
            errors.append(f"Change Set ID 与 project_id 不匹配: {change_set_id}")
        if ref.get("status") not in PENDING_STATUSES:
            errors.append(f"{change_set_id}.status 非法")
        check_digest(ref.get("change_set_digest"), f"{change_set_id}.change_set_digest", errors)
        check_digest(ref.get("base_snapshot_digest"), f"{change_set_id}.base_snapshot_digest", errors)
        if ref.get("status") == "approved_pending_apply" and not ref.get("approval_ref"):
            errors.append(f"{change_set_id} 已批准但缺少 approval_ref")

    integrity = require_mapping(snapshot.get("snapshot_integrity"), "snapshot_integrity", errors)
    if integrity.get("canonicalization") != "organization-snapshot-canonical-json-v1":
        errors.append("Snapshot canonicalization 无效")
    if integrity.get("digest_algorithm") != "sha256":
        errors.append("Snapshot digest_algorithm 必须为 sha256")
    if verify_digest:
        check_digest(integrity.get("snapshot_digest"), "snapshot_integrity.snapshot_digest", errors)
        if isinstance(root.get("organization_snapshot"), dict) and integrity.get("snapshot_digest") != canonical_snapshot_digest(root):
            errors.append("snapshot_digest 不匹配")
    return errors


def validate_change_set(change_set_doc: Any, snapshot_doc: Any | None = None, *, verify_digest: bool = True) -> list[str]:
    errors: list[str] = []
    root = require_mapping(change_set_doc, "document", errors)
    change_set = require_mapping(root.get("organization_change_set"), "organization_change_set", errors)
    require_keys(change_set, {"schema_version", "identity", "base", "proposal", "impact", "verification", "approval_requirement", "integrity"}, "organization_change_set", errors)
    if change_set.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"organization_change_set.schema_version 必须为 {SCHEMA_VERSION}")
    identity = require_mapping(change_set.get("identity"), "change_set.identity", errors)
    project_id = identity.get("project_id")
    match = CHANGE_SET_RE.fullmatch(str(identity.get("change_set_id", "")))
    if not match or match.group(1) != project_id:
        errors.append("change_set_id 与 project_id 不匹配")
    base = require_mapping(change_set.get("base"), "change_set.base", errors)
    check_digest(base.get("snapshot_digest"), "change_set.base.snapshot_digest", errors)
    check_digest(base.get("decision_basis_digest"), "change_set.base.decision_basis_digest", errors)
    proposal = require_mapping(change_set.get("proposal"), "change_set.proposal", errors)
    operations = require_list(proposal.get("operations"), "change_set.proposal.operations", errors)
    operation_ids: set[str] = set()
    for index, raw in enumerate(operations):
        operation = require_mapping(raw, f"operations[{index}]", errors)
        require_keys(operation, {"operation_id", "operation_type", "target_id", "before", "after", "reason"}, f"operations[{index}]", errors)
        operation_id = operation.get("operation_id")
        if operation_id in operation_ids:
            errors.append(f"operation_id 重复: {operation_id}")
        operation_ids.add(operation_id)
        op_type = operation.get("operation_type")
        if op_type not in OPERATION_TYPES:
            errors.append(f"operations[{index}].operation_type 非法")
        target_id = operation.get("target_id")
        before, after = operation.get("before"), operation.get("after")
        check_materialization_tokens(after, f"operations[{index}].after", errors)
        if op_type and op_type.startswith("create_") or op_type == "issue_temporary_grant":
            if before is not None:
                errors.append(f"{operation_id}.before 创建操作必须为 null")
        if op_type in {"update_department", "update_position"} and isinstance(before, dict) and isinstance(after, dict):
            id_key = "department_id" if op_type == "update_department" else "position_id"
            if before.get(id_key) != target_id or after.get(id_key) != target_id:
                errors.append(f"{operation_id} 不得改变稳定 ID")
        if isinstance(after, dict):
            id_key = "department_id" if "department" in str(op_type) else "position_id" if "position" in str(op_type) else "grant_id" if "grant" in str(op_type) else None
            if id_key and after.get(id_key) != target_id:
                errors.append(f"{operation_id}.after.{id_key} 必须等于 target_id")
    approval = require_mapping(change_set.get("approval_requirement"), "approval_requirement", errors)
    if approval.get("human_approval_required") is not True:
        errors.append("Organization Change Set 必须要求人工审批")
    integrity = require_mapping(change_set.get("integrity"), "change_set.integrity", errors)
    if integrity.get("canonicalization") != "organization-change-set-canonical-json-v1":
        errors.append("Change Set canonicalization 无效")
    if verify_digest:
        check_digest(integrity.get("change_set_digest"), "change_set.integrity.change_set_digest", errors)
        if isinstance(root.get("organization_change_set"), dict) and integrity.get("change_set_digest") != canonical_change_set_digest(root):
            errors.append("change_set_digest 不匹配")
    if snapshot_doc is not None:
        snapshot = snapshot_doc.get("organization_snapshot", {})
        if project_id != snapshot.get("identity", {}).get("project_id"):
            errors.append("Change Set 与 Snapshot project_id 不一致")
        if base.get("decision_basis_digest") != canonical_decision_basis_digest(snapshot_doc):
            errors.append("Change Set 决策基线已 stale")
    return errors


def validate_event(event: Any) -> list[str]:
    errors: list[str] = []
    event = require_mapping(event, "event", errors)
    require_keys(event, EVENT_REQUIRED_FIELDS, "event", errors)
    if event.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"event.schema_version 必须为 {SCHEMA_VERSION}")
    event_type = event.get("event_type")
    if event_type not in CORE_EVENTS and not str(event_type).startswith("project."):
        errors.append(f"未知 event_type: {event_type}")
    payload = require_mapping(event.get("payload"), "event.payload", errors)
    if event_type in EVENT_PAYLOAD_FIELDS:
        require_keys(payload, EVENT_PAYLOAD_FIELDS[event_type], "event.payload", errors)
    actor = require_mapping(event.get("actor"), "event.actor", errors)
    if actor.get("actor_kind") not in {"human", "instance", "system"}:
        errors.append("event.actor.actor_kind 非法")
    concurrency = require_mapping(event.get("concurrency"), "event.concurrency", errors)
    expected = concurrency.get("expected_organization_revision")
    resulting = concurrency.get("resulting_organization_revision")
    if isinstance(expected, int) and resulting != expected + 1:
        errors.append("resulting_organization_revision 必须比 expected 增加 1")
    integrity = require_mapping(event.get("integrity"), "event.integrity", errors)
    if integrity.get("canonicalization") != "registry-event-canonical-json-v1":
        errors.append("Event canonicalization 无效")
    check_digest(integrity.get("event_digest"), "event.integrity.event_digest", errors)
    if isinstance(event, dict) and integrity.get("event_digest") != canonical_event_digest(event):
        errors.append("event_digest 不匹配")
    return errors


def _replace_by_id(items: list[dict[str, Any]], id_key: str, target_id: str, after: dict[str, Any] | None) -> None:
    items[:] = [item for item in items if item.get(id_key) != target_id]
    if after is not None:
        items.append(copy.deepcopy(after))
    items.sort(key=lambda item: item[id_key])


def _apply_operation(snapshot: dict[str, Any], operation: dict[str, Any]) -> None:
    op_type = operation["operation_type"]
    target_id = operation["target_id"]
    after = operation.get("after")
    formal = snapshot["formal_structure"]
    runtime = snapshot["runtime"]
    index = snapshot["governance"]["used_identity_index"]
    if op_type in {"create_department", "update_department", "transition_department"}:
        _replace_by_id(formal["departments"], "department_id", target_id, after)
        if op_type == "create_department" and target_id not in index["department_ids"]:
            index["department_ids"].append(target_id)
    elif op_type in {"create_position", "update_position", "transition_position"}:
        _replace_by_id(formal["positions"], "position_id", target_id, after)
        if op_type == "create_position" and target_id not in index["position_ids"]:
            index["position_ids"].append(target_id)
    elif op_type in {"issue_temporary_grant", "revoke_temporary_grant"}:
        _replace_by_id(runtime["temporary_grants"], "grant_id", target_id, after)
        if op_type == "issue_temporary_grant" and target_id not in index["temporary_grant_ids"]:
            index["temporary_grant_ids"].append(target_id)
    elif op_type == "migrate_governance_binding":
        snapshot["governance_bindings"][target_id] = copy.deepcopy(after)
    for values in index.values():
        values.sort()


def replay_history(history_doc: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    root = require_mapping(history_doc, "history", errors)
    events = require_list(root.get("organization_event_history"), "organization_event_history", errors)
    if not events:
        errors.append("organization_event_history 不能为空")
        return None, errors
    snapshot: dict[str, Any] | None = None
    previous_digest: str | None = None
    mutation_ids: set[str] = set()
    for index, event in enumerate(events, start=1):
        errors.extend(f"sequence {index}: {message}" for message in validate_event(event))
        if not isinstance(event, dict):
            continue
        if event.get("sequence") != index:
            errors.append(f"sequence 必须连续，期望 {index}")
        if event.get("mutation_id") in mutation_ids:
            errors.append(f"mutation_id 重复: {event.get('mutation_id')}")
        mutation_ids.add(event.get("mutation_id"))
        integrity = event.get("integrity", {})
        if integrity.get("previous_event_digest") != previous_digest:
            errors.append(f"sequence {index}: previous_event_digest 不匹配")
        concurrency = event.get("concurrency", {})
        if index == 1:
            if event.get("event_type") != "core.organization_initialized":
                errors.append("首个事件必须是 core.organization_initialized")
                continue
            if concurrency.get("expected_organization_revision") != 0 or concurrency.get("expected_snapshot_digest") is not None:
                errors.append("初始化事件必须从 revision=0、snapshot_digest=null 开始")
            initial = copy.deepcopy(event.get("payload", {}).get("initial_organization"))
            if not isinstance(initial, dict):
                errors.append("初始化事件 initial_organization 必须是映射")
                continue
            snapshot = initial
            snapshot["schema_version"] = SCHEMA_VERSION
        elif snapshot is not None:
            current_doc = {"organization_snapshot": snapshot}
            current_digest = canonical_snapshot_digest(current_doc)
            if concurrency.get("expected_organization_revision") != snapshot["identity"]["organization_revision"]:
                errors.append(f"sequence {index}: expected_organization_revision 不匹配")
            if concurrency.get("expected_snapshot_digest") != current_digest:
                errors.append(f"sequence {index}: expected_snapshot_digest 不匹配")
            event_type = event.get("event_type")
            payload = event.get("payload", {})
            if event_type == "core.change_set_submitted":
                ref = copy.deepcopy(payload["change_set_ref"])
                _replace_by_id(snapshot["governance"]["pending_change_set_refs"], "change_set_id", ref["change_set_id"], ref)
            elif event_type == "core.change_set_decided":
                refs = snapshot["governance"]["pending_change_set_refs"]
                ref = next((item for item in refs if item["change_set_id"] == payload["change_set_id"]), None)
                if ref is None:
                    errors.append(f"sequence {index}: 决定引用未知 Change Set")
                elif payload["decision"] == "approved":
                    ref["status"] = "approved_pending_apply"
                    ref["approval_ref"] = payload["decision_ref"]
                else:
                    refs.remove(ref)
            elif event_type == "core.change_set_applied":
                for operation in payload["operations"]:
                    _apply_operation(snapshot, operation)
                change_ref = payload["change_set_ref"]
                snapshot["governance"]["pending_change_set_refs"] = [item for item in snapshot["governance"]["pending_change_set_refs"] if item["change_set_id"] != change_ref["change_set_id"]]
                snapshot["governance"]["latest_applied_change_set"] = {**copy.deepcopy(change_ref), "approval_ref": payload["approval_ref"], "applied_by_event_id": event["event_id"]}
            elif event_type in {"core.department_lifecycle_transitioned", "core.position_lifecycle_transitioned"}:
                collection = "departments" if "department" in event_type else "positions"
                id_key = "department_id" if collection == "departments" else "position_id"
                target_id = payload[id_key]
                item = next((value for value in snapshot["formal_structure"][collection] if value[id_key] == target_id), None)
                if item is not None:
                    item["lifecycle"].update({"state": payload["to_state"], "state_entered_at": event["recorded_at"], "transition_ref": event["event_id"]})
            elif event_type == "core.instance_registered":
                instance = copy.deepcopy(payload["instance"])
                _replace_by_id(snapshot["runtime"]["instances"], "instance_id", instance["instance_id"], instance)
                snapshot["governance"]["used_identity_index"]["instance_ids"].append(instance["instance_id"])
                snapshot["governance"]["used_identity_index"]["instance_ids"].sort()
            elif event_type == "core.instance_lifecycle_transitioned":
                target_id = payload["instance_id"]
                item = next((value for value in snapshot["runtime"]["instances"] if value["instance_id"] == target_id), None)
                if item is not None and payload["to_state"] == "ended":
                    snapshot["runtime"]["instances"].remove(item)
                elif item is not None:
                    item["lifecycle"].update({"state": payload["to_state"], "state_entered_at": event["recorded_at"], "transition_ref": event["event_id"]})
            elif event_type == "core.temporary_grant_usage_changed":
                grant = next((value for value in snapshot["runtime"]["temporary_grants"] if value["grant_id"] == payload["grant_id"]), None)
                if grant is not None:
                    grant["usage"] = copy.deepcopy(payload["usage_after"])
            elif event_type == "core.governance_binding_migrated":
                snapshot["governance_bindings"][payload["binding_kind"]] = copy.deepcopy(payload["after"])
        if snapshot is not None:
            snapshot["identity"]["organization_revision"] = index
            snapshot["identity"]["updated_at"] = event["recorded_at"]
            snapshot["event_watermark"] = {"last_event_id": event["event_id"], "last_event_sequence": index, "last_event_digest": integrity.get("event_digest")}
            snapshot["snapshot_integrity"] = {"canonicalization": "organization-snapshot-canonical-json-v1", "digest_algorithm": "sha256", "snapshot_digest": None}
            snapshot["snapshot_integrity"]["snapshot_digest"] = canonical_snapshot_digest({"organization_snapshot": snapshot})
        previous_digest = integrity.get("event_digest")
    return ({"organization_snapshot": snapshot} if snapshot is not None else None), errors


def validate_history(history_doc: Any, snapshot_doc: Any) -> list[str]:
    replayed, errors = replay_history(history_doc)
    if replayed is None:
        return errors
    errors.extend(validate_snapshot(replayed))
    if replayed.get("organization_snapshot") != snapshot_doc.get("organization_snapshot"):
        errors.append("Snapshot 无法由 Organization Event History 完整重建")
    return errors


def validate_contract_templates(snapshot_template: Any, event_template: Any, change_set_template: Any, validation_template: Any) -> list[str]:
    errors: list[str] = []
    for name, document, root_key in (
        ("Snapshot", snapshot_template, "organization_snapshot"),
        ("Event", event_template, "event"),
        ("Change Set", change_set_template, "organization_change_set"),
        ("Validation", validation_template, "organization_validation"),
    ):
        root = require_mapping(document, name, errors)
        if root_key not in root:
            errors.append(f"{name} 模板缺少 {root_key}")
        elif root[root_key].get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{name} 模板 schema_version 不一致")
    core = set(event_template.get("event_namespace", {}).get("core", []))
    if core != CORE_EVENTS:
        errors.append("Event 模板 core 事件集合与校验器不一致")
    payload_contracts = set(event_template.get("payload_contracts", {}))
    if payload_contracts != CORE_EVENTS:
        errors.append("Event 模板必须为每个 core 事件定义 Payload Contract")
    operation_contracts = set(change_set_template.get("operation_contracts", {}))
    if operation_contracts != OPERATION_TYPES:
        errors.append("Change Set 模板 operation 集合与校验器不一致")
    rules = "\n".join(event_template.get("application_contract", []))
    for phrase in ("expected_snapshot_digest", "原子事务", "禁止通用 JSON Patch", "哈希环"):
        if phrase not in rules:
            errors.append(f"Event 应用契约缺少关键规则: {phrase}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--change-set", type=Path)
    parser.add_argument("--templates", action="store_true", help="校验仓库内四份 Organization 契约模板")
    args = parser.parse_args()
    if not any((args.snapshot, args.change_set, args.templates)):
        parser.error("至少提供 --snapshot、--change-set 或 --templates")
    try:
        snapshot_doc = read_yaml(args.snapshot) if args.snapshot else None
        history_doc = read_yaml(args.history) if args.history else None
        change_set_doc = read_yaml(args.change_set) if args.change_set else None
        if args.templates:
            base = Path(__file__).resolve().parents[1] / "contracts"
            templates = [read_yaml(base / name) for name in ("organization-snapshot.template.yaml", "organization-event.template.yaml", "organization-change-set.template.yaml", "organization-validation.template.yaml")]
        else:
            templates = []
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"无法读取 Organization 契约: {exc}", file=sys.stderr)
        return 2
    errors: list[str] = []
    if templates:
        errors.extend(validate_contract_templates(*templates))
    if snapshot_doc is not None:
        errors.extend(validate_snapshot(snapshot_doc))
    if change_set_doc is not None:
        errors.extend(validate_change_set(change_set_doc, snapshot_doc))
    if history_doc is not None:
        if snapshot_doc is None:
            errors.append("--history 必须同时提供 --snapshot")
        else:
            errors.extend(validate_history(history_doc, snapshot_doc))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: Organization Registry 契约、摘要、审批基线与事件历史一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
