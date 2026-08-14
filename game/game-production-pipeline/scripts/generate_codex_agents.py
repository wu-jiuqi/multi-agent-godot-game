#!/usr/bin/env python3
"""Validate approved project Agent Presets and generate managed Codex TOML adapters."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from pipeline_common import (
    AGENT_PRESET_SCHEMA,
    APPROVAL_SCHEMA,
    MANAGED_MARKER,
    SKILL_BINDINGS_SCHEMA,
    canonical_digest,
    directory_digest,
    ensure_within,
    file_digest,
    load_yaml,
    manifest_version,
    plugin_root,
    text_digest,
    write_new_text,
)
from validate_plugin_lock import evaluate_lock


PRESET_ID_RE = re.compile(r"^preset:[a-z0-9][a-z0-9:-]*$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_preset(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} 缺少 YAML frontmatter")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ValueError(f"{path} frontmatter 未闭合")
    metadata = load_yaml_text(text[4:marker], path)
    body = text[marker + 5 :].strip() + "\n"
    if not body.strip():
        raise ValueError(f"{path} 缺少 developer instructions")
    return metadata, body


def load_yaml_text(text: str, path: Path) -> dict[str, Any]:
    import yaml

    value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"{path} frontmatter 必须是映射")
    return value


def preset_digest(metadata: dict[str, Any], body: str) -> str:
    excluded = {"status", "approval_id", "preset_digest"}
    approved_subject = {key: value for key, value in metadata.items() if key not in excluded}
    return canonical_digest({"metadata": approved_subject, "developer_instructions": body})


def load_approvals(project_root: Path) -> dict[str, dict[str, Any]]:
    approvals: dict[str, dict[str, Any]] = {}
    directory = project_root / "game-pipeline" / "approvals"
    if not directory.is_dir():
        return approvals
    for path in sorted(directory.glob("*.yaml")):
        try:
            document = load_yaml(path)
        except (OSError, ValueError):
            continue
        approval = document.get("approval")
        if isinstance(approval, dict) and isinstance(approval.get("approval_id"), str):
            approvals[approval["approval_id"]] = approval
    return approvals


def load_bindings(project_root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    path = project_root / "game-pipeline" / "bindings" / "skill-bindings.yaml"
    try:
        document = load_yaml(path)
    except (OSError, ValueError) as exc:
        return {}, [str(exc)]
    root = document.get("skill_bindings")
    if not isinstance(root, dict):
        return {}, ["skill-bindings.yaml 缺少 skill_bindings 映射"]
    if root.get("schema_version") != SKILL_BINDINGS_SCHEMA:
        errors.append(f"不支持的 Skill Binding schema: {root.get('schema_version')}")
    entries = root.get("bindings")
    if not isinstance(entries, list):
        return {}, errors + ["skill_bindings.bindings 必须是数组"]
    bindings: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("preset_id"), str):
            errors.append(f"bindings[{index}] 缺少 preset_id")
            continue
        preset_id = entry["preset_id"]
        if preset_id in bindings:
            errors.append(f"重复 Skill Binding: {preset_id}")
        bindings[preset_id] = entry
    return bindings, errors


def validate_skill_binding(
    entry: dict[str, Any],
    metadata: dict[str, Any],
    computed_digest: str,
    project_root: Path,
    source_root: Path,
) -> list[str]:
    errors: list[str] = []
    if entry.get("preset_digest") != computed_digest:
        errors.append("Skill Binding 的 preset_digest 不匹配")
    if entry.get("approval_id") != metadata.get("approval_id"):
        errors.append("Skill Binding 的 approval_id 不匹配")
    skills = entry.get("skills")
    if not isinstance(skills, list):
        return errors + ["Skill Binding.skills 必须是数组"]
    bound_ids: list[str] = []
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            errors.append(f"Skill Binding.skills[{index}] 必须是映射")
            continue
        skill_id = skill.get("skill_id")
        source = skill.get("source")
        relative_path = skill.get("path")
        expected_digest = skill.get("digest")
        if not all(isinstance(value, str) and value for value in (skill_id, source, relative_path, expected_digest)):
            errors.append(f"Skill Binding.skills[{index}] 字段不完整")
            continue
        bound_ids.append(skill_id)
        if source not in {"plugin", "project"}:
            errors.append(f"Skill {skill_id} source 必须为 plugin 或 project")
            continue
        base = source_root if source == "plugin" else project_root
        try:
            path = ensure_within(base, base / relative_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.exists():
            errors.append(f"Skill {skill_id} 路径不存在: {relative_path}")
            continue
        actual_digest = directory_digest(path) if path.is_dir() else file_digest(path)
        if actual_digest != expected_digest:
            errors.append(f"Skill {skill_id} 摘要不匹配")
    declared = metadata.get("skills")
    if not isinstance(declared, list) or any(not isinstance(item, str) for item in declared):
        errors.append("Agent Preset.skills 必须是字符串数组")
    elif set(declared) != set(bound_ids):
        errors.append("Agent Preset.skills 与批准的 Skill Binding 不一致")
    return errors


def validate_approval(approval: dict[str, Any] | None, metadata: dict[str, Any], digest: str) -> list[str]:
    if approval is None:
        return ["找不到 Agent Preset 的人工审批记录"]
    errors: list[str] = []
    expected = {
        "schema_version": APPROVAL_SCHEMA,
        "subject_kind": "agent-preset",
        "subject_id": metadata.get("preset_id"),
        "subject_digest": digest,
        "decision": "approved",
    }
    for key, value in expected.items():
        if approval.get(key) != value:
            errors.append(f"审批记录 {key} 不匹配")
    for key in ("decided_by", "decided_at"):
        if not isinstance(approval.get(key), str) or not approval.get(key):
            errors.append(f"审批记录缺少 {key}")
    return errors


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_adapter(metadata: dict[str, Any], body: str, source_path: str, digest: str, version: str) -> str:
    if '"""' in body:
        raise ValueError("developer instructions 不能包含 TOML 三引号")
    skills = "\n".join(f"- `{skill}`" for skill in metadata["skills"]) or "- 无"
    instructions = (
        body.rstrip()
        + "\n\n## Approved Runtime Binding\n\n"
        + f"Source preset: `{source_path}`\nPreset digest: `{digest}`\nApproved skills:\n{skills}\n\n"
        + "Only act inside this approved responsibility and authority boundary. "
        + "Before spawning or starting another Agent Instance, validate its approved Position or Temporary Grant and register it in the project Registry.\n"
    )
    sandbox_mode = metadata.get("sandbox_mode", "workspace-write")
    return (
        f"# {MANAGED_MARKER}\n"
        f"# source-preset: {source_path}\n"
        f"# preset-digest: {digest}\n"
        f"# generator-version: {version}\n"
        f"name = {toml_string(metadata['name'])}\n"
        f"description = {toml_string(metadata['description'])}\n"
        f"sandbox_mode = {toml_string(sandbox_mode)}\n"
        f'developer_instructions = """\n{instructions}"""\n'
    )


def validate_metadata(metadata: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "preset_id",
        "slug",
        "name",
        "description",
        "version",
        "status",
        "preset_digest",
        "approval_id",
        "skills",
        "sandbox_mode",
    }
    missing = sorted(required - set(metadata))
    if missing:
        errors.append(f"{path.name} 缺少字段: {', '.join(missing)}")
        return errors
    if metadata.get("schema_version") != AGENT_PRESET_SCHEMA:
        errors.append(f"{path.name} schema_version 非法")
    if not isinstance(metadata.get("preset_id"), str) or not PRESET_ID_RE.fullmatch(metadata["preset_id"]):
        errors.append(f"{path.name} preset_id 非法")
    if not isinstance(metadata.get("slug"), str) or not SLUG_RE.fullmatch(metadata["slug"]):
        errors.append(f"{path.name} slug 非法")
    if not isinstance(metadata.get("version"), str) or not VERSION_RE.fullmatch(metadata["version"]):
        errors.append(f"{path.name} version 非法")
    if metadata.get("status") not in {"pending", "approved", "retired"}:
        errors.append(f"{path.name} status 非法")
    if metadata.get("sandbox_mode") not in {"read-only", "workspace-write", "danger-full-access"}:
        errors.append(f"{path.name} sandbox_mode 非法")
    for key in ("name", "description"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            errors.append(f"{path.name} {key} 必须是非空字符串")
    return errors


def build_generation_plan(project_root: Path, source_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    project_root = project_root.resolve()
    source_root = source_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    lock = evaluate_lock(project_root, source_root)
    if lock["state"] != "normal":
        errors.append(f"plugin lock 状态为 {lock['state']}，禁止生成 Agent 适配器")
    bindings, binding_errors = load_bindings(project_root)
    errors.extend(binding_errors)
    approvals = load_approvals(project_root)
    desired: dict[str, str] = {}
    presets: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    preset_dir = project_root / "game-pipeline" / "agents"
    for path in sorted(preset_dir.glob("*.md")) if preset_dir.is_dir() else []:
        if path.name.lower() == "readme.md":
            continue
        try:
            metadata, body = parse_preset(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        item_errors = validate_metadata(metadata, path)
        if item_errors:
            errors.extend(item_errors)
            continue
        digest = preset_digest(metadata, body)
        status = metadata["status"]
        item = {
            "path": path.relative_to(project_root).as_posix(),
            "preset_id": metadata["preset_id"],
            "status": status,
            "preset_digest": digest,
        }
        presets.append(item)
        if status != "approved":
            if metadata.get("preset_digest") not in {None, digest}:
                warnings.append(f"{path.name} 草案摘要已变化；当前计算值为 {digest}")
            warnings.append(f"跳过未批准 Preset: {metadata['preset_id']} ({status})，当前摘要 {digest}")
            continue
        if metadata.get("preset_digest") != digest:
            errors.append(f"{path.name} preset_digest 不匹配")
        slug = metadata["slug"]
        if slug in seen_slugs:
            errors.append(f"生成文件 slug 冲突: {slug}")
            continue
        seen_slugs.add(slug)
        approval = approvals.get(metadata["approval_id"])
        errors.extend(f"{path.name}: {message}" for message in validate_approval(approval, metadata, digest))
        binding_entry = bindings.get(metadata["preset_id"])
        if binding_entry is None:
            errors.append(f"{path.name}: 缺少批准的 Skill Binding")
        else:
            errors.extend(
                f"{path.name}: {message}"
                for message in validate_skill_binding(binding_entry, metadata, digest, project_root, source_root)
            )
        try:
            content = render_adapter(
                metadata,
                body,
                path.relative_to(project_root).as_posix(),
                digest,
                manifest_version(source_root),
            )
        except ValueError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        desired[f".codex/agents/{slug}.toml"] = content

    actions: list[dict[str, str]] = []
    for relative_path, content in sorted(desired.items()):
        target = ensure_within(project_root, project_root / relative_path)
        if not target.exists():
            action = "create"
        else:
            existing = target.read_text(encoding="utf-8-sig")
            if existing == content:
                action = "unchanged"
            elif existing.startswith(f"# {MANAGED_MARKER}\n"):
                action = "update_managed"
            else:
                action = "conflict"
                errors.append(f"拒绝覆盖非托管 Codex Agent: {relative_path}")
        actions.append({"path": relative_path, "action": action, "sha256": text_digest(content)})
    subject = {
        "schema_version": "game-production-agent-generation-plan/v1",
        "project_root": str(project_root),
        "plugin_version": manifest_version(source_root),
        "presets": presets,
        "actions": actions,
    }
    plan = {
        **subject,
        "plan_digest": canonical_digest(subject),
        "errors": errors,
        "warnings": warnings,
        "can_apply": not errors,
    }
    return plan, desired


def atomic_replace(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.game-pipeline.tmp")
    if temp.exists():
        raise FileExistsError(f"临时文件已存在: {temp}")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def apply_generation(plan: dict[str, Any], desired: dict[str, str], project_root: Path) -> list[str]:
    if not plan["can_apply"]:
        raise ValueError("生成计划存在错误")
    # Validate every target before the first write.
    for action in plan["actions"]:
        if action["action"] == "unchanged":
            continue
        if action["action"] == "conflict":
            raise ValueError(f"存在冲突: {action['path']}")
        target = ensure_within(project_root, project_root / action["path"])
        if action["action"] == "create" and target.exists():
            raise ValueError(f"计划后目标已存在: {action['path']}")
        if action["action"] == "update_managed":
            existing = target.read_text(encoding="utf-8-sig") if target.exists() else ""
            if not existing.startswith(f"# {MANAGED_MARKER}\n"):
                raise ValueError(f"计划后目标失去托管标记: {action['path']}")

    changed: list[str] = []
    for action in plan["actions"]:
        if action["action"] == "unchanged":
            continue
        target = ensure_within(project_root, project_root / action["path"])
        if action["action"] == "create":
            write_new_text(target, desired[action["path"]])
        else:
            atomic_replace(target, desired[action["path"]])
        changed.append(action["path"])
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.apply and args.check:
        parser.error("--apply 与 --check 不能同时使用")
    plan, desired = build_generation_plan(args.project_root, args.plugin_root)
    if args.check and plan["can_apply"]:
        stale = [item for item in plan["actions"] if item["action"] != "unchanged"]
        if stale:
            plan["errors"].append("Codex Agent 适配器缺失或过期")
            plan["can_apply"] = False
    if args.apply:
        try:
            plan["changed"] = apply_generation(plan, desired, args.project_root.resolve())
            plan["mode"] = "applied"
        except (OSError, ValueError) as exc:
            plan["errors"].append(str(exc))
            plan["can_apply"] = False
    else:
        plan["mode"] = "check" if args.check else "plan"
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan["can_apply"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
