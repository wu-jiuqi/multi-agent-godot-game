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
4. Run `../../scripts/bootstrap_game_pipeline.py` without `--apply`. Present the complete file-impact plan, conflicts, and `approval_digest` to the user.
5. Do not apply until the user explicitly confirms that exact digest. Then rerun with `--apply --approval-digest <digest>`.
6. Run `../../scripts/validate_project_instance.py --project-root <root>` and report every warning or blocker.

The initialized control plane must include `game-pipeline/assets/{contracts,budgets,evidence,rights,protected-path-snapshots}/` and `game-pipeline/loops/{contracts,registry}/` README baselines. Do not place the placeholder Asset Contract template in the scanned contracts directory; copy it only when a real asset demand exists and replace every placeholder with project facts.

## Boundaries

- Initialization may create an empty organization baseline, a blocked project-brief draft, and an initial pending Change Set. It must not activate departments, positions, project Agent Presets, or runtime agents.
- Never overwrite an unmanaged file. Managed blocks may only be updated by their marker and matching digest.
- Keep `game-pipeline/` tracked by the target repository. Ignore only `.runtime/`, `.cache/`, `tmp/`, raw temporary evidence, and generated SVG views.
- Treat plugin governance approval and Codex filesystem/sandbox permission as separate checks; neither substitutes for the other.
- A version mismatch fails closed. Use migration planning rather than editing `plugin-lock.yaml` by hand.

## Outputs

Return the project path, installed plugin identity/version, lock validation result, created or unchanged files, asset/loop control-plane paths, pending human decisions, and the next recommended skill. For first-time setup, route to `$prepare-game-project-brief`; only a confirmed staffing-ready brief may continue to `$design-game-organization`.
