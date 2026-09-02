#!/usr/bin/env python3
"""Apply or roll back an approved game-production-pipeline migration plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from pipeline_common import APPROVAL_SCHEMA, dump_yaml, ensure_within, plugin_root
from plan_plugin_migration import prepare_migration
from validate_plugin_lock import evaluate_lock
from validate_project_instance import validate_instance


DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_replace_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.game-pipeline-migration.tmp")
    if temp_path.exists():
        raise FileExistsError(f"迁移临时文件已存在，拒绝覆盖: {temp_path}")
    try:
        with temp_path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def write_new_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def write_json(path: Path, value: dict[str, Any], *, replace: bool) -> None:
    content = (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if replace:
        atomic_replace_bytes(path, content)
    else:
        write_new_bytes(path, content)


def approval_content(plan: dict[str, Any], approved_by: str) -> bytes:
    if not approved_by.strip():
        raise ValueError("approved_by 不能为空")
    document = {
        "approval": {
            "schema_version": APPROVAL_SCHEMA,
            "approval_id": f"approval:{plan['project_id']}:migration:{plan['plan_digest'][:12]}",
            "subject_kind": "plugin-migration-plan",
            "subject_id": f"{plan['from_version']}->{plan['to_version']}",
            "subject_digest": plan["plan_digest"],
            "decision": "approved",
            "decided_by": approved_by,
            "decided_at": plan["migration_at"],
            "evidence": {
                "migrator": plan["migrator"],
                "from_framework_digest": plan["from_framework_digest"],
                "to_framework_digest": plan["to_framework_digest"],
            },
        }
    }
    return dump_yaml(document).encode("utf-8")


def binding_approval_content(
    plan: dict[str, Any],
    approval_digest: str | None,
    approved_by: str | None,
) -> tuple[str, bytes] | None:
    binding = plan.get("skill_binding_approval")
    if not isinstance(binding, dict) or not binding.get("required"):
        return None
    expected_digest = binding.get("subject_digest")
    if approval_digest != expected_digest:
        raise ValueError(
            "binding_approval_digest 与 Skill Binding 新摘要不匹配；必须独立查看并确认"
        )
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("binding_approved_by 不能为空")
    record_path = binding.get("approval_record")
    if not isinstance(record_path, str) or not record_path:
        raise ValueError("迁移计划缺少 Skill Binding 审批记录路径")
    document = {
        "approval": {
            "schema_version": APPROVAL_SCHEMA,
            "approval_id": binding["approval_id"],
            "subject_kind": "skill-binding",
            "subject_id": binding["subject_id"],
            "subject_digest": expected_digest,
            "decision": "approved",
            "decided_by": approved_by,
            "decided_at": plan["migration_at"],
            "evidence": {
                "migration_plan": f"sha256:{plan['plan_digest']}",
                "plugin_version": plan["to_version"],
                "framework_digest": plan["to_framework_digest"],
            },
        }
    }
    return record_path, dump_yaml(document).encode("utf-8")


def backup_directory(project_root: Path, plan_digest: str) -> Path:
    if not DIGEST_RE.fullmatch(plan_digest):
        raise ValueError("plan_digest 必须是 64 位小写 SHA-256")
    return ensure_within(
        project_root,
        project_root / "game-pipeline" / ".cache" / "migrations" / plan_digest,
    )


def preflight_actions(project_root: Path, plan: dict[str, Any], desired: dict[str, str]) -> None:
    if not plan.get("can_apply"):
        raise ValueError("迁移计划包含阻断项，不能应用")
    for action in plan.get("actions", []):
        relative_path = action["path"]
        if relative_path not in desired:
            raise ValueError(f"迁移器没有提供计划内容: {relative_path}")
        target = ensure_within(project_root, project_root / relative_path)
        current_digest = sha256(target.read_bytes()) if target.is_file() else None
        if current_digest != action.get("before_sha256"):
            raise ValueError(f"计划后文件发生变化: {relative_path}")
        desired_digest = sha256(desired[relative_path].encode("utf-8"))
        if desired_digest != action.get("after_sha256"):
            raise ValueError(f"迁移器输出与计划摘要不一致: {relative_path}")


def create_backup(
    project_root: Path,
    plan: dict[str, Any],
    approval_files: dict[str, bytes],
) -> tuple[Path, dict[str, Any]]:
    root = backup_directory(project_root, plan["plan_digest"])
    if root.exists():
        raise FileExistsError(f"迁移备份已存在，拒绝复用: {root}")

    targets = [dict(action) for action in plan["actions"]]
    for approval_path, approval_bytes in approval_files.items():
        approval_target = ensure_within(project_root, project_root / approval_path)
        if approval_target.exists():
            raise FileExistsError(f"迁移审批记录已存在，拒绝覆盖: {approval_path}")
        targets.append(
            {
                "path": approval_path,
                "action": "create",
                "before_sha256": None,
                "after_sha256": sha256(approval_bytes),
            }
        )

    created_parent_dirs: set[str] = set()
    for target_info in targets:
        parent = (project_root / target_info["path"]).parent
        while parent != project_root and not parent.exists():
            created_parent_dirs.add(parent.relative_to(project_root).as_posix())
            parent = parent.parent

    root.mkdir(parents=True, exist_ok=False)
    files_root = root / "files"
    records: list[dict[str, Any]] = []
    for target_info in targets:
        relative_path = target_info["path"]
        target = ensure_within(project_root, project_root / relative_path)
        record = dict(target_info)
        if target.is_file():
            backup_file = ensure_within(root, files_root / relative_path)
            write_new_bytes(backup_file, target.read_bytes())
            record["backup_file"] = backup_file.relative_to(root).as_posix()
        else:
            record["backup_file"] = None
        records.append(record)

    manifest = {
        "schema_version": "game-production-plugin-migration-backup/v1",
        "status": "backed_up",
        "project_root": str(project_root),
        "plan_digest": plan["plan_digest"],
        "from_version": plan["from_version"],
        "to_version": plan["to_version"],
        "migration_at": plan["migration_at"],
        "migrator": plan["migrator"],
        "created_parent_dirs": sorted(created_parent_dirs),
        "targets": records,
    }
    write_json(root / "manifest.json", manifest, replace=False)
    return root, manifest


def restore_backup(root: Path, manifest: dict[str, Any], *, force: bool, status: str) -> dict[str, Any]:
    project_root = Path(manifest["project_root"]).resolve()
    targets = list(manifest.get("targets", []))
    if not force:
        for record in targets:
            target = ensure_within(project_root, project_root / record["path"])
            current_digest = sha256(target.read_bytes()) if target.is_file() else None
            if current_digest != record.get("after_sha256"):
                raise ValueError(f"迁移后文件已变化，拒绝覆盖回退: {record['path']}")

    # Restore the lock last so the final visible state always matches the restored project files.
    targets.sort(key=lambda item: item["path"] == "game-pipeline/plugin-lock.yaml")
    restored: list[str] = []
    removed: list[str] = []
    for record in targets:
        target = ensure_within(project_root, project_root / record["path"])
        backup_file = record.get("backup_file")
        if backup_file is None:
            if target.exists():
                target.unlink()
                removed.append(record["path"])
        else:
            source = ensure_within(root, root / backup_file)
            if not source.is_file():
                raise FileNotFoundError(f"迁移备份缺少文件: {backup_file}")
            atomic_replace_bytes(target, source.read_bytes())
            restored.append(record["path"])

    for relative_dir in sorted(manifest.get("created_parent_dirs", []), key=lambda value: value.count("/"), reverse=True):
        directory = ensure_within(project_root, project_root / relative_dir)
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()

    manifest = {
        **manifest,
        "status": status,
        "rollback": {"restored": sorted(restored), "removed": sorted(removed)},
    }
    write_json(root / "manifest.json", manifest, replace=True)
    return manifest


def apply_migration(
    project_root: Path,
    source_root: Path,
    migration_at: str,
    approval_digest: str,
    approved_by: str,
    binding_approval_digest: str | None = None,
    binding_approved_by: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    source_root = source_root.resolve()
    plan, desired = prepare_migration(project_root, source_root, migration_at)
    if approval_digest != plan["plan_digest"]:
        raise ValueError("approval_digest 与当前迁移计划不匹配；必须重新查看并确认")
    preflight_actions(project_root, plan, desired)
    approval_bytes = approval_content(plan, approved_by)
    approval_files = {plan["approval_record"]: approval_bytes}
    binding_approval = binding_approval_content(
        plan, binding_approval_digest, binding_approved_by
    )
    if binding_approval is not None:
        binding_path, binding_bytes = binding_approval
        if binding_path in approval_files:
            raise ValueError("Skill Binding 与迁移审批记录路径冲突")
        approval_files[binding_path] = binding_bytes
    backup_root, backup_manifest = create_backup(project_root, plan, approval_files)

    applied: list[str] = []
    unchanged: list[str] = []
    try:
        actions = list(plan["actions"])
        lock_actions = [item for item in actions if item["path"] == "game-pipeline/plugin-lock.yaml"]
        if len(lock_actions) != 1:
            raise ValueError("迁移计划必须且只能包含一个 plugin lock 动作")

        def apply_action(action: dict[str, Any]) -> None:
            relative_path = action["path"]
            target = ensure_within(project_root, project_root / relative_path)
            content = desired[relative_path].encode("utf-8")
            if action["action"] == "unchanged":
                unchanged.append(relative_path)
            elif action["action"] == "create":
                write_new_bytes(target, content)
                applied.append(relative_path)
            elif action["action"] == "update":
                atomic_replace_bytes(target, content)
                applied.append(relative_path)
            else:
                raise ValueError(f"不支持的迁移动作: {action['action']}")

        for action in actions:
            if action["path"] != "game-pipeline/plugin-lock.yaml":
                apply_action(action)

        # Approvals are written before the lock; the lock remains the final migration commit point.
        for approval_path, content in approval_files.items():
            approval_target = ensure_within(project_root, project_root / approval_path)
            write_new_bytes(approval_target, content)
            applied.append(approval_path)
        apply_action(lock_actions[0])

        lock_result = evaluate_lock(project_root, source_root)
        if lock_result["state"] != "normal":
            raise ValueError(f"迁移后 plugin lock 校验失败: {lock_result}")
        instance_result = validate_instance(project_root, source_root)
        if instance_result["state"] != "normal":
            raise ValueError(f"迁移后项目实例校验失败: {instance_result}")
        history_digests = plan.get("history_digests_before", {})
        if isinstance(history_digests, dict):
            for relative_path, expected_digest in history_digests.items():
                history_path = ensure_within(project_root, project_root / relative_path)
                actual_digest = sha256(history_path.read_bytes()) if history_path.is_file() else None
                if actual_digest != expected_digest:
                    raise ValueError(f"迁移不得改写 Event History: {relative_path}")
        idempotent_plan, _ = prepare_migration(project_root, source_root, migration_at)
        if idempotent_plan["outcome"] != "no_change":
            raise ValueError(f"迁移后重复规划不是 no_change: {idempotent_plan['outcome']}")

        backup_manifest = {
            **backup_manifest,
            "status": "applied",
            "result": {
                "applied": applied,
                "unchanged": unchanged,
                "plugin_lock_state": lock_result["state"],
                "project_state": instance_result["state"],
                "idempotent_outcome": idempotent_plan["outcome"],
            },
        }
        write_json(backup_root / "manifest.json", backup_manifest, replace=True)
    except Exception as exc:
        try:
            restore_backup(backup_root, backup_manifest, force=True, status="auto_rolled_back")
        except Exception as rollback_exc:
            raise RuntimeError(f"迁移失败且自动回退失败: {exc}; rollback: {rollback_exc}") from rollback_exc
        raise RuntimeError(f"迁移失败，已自动回退: {exc}") from exc

    return {
        **plan,
        "mode": "applied",
        "applied": applied,
        "unchanged": unchanged,
        "backup": str(backup_root),
        "plugin_lock_state": "normal",
        "project_state": "normal",
        "idempotent_outcome": "no_change",
    }


def rollback_migration(project_root: Path, plan_digest: str, confirm_digest: str) -> dict[str, Any]:
    project_root = project_root.resolve()
    if plan_digest != confirm_digest:
        raise ValueError("confirm_rollback 必须与 plan_digest 完全一致")
    root = backup_directory(project_root, plan_digest)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"找不到迁移备份: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "game-production-plugin-migration-backup/v1":
        raise ValueError("不支持的迁移备份 schema")
    if manifest.get("plan_digest") != plan_digest:
        raise ValueError("迁移备份 plan_digest 不匹配")
    if Path(manifest.get("project_root", "")).resolve() != project_root:
        raise ValueError("迁移备份不属于当前项目")
    if manifest.get("status") != "applied":
        raise ValueError(f"只有 applied 备份可以手工回退，当前为 {manifest.get('status')}")
    restored_manifest = restore_backup(root, manifest, force=False, status="rolled_back")
    lock_result = evaluate_lock(project_root, plugin_root())
    return {
        "mode": "rolled_back",
        "project_root": str(project_root),
        "plan_digest": plan_digest,
        "backup": str(root),
        "restored": restored_manifest["rollback"]["restored"],
        "removed": restored_manifest["rollback"]["removed"],
        "plugin_lock_state": lock_result["state"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, default=plugin_root())
    parser.add_argument("--migration-at", help="Apply 必须复用 dry-run 输出中的 migration_at")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-digest")
    parser.add_argument("--approved-by")
    parser.add_argument("--binding-approval-digest")
    parser.add_argument("--binding-approved-by")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--plan-digest")
    parser.add_argument("--confirm-rollback")
    args = parser.parse_args()

    try:
        if args.rollback:
            if args.apply:
                parser.error("--apply 与 --rollback 不能同时使用")
            if not args.plan_digest or not args.confirm_rollback:
                parser.error("--rollback 必须提供 --plan-digest 与 --confirm-rollback")
            result = rollback_migration(args.project_root, args.plan_digest, args.confirm_rollback)
        elif args.apply:
            if not args.migration_at or not args.approval_digest or not args.approved_by:
                parser.error("--apply 必须提供 --migration-at、--approval-digest 与 --approved-by")
            result = apply_migration(
                args.project_root,
                args.plugin_root,
                args.migration_at,
                args.approval_digest,
                args.approved_by,
                args.binding_approval_digest,
                args.binding_approved_by,
            )
        else:
            result, _ = prepare_migration(args.project_root, args.plugin_root, args.migration_at)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"mode": "blocked", "error": str(exc)}, ensure_ascii=True, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=True, indent=2))
    if result.get("mode") in {"applied", "rolled_back"}:
        return 0
    return 0 if result.get("outcome") in {"no_change", "migration_ready"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
