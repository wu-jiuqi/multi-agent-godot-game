---
name: design-game-organization
description: Design and visualize a project-specific game-production organization. Use when a project needs departments, positions, Agent Presets, skill bindings, staffing changes, or an auditable organization proposal.
---

# Design Game Organization

Translate project needs into a visible staffing proposal while keeping every persistent organization change behind human approval.

## Required Context

Validate the project instance first. Read the project facts and then these shared contracts only as needed:

- `../../architecture.md`
- `../../agents/project-agent-architect.md`
- `../../agents/department-manager.md`
- `../../contracts/organization-identity.md`
- `../../contracts/organization-registry.md`
- `../../contracts/authority-delegation.md`

## Workflow

1. Separate verified project facts from assumptions and design choices. Do not place genre, story, visual style, mechanics, or acceptance thresholds into the global plugin.
2. Map required responsibilities before naming agents. Prefer the smallest viable organization; a department manager may cover multiple functions until workload or risk justifies specialization.
3. Propose persistent changes as a project-owned Organization Change Set. Include stable IDs, responsibilities, authority boundaries, required Skills, acceptance ownership, cost, risks, rollback, and affected loops.
4. Create or revise project Agent Presets under `game-pipeline/agents/` only as proposal artifacts. Keep them `pending`; do not generate `.codex/agents/*.toml` yet.
5. Validate the proposal with `../../scripts/validate_organization_registry.py` and render the current and proposed views with `../../scripts/render_organization.py`.
6. Show the user the organization diagram, affected departments, new or removed positions, authority changes, and approval digest. Stop for explicit human approval.
7. After an approval record exists and its subject digest still matches, apply the Change Set, update bindings/history/snapshot, and generate approved Codex adapters with `../../scripts/generate_codex_agents.py`.

## Approval Rule

Creating, removing, merging, splitting, or materially changing any persistent department, position, Agent Preset, or Skill binding requires human approval. Runtime Agent Instances do not require individual approval only when an approved position and unexpired Temporary Grant explicitly authorize their type, quota, scope, and lifetime; each instance must still be registered and visible.

Return the diagram location, Change Set ID and digest, validation result, unresolved choices, and whether work is waiting for human approval.
