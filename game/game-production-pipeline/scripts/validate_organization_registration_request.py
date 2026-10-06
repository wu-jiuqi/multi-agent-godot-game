#!/usr/bin/env python3
"""Validate the PM -> AGT-ORG organization registration request contract."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "game-production-organization-registration-request/v1"
PROJECT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUEST_RE = re.compile(r"^org-reg-request:([a-z0-9]+(?:-[a-z0-9]+)*):[0-9A-HJKMNP-TV-Z]{26}$")
CHANGE_SET_RE = re.compile(r"^chg:([a-z0-9]+(?:-[a-z0-9]+)*):[0-9A-HJKMNP-TV-Z]{26}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
STATUSES = {"submitted", "change_set_generated", "awaiting_human_approval", "approved_pending_apply", "applied", "rejected", "withdrawn", "stale"}
DECISIONS = {"pending", "approved", "rejected", "withdrawn", "stale"}


def mapping(value: Any, location: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{location} 必须是映射")
        return {}
    return value


def require(value: dict[str, Any], keys: set[str], location: str, errors: list[str]) -> None:
    for key in sorted(keys - value.keys()):
        errors.append(f"{location}.{key} 缺失")


def digest(value: Any, location: str, errors: list[str]) -> None:
    if value is not None and (not isinstance(value, str) or not DIGEST_RE.fullmatch(value)):
        errors.append(f"{location} 必须是 64 位小写 SHA-256 或 null")


def validate(document: Any) -> list[str]:
    errors: list[str] = []
    root = mapping(document, "document", errors)
    request = mapping(root.get("organization_registration_request"), "organization_registration_request", errors)
    require(request, {"schema_version", "identity", "requester", "target", "request", "evidence", "routing", "approval", "application", "integrity"}, "organization_registration_request", errors)
    if request.get("schema_version") != SCHEMA:
        errors.append(f"schema_version 必须为 {SCHEMA}")

    identity = mapping(request.get("identity"), "identity", errors)
    require(identity, {"request_id", "project_id", "status", "created_at", "updated_at"}, "identity", errors)
    project_id = identity.get("project_id")
    if not isinstance(project_id, str) or not PROJECT_RE.fullmatch(project_id):
        errors.append("identity.project_id 必须是小写连字符 ID")
    if not isinstance(identity.get("request_id"), str) or not REQUEST_RE.fullmatch(str(identity.get("request_id"))):
        errors.append("identity.request_id 格式无效")
    if identity.get("status") not in STATUSES:
        errors.append("identity.status 无效")

    requester = mapping(request.get("requester"), "requester", errors)
    require(requester, {"actor_kind", "actor_id", "position_id", "agent_id", "role"}, "requester", errors)
    if requester.get("agent_id") != "AGT-PM" or requester.get("role") != "product_manager":
        errors.append("请求必须由 AGT-PM 以 product_manager 身份发起")

    target = mapping(request.get("target"), "target", errors)
    require(target, {"registration_kind", "requested_slots", "requested_mapping_modes"}, "target", errors)
    if target.get("registration_kind") != "project_organization":
        errors.append("target.registration_kind 必须为 project_organization")
    slots = target.get("requested_slots")
    modes = target.get("requested_mapping_modes")
    if not isinstance(slots, list) or not slots:
        errors.append("target.requested_slots 必须为非空数组")
    if not isinstance(modes, list) or len(modes or []) != len(slots or []):
        errors.append("requested_mapping_modes 必须与 requested_slots 等长")

    evidence = mapping(request.get("evidence"), "evidence", errors)
    require(evidence, {"project_brief_ref", "organization_snapshot_ref", "fact_refs"}, "evidence", errors)
    snapshot_ref = mapping(evidence.get("organization_snapshot_ref"), "evidence.organization_snapshot_ref", errors)
    require(snapshot_ref, {"uri", "organization_revision", "digest"}, "evidence.organization_snapshot_ref", errors)
    digest(snapshot_ref.get("digest"), "evidence.organization_snapshot_ref.digest", errors)

    routing = mapping(request.get("routing"), "routing", errors)
    require(routing, {"coordinator_agent_id", "handoff"}, "routing", errors)
    if routing.get("coordinator_agent_id") != "AGT-ORG":
        errors.append("routing.coordinator_agent_id 必须为 AGT-ORG")
    handoff = mapping(routing.get("handoff"), "routing.handoff", errors)
    require(handoff, {"submitted_at", "change_set_ref", "change_set_digest", "response_due_at"}, "routing.handoff", errors)
    change_set_ref = handoff.get("change_set_ref")
    if change_set_ref is not None and (not isinstance(change_set_ref, str) or not CHANGE_SET_RE.fullmatch(change_set_ref)):
        errors.append("routing.handoff.change_set_ref 格式无效")
    digest(handoff.get("change_set_digest"), "routing.handoff.change_set_digest", errors)

    approval = mapping(request.get("approval"), "approval", errors)
    require(approval, {"human_approval_required", "approval_ref", "decision", "decision_basis"}, "approval", errors)
    if approval.get("human_approval_required") is not True:
        errors.append("organization registration request 必须要求人类审批")
    if approval.get("decision") not in DECISIONS:
        errors.append("approval.decision 无效")
    application = mapping(request.get("application"), "application", errors)
    require(application, {"apply_event_ref", "applied_at"}, "application", errors)
    integrity = mapping(request.get("integrity"), "integrity", errors)
    require(integrity, {"canonicalization", "digest_algorithm", "request_digest"}, "integrity", errors)
    if integrity.get("canonicalization") != "organization-registration-request-canonical-json-v1":
        errors.append("integrity.canonicalization 无效")
    digest(integrity.get("request_digest"), "integrity.request_digest", errors)

    if identity.get("status") == "applied" and not application.get("apply_event_ref"):
        errors.append("applied 请求必须引用 apply Event")
    if identity.get("status") in {"approved_pending_apply", "applied"} and approval.get("decision") != "approved":
        errors.append("进入 approved_pending_apply/applied 前必须存在 approved 人审决定")
    if identity.get("status") == "change_set_generated" and not change_set_ref:
        errors.append("change_set_generated 必须引用 AGT-ORG 生成的 Change Set")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        document = yaml.safe_load(args.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"无法读取注册请求: {exc}", file=sys.stderr)
        return 2
    errors = validate(document)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: PM -> AGT-ORG organization registration request valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
