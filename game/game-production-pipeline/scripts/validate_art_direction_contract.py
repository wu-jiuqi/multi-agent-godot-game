#!/usr/bin/env python3
"""Validate one versioned Art Direction Contract without mutating project state."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pipeline_common import canonical_digest, file_digest, load_yaml


SCHEMA_VERSION = "game-production-art-direction/v1"
GATE_ORDER = ("D0", "D1", "D2", "D3", "D4")
LIFECYCLE_STATES = {
    "draft",
    "brief_ready",
    "exploring",
    "direction_selected",
    "benchmarking",
    "production_ready",
    "rework_required",
    "blocked",
    "withdrawn",
}
GATE_REQUIREMENTS = {
    "brief_ready": ("D0",),
    "exploring": ("D0",),
    "direction_selected": ("D2",),
    "benchmarking": ("D2",),
    "production_ready": ("D4",),
}
DOMAINS = {"character", "environment", "props", "vfx", "animation", "ui", "marketing"}
ASSET_MODES = {"2d", "3d"}
LANGUAGE_FIELDS = (
    "shape",
    "silhouette",
    "proportion",
    "line_edge",
    "value",
    "color",
    "material_surface",
    "lighting",
    "composition_camera",
    "detail_density",
    "graphic_design",
    "motion",
    "vfx",
    "ui_visual",
)
REVIEW_FIELDS = (
    "brief_review",
    "exploration_review",
    "direction_approval",
    "benchmark_art_review",
    "benchmark_technical_review",
    "qa_review",
    "rights_review",
)
REVIEW_DIGEST_KIND = {
    "brief_review": "brief_subject_digest",
    "exploration_review": "exploration_subject_digest",
    "direction_approval": "direction_subject_digest",
    "benchmark_art_review": "benchmark_subject_digest",
    "benchmark_technical_review": "benchmark_subject_digest",
    "qa_review": "contract_subject_digest",
    "rights_review": "contract_subject_digest",
}
REVIEW_BY_GATE = {
    "D0": ("brief_review",),
    "D1": ("brief_review", "exploration_review"),
    "D2": ("brief_review", "exploration_review", "direction_approval"),
    "D3": (
        "brief_review",
        "exploration_review",
        "direction_approval",
        "benchmark_art_review",
        "benchmark_technical_review",
    ),
    "D4": REVIEW_FIELDS,
}
REASON_CODES = [
    "BRIEF",
    "RESEARCH",
    "DIRECTION",
    "STYLE",
    "READABILITY",
    "TECH",
    "PERF",
    "RIGHTS",
    "UI_BOUNDARY",
    "REGRESSION",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HTTPS_RE = re.compile(r"^https://", re.IGNORECASE)


def mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是映射")
        return {}
    return value


def sequence(value: Any, label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} 必须是数组")
        return []
    return value


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def strings(value: Any) -> list[str]:
    return [item for item in value if nonempty_string(item)] if isinstance(value, list) else []


def parse_time(value: Any) -> bool:
    if not nonempty_string(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return False
    return True


def identity_subject(contract: dict[str, Any]) -> dict[str, Any]:
    identity = contract.get("identity") if isinstance(contract.get("identity"), dict) else {}
    return {
        "art_direction_id": identity.get("art_direction_id"),
        "project_id": identity.get("project_id"),
        "display_name": identity.get("display_name"),
        "revision": identity.get("revision"),
        "previous_revision_digest": identity.get("previous_revision_digest"),
    }


def brief_subject(document: dict[str, Any]) -> dict[str, Any]:
    contract = document.get("art_direction_contract")
    if not isinstance(contract, dict):
        raise ValueError("缺少 art_direction_contract 映射")
    rights = contract.get("rights") if isinstance(contract.get("rights"), dict) else {}
    return {
        "schema_version": contract.get("schema_version"),
        "identity": identity_subject(contract),
        "responsibility": contract.get("responsibility"),
        "scope": contract.get("scope"),
        "brief": contract.get("brief"),
        "rights_policy": {"generative_ai_policy": rights.get("generative_ai_policy")},
    }


def exploration_subject(document: dict[str, Any]) -> dict[str, Any]:
    contract = document["art_direction_contract"]
    exploration = copy.deepcopy(contract.get("style_exploration"))
    if isinstance(exploration, dict):
        exploration.pop("selected_option_id", None)
    return {
        "brief": brief_subject(document),
        "research": contract.get("research"),
        "style_exploration": exploration,
    }


def direction_subject(document: dict[str, Any]) -> dict[str, Any]:
    contract = document["art_direction_contract"]
    exploration = contract.get("style_exploration") if isinstance(contract.get("style_exploration"), dict) else {}
    return {
        "exploration": exploration_subject(document),
        "selected_option_id": exploration.get("selected_option_id"),
    }


def benchmark_subject(document: dict[str, Any]) -> dict[str, Any]:
    contract = document["art_direction_contract"]
    return {
        "direction": direction_subject(document),
        "style_bible": contract.get("style_bible"),
        "translation_matrix": contract.get("translation_matrix"),
        "technical_profiles": contract.get("technical_profiles"),
        "performance": contract.get("performance"),
        "benchmark": contract.get("benchmark"),
    }


def contract_subject(document: dict[str, Any]) -> dict[str, Any]:
    contract = document["art_direction_contract"]
    return {"benchmark": benchmark_subject(document), "rights": contract.get("rights")}


def art_direction_digests(document: dict[str, Any]) -> dict[str, str]:
    return {
        "brief_subject_digest": canonical_digest(brief_subject(document)),
        "exploration_subject_digest": canonical_digest(exploration_subject(document)),
        "direction_subject_digest": canonical_digest(direction_subject(document)),
        "benchmark_subject_digest": canonical_digest(benchmark_subject(document)),
        "contract_subject_digest": canonical_digest(contract_subject(document)),
    }


def validate_artifact_ref(
    value: Any,
    label: str,
    errors: list[str],
    *,
    project_root: Path | None,
    file_checks: list[dict[str, str]],
) -> dict[str, Any]:
    ref = mapping(value, label, errors)
    for key in ("artifact_id", "uri"):
        if not nonempty_string(ref.get(key)):
            errors.append(f"{label}.{key} 必须是非空字符串")
    if not isinstance(ref.get("version"), (str, int)) or isinstance(ref.get("version"), bool):
        errors.append(f"{label}.version 必须是字符串或整数")
    sha256 = ref.get("sha256")
    if not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256):
        errors.append(f"{label}.sha256 必须是 64 位小写 SHA-256")
    uri = ref.get("uri")
    if project_root is None or not isinstance(uri, str) or not uri.startswith("repo://"):
        return ref
    relative = uri.removeprefix("repo://").replace("\\", "/")
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or ":" in relative:
        errors.append(f"{label}.uri 必须是项目内安全 repo:// 路径")
        return ref
    root = project_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        errors.append(f"{label}.uri 越出 project_root")
        return ref
    state = "missing"
    actual = ""
    if path.is_file():
        actual = file_digest(path)
        state = "matched" if actual == sha256 else "mismatch"
    file_checks.append({"label": label, "uri": uri, "state": state, "actual_sha256": actual})
    if state == "missing":
        errors.append(f"{label} 引用的文件不存在: {relative}")
    elif state == "mismatch":
        errors.append(f"{label} 引用的文件 SHA-256 不匹配: {relative}")
    return ref


def validate_review(value: Any, label: str, expected_digest: str, errors: list[str]) -> dict[str, Any]:
    review = mapping(value, label, errors)
    status = review.get("status")
    if status not in {"pending", "approved", "rejected", "stale"}:
        errors.append(f"{label}.status 非法")
    if status == "approved":
        if not nonempty_string(review.get("reviewer")):
            errors.append(f"{label}.reviewer 缺失")
        if review.get("subject_digest") != expected_digest:
            errors.append(f"{label}.subject_digest 已过期或不匹配")
        if not parse_time(review.get("reviewed_at")):
            errors.append(f"{label}.reviewed_at 必须是 ISO 8601 时间")
        if not strings(review.get("evidence_refs")):
            errors.append(f"{label}.evidence_refs 不能为空")
    return review


def metric_result(metric: dict[str, Any]) -> str | None:
    limit = metric.get("limit")
    measured = metric.get("measured")
    comparator = metric.get("comparator")
    if not isinstance(limit, (int, float)) or isinstance(limit, bool):
        return None
    if not isinstance(measured, (int, float)) or isinstance(measured, bool):
        return None
    if not math.isfinite(float(limit)) or not math.isfinite(float(measured)):
        return None
    passed = {
        "<=": measured <= limit,
        "<": measured < limit,
        ">=": measured >= limit,
        ">": measured > limit,
        "==": measured == limit,
    }.get(comparator)
    return None if passed is None else ("passed" if passed else "failed")


def validate_previous_revision(document: dict[str, Any], previous: dict[str, Any], errors: list[str]) -> None:
    current = document.get("art_direction_contract", {})
    prior = previous.get("art_direction_contract", {}) if isinstance(previous, dict) else {}
    current_identity = current.get("identity", {}) if isinstance(current, dict) else {}
    prior_identity = prior.get("identity", {}) if isinstance(prior, dict) else {}
    if current_identity.get("art_direction_id") != prior_identity.get("art_direction_id"):
        errors.append("上一 revision 的 art_direction_id 不一致")
        return
    current_revision = current_identity.get("revision")
    prior_revision = prior_identity.get("revision")
    if current_revision == prior_revision:
        if canonical_digest(document) != canonical_digest(previous):
            errors.append("同一 Art Direction revision 不得原地修改")
        return
    if not isinstance(current_revision, int) or current_revision != prior_revision + 1:
        errors.append("新 revision 必须紧接上一 revision")
    expected = art_direction_digests(previous)["contract_subject_digest"]
    if current_identity.get("previous_revision_digest") != expected:
        errors.append("previous_revision_digest 不匹配上一 revision contract subject")


def validate_art_direction_contract(
    document: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
    project_root: Path | None = None,
    target_gate: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    file_checks: list[dict[str, str]] = []
    contract = mapping(document.get("art_direction_contract"), "art_direction_contract", errors)
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须为 {SCHEMA_VERSION}")

    identity = mapping(contract.get("identity"), "identity", errors)
    art_direction_id = identity.get("art_direction_id")
    if not isinstance(art_direction_id, str) or not art_direction_id.startswith("artdir:"):
        errors.append("identity.art_direction_id 必须以 artdir: 开头")
    for key in ("project_id", "display_name"):
        if not nonempty_string(identity.get(key)):
            errors.append(f"identity.{key} 必须是非空字符串")
    revision = identity.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("identity.revision 必须是正整数")
    if revision == 1 and identity.get("previous_revision_digest") is not None:
        errors.append("revision 1 的 previous_revision_digest 必须为 null")
    if revision != 1 and not SHA256_RE.fullmatch(str(identity.get("previous_revision_digest", ""))):
        errors.append("revision > 1 必须提供 previous_revision_digest")
    lifecycle = identity.get("lifecycle_state")
    if lifecycle not in LIFECYCLE_STATES:
        errors.append("identity.lifecycle_state 非法")

    responsibility = mapping(contract.get("responsibility"), "responsibility", errors)
    for key in ("owner", "game_director", "game_designer", "technical_integrator", "qa_reviewer", "rights_reviewer"):
        if not nonempty_string(responsibility.get(key)):
            errors.append(f"responsibility.{key} 必须是非空字符串")
    if responsibility.get("owner") in {responsibility.get("qa_reviewer"), responsibility.get("rights_reviewer")}:
        errors.append("主美 owner 不能同时充当 QA 或权利评审者")

    scope = mapping(contract.get("scope"), "scope", errors)
    required_domains = strings(scope.get("required_domains"))
    if not required_domains or len(required_domains) != len(set(required_domains)):
        errors.append("scope.required_domains 必须是非空且不重复的数组")
    unknown_domains = set(required_domains) - DOMAINS
    if unknown_domains:
        errors.append(f"scope.required_domains 含未知域: {sorted(unknown_domains)}")
    asset_modes = strings(scope.get("asset_modes"))
    if set(asset_modes) - ASSET_MODES:
        errors.append("scope.asset_modes 只允许 2d/3d")
    if not strings(scope.get("target_platforms")):
        errors.append("scope.target_platforms 不能为空")
    if not strings(scope.get("camera_and_gameplay_contexts")):
        errors.append("scope.camera_and_gameplay_contexts 不能为空")
    sequence(scope.get("out_of_scope"), "scope.out_of_scope", errors)

    brief = mapping(contract.get("brief"), "brief", errors)
    validate_artifact_ref(brief.get("project_brief_ref"), "brief.project_brief_ref", errors, project_root=project_root, file_checks=file_checks)
    research = mapping(contract.get("research"), "research", errors)
    source_refs = sequence(research.get("source_refs"), "research.source_refs", errors)
    source_kinds: set[str] = set()
    source_ids: set[str] = set()
    for index, raw in enumerate(source_refs):
        label = f"research.source_refs[{index}]"
        source = mapping(raw, label, errors)
        source_id = source.get("source_id")
        if not nonempty_string(source_id):
            errors.append(f"{label}.source_id 缺失")
        elif source_id in source_ids:
            errors.append(f"重复 source_id: {source_id}")
        source_ids.add(source_id)
        if not nonempty_string(source.get("title")) or not HTTPS_RE.match(str(source.get("uri", ""))):
            errors.append(f"{label} 必须提供 title 和 https URI")
        kind = source.get("source_kind")
        if kind not in {"primary", "secondary", "video"}:
            errors.append(f"{label}.source_kind 非法")
        else:
            source_kinds.add(kind)
        if source.get("rights_use") not in {"owned", "licensed", "public-domain", "reference-only"}:
            errors.append(f"{label}.rights_use 非法")
        if not strings(source.get("extracted_principles")):
            errors.append(f"{label}.extracted_principles 不能为空")
        if not strings(source.get("avoid_copying")):
            errors.append(f"{label}.avoid_copying 不能为空")

    exploration = mapping(contract.get("style_exploration"), "style_exploration", errors)
    minimum_option_count = exploration.get("minimum_option_count")
    if not isinstance(minimum_option_count, int) or isinstance(minimum_option_count, bool) or minimum_option_count < 3:
        errors.append("style_exploration.minimum_option_count 必须至少为 3")
        minimum_option_count = 3
    options = sequence(exploration.get("options"), "style_exploration.options", errors)
    option_ids: set[str] = set()
    signatures: set[str] = set()
    for index, raw in enumerate(options):
        label = f"style_exploration.options[{index}]"
        option = mapping(raw, label, errors)
        option_id = option.get("option_id")
        if not nonempty_string(option_id):
            errors.append(f"{label}.option_id 缺失")
        elif option_id in option_ids:
            errors.append(f"重复 option_id: {option_id}")
        option_ids.add(option_id)
        for key in ("title", "thesis", "signature", "experience_fit", "production_cost", "technical_risk", "ui_translation"):
            if not nonempty_string(option.get(key)):
                errors.append(f"{label}.{key} 必须是非空字符串")
        if nonempty_string(option.get("signature")):
            signatures.add(option["signature"].strip().casefold())
        if not strings(option.get("differentiation_axes")):
            errors.append(f"{label}.differentiation_axes 不能为空")
        if not strings(option.get("evidence_refs")):
            errors.append(f"{label}.evidence_refs 不能为空")
    selected_option_id = exploration.get("selected_option_id")
    if selected_option_id is not None and selected_option_id not in option_ids:
        errors.append("style_exploration.selected_option_id 未指向现有 option")

    bible = mapping(contract.get("style_bible"), "style_bible", errors)
    language = mapping(bible.get("language"), "style_bible.language", errors)
    for key in LANGUAGE_FIELDS:
        entry = mapping(language.get(key), f"style_bible.language.{key}", errors)
        for field in ("rule", "avoid"):
            if field not in entry:
                errors.append(f"style_bible.language.{key} 缺少 {field}")
    translation = mapping(contract.get("translation_matrix"), "translation_matrix", errors)
    mappings = sequence(translation.get("mappings"), "translation_matrix.mappings", errors)
    mapped_domains: set[str] = set()
    for index, raw in enumerate(mappings):
        item = mapping(raw, f"translation_matrix.mappings[{index}]", errors)
        domains = sequence(item.get("domains"), f"translation_matrix.mappings[{index}].domains", errors)
        for entry_index, raw_entry in enumerate(domains):
            entry = mapping(raw_entry, f"translation_matrix.mappings[{index}].domains[{entry_index}]", errors)
            if entry.get("domain") in DOMAINS and nonempty_string(entry.get("rule")) and nonempty_string(entry.get("evidence_ref")):
                mapped_domains.add(entry["domain"])

    profiles = mapping(contract.get("technical_profiles"), "technical_profiles", errors)
    two_d = mapping(profiles.get("two_d"), "technical_profiles.two_d", errors)
    three_d = mapping(profiles.get("three_d"), "technical_profiles.three_d", errors)
    ui = mapping(profiles.get("ui"), "technical_profiles.ui", errors)
    if two_d.get("enabled") not in {True, False} or three_d.get("enabled") not in {True, False} or ui.get("enabled") not in {True, False}:
        errors.append("technical_profiles 的 enabled 必须是布尔值")

    performance = mapping(contract.get("performance"), "performance", errors)
    context = mapping(performance.get("measurement_context"), "performance.measurement_context", errors)
    metrics = sequence(performance.get("metrics"), "performance.metrics", errors)
    metric_statuses: list[str | None] = []
    for index, raw in enumerate(metrics):
        label = f"performance.metrics[{index}]"
        metric = mapping(raw, label, errors)
        for key in ("metric_id", "unit", "evidence_ref"):
            if not nonempty_string(metric.get(key)):
                errors.append(f"{label}.{key} 必须是非空字符串")
        computed = metric_result(metric)
        if computed is None:
            errors.append(f"{label} 的 comparator/limit/measured 无效")
        elif metric.get("result") != computed:
            errors.append(f"{label}.result 应为 {computed}")
        metric_statuses.append(computed)

    benchmark = mapping(contract.get("benchmark"), "benchmark", errors)
    benchmark_domains = set(strings(benchmark.get("covered_domains")))
    rights = mapping(contract.get("rights"), "rights", errors)
    if rights.get("clearance_state") not in {"unknown", "conditional", "cleared", "blocked"}:
        errors.append("rights.clearance_state 非法")
    if rights.get("generative_ai_policy") not in {"forbidden", "research-only", "concept-only", "allowed"}:
        errors.append("rights.generative_ai_policy 非法")
    ai_records = sequence(rights.get("ai_use_records"), "rights.ai_use_records", errors)
    for index, raw in enumerate(ai_records):
        label = f"rights.ai_use_records[{index}]"
        record = mapping(raw, label, errors)
        for key in ("provider", "model", "version", "terms_snapshot_ref", "human_contribution_ref", "output_disposition"):
            if not nonempty_string(record.get(key)):
                errors.append(f"{label}.{key} 必须是非空字符串")
        sequence(record.get("input_asset_refs"), f"{label}.input_asset_refs", errors)
    if rights.get("generative_ai_policy") == "forbidden" and ai_records:
        errors.append("generative_ai_policy=forbidden 时不得存在 ai_use_records")

    try:
        digests = art_direction_digests(document)
    except (TypeError, ValueError) as exc:
        errors.append(f"无法计算阶段摘要: {exc}")
        digests = {key: "" for key in (
            "brief_subject_digest", "exploration_subject_digest", "direction_subject_digest", "benchmark_subject_digest", "contract_subject_digest"
        )}
    verification = mapping(contract.get("verification"), "verification", errors)
    automated_checks = sequence(verification.get("automated_checks"), "verification.automated_checks", errors)
    automated_statuses: list[str] = []
    for index, raw in enumerate(automated_checks):
        check = mapping(raw, f"verification.automated_checks[{index}]", errors)
        if not nonempty_string(check.get("check_id")) or not nonempty_string(check.get("command")):
            errors.append(f"verification.automated_checks[{index}] 缺少 check_id/command")
        if check.get("status") not in {"pending", "passed", "failed"}:
            errors.append(f"verification.automated_checks[{index}].status 非法")
        automated_statuses.append(check.get("status"))
    reviews = {
        name: validate_review(verification.get(name), f"verification.{name}", digests[REVIEW_DIGEST_KIND[name]], errors)
        for name in REVIEW_FIELDS
    }

    rework = mapping(contract.get("rework"), "rework", errors)
    if rework.get("allowed_reason_codes") != REASON_CODES:
        errors.append("rework.allowed_reason_codes 必须保持标准顺序和全集")
    issues = sequence(rework.get("current_issues"), "rework.current_issues", errors)
    open_issues: list[dict[str, Any]] = []
    for index, raw in enumerate(issues):
        issue = mapping(raw, f"rework.current_issues[{index}]", errors)
        if issue.get("reason_code") not in REASON_CODES or issue.get("status") not in {"open", "resolved"}:
            errors.append(f"rework.current_issues[{index}] 的 reason_code/status 非法")
        for key in ("issue_id", "owner", "required_change"):
            if not nonempty_string(issue.get(key)):
                errors.append(f"rework.current_issues[{index}].{key} 缺失")
        if issue.get("status") == "open":
            open_issues.append(issue)
    sequence(rework.get("history"), "rework.history", errors)
    if lifecycle in {"rework_required", "blocked"} and not open_issues:
        errors.append(f"{lifecycle} 状态必须有开放返工 issue")

    publication = mapping(contract.get("publication"), "publication", errors)
    direction_review = reviews.get("direction_approval", {})
    if direction_review.get("status") == "approved" and (
        direction_review.get("reviewer") != responsibility.get("game_director")
        or not str(direction_review.get("reviewer", "")).startswith("human:")
    ):
        errors.append("direction_approval requires the human game_director")
    if publication.get("release_state") not in {"not-ready", "candidate", "approved", "withdrawn"}:
        errors.append("publication.release_state 非法")
    integrity = mapping(contract.get("integrity"), "integrity", errors)
    for key, digest in digests.items():
        if integrity.get(key) != digest:
            errors.append(f"integrity.{key} 不匹配")

    gate_issues: dict[str, list[str]] = {gate: [] for gate in GATE_ORDER}
    for field in ("player_experience_goal", "visual_problem"):
        if not nonempty_string(brief.get(field)):
            gate_issues["D0"].append(f"brief.{field} 缺失")
    for field in ("gameplay_readability_goals", "game_pillars", "creative_constraints", "anti_goals"):
        if not strings(brief.get(field)):
            gate_issues["D0"].append(f"brief.{field} 不能为空")
    if rights.get("clearance_state") not in {"conditional", "cleared"}:
        gate_issues["D0"].append("rights.clearance_state 未达到 conditional/cleared")
    if reviews.get("brief_review", {}).get("status") != "approved":
        gate_issues["D0"].append("brief_review 尚未批准")

    gate_issues["D1"].extend(gate_issues["D0"])
    if not parse_time(research.get("researched_at")):
        gate_issues["D1"].append("research.researched_at 缺失或非法")
    if len(source_refs) < 3:
        gate_issues["D1"].append("research.source_refs 至少需要 3 项")
    if "primary" not in source_kinds or "video" not in source_kinds:
        gate_issues["D1"].append("研究必须同时包含 primary 与 video 来源")
    if not strings(research.get("outside_game_influences")):
        gate_issues["D1"].append("research.outside_game_influences 不能为空")
    if len(options) < minimum_option_count or len(signatures) < minimum_option_count:
        gate_issues["D1"].append("候选方向数量或独立 signature 未达到 minimum_option_count")
    if not nonempty_string(exploration.get("recommendation")):
        gate_issues["D1"].append("style_exploration.recommendation 缺失")
    if reviews.get("exploration_review", {}).get("status") != "approved":
        gate_issues["D1"].append("exploration_review 尚未批准")

    gate_issues["D2"].extend(gate_issues["D1"])
    if selected_option_id not in option_ids:
        gate_issues["D2"].append("尚未唯一选择现有方向 option")
    if reviews.get("direction_approval", {}).get("status") != "approved":
        gate_issues["D2"].append("direction_approval 尚未批准")

    gate_issues["D3"].extend(gate_issues["D2"])
    art_pillars = sequence(bible.get("art_pillars"), "style_bible.art_pillars", errors)
    if not 3 <= len(art_pillars) <= 5:
        gate_issues["D3"].append("style_bible.art_pillars 必须为 3–5 项")
    if len(strings(bible.get("invariants"))) < 3 or not strings(bible.get("controlled_variations")):
        gate_issues["D3"].append("style_bible 必须包含至少 3 个 invariants 和 controlled_variations")
    for key in LANGUAGE_FIELDS:
        entry = language.get(key) if isinstance(language.get(key), dict) else {}
        if not nonempty_string(entry.get("rule")) or not nonempty_string(entry.get("avoid")):
            gate_issues["D3"].append(f"style_bible.language.{key} 未完成 rule/avoid")
    if not sequence(bible.get("semantic_cues"), "style_bible.semantic_cues", errors):
        gate_issues["D3"].append("style_bible.semantic_cues 不能为空")
    missing_mappings = set(required_domains) - mapped_domains
    if missing_mappings:
        gate_issues["D3"].append(f"translation_matrix 缺少域: {sorted(missing_mappings)}")
    if "2d" in asset_modes and two_d.get("enabled") is not True:
        gate_issues["D3"].append("scope 使用 2d，但 two_d Profile 未启用")
    if "3d" in asset_modes and three_d.get("enabled") is not True:
        gate_issues["D3"].append("scope 使用 3d，但 three_d Profile 未启用")
    if "ui" in required_domains and ui.get("enabled") is not True:
        gate_issues["D3"].append("scope 包含 ui，但 UI Profile 未启用")
    profile_fields = {
        "two_d": (two_d, ("source_formats", "runtime_formats", "color_space", "alpha_policy", "filtering", "mipmap_policy", "compression_policy", "max_texture_dimension", "atlas_policy")),
        "three_d": (three_d, ("units", "axis_convention", "source_formats", "runtime_format", "mesh_budget_ref", "material_budget_ref", "lod_policy", "skeleton_policy", "texture_policy")),
        "ui": (ui, ("reference_viewports", "scale_policy", "safe_area_policy", "typography_ref", "token_ref", "contrast_policy", "localization_policy", "structural_workflow_boundary")),
    }
    for profile_name, (profile, fields) in profile_fields.items():
        if profile.get("enabled") is not True:
            continue
        for field in fields:
            value = profile.get(field)
            if isinstance(value, list):
                valid = bool(strings(value))
            elif field == "max_texture_dimension":
                valid = isinstance(value, int) and not isinstance(value, bool) and value > 0
            else:
                valid = nonempty_string(value)
            if not valid:
                gate_issues["D3"].append(f"technical_profiles.{profile_name}.{field} 未完成")
    if not nonempty_string(performance.get("budget_profile_ref")):
        gate_issues["D3"].append("performance.budget_profile_ref 缺失")
    for field in ("platform", "hardware_profile", "scenario_ref", "build_ref"):
        if not nonempty_string(context.get(field)):
            gate_issues["D3"].append(f"performance.measurement_context.{field} 缺失")
    if not metrics or any(status != "passed" for status in metric_statuses):
        gate_issues["D3"].append("性能指标缺失或未全部通过")
    if benchmark.get("in_engine") is not True:
        gate_issues["D3"].append("benchmark.in_engine 必须为 true")
    for field in ("benchmark_id", "scene_ref", "target_platform", "build_ref"):
        if not nonempty_string(benchmark.get(field)):
            gate_issues["D3"].append(f"benchmark.{field} 缺失")
    missing_benchmark_domains = set(required_domains) - benchmark_domains
    if missing_benchmark_domains:
        gate_issues["D3"].append(f"benchmark.covered_domains 缺少域: {sorted(missing_benchmark_domains)}")
    for field in ("style_frame_refs", "capture_refs", "readability_evidence_refs"):
        if not strings(benchmark.get(field)):
            gate_issues["D3"].append(f"benchmark.{field} 不能为空")
    if any(status != "passed" for status in automated_statuses) or not automated_checks:
        gate_issues["D3"].append("自动检查缺失或未全部通过")
    for review_name in ("benchmark_art_review", "benchmark_technical_review"):
        if reviews.get(review_name, {}).get("status") != "approved":
            gate_issues["D3"].append(f"{review_name} 尚未批准")

    gate_issues["D4"].extend(gate_issues["D3"])
    if rights.get("clearance_state") != "cleared":
        gate_issues["D4"].append("D4 要求 rights.clearance_state=cleared")
    for field in ("reference_register_ref", "release_clearance_ref"):
        if not nonempty_string(rights.get(field)):
            gate_issues["D4"].append(f"rights.{field} 缺失")
    if rights.get("attribution_required") is True and not nonempty_string(rights.get("attribution_manifest_ref")):
        gate_issues["D4"].append("需要署名但缺少 attribution_manifest_ref")
    for review_name in REVIEW_FIELDS:
        if reviews.get(review_name, {}).get("status") != "approved":
            gate_issues["D4"].append(f"{review_name} 尚未批准")
    if open_issues:
        gate_issues["D4"].append("仍有开放返工 issue")
    if publication.get("release_state") != "approved":
        gate_issues["D4"].append("publication.release_state 尚未 approved")
    if publication.get("frozen_revision_digest") != digests["contract_subject_digest"]:
        gate_issues["D4"].append("publication.frozen_revision_digest 不匹配")
    if not strings(publication.get("approval_refs")):
        gate_issues["D4"].append("publication.approval_refs 不能为空")

    # An autonomous charter replaces repeated owner sign-off only with a real,
    # independently reviewed decision bound to this exact production baseline.
    delegated_d4 = False
    charter_path = project_root / "game-pipeline/project-definition/production-charter.yaml" if project_root else None
    receipt = publication.get("gate_decision_ref")
    if receipt is not None or (charter_path is not None and charter_path.is_file()):
        try:
            from validate_production_charter import load_approvals, safe_path
            from evaluate_production_gate import evaluate_production_gate
            if charter_path is None or not charter_path.is_file():
                raise ValueError("delegated D4 requires project_root and production charter")
            charter_document = load_yaml(charter_path)
            policy = next((g for g in charter_document["production_charter"]["gates"] if g["gate_id"] == "D4"), {})
            c = charter_document["production_charter"]
            delegated_d4 = (policy.get("owner_kind") == "independent" and c.get("mode") == "autonomous-after-approval"
                            and c.get("review", {}).get("status") == "approved")
            if delegated_d4 or receipt is not None:
                if not isinstance(receipt, dict):
                    raise ValueError("delegated D4 requires publication.gate_decision_ref")
                receipt_path = safe_path(project_root, receipt.get("path"))
                if file_digest(receipt_path) != receipt.get("sha256"):
                    raise ValueError("D4 receipt file digest mismatch")
                decision = load_yaml(receipt_path)
                d = decision.get("production_gate_decision", {})
                if d.get("gate_id") != "D4" or d.get("producer") != responsibility.get("owner"):
                    raise ValueError("D4 receipt gate/producer mismatch")
                subject = d.get("subject", {})
                if subject.get("kind") != "art-direction" or subject.get("digest") != digests["contract_subject_digest"]:
                    raise ValueError("D4 receipt does not reference this art baseline")
                approvals, approval_errors = load_approvals(project_root / "game-pipeline/approvals")
                result = evaluate_production_gate(decision, charter_document, project_root=project_root, approvals=approvals)
                if approval_errors or result["state"] != "pass":
                    raise ValueError("; ".join(approval_errors + result.get("errors", []) + [result["state"]]))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            gate_issues["D4"].append(f"delegated D4: {exc}")

    enforced = set(GATE_REQUIREMENTS.get(lifecycle, ()))
    if target_gate in GATE_ORDER:
        enforced.add(target_gate)
    for gate in GATE_ORDER:
        if gate in enforced:
            errors.extend(f"{gate}: {issue}" for issue in gate_issues[gate])
    if lifecycle == "withdrawn" and publication.get("release_state") != "withdrawn":
        errors.append("withdrawn 生命周期要求 publication.release_state=withdrawn")
    if previous is not None:
        validate_previous_revision(document, previous, errors)
    if project_root is None:
        warnings.append("未提供 --project-root；repo:// 引用未执行真实文件 SHA-256 检查")

    return {
        "state": "valid" if not errors else "invalid",
        "schema_version": SCHEMA_VERSION,
        "art_direction_id": art_direction_id,
        "revision": revision,
        "lifecycle_state": lifecycle,
        "digests": digests,
        "gate_results": {
            gate: {"state": "passed" if not issues else "blocked", "issues": issues}
            for gate, issues in gate_issues.items()
        },
        "file_verification": "checked" if project_root is not None else "not-checked",
        "delegated_d4": delegated_d4,
        "file_checks": file_checks,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--gate", choices=GATE_ORDER)
    args = parser.parse_args()
    try:
        document = load_yaml(args.contract)
        previous = load_yaml(args.previous) if args.previous else None
        result = validate_art_direction_contract(
            document,
            previous=previous,
            project_root=args.project_root,
            target_gate=args.gate,
        )
    except (OSError, ValueError) as exc:
        result = {"state": "invalid", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("state") == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
