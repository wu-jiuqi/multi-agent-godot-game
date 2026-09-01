#!/usr/bin/env python3
"""Validate a specialist asset contract without mutating project files."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pipeline_common import canonical_digest, file_digest, load_yaml


SCHEMA_VERSION = "game-production-specialist-asset/v1"
ASSET_ID_RE = re.compile(r"^asset:[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUEST_ID_RE = re.compile(r"^request:[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LICENSE_TOKEN_RE = re.compile(r"^[A-Za-z0-9.+():-]+(?: (?:AND|OR|WITH) [A-Za-z0-9.+():-]+)*$")

ASSET_KINDS = {"ui", "2d-art", "3d-model", "animation", "vfx", "audio", "font", "video", "other"}
LIFECYCLE_STATES = {
    "draft",
    "ready",
    "in_production",
    "source_submitted",
    "runtime_built",
    "integrated",
    "review",
    "approved",
    "released",
    "rework_required",
    "blocked",
    "withdrawn",
}
PRIORITIES = {"p0", "p1", "p2"}
RIGHTS_VALUES = {"allowed", "conditional", "forbidden", "unknown"}
CLEARANCE_STATES = {"cleared", "conditional", "blocked", "unknown"}
PROVENANCE = {"original", "commissioned", "marketplace", "open-license", "generated", "mixed"}
BACKENDS = {"git", "git-lfs", "perforce", "external-dam"}
COMPARISONS = {"lte", "gte", "eq"}
RESULTS = {"pending", "passed", "failed", "stale"}
REVIEW_STATUSES = {"pending", "approved", "rejected", "stale"}
RELEASE_STATES = {"not-ready", "candidate", "approved", "withdrawn"}
REASON_CODES = ["REQ", "SRC", "RGT", "IMP", "PERF", "REG", "SCOPE"]
REVIEW_FIELDS = ("producer_self_check", "intent_review", "technical_review", "qa_review", "rights_review")
FROZEN_STATES = {"approved", "released", "withdrawn"}
GATE_REQUIREMENTS = {
    "ready": ("A0",),
    "in_production": ("A0",),
    "source_submitted": ("A0", "A1"),
    "runtime_built": ("A0", "A1"),
    "integrated": ("A0", "A1", "A2"),
    "review": ("A0", "A1", "A2"),
    "approved": ("A0", "A1", "A2", "A3"),
    "released": ("A0", "A1", "A2", "A3"),
}


def mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是映射")
        return {}
    return value


def sequence(value: Any, label: str, errors: list[str], *, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} 必须是数组")
        return []
    if nonempty and not value:
        errors.append(f"{label} 不能为空")
    return value


def require_string(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} 必须是非空字符串")
        return ""
    return value


def require_strings(value: Any, label: str, errors: list[str], *, nonempty: bool = False) -> list[str]:
    values = sequence(value, label, errors, nonempty=nonempty)
    for index, item in enumerate(values):
        require_string(item, f"{label}[{index}]", errors)
    return [item for item in values if isinstance(item, str) and item]


def require_sha256(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        errors.append(f"{label} 必须是 64 位小写 SHA-256")
        return ""
    return value


def repo_relative_path(value: Any, label: str, errors: list[str]) -> str:
    path_text = require_string(value, label, errors).replace("\\", "/")
    path = PurePosixPath(path_text)
    if path.is_absolute() or ".." in path.parts or ":" in path_text:
        errors.append(f"{label} 必须是仓库内相对路径: {value}")
        return ""
    return path.as_posix()


def controlled_uri(value: Any, label: str, errors: list[str]) -> tuple[str, str | None]:
    uri = require_string(value, label, errors)
    for scheme in ("repo://", "dam://", "vcs://", "https://"):
        if uri.startswith(scheme):
            suffix = uri[len(scheme) :]
            if not suffix:
                errors.append(f"{label} 缺少 URI 路径")
            if scheme == "repo://":
                relative = repo_relative_path(suffix, label, errors)
                return uri, relative or None
            return uri, None
    if uri:
        errors.append(f"{label} 必须使用 repo://、dam://、vcs:// 或 https://")
    return uri, None


def verify_repo_file(
    project_root: Path | None,
    relative: str | None,
    expected_digest: str,
    label: str,
    errors: list[str],
    file_checks: list[dict[str, Any]],
) -> None:
    if project_root is None or relative is None:
        return
    root = project_root.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        errors.append(f"{label} 越出项目根目录")
        return
    if not target.is_file():
        errors.append(f"{label} 引用的文件不存在: {relative}")
        file_checks.append({"uri": f"repo://{relative}", "state": "missing"})
        return
    actual = file_digest(target)
    state = "matched" if actual == expected_digest else "mismatch"
    file_checks.append({"uri": f"repo://{relative}", "state": state, "sha256": actual})
    if state == "mismatch":
        errors.append(f"{label} 文件摘要不匹配: {relative}")


def validate_artifact_ref(
    value: Any,
    label: str,
    errors: list[str],
    project_root: Path | None,
    file_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    ref = mapping(value, label, errors)
    require_string(ref.get("artifact_id"), f"{label}.artifact_id", errors)
    version = ref.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append(f"{label}.version 必须是正整数")
    _, relative = controlled_uri(ref.get("uri"), f"{label}.uri", errors)
    digest = require_sha256(ref.get("sha256"), f"{label}.sha256", errors)
    verify_repo_file(project_root, relative, digest, label, errors, file_checks)
    return ref


def validate_file_ref(
    value: Any,
    label: str,
    errors: list[str],
    project_root: Path | None,
    file_checks: list[dict[str, Any]],
    *,
    require_tool: bool = False,
) -> dict[str, Any]:
    ref = mapping(value, label, errors)
    require_string(ref.get("file_id"), f"{label}.file_id", errors)
    _, relative = controlled_uri(ref.get("uri"), f"{label}.uri", errors)
    digest = require_sha256(ref.get("sha256"), f"{label}.sha256", errors)
    require_string(ref.get("format"), f"{label}.format", errors)
    if require_tool:
        tool = mapping(ref.get("tool"), f"{label}.tool", errors)
        require_string(tool.get("name"), f"{label}.tool.name", errors)
        require_string(tool.get("version"), f"{label}.tool.version", errors)
    verify_repo_file(project_root, relative, digest, label, errors, file_checks)
    return ref


def asset_subject(contract: dict[str, Any]) -> dict[str, Any]:
    identity = contract.get("identity") if isinstance(contract.get("identity"), dict) else {}
    immutable_identity = {
        key: identity.get(key)
        for key in ("asset_id", "project_id", "asset_kind", "display_name", "revision", "previous_revision_digest")
    }
    return {
        "schema_version": contract.get("schema_version"),
        "identity": immutable_identity,
        "demand": contract.get("demand"),
        "responsibility": contract.get("responsibility"),
        "consumer_boundary": contract.get("consumer_boundary"),
        "source_package": contract.get("source_package"),
        "rights": contract.get("rights"),
        "import_recipe": contract.get("import_recipe"),
        "runtime_package": contract.get("runtime_package"),
        "performance": contract.get("performance"),
        "domain_extension": contract.get("domain_extension"),
    }


def asset_subject_digest(document: dict[str, Any]) -> str:
    contract = document.get("specialist_asset_contract")
    if not isinstance(contract, dict):
        raise ValueError("缺少 specialist_asset_contract 映射")
    return canonical_digest(asset_subject(contract))


def source_subject_digest(contract: dict[str, Any]) -> str:
    return canonical_digest(contract.get("source_package"))


def recipe_digest(contract: dict[str, Any]) -> str:
    return canonical_digest(contract.get("import_recipe"))


def compare_metric(comparison: str, measured: float, limit: float) -> bool:
    if comparison == "lte":
        return measured <= limit
    if comparison == "gte":
        return measured >= limit
    return measured == limit


def validate_review(record_value: Any, label: str, subject_digest: str, errors: list[str]) -> dict[str, Any]:
    record = mapping(record_value, label, errors)
    status = record.get("status")
    if status not in REVIEW_STATUSES:
        errors.append(f"{label}.status 非法")
    evidence = require_strings(record.get("evidence_refs"), f"{label}.evidence_refs", errors)
    if status in {"approved", "rejected"}:
        require_string(record.get("reviewer"), f"{label}.reviewer", errors)
        require_string(record.get("reviewed_at"), f"{label}.reviewed_at", errors)
        if not evidence:
            errors.append(f"{label} 已完成评审时必须有证据")
    if status == "approved" and record.get("subject_digest") != subject_digest:
        errors.append(f"{label}.subject_digest 已过期或不匹配")
    return record


def path_parts(path_text: str) -> tuple[str, ...]:
    return PurePosixPath(path_text).parts


def paths_overlap(first: str, second: str) -> bool:
    left = path_parts(first)
    right = path_parts(second)
    return left[: len(right)] == right or right[: len(left)] == left


def parse_time(value: Any, label: str, errors: list[str]) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        errors.append(f"{label} 必须是 ISO-8601 时间或 null")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} 不是合法 ISO-8601 时间")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{label} 必须包含时区")
        return None
    return parsed.astimezone(UTC)


def validate_previous_revision(current: dict[str, Any], previous: dict[str, Any], errors: list[str]) -> None:
    current_contract = current.get("specialist_asset_contract")
    previous_contract = previous.get("specialist_asset_contract")
    if not isinstance(current_contract, dict) or not isinstance(previous_contract, dict):
        errors.append("当前或上一版本缺少 specialist_asset_contract")
        return
    current_identity = current_contract.get("identity", {})
    previous_identity = previous_contract.get("identity", {})
    if current_identity.get("asset_id") != previous_identity.get("asset_id"):
        errors.append("当前与上一版本 asset_id 不一致")
        return
    current_revision = current_identity.get("revision")
    previous_revision = previous_identity.get("revision")
    if not isinstance(current_revision, int) or not isinstance(previous_revision, int):
        return
    previous_digest = asset_subject_digest(previous)
    if current_revision == previous_revision:
        if previous_identity.get("lifecycle_state") in FROZEN_STATES and asset_subject_digest(current) != previous_digest:
            errors.append("冻结 revision 不得原地修改；必须创建新 revision")
    elif current_revision == previous_revision + 1:
        if current_identity.get("previous_revision_digest") != previous_digest:
            errors.append("新 revision 的 previous_revision_digest 不匹配上一版本")
    else:
        errors.append("revision 必须保持不变或恰好递增 1")


def validate_specialist_asset_contract(
    document: object,
    *,
    previous: dict[str, Any] | None = None,
    project_root: Path | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    file_checks: list[dict[str, Any]] = []
    if not isinstance(document, dict):
        return {"state": "invalid", "errors": ["根节点必须是映射"], "warnings": [], "gate_results": {}}
    contract = mapping(document.get("specialist_asset_contract"), "specialist_asset_contract", errors)
    required_sections = (
        "identity",
        "demand",
        "responsibility",
        "consumer_boundary",
        "source_package",
        "rights",
        "import_recipe",
        "runtime_package",
        "performance",
        "verification",
        "rework",
        "publication",
        "domain_extension",
        "integrity",
    )
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须为 {SCHEMA_VERSION}")
    for section_name in required_sections:
        if not isinstance(contract.get(section_name), dict):
            errors.append(f"{section_name} 必须是映射")

    identity = mapping(contract.get("identity"), "identity", errors)
    asset_id = require_string(identity.get("asset_id"), "identity.asset_id", errors)
    if asset_id and not ASSET_ID_RE.fullmatch(asset_id):
        errors.append("identity.asset_id 必须为 asset:<project>:<domain>:<name> 的小写稳定 ID")
    project_id = require_string(identity.get("project_id"), "identity.project_id", errors)
    if asset_id and project_id and asset_id.split(":", 2)[1] != project_id:
        errors.append("identity.asset_id 中的 project 与 project_id 不一致")
    if identity.get("asset_kind") not in ASSET_KINDS:
        errors.append("identity.asset_kind 非法")
    require_string(identity.get("display_name"), "identity.display_name", errors)
    revision = identity.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("identity.revision 必须是正整数")
    previous_digest_value = identity.get("previous_revision_digest")
    if revision == 1 and previous_digest_value is not None:
        errors.append("revision 1 的 previous_revision_digest 必须为 null")
    if isinstance(revision, int) and revision > 1:
        require_sha256(previous_digest_value, "identity.previous_revision_digest", errors)
    lifecycle = identity.get("lifecycle_state")
    if lifecycle not in LIFECYCLE_STATES:
        errors.append("identity.lifecycle_state 非法")

    demand = mapping(contract.get("demand"), "demand", errors)
    request_id = require_string(demand.get("request_id"), "demand.request_id", errors)
    if request_id and not REQUEST_ID_RE.fullmatch(request_id):
        errors.append("demand.request_id 必须为 request:<project>:<id>")
    upstream_refs = sequence(demand.get("upstream_refs"), "demand.upstream_refs", errors, nonempty=True)
    for index, ref in enumerate(upstream_refs):
        validate_artifact_ref(ref, f"demand.upstream_refs[{index}]", errors, project_root, file_checks)
    require_strings(demand.get("use_contexts"), "demand.use_contexts", errors, nonempty=True)
    require_string(demand.get("player_facing_outcome"), "demand.player_facing_outcome", errors)
    require_strings(demand.get("acceptance_intent"), "demand.acceptance_intent", errors, nonempty=True)
    require_string(demand.get("target_milestone"), "demand.target_milestone", errors)
    if demand.get("priority") not in PRIORITIES:
        errors.append("demand.priority 非法")

    responsibility = mapping(contract.get("responsibility"), "responsibility", errors)
    for role in ("requester", "producer", "intent_reviewer", "technical_integrator", "qa_reviewer", "rights_reviewer"):
        require_string(responsibility.get(role), f"responsibility.{role}", errors)

    boundary = mapping(contract.get("consumer_boundary"), "consumer_boundary", errors)
    require_strings(boundary.get("authoritative_source_refs"), "consumer_boundary.authoritative_source_refs", errors, nonempty=True)
    if boundary.get("access") != "read_only":
        errors.append("consumer_boundary.access 必须为 read_only")
    generated_paths = [repo_relative_path(item, "consumer_boundary.generated_output_paths", errors) for item in sequence(boundary.get("generated_output_paths"), "consumer_boundary.generated_output_paths", errors, nonempty=True)]
    protected_paths = [repo_relative_path(item, "consumer_boundary.protected_paths", errors) for item in sequence(boundary.get("protected_paths"), "consumer_boundary.protected_paths", errors, nonempty=True)]
    if boundary.get("reverse_write_requires_separate_workflow") is not True:
        errors.append("consumer_boundary.reverse_write_requires_separate_workflow 必须为 true")
    validate_artifact_ref(boundary.get("protected_path_snapshot_ref"), "consumer_boundary.protected_path_snapshot_ref", errors, project_root, file_checks)
    for generated in filter(None, generated_paths):
        for protected in filter(None, protected_paths):
            if paths_overlap(generated, protected):
                errors.append(f"generated_output_paths 与 protected_paths 重叠: {generated} / {protected}")

    source = mapping(contract.get("source_package"), "source_package", errors)
    editable_truth = sequence(source.get("editable_truth"), "source_package.editable_truth", errors, nonempty=True)
    for index, ref in enumerate(editable_truth):
        validate_file_ref(ref, f"source_package.editable_truth[{index}]", errors, project_root, file_checks, require_tool=True)
    for group_name in ("intermediate_files", "dependencies"):
        for index, ref in enumerate(sequence(source.get(group_name), f"source_package.{group_name}", errors)):
            validate_file_ref(ref, f"source_package.{group_name}[{index}]", errors, project_root, file_checks)
    vcs = mapping(source.get("version_control"), "source_package.version_control", errors)
    if vcs.get("backend") not in BACKENDS:
        errors.append("source_package.version_control.backend 非法")
    if vcs.get("visibility") not in {"private", "public"}:
        errors.append("source_package.version_control.visibility 非法")
    require_string(vcs.get("immutable_revision_ref"), "source_package.version_control.immutable_revision_ref", errors)
    if not isinstance(vcs.get("exclusive_lock_required"), bool):
        errors.append("source_package.version_control.exclusive_lock_required 必须是布尔值")

    rights = mapping(contract.get("rights"), "rights", errors)
    if rights.get("provenance") not in PROVENANCE:
        errors.append("rights.provenance 非法")
    require_string(rights.get("creator_or_supplier"), "rights.creator_or_supplier", errors)
    controlled_uri(rights.get("source_uri"), "rights.source_uri", errors)
    license_expression = require_string(rights.get("license_expression"), "rights.license_expression", errors)
    if license_expression and ("\n" in license_expression or not LICENSE_TOKEN_RE.fullmatch(license_expression)):
        errors.append("rights.license_expression 不是受支持的 SPDX/LicenseRef 表达式")
    require_string(rights.get("license_text_or_contract_ref"), "rights.license_text_or_contract_ref", errors)
    require_string(rights.get("acquisition_proof_ref"), "rights.acquisition_proof_ref", errors)
    for permission in ("commercial_use", "modification", "compiled_distribution", "raw_redistribution"):
        if rights.get(permission) not in RIGHTS_VALUES:
            errors.append(f"rights.{permission} 非法")
    if not isinstance(rights.get("attribution_required"), bool):
        errors.append("rights.attribution_required 必须是布尔值")
    if rights.get("attribution_required") is True:
        require_string(rights.get("attribution_text"), "rights.attribution_text", errors)
    require_strings(rights.get("platform_scope"), "rights.platform_scope", errors, nonempty=True)
    require_strings(rights.get("territory_scope"), "rights.territory_scope", errors, nonempty=True)
    expires_at = parse_time(rights.get("expires_at"), "rights.expires_at", errors)
    require_strings(rights.get("ai_use_restrictions"), "rights.ai_use_restrictions", errors)
    if rights.get("clearance_state") not in CLEARANCE_STATES:
        errors.append("rights.clearance_state 非法")

    recipe = mapping(contract.get("import_recipe"), "import_recipe", errors)
    if recipe.get("engine_adapter") not in {"generic", "godot"}:
        errors.append("import_recipe.engine_adapter 必须是 generic 或 godot")
    require_string(recipe.get("engine_version"), "import_recipe.engine_version", errors)
    importer = mapping(recipe.get("importer"), "import_recipe.importer", errors)
    require_string(importer.get("name"), "import_recipe.importer.name", errors)
    require_string(importer.get("version"), "import_recipe.importer.version", errors)
    interchange_format = require_string(recipe.get("interchange_format"), "import_recipe.interchange_format", errors).lower()
    validate_artifact_ref(recipe.get("preset_ref"), "import_recipe.preset_ref", errors, project_root, file_checks)
    requires_sidecar = recipe.get("requires_import_sidecar")
    if not isinstance(requires_sidecar, bool):
        errors.append("import_recipe.requires_import_sidecar 必须是布尔值")
    sidecars = sequence(recipe.get("sidecar_refs"), "import_recipe.sidecar_refs", errors)
    for index, ref in enumerate(sidecars):
        validate_artifact_ref(ref, f"import_recipe.sidecar_refs[{index}]", errors, project_root, file_checks)
    postprocess = recipe.get("postprocess_ref")
    if postprocess is not None:
        validate_artifact_ref(postprocess, "import_recipe.postprocess_ref", errors, project_root, file_checks)
    validate_artifact_ref(recipe.get("toolchain_lock_ref"), "import_recipe.toolchain_lock_ref", errors, project_root, file_checks)
    if recipe.get("reproducibility") not in {"deterministic", "best-effort"}:
        errors.append("import_recipe.reproducibility 非法")
    if recipe.get("reproducibility") == "best-effort":
        require_string(recipe.get("non_determinism_reason"), "import_recipe.non_determinism_reason", errors)
    if recipe.get("engine_adapter") == "godot":
        native = interchange_format in {"tscn", "scn", "tres", "res"}
        if native and requires_sidecar is True:
            errors.append("Godot 原生资源不应要求 .import sidecar")
        if not native and requires_sidecar is not True:
            errors.append("Godot 非原生导入资产必须要求 .import sidecar")
        if requires_sidecar is True and not sidecars:
            errors.append("Godot 非原生导入资产缺少 sidecar_refs")

    runtime = mapping(contract.get("runtime_package"), "runtime_package", errors)
    outputs = sequence(runtime.get("outputs"), "runtime_package.outputs", errors, nonempty=True)
    for index, ref in enumerate(outputs):
        output = validate_file_ref(ref, f"runtime_package.outputs[{index}]", errors, project_root, file_checks)
        require_string(output.get("platform"), f"runtime_package.outputs[{index}].platform", errors)
        if output.get("role") not in {"primary", "lod", "collision", "material", "texture", "stream", "scene", "other"}:
            errors.append(f"runtime_package.outputs[{index}].role 非法")
    cache_paths = [repo_relative_path(item, "runtime_package.cache_paths", errors) for item in sequence(runtime.get("cache_paths"), "runtime_package.cache_paths", errors)]
    if recipe.get("engine_adapter") == "godot" and ".godot/imported" not in cache_paths:
        errors.append("Godot Contract 必须把 .godot/imported 登记为 cache")

    performance = mapping(contract.get("performance"), "performance", errors)
    validate_artifact_ref(performance.get("budget_profile_ref"), "performance.budget_profile_ref", errors, project_root, file_checks)
    context = mapping(performance.get("measurement_context"), "performance.measurement_context", errors)
    for key in ("platform", "hardware_profile", "scenario_ref", "build_ref"):
        require_string(context.get(key), f"performance.measurement_context.{key}", errors)
    platform_scope = rights.get("platform_scope") if isinstance(rights.get("platform_scope"), list) else []
    if context.get("platform") and "all" not in platform_scope and context.get("platform") not in platform_scope:
        errors.append("performance.measurement_context.platform 不在授权 platform_scope 内")
    metrics = sequence(performance.get("metrics"), "performance.metrics", errors, nonempty=True)
    metric_ids: set[str] = set()
    computed_metric_results: list[str] = []
    for index, raw_metric in enumerate(metrics):
        label = f"performance.metrics[{index}]"
        metric = mapping(raw_metric, label, errors)
        metric_id = require_string(metric.get("metric_id"), f"{label}.metric_id", errors)
        if metric_id in metric_ids:
            errors.append(f"重复 metric_id: {metric_id}")
        metric_ids.add(metric_id)
        comparison = metric.get("comparison")
        if comparison not in COMPARISONS:
            errors.append(f"{label}.comparison 非法")
        limit = metric.get("limit")
        measured = metric.get("measured")
        if not isinstance(limit, (int, float)) or isinstance(limit, bool) or not math.isfinite(float(limit)):
            errors.append(f"{label}.limit 必须是有限数值")
        require_string(metric.get("unit"), f"{label}.unit", errors)
        computed = "pending"
        if measured is not None:
            if not isinstance(measured, (int, float)) or isinstance(measured, bool) or not math.isfinite(float(measured)):
                errors.append(f"{label}.measured 必须是有限数值或 null")
            elif comparison in COMPARISONS and isinstance(limit, (int, float)) and not isinstance(limit, bool):
                computed = "passed" if compare_metric(comparison, float(measured), float(limit)) else "failed"
                require_string(metric.get("evidence_ref"), f"{label}.evidence_ref", errors)
        if metric.get("result") != computed:
            errors.append(f"{label}.result 应为 {computed}")
        computed_metric_results.append(computed)

    try:
        expected_subject_digest = asset_subject_digest(document)
    except ValueError:
        expected_subject_digest = ""
    expected_source_digest = source_subject_digest(contract)
    expected_recipe_digest = recipe_digest(contract)

    verification = mapping(contract.get("verification"), "verification", errors)
    automated_checks = sequence(verification.get("automated_checks"), "verification.automated_checks", errors, nonempty=True)
    automated_statuses: list[str] = []
    check_ids: set[str] = set()
    for index, raw_check in enumerate(automated_checks):
        label = f"verification.automated_checks[{index}]"
        check = mapping(raw_check, label, errors)
        check_id = require_string(check.get("check_id"), f"{label}.check_id", errors)
        if check_id in check_ids:
            errors.append(f"重复 check_id: {check_id}")
        check_ids.add(check_id)
        require_string(check.get("command"), f"{label}.command", errors)
        require_string(check.get("expected_result"), f"{label}.expected_result", errors)
        status = check.get("status")
        if status not in RESULTS:
            errors.append(f"{label}.status 非法")
        if status == "passed":
            require_string(check.get("evidence_ref"), f"{label}.evidence_ref", errors)
        automated_statuses.append(status)
    reviews = {
        key: validate_review(verification.get(key), f"verification.{key}", expected_subject_digest, errors)
        for key in REVIEW_FIELDS
    }

    rework = mapping(contract.get("rework"), "rework", errors)
    if rework.get("allowed_reason_codes") != REASON_CODES:
        errors.append("rework.allowed_reason_codes 必须保持标准顺序和全集")
    current_issues = sequence(rework.get("current_issues"), "rework.current_issues", errors)
    for index, raw_issue in enumerate(current_issues):
        label = f"rework.current_issues[{index}]"
        issue = mapping(raw_issue, label, errors)
        require_string(issue.get("issue_id"), f"{label}.issue_id", errors)
        if issue.get("reason_code") not in REASON_CODES:
            errors.append(f"{label}.reason_code 非法")
        if not isinstance(issue.get("found_on_revision"), int) or isinstance(issue.get("found_on_revision"), bool):
            errors.append(f"{label}.found_on_revision 必须是整数")
        require_string(issue.get("owner"), f"{label}.owner", errors)
        require_string(issue.get("required_change"), f"{label}.required_change", errors)
        require_strings(issue.get("required_rechecks"), f"{label}.required_rechecks", errors, nonempty=True)
        if issue.get("status") not in {"open", "resolved"}:
            errors.append(f"{label}.status 非法")
        require_strings(issue.get("evidence_refs"), f"{label}.evidence_refs", errors)
    sequence(rework.get("history"), "rework.history", errors)
    open_issues = [issue for issue in current_issues if isinstance(issue, dict) and issue.get("status") == "open"]
    if lifecycle in {"rework_required", "blocked"} and not open_issues:
        errors.append(f"{lifecycle} 状态必须有开放返修 issue")

    publication = mapping(contract.get("publication"), "publication", errors)
    if publication.get("release_state") not in RELEASE_STATES:
        errors.append("publication.release_state 非法")
    approval_refs = require_strings(publication.get("approval_refs"), "publication.approval_refs", errors)
    build_refs = require_strings(publication.get("build_refs"), "publication.build_refs", errors)
    released_at = parse_time(publication.get("released_at"), "publication.released_at", errors)
    if publication.get("release_state") == "withdrawn":
        require_string(publication.get("withdrawal_reason"), "publication.withdrawal_reason", errors)

    mapping(contract.get("domain_extension"), "domain_extension", errors)
    integrity = mapping(contract.get("integrity"), "integrity", errors)
    if integrity.get("contract_subject_digest") != expected_subject_digest:
        errors.append("integrity.contract_subject_digest 不匹配当前 Contract subject")

    now = (as_of or datetime.now(UTC)).astimezone(UTC)
    gate_issues: dict[str, list[str]] = {"A0": [], "A1": [], "A2": [], "A3": []}
    for permission in ("commercial_use", "modification", "compiled_distribution"):
        if rights.get(permission) in {"forbidden", "unknown", None}:
            gate_issues["A0"].append(f"rights.{permission} 未形成可生产结论")
    if rights.get("clearance_state") not in {"conditional", "cleared"}:
        gate_issues["A0"].append("rights.clearance_state 未达到 conditional/cleared")
    if expires_at is not None and expires_at <= now:
        gate_issues["A0"].append("rights.expires_at 已过期")

    gate_issues["A1"].extend(gate_issues["A0"])
    if rights.get("clearance_state") != "cleared":
        gate_issues["A1"].append("Source Gate 要求 rights.clearance_state=cleared")
    if vcs.get("visibility") == "public" and rights.get("raw_redistribution") != "allowed":
        gate_issues["A1"].append("公开 VCS 与原始文件再分发权冲突")

    gate_issues["A2"].extend(gate_issues["A1"])
    if runtime.get("source_subject_digest") != expected_source_digest:
        gate_issues["A2"].append("runtime_package.source_subject_digest 不匹配")
    if runtime.get("recipe_digest") != expected_recipe_digest:
        gate_issues["A2"].append("runtime_package.recipe_digest 不匹配")
    if any(status != "passed" for status in computed_metric_results):
        gate_issues["A2"].append("性能指标尚未全部通过")
    if any(status != "passed" for status in automated_statuses):
        gate_issues["A2"].append("自动检查尚未全部通过")
    for review_name in ("producer_self_check", "technical_review"):
        if reviews.get(review_name, {}).get("status") != "approved":
            gate_issues["A2"].append(f"{review_name} 尚未批准")

    gate_issues["A3"].extend(gate_issues["A2"])
    for review_name in REVIEW_FIELDS:
        if reviews.get(review_name, {}).get("status") != "approved":
            gate_issues["A3"].append(f"{review_name} 尚未批准")
    if open_issues:
        gate_issues["A3"].append("仍有开放返修 issue")
    if publication.get("release_state") != "approved":
        gate_issues["A3"].append("publication.release_state 尚未 approved")
    if publication.get("frozen_revision_digest") != expected_subject_digest:
        gate_issues["A3"].append("publication.frozen_revision_digest 不匹配")
    if not approval_refs:
        gate_issues["A3"].append("缺少 approval_refs")
    if rights.get("attribution_required") is True and not publication.get("attribution_manifest_ref"):
        gate_issues["A3"].append("需要署名但缺少 attribution_manifest_ref")

    for gate_name in GATE_REQUIREMENTS.get(lifecycle, ()):
        errors.extend(f"{gate_name}: {message}" for message in gate_issues[gate_name])
    if lifecycle == "released":
        if not build_refs:
            errors.append("released 状态缺少 publication.build_refs")
        if released_at is None:
            errors.append("released 状态缺少 publication.released_at")
    if lifecycle == "withdrawn" and publication.get("release_state") != "withdrawn":
        errors.append("withdrawn 生命周期要求 publication.release_state=withdrawn")

    if previous is not None:
        validate_previous_revision(document, previous, errors)
    if project_root is None:
        warnings.append("未提供 --project-root；repo:// 文件存在性与真实 SHA-256 尚未检查")

    gate_results = {
        name: {"state": "passed" if not issues else "blocked", "issues": issues}
        for name, issues in gate_issues.items()
    }
    return {
        "state": "valid" if not errors else "invalid",
        "schema_version": SCHEMA_VERSION,
        "asset_id": asset_id,
        "revision": revision,
        "lifecycle_state": lifecycle,
        "digests": {
            "source_subject_digest": expected_source_digest,
            "recipe_digest": expected_recipe_digest,
            "contract_subject_digest": expected_subject_digest,
        },
        "gate_results": gate_results,
        "file_verification": "checked" if project_root is not None else "not-checked",
        "file_checks": file_checks,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    try:
        document = load_yaml(args.contract)
        previous = load_yaml(args.previous) if args.previous else None
    except (OSError, ValueError) as exc:
        print(json.dumps({"state": "invalid", "errors": [str(exc)]}, ensure_ascii=True, indent=2))
        return 2
    result = validate_specialist_asset_contract(
        document,
        previous=previous,
        project_root=args.project_root,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["state"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
