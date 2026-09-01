---
name: operate-game-production-loop
description: Execute an approved game-production loop with authorized Codex agents. Use when a user asks to start, resume, coordinate, interrupt, recover, or inspect multi-agent production work in an initialized project.
---

# Operate Game Production Loop

Run dynamic multi-agent work through explicit contracts, Registry state, delegated authority, and evidence-backed handoffs.

## Preflight

1. Run `../../scripts/validate_project_instance.py --project-root <root>` and stop on a blocked plugin lock, stale generated Agent adapter, invalid Registry, or missing required input.
2. Read `../../agents/pipeline-director.md`, `../../agents/department-manager.md`, `../../contracts/authority-delegation.md`, and the selected Pipeline/Loop Contract.
3. Confirm the requested work is inside an approved position's responsibility and authority. A Codex tool permission does not create organization authority.
4. If `loop_type` is `specialist-asset-production` or a deliverable has `artifact_type: specialist-asset-contract`, require `asset_contract_policy` and use `../../contracts/specialist-asset-production.loop-contract.yaml` as the minimum invariant set. Refuse an asset Loop that removes the A0/A2/A3 bindings or permits reverse writes into protected sources.

## Execution

1. Bind a concrete objective, inputs, outputs, acceptance checks, budget, owner, escalation route, and failure return path before dispatch.
2. Select only generated `.codex/agents/*.toml` whose source Agent Preset and Skill bindings remain approved and digest-matched.
3. Before starting each Agent Instance, append its Registry start event with position, parent, scope, grant, budget, and expected artifacts. Never create an invisible worker.
4. Let a lower level decide within delegated authority. Escalate only missing authority, cross-department conflicts, exhausted budgets, gate decisions, or direction-changing choices.
5. Validate each handoff and append status/artifact events. The receiver may reject incomplete work to the named return path.
6. On interruption, persist state and evidence before recovery. Resume only from a legal state-machine transition.
7. Close instances and the loop only after acceptance checks pass; do not reinterpret approval as completed production work.

## Specialist Asset Loops

For P6 professional asset work, run the read-only gate evaluator with the project root before each relevant transition:

- `draft → ready` and `ready → active`: `evaluate_specialist_asset_gate.py --gate A0`; register the exact Contract as `INPUT-ASSET-CONTRACT-A0`.
- `active → review`: `evaluate_specialist_asset_gate.py --gate A2`; register the current Contract as `DELIVERABLE-ASSET-CONTRACT-A3`, with lifecycle still allowed to be `review`.
- `review → completed`: `evaluate_specialist_asset_gate.py --gate A3`; reject completion unless the frozen revision and all required reviews match.

Every Registry artifact reference must contain `asset_id`, integer revision, `repo://` Contract URI, file SHA-256, and `contract_subject_digest`. Record the gate result through `core.acceptance_recorded` with `acceptance_kind: asset-gate`; never copy the asset body into Registry. Run `validate_specialist_asset_loop.py` before a state transition. A0/A1/A2/A3 failures route by `REQ/SRC/RGT/IMP/PERF/REG/SCOPE`; a requested UI change returns to a separate UI workflow instead of being written by the asset Loop.

## Human Gates

Route scope, core experience, greybox, content freeze, and release decisions through `$review-game-gates`. Automatic checks may recommend a result but cannot write the human decision.

Return current loop state, active and pending instances, artifacts, consumed budget, blocked reasons, escalations, next legal transitions, and any human decision required.
