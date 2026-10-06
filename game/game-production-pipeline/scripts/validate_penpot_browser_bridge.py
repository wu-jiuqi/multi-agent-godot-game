#!/usr/bin/env python3
"""Validate the local Penpot browser-task request/ack/result envelope.

This is a read-only structural and digest check.  It never opens a browser,
logs in, calls Penpot MCP, or claims that a remote operation really happened.
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

SCHEMA = "game-production-penpot-browser-task/v1"
CANONICALIZATION = "penpot-browser-task-canonical-json-v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ULID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
FAILURE_ROUTES = {"BRIDGE", "UI_VISUAL", "UI_STRUCTURE", "UI_TECH", "UI_READABILITY", "HUMAN_REVIEW"}


def _mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是映射")
        return {}
    return value


def _text(value: Any, label: str, errors: list[str], *, nullable: bool = False) -> bool:
    if nullable and value is None:
        return True
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} 必须是非空字符串")
        return False
    return True


def _enum(value: Any, allowed: set[str], label: str, errors: list[str], *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{label} 不在允许集合: {sorted(allowed)}")


def _digest(value: Any, label: str, errors: list[str], *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        errors.append(f"{label} 必须是 64 位小写 SHA-256")


def _timestamp(value: Any, label: str, errors: list[str], *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append(f"{label} 必须是带时区的 ISO 8601 时间")


def _ref(value: Any, label: str, errors: list[str], project_root: Path | None) -> None:
    ref = _mapping(value, label, errors)
    _text(ref.get("artifact_id"), f"{label}.artifact_id", errors)
    uri = ref.get("uri")
    if not isinstance(uri, str) or not uri.startswith("repo://") or uri.removeprefix("repo://").startswith(("/", "../")):
        errors.append(f"{label}.uri 必须是项目内 repo:// 路径")
    _digest(ref.get("sha256"), f"{label}.sha256", errors)
    if project_root is not None and isinstance(uri, str) and uri.startswith("repo://"):
        relative = uri.removeprefix("repo://")
        path = (project_root / relative).resolve()
        try:
            path.relative_to(project_root.resolve())
        except ValueError:
            errors.append(f"{label}.uri 越出项目根目录")
            return
        if not path.is_file():
            errors.append(f"{label}.uri 本地文件不存在: {relative}")


def _walk_json(value: Any, label: str, errors: list[str], active: set[int] | None = None) -> None:
    active = active or set()
    if isinstance(value, (dict, list)):
        if id(value) in active:
            errors.append(f"{label} 不允许循环引用")
            return
        active.add(id(value))
        entries = value.items() if isinstance(value, dict) else enumerate(value)
        for key, item in entries:
            if isinstance(value, dict) and not isinstance(key, str):
                errors.append(f"{label} 对象键必须是字符串")
            _walk_json(item, f"{label}.{key}", errors, active)
        active.remove(id(value))
    elif isinstance(value, str) and re.search(r"<[^<>]+>", value):
        errors.append(f"{label} 含未填写模板占位符")
    elif type(value) is float and not math.isfinite(value):
        errors.append(f"{label} 不允许非有限数字")
    elif value is not None and type(value) not in {str, int, bool}:
        errors.append(f"{label} 不是 JSON 值")


def _failure(value: Any, label: str, errors: list[str]) -> None:
    item = _mapping(value, label, errors)
    _text(item.get("code"), f"{label}.code", errors)
    _text(item.get("detail"), f"{label}.detail", errors)
    if type(item.get("retryable")) is not bool:
        errors.append(f"{label}.retryable 必须是布尔值")
    _enum(item.get("route"), FAILURE_ROUTES, f"{label}.route", errors)


def _id(value: Any, prefix: str, label: str, errors: list[str], *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.startswith(prefix + ":") or value.endswith(":"):
        errors.append(f"{label} 必须以 {prefix}: 开头")


def validate_penpot_browser_bridge(document: Any, *, project_root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    task = document.get("penpot_browser_task") if isinstance(document, dict) else None
    task = _mapping(task, "penpot_browser_task", errors)
    _walk_json(task, "penpot_browser_task", errors)
    if task.get("schema_version") != SCHEMA:
        errors.append(f"schema_version 必须为 {SCHEMA}")
    identity = _mapping(task.get("identity"), "identity", errors)
    project_id = identity.get("project_id")
    if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
        errors.append("identity.project_id 必须是有效项目 ID")
    _id(identity.get("task_id"), "penpot-task", "identity.task_id", errors)
    if type(identity.get("revision")) is not int or identity.get("revision") < 1:
        errors.append("identity.revision 必须是正整数")
    _enum(identity.get("lifecycle_state"), {"requested", "acknowledged", "completed", "failed", "blocked"}, "identity.lifecycle_state", errors)

    request = _mapping(task.get("request"), "request", errors)
    _id(request.get("request_id"), "penpot-request", "request.request_id", errors)
    _timestamp(request.get("created_at"), "request.created_at", errors)
    _enum(request.get("source"), {"local_project"}, "request.source", errors)
    operation = request.get("operation")
    _enum(operation, {"cloud_browser_open", "penpot_task"}, "request.operation", errors)
    _enum(request.get("action"), {"inspect", "capture", "create", "update"}, "request.action", errors)
    target = _mapping(request.get("target"), "request.target", errors)
    if operation == "cloud_browser_open":
        url = target.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            errors.append("cloud_browser_open 必须带安全 HTTPS target.url")
    if operation == "penpot_task" and not any(isinstance(target.get(k), str) and target.get(k).strip() for k in ("url", "file_id", "page_id")):
        errors.append("penpot_task.target 至少需要 url/file_id/page_id 之一")
    for key in ("url", "file_id", "page_id", "shape_id"):
        if key in target and target[key] is not None:
            _text(target[key], f"request.target.{key}", errors)
    refs = request.get("input_refs")
    if not isinstance(refs, list) or not refs:
        errors.append("request.input_refs 必须是非空数组")
    else:
        for i, ref in enumerate(refs):
            _ref(ref, f"request.input_refs[{i}]", errors, project_root)
    constraints = _mapping(request.get("constraints"), "request.constraints", errors)
    if type(constraints.get("read_only")) is not bool:
        errors.append("request.constraints.read_only 必须是布尔值")
    caps = constraints.get("requested_capabilities")
    if not isinstance(caps, list) or any(not isinstance(c, str) or not c for c in caps):
        errors.append("request.constraints.requested_capabilities 必须是字符串数组")
    if type(constraints.get("timeout_seconds")) is not int or constraints.get("timeout_seconds") <= 0:
        errors.append("request.constraints.timeout_seconds 必须是正整数")
    _text(request.get("local_note"), "request.local_note", errors)

    ack = _mapping(task.get("ack"), "ack", errors)
    ack_status = ack.get("status")
    _enum(ack_status, {"pending", "accepted", "rejected"}, "ack.status", errors)
    _id(ack.get("ack_id"), "penpot-ack", "ack.ack_id", errors, nullable=ack_status == "pending")
    _timestamp(ack.get("at"), "ack.at", errors, nullable=ack_status == "pending")
    _enum(ack.get("receiver"), {"dot_cloud_browser"}, "ack.receiver", errors)
    _digest(ack.get("request_digest"), "ack.request_digest", errors, nullable=ack_status == "pending")
    connection = _mapping(ack.get("connection_evidence"), "ack.connection_evidence", errors)
    connection_status = connection.get("status")
    _enum(connection_status, {"pending", "verified", "failed"}, "ack.connection_evidence.status", errors)
    _timestamp(connection.get("observed_at"), "ack.connection_evidence.observed_at", errors, nullable=connection_status == "pending")
    _enum(connection.get("browser"), {"cloud_browser"}, "ack.connection_evidence.browser", errors)
    for key in ("browser_session_id", "tab_id", "origin"):
        _text(connection.get(key), f"ack.connection_evidence.{key}", errors, nullable=connection_status == "pending")
    if connection_status == "verified":
        _ref(connection.get("evidence_ref"), "ack.connection_evidence.evidence_ref", errors, project_root)
        if ack_status != "accepted":
            errors.append("connection_evidence.verified 需要 ack.status=accepted")
    elif connection_status == "failed":
        _failure(connection.get("failure"), "ack.connection_evidence.failure", errors)
    if ack_status == "accepted" and connection_status != "verified":
        errors.append("ack.accepted 必须带 verified connection_evidence")
    if ack_status == "rejected":
        if connection_status != "failed":
            errors.append("ack.rejected 必须带 failed connection_evidence")
        _failure(connection.get("failure"), "ack.connection_evidence.failure", errors)

    result = _mapping(task.get("result"), "result", errors)
    result_status = result.get("status")
    _enum(result_status, {"pending", "succeeded", "failed", "blocked"}, "result.status", errors)
    _id(result.get("result_id"), "penpot-result", "result.result_id", errors, nullable=result_status == "pending")
    _timestamp(result.get("completed_at"), "result.completed_at", errors, nullable=result_status == "pending")
    _digest(result.get("request_digest"), "result.request_digest", errors, nullable=result_status == "pending")
    _digest(result.get("ack_digest"), "result.ack_digest", errors, nullable=result_status == "pending")
    if result_status == "succeeded":
        output = _mapping(result.get("output"), "result.output", errors)
        _text(output.get("state"), "result.output.state", errors)
        output_refs = output.get("evidence_refs")
        if not isinstance(output_refs, list) or not output_refs:
            errors.append("result.succeeded 必须有非空 output.evidence_refs")
        else:
            for i, ref in enumerate(output_refs):
                _ref(ref, f"result.output.evidence_refs[{i}]", errors, project_root)
        _timestamp(output.get("returned_at"), "result.output.returned_at", errors)
        if ack_status != "accepted" or connection_status != "verified":
            errors.append("result.succeeded 需要 accepted ack 和 verified connection_evidence")
    elif result_status in {"failed", "blocked"}:
        _failure(result.get("failure"), "result.failure", errors)
    elif result_status == "pending" and identity.get("lifecycle_state") in {"completed", "failed", "blocked"}:
        errors.append("terminal lifecycle_state 不能搭配 result.pending")

    lifecycle = identity.get("lifecycle_state")
    if lifecycle == "requested" and (ack_status != "pending" or result_status != "pending"):
        errors.append("requested 状态必须保持 pending ack/result")
    if lifecycle == "acknowledged" and ack_status != "accepted":
        errors.append("acknowledged 状态必须有 accepted ack")
    if lifecycle == "completed" and result_status != "succeeded":
        errors.append("completed 状态必须有 succeeded result")
    if lifecycle in {"failed", "blocked"} and result_status not in {"failed", "blocked"} and ack_status != "rejected":
        errors.append("failed/blocked 状态必须记录失败 ack 或 result")

    integrity = _mapping(task.get("integrity"), "integrity", errors)
    if integrity.get("canonicalization") != CANONICALIZATION:
        errors.append(f"integrity.canonicalization 必须为 {CANONICALIZATION}")
    if integrity.get("digest_algorithm") != "sha256":
        errors.append("integrity.digest_algorithm 必须为 sha256")
    _digest(integrity.get("request_digest"), "integrity.request_digest", errors)
    _digest(integrity.get("ack_digest"), "integrity.ack_digest", errors)
    _digest(integrity.get("result_digest"), "integrity.result_digest", errors)
    try:
        request_digest = canonical_digest(request)
        ack_digest = canonical_digest(ack)
        result_digest = canonical_digest(result)
        if integrity.get("request_digest") != request_digest:
            errors.append("integrity.request_digest 不匹配")
        if integrity.get("ack_digest") != ack_digest:
            errors.append("integrity.ack_digest 不匹配")
        if integrity.get("result_digest") != result_digest:
            errors.append("integrity.result_digest 不匹配")
        if ack_status != "pending" and ack.get("request_digest") != request_digest:
            errors.append("ack.request_digest 不匹配 request")
        if result_status != "pending":
            if result.get("request_digest") != request_digest:
                errors.append("result.request_digest 不匹配 request")
            if result.get("ack_digest") != ack_digest:
                errors.append("result.ack_digest 不匹配 ack")
    except (TypeError, ValueError, RecursionError) as exc:
        errors.append(f"无法计算摘要: {exc}")

    return {
        "state": "invalid" if errors else "valid",
        "task_id": identity.get("task_id"),
        "request_digest": canonical_digest(request) if isinstance(request, dict) else None,
        "ack_digest": canonical_digest(ack) if isinstance(ack, dict) else None,
        "result_digest": canonical_digest(result) if isinstance(result, dict) else None,
        "errors": errors,
        "warnings": ["仅校验本地 request/ack/result 记录；未打开浏览器、未登录 Penpot、未验证远程执行。"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    try:
        result = validate_penpot_browser_bridge(load_yaml(args.task), project_root=args.project_root)
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        result = {"state": "invalid", "errors": [str(exc)], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
