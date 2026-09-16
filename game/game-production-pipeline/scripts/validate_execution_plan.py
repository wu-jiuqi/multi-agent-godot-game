#!/usr/bin/env python3
"""Validate versioned execution plans, tool capabilities and dependency/write ownership."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import canonical_digest, file_digest, load_yaml
from validate_production_charter import SHA256, nonempty, number, safe_path, timestamp

MODES = {"generate", "automate", "takeover", "decide"}
STATUSES = {"draft", "approved", "running", "completed", "blocked", "cancelled"}


def plan_body(document):
    return document.get("execution_plan", document)


def execution_subject(document):
    p = plan_body(document)
    return {k: v for k, v in p.items() if k not in {"status", "integrity"}}


def plan_digest(document):
    return canonical_digest(execution_subject(document))


def registry_digest(document):
    r = document.get("tool_registry", document)
    return canonical_digest({k: v for k, v in r.items() if k != "integrity"})


def path_key(value):
    if not nonempty(value):
        raise ValueError("path must be a non-empty string")
    value = value.removeprefix("repo://").replace("\\", "/")
    parts = value.split("/")
    if value.startswith("/") or ":" in value or any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"invalid repo path: {value}")
    return "/".join(parts).casefold()


def overlap(a, b):
    a, b = path_key(a), path_key(b)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def check_ref(ref, label, errors, root=None):
    if not isinstance(ref, dict):
        errors.append(f"{label} must be a file reference")
        return
    try:
        path_key(ref.get("path"))
        if not isinstance(ref.get("sha256"), str) or not SHA256.fullmatch(ref["sha256"]):
            raise ValueError("missing sha256")
        if root is not None and file_digest(safe_path(root, ref["path"])) != ref["sha256"]:
            raise ValueError("file digest mismatch")
    except (OSError, ValueError) as exc:
        errors.append(f"{label}: {exc}")


def _validate_tool_registry(document, *, project_root=None):
    errors = []
    if not isinstance(document, dict) or not isinstance(document.get("tool_registry", document), dict):
        return {"state": "invalid", "errors": ["missing tool_registry"]}
    r = document.get("tool_registry", document)
    if r.get("schema_version") != "game-production-tool-registry/v1":
        errors.append("unsupported tool registry schema")
    if not nonempty(r.get("registry_id")) or type(r.get("version")) is not int or r["version"] < 1:
        errors.append("tool registry identity/version required")
    tools = r.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("registry.tools must be a non-empty array")
        tools = []
    ids = set()
    for tool in tools:
        if not isinstance(tool, dict):
            errors.append("tool must be a mapping")
            continue
        tid = tool.get("tool_id")
        if not nonempty(tid) or tid in ids:
            errors.append("missing/duplicate tool_id")
        else:
            ids.add(tid)
        for key in ("provider", "name", "version"):
            if not nonempty(tool.get(key)):
                errors.append(f"tool missing {key}")
        for key in ("capabilities", "permission_scope"):
            value = tool.get(key)
            if not isinstance(value, list) or not value or any(not nonempty(x) for x in value):
                errors.append(f"tool {key} must be non-empty strings")
        if type(tool.get("deterministic")) is not bool:
            errors.append("tool.deterministic must be boolean")
        rb = tool.get("rollback")
        if not isinstance(rb, dict) or type(rb.get("supported")) is not bool:
            errors.append("tool.rollback policy required")
        elif rb["supported"] and not nonempty(rb.get("procedure_ref")):
            errors.append("supported rollback requires procedure")
        source = tool.get("source")
        check_ref(source, f"tool {tid} source", errors, project_root)
    digest = registry_digest(document)
    if r.get("integrity", {}).get("registry_digest") != digest:
        errors.append("tool registry_digest mismatch")
    return {"state": "invalid" if errors else "valid", "registry_digest": digest, "errors": errors}


def dependencies(task):
    return set(task.get("depends_on", [])) | set(task.get("join", {}).get("required_task_ids", []))


def _validate_execution_plan(document, *, project_root=None):
    errors, warnings = [], []
    if not isinstance(document, dict) or not isinstance(plan_body(document), dict):
        return {"state": "invalid", "errors": ["missing execution_plan"], "warnings": []}
    p = plan_body(document)

    def strings(value, label, required=False):
        if not isinstance(value, list) or any(not nonempty(x) for x in value):
            errors.append(f"{label} must be a string array")
            return []
        if required and not value:
            errors.append(f"{label} cannot be empty")
        if len(value) != len(set(value)):
            errors.append(f"{label} contains duplicates")
        return value

    if p.get("schema_version") != "game-production-execution-plan/v1":
        errors.append("unsupported execution plan schema")
    for key in ("plan_id", "project_id"):
        if not nonempty(p.get(key)):
            errors.append(f"missing {key}")
    if type(p.get("version")) is not int or p["version"] < 1:
        errors.append("version must be a positive integer")
    if p.get("status") not in STATUSES or p.get("mode") not in MODES:
        errors.append("invalid status/mode")
    charter = p.get("production_charter_ref")
    if not isinstance(charter, dict):
        errors.append("production_charter_ref required")
    else:
        try:
            path_key(charter.get("path"))
        except ValueError as exc:
            errors.append(str(exc))
        if not SHA256.fullmatch(str(charter.get("subject_digest", ""))):
            errors.append("charter subject_digest required")
    context = p.get("context")
    if not isinstance(context, dict):
        errors.append("context required")
        context = {}
    inputs = context.get("input_refs")
    if not isinstance(inputs, list) or not inputs:
        errors.append("context.input_refs cannot be empty")
        inputs = []
    for ref in inputs:
        check_ref(ref, "context input", errors, project_root)
    if context.get("context_digest") != canonical_digest(inputs):
        errors.append("context_digest mismatch")
    if not timestamp(context.get("captured_at")):
        errors.append("context captured_at must include timezone")
    model = p.get("model")
    if not isinstance(model, dict):
        errors.append("model invocation identity required")
    else:
        for key in ("provider", "name", "version"):
            if not nonempty(model.get(key)):
                errors.append(f"model missing {key}")
        if not SHA256.fullmatch(str(model.get("source_digest", ""))):
            errors.append("model configuration source_digest required")
        check_ref(model.get("source_ref"), "model invocation configuration", errors, project_root)
        if isinstance(model.get("source_ref"), dict) and model["source_ref"].get("sha256") != model.get("source_digest"):
            errors.append("model configuration digest mismatch")
    registry_ref = p.get("tool_registry_ref")
    check_ref(registry_ref, "tool registry", errors, project_root)
    registry = None
    if project_root is not None and isinstance(registry_ref, dict):
        try:
            registry_doc = load_yaml(safe_path(project_root, registry_ref.get("path")))
            result = validate_tool_registry(registry_doc, project_root=project_root)
            errors.extend(result["errors"])
            registry = {t["tool_id"]: t for t in registry_doc["tool_registry"]["tools"] if isinstance(t, dict) and "tool_id" in t}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"tool registry: {exc}")
    tools = {}
    if not isinstance(p.get("tools"), list) or not p["tools"]:
        errors.append("plan tools required")
    for tool in p.get("tools", []) if isinstance(p.get("tools"), list) else []:
        if not isinstance(tool, dict) or not nonempty(tool.get("tool_id")):
            errors.append("invalid plan tool")
            continue
        tid = tool["tool_id"]
        if tid in tools:
            errors.append("duplicate plan tool")
        tools[tid] = tool
        capabilities = strings(tool.get("capability_refs"), "tool.capability_refs", True)
        permissions = strings(tool.get("permission_scope"), "tool.permission_scope", True)
        if not nonempty(tool.get("version")) or not SHA256.fullmatch(str(tool.get("source_digest", ""))):
            errors.append("plan tool requires version/source_digest")
        if registry is not None:
            registered = registry.get(tid, {})
            if registered.get("version") != tool.get("version") or registered.get("source", {}).get("sha256") != tool.get("source_digest"):
                errors.append(f"tool identity/version drift: {tid}")
            if set(capabilities) - set(registered.get("capabilities", [])) or set(permissions) - set(registered.get("permission_scope", [])):
                errors.append(f"tool capability/permission escalation: {tid}")
    lanes = {}
    for lane in p.get("lanes", []) if isinstance(p.get("lanes"), list) else []:
        if not isinstance(lane, dict) or not nonempty(lane.get("lane_id")):
            errors.append("invalid lane")
            continue
        lid = lane["lane_id"]
        if lid in lanes:
            errors.append("duplicate lane_id")
        lanes[lid] = lane
        if type(lane.get("max_parallel")) is not int or lane["max_parallel"] < 1:
            errors.append("lane max_parallel must be positive integer")
    if not lanes:
        errors.append("at least one lane required")
    tasks = {}
    raw_tasks = p.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        errors.append("tasks required")
        raw_tasks = []
    for task in raw_tasks:
        if not isinstance(task, dict) or not nonempty(task.get("task_id")):
            errors.append("task_id required")
            continue
        tid = task["task_id"]
        if tid in tasks:
            errors.append(f"duplicate task: {tid}")
        tasks[tid] = task
        if task.get("lane_id") not in lanes:
            errors.append(f"unknown lane: {tid}")
        if task.get("mode") not in MODES:
            errors.append(f"invalid mode: {tid}")
        for key in ("action", "authority_action", "responsible_role", "reviewer_role"):
            if not nonempty(task.get(key)):
                errors.append(f"{tid} missing {key}")
        if task.get("responsible_role") == task.get("reviewer_role"):
            errors.append(f"independent reviewer required: {tid}")
        if task.get("mode") in {"decide", "takeover"} and not nonempty(task.get("decision_scope")):
            errors.append(f"{tid} decision/takeover scope required")
        if not number(task.get("estimated_cost")):
            errors.append(f"{tid} finite estimated_cost required")
        tool_ids = strings(task.get("tool_ids"), f"{tid}.tool_ids", True)
        if set(tool_ids) - set(tools):
            errors.append(f"{tid} references unknown tools")
        strings(task.get("depends_on"), f"{tid}.depends_on")
        writes = strings(task.get("write_set"), f"{tid}.write_set", True)
        outputs = strings(task.get("output_refs"), f"{tid}.output_refs", True)
        for path in writes + outputs:
            try:
                path_key(path)
                if project_root is not None:
                    safe_path(project_root, path)
            except ValueError as exc:
                errors.append(str(exc))
        for path in outputs:
            try:
                if not any(path_key(path) == path_key(w) or path_key(path).startswith(path_key(w) + "/") for w in writes):
                    errors.append(f"{tid} output outside write ownership")
            except ValueError:
                pass
        if type(task.get("generated_assets")) is not bool:
            errors.append(f"{tid}.generated_assets must be boolean")
        refs = task.get("asset_contract_refs")
        if not isinstance(refs, list):
            errors.append(f"{tid}.asset_contract_refs must be array")
            refs = []
        if task.get("generated_assets") and not refs:
            errors.append(f"{tid} generated assets require asset contracts")
        for ref in refs:
            check_ref(ref, f"{tid} asset contract", errors, project_root)
            if project_root is not None and isinstance(ref, dict):
                try:
                    from validate_specialist_asset_contract import validate_specialist_asset_contract
                    asset = load_yaml(safe_path(project_root, ref.get("path")))
                    validation = validate_specialist_asset_contract(asset, project_root=project_root, target_gate="A0")
                    errors.extend(f"{tid} asset contract: {x}" for x in validation["errors"])
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
        sc = task.get("self_check")
        if not isinstance(sc, dict) or sc.get("required") is not True or not nonempty(sc.get("command_ref")):
            errors.append(f"{tid} executable self-check required")
        elif type(sc.get("max_repairs")) is not int or sc["max_repairs"] < 0:
            errors.append(f"{tid} invalid max_repairs")
        join = task.get("join")
        if not isinstance(join, dict) or join.get("strategy") != "all":
            errors.append("only explicit all-joins are supported")
        else:
            strings(join.get("required_task_ids"), f"{tid}.join.required_task_ids")
    retry = p.get("retry_policy", {})
    if not isinstance(retry, dict):
        retry = {}
    if type(retry.get("max_attempts")) is not int or retry["max_attempts"] < 1:
        errors.append("positive max_attempts required")
    if retry.get("on_exhausted") not in {"blocked", "escalate", "takeover"}:
        errors.append("invalid exhausted policy")
    budget = p.get("budget", {})
    if not isinstance(budget, dict) or not number(budget.get("max_cost")) or not nonempty(budget.get("unit")):
        errors.append("finite plan budget/unit required")
    if p.get("asset_contract_policy", {}).get("generated_assets_require_contract") is not True:
        errors.append("generated asset contract policy cannot be disabled")
    required = strings(p.get("acceptance", {}).get("required_task_ids"), "acceptance tasks", True)
    if set(required) - set(tasks):
        errors.append("acceptance references unknown tasks")
    store = p.get("evidence_store", {})
    try:
        if not isinstance(store, dict):
            raise ValueError("evidence store required")
        path_key(store.get("uri"))
        if project_root is not None:
            safe_path(project_root, store["uri"])
    except ValueError as exc:
        errors.append(str(exc))
    # Avoid graph processing on ill-typed input.
    if not errors:
        edges = {tid: dependencies(t) for tid, t in tasks.items()}
        for tid, deps in edges.items():
            if deps - tasks.keys() or tid in deps:
                errors.append(f"unknown/self dependency: {tid}")
        visiting, visited, ancestors = set(), set(), {}
        def visit(tid):
            if tid in visiting:
                errors.append("dependency cycle")
                return set()
            if tid in visited:
                return ancestors[tid]
            visiting.add(tid)
            parents = set(edges.get(tid, set()))
            for dependency in edges.get(tid, set()):
                if dependency in tasks:
                    parents |= visit(dependency)
            visiting.remove(tid)
            visited.add(tid)
            ancestors[tid] = parents
            return parents
        for tid in tasks:
            visit(tid)
        ids = list(tasks)
        for index, left in enumerate(ids):
            for right in ids[index + 1:]:
                if left not in ancestors[right] and right not in ancestors[left]:
                    if any(overlap(a, b) for a in tasks[left]["write_set"] for b in tasks[right]["write_set"]):
                        errors.append(f"unordered write ownership conflict: {left}/{right}")
    digest = plan_digest(document)
    recorded = p.get("integrity", {}).get("plan_digest")
    if recorded != digest:
        errors.append("plan_digest mismatch")
    if project_root is None:
        warnings.append("structure only; physical inputs, tool sources and authority not verified")
    return {"state": "invalid" if errors else "valid", "plan_id": p.get("plan_id"),
            "plan_digest": digest, "task_count": len(tasks), "errors": errors, "warnings": warnings}


def validate_execution_plan(document, **kwargs):
    try:
        return _validate_execution_plan(document, **kwargs)
    except (AttributeError, TypeError, ValueError, KeyError) as exc:
        return {"state": "invalid", "errors": ["malformed contract: " + str(exc)], "warnings": [], "launch_ready": False}


def validate_tool_registry(document, **kwargs):
    try:
        return _validate_tool_registry(document, **kwargs)
    except (AttributeError, TypeError, ValueError, KeyError) as exc:
        return {"state": "invalid", "errors": ["malformed contract: " + str(exc)], "warnings": [], "launch_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    try:
        result = validate_execution_plan(load_yaml(args.plan), project_root=args.project_root)
    except (OSError, ValueError, TypeError) as exc:
        result = {"state": "invalid", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["state"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
