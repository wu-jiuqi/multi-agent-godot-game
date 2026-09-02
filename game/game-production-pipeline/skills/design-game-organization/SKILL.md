---
name: design-game-organization
description: Design and visualize a project-specific game-production organization. Use when a project needs departments, positions, Agent Presets, skill bindings, staffing changes, or an auditable organization proposal.
---

# Design Game Organization

Translate project needs into a visible staffing proposal while keeping every persistent organization change behind human approval.

## Required Context

Validate the project instance first. Require `game-pipeline/project-definition/project-brief.yaml` to be `confirmed`, staffing-ready, digest-matched, and backed by a valid human approval record. Draft or blocked briefs return to `$prepare-game-project-brief`.

Read the confirmed project brief and then these shared contracts only as needed:

- `../../architecture.md`
- `../../agents/project-agent-architect.md`
- `../../agents/department-manager.md`
- `../../contracts/organization-identity.md`
- `../../contracts/organization-registry.md`
- `../../contracts/authority-delegation.md`

## Workflow

1. Preserve each brief statement's `confirmed`, `preference`, `hypothesis`, or `unknown` status. Do not reinterpret a preference or hypothesis as an approved project fact.
2. Map the brief's responsibility needs to complete coverage before naming agents. Prefer the smallest viable organization; a department manager may cover multiple functions until workload or risk justifies specialization.
   When sustained art direction, multi-domain style consistency, or visual acceptance is required, consider `../../agents/art-director.md`, `../../departments/art.md`, and `$direct-game-art`. Keep the Art Director optional and project-approved; do not instantiate the department merely because the templates exist.
3. Propose persistent changes as a project-owned Organization Change Set. Include stable IDs, responsibilities, authority boundaries, required Skills, acceptance ownership, cost, risks, rollback, and affected loops.
4. Create or revise project Agent Presets under `game-pipeline/agents/` only as proposal artifacts. Keep them `pending`; do not generate `.codex/agents/*.toml` yet.
5. Validate the proposal with `../../scripts/validate_organization_registry.py` and render the current and proposed views with `../../scripts/render_organization.py`.
6. Show the user the organization diagram, affected departments, new or removed positions, authority changes, and approval digest. Stop for explicit human approval.
7. After an approval record exists and its subject digest still matches, apply the Change Set, update bindings/history/snapshot, and generate approved Codex adapters with `../../scripts/generate_codex_agents.py`.

## Approval Rule

Creating, removing, merging, splitting, or materially changing any persistent department, position, Agent Preset, or Skill binding requires human approval. Runtime Agent Instances do not require individual approval only when an approved position and unexpired Temporary Grant explicitly authorize their type, quota, scope, and lifetime; each instance must still be registered and visible.

Return the diagram location, Change Set ID and digest, validation result, unresolved choices, and whether work is waiting for human approval.
