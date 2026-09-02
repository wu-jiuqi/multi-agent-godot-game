---
name: adapt-godot-production
description: Adapt approved game-production tasks and artifacts to a Godot project. Use when contracts, content, UI, gameplay, tests, or evidence must be mapped into Godot scenes, resources, nodes, imports, and builds.
---

# Adapt Godot Production

Bridge the engine-agnostic production contract to Godot without changing the approved game design or bypassing its gates.

## Workflow

1. Read the target project's `AGENTS.md`, `project.godot`, engine version, renderer, language choice, addons, test setup, and Git status.
2. Validate the project instance and bound work contract. Read `../../adapters/godot.md` and `../../agents/godot-implementer.md`.
3. Map each contract artifact to a concrete Godot path and type: packed scene, resource, imported asset, script, test, editor tool, build, or capture. Record the mapping before implementation.
4. Prefer editor-authored scenes and preconfigured nodes/resources. Generate nodes dynamically only when runtime behavior requires it or the generated approach is demonstrably safer and simpler.
5. Use the narrowest relevant installed Godot Skill for implementation, testing, UI, assets, animation, or export. Keep this Skill responsible for production mapping and evidence, not for duplicating engine-specific expertise.
6. Preserve project conventions and unrelated changes. Never edit `.godot/` imported cache as source, silently change engine settings, or replace user assets without an approved task.
7. Verify with the appropriate combination of parser/import checks, automated tests, editor execution, playable build, screenshots, profiler data, and manual play evidence required by the contract.
8. Return produced artifacts and evidence to the owning production loop. Route qualitative milestones through `$review-game-gates`.

For a Specialist Asset Loop, preserve the Contract's `asset_id + revision + file digest + subject digest` in the handoff, commit required `.import` sidecars, treat `.godot/imported/` only as cache, and provide actual target-scene profiler evidence before A2. Run `validate_specialist_asset_loop.py` before returning the Registry snapshot. Do not edit UI protected paths; an asset-driven UI change is a separate upstream workflow.

For an Art Direction Loop, map the approved benchmark to editor-authored `.tscn` scenes and `.tres` resources where practical. Use the real renderer/import path and target camera; include representative 2D/3D/VFX/motion/UI domains declared by the Contract. Shared UI visual tokens belong in a Theme resource, but existing UI scene hierarchy, responsive behavior, focus, and interaction remain read-only until a UI workflow authorizes them. Record build, platform, scenario, profiler/capture evidence, five stage digests, and D3/D4 results in the handoff.

## Failure Routing

- Missing or contradictory game-design input returns to the design owner.
- Engine/API uncertainty returns to technical validation before implementation.
- Import, scene, or build failures return to the responsible implementation position with reproducible logs.
- Changes outside delegated scope stop for escalation rather than being inferred.

Return Godot version, artifact mapping, modified files, validation evidence, remaining manual checks, and the next gate.
