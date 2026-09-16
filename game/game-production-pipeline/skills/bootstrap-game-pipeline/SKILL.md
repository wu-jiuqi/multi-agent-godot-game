---
name: bootstrap-game-pipeline
description: Initialize the game-production-pipeline plugin inside a target game repository. Use when a user asks to install, bootstrap, instantiate, migrate, or verify the project-level multi-agent workspace and plugin version lock.
---

# Bootstrap Game Pipeline

Create the project-owned control plane without inventing project direction or silently changing existing files.

## Workflow

1. Read the target repository's `AGENTS.md`, Git status, engine metadata, and existing `.agents/`, `.codex/`, and `game-pipeline/` directories. Preserve unrelated work.
2. Resolve the plugin root as two directories above this `SKILL.md`. Treat that plugin directory as read-only source material; project facts belong in the target repository.
3. Collect only verifiable bootstrap facts: project ID, display name, engine, repository root, and requested plugin version. Ask for any direction-changing value that cannot be discovered.
4. If no plugin lock exists, run `../../scripts/bootstrap_game_pipeline.py` without `--apply`. Present the complete file-impact plan, conflicts, and `approval_digest` to the user.
5. If a plugin lock exists but does not match the installed plugin, run `../../scripts/migrate_plugin.py` without `--apply`. Present all actions, plugin Skill digest changes, Skill Binding approval details, Agent Adapter actions, conflicts, and `plan_digest`.
6. Do not apply bootstrap until the user explicitly confirms its exact digest. Do not apply migration until the user explicitly confirms the exact `plan_digest`; when `skill_binding_approval.required` is true, also require a separate explicit confirmation of its exact `subject_digest`. Never infer one approval from the other.
7. Apply with the matching bootstrap arguments, or migrate with `--approval-digest <plan_digest> --approved-by <human>` plus `--binding-approval-digest <subject_digest> --binding-approved-by <human>` when required.
8. Run `../../scripts/validate_project_instance.py --project-root <root>` and report every warning or blocker. Migration must also return `idempotent_outcome=no_change`.

The initialized control plane must include `game-pipeline/assets/{contracts,budgets,evidence,rights,protected-path-snapshots}/` and `game-pipeline/loops/{contracts,registry}/` README baselines. Do not place the placeholder Asset Contract template in the scanned contracts directory; copy it only when a real asset demand exists and replace every placeholder with project facts.

## Boundaries

- Initialization may create an empty organization baseline, a blocked project-brief draft, and an initial pending Change Set. It must not activate departments, positions, project Agent Presets, or runtime agents.
- Never overwrite an unmanaged file. Managed blocks may only be updated by their marker and matching digest.
- Keep `game-pipeline/` tracked by the target repository. Ignore only `.runtime/`, `.cache/`, `tmp/`, raw temporary evidence, and generated SVG views.
- Treat plugin governance approval and Codex filesystem/sandbox permission as separate checks; neither substitutes for the other.
- A version mismatch fails closed. Use migration planning rather than editing `plugin-lock.yaml` by hand.
- Plugin Skill digests, the independently approved Skill Binding subject, managed `.codex/agents/*.toml`, migration approvals, managed blocks, and the plugin lock form one migration transaction. Any postcondition failure must restore all of them from the byte backup.

## Outputs

Return the project path, installed plugin identity/version, lock validation result, created or unchanged files, asset/loop control-plane paths, pending human decisions, and the next recommended skill. For first-time setup, route to `$prepare-game-project-brief`; the director and owner co-design the launch packet; a draft brief may support provisional organization design, while applying staffing requires a confirmed staffing-ready brief.
