---
name: operate-game-production-loop
description: Execute an approved game-production loop with authorized Codex agents. Use when a user asks to start, resume, coordinate, interrupt, recover, or inspect multi-agent production work in an initialized project.
---

# Operate Game Production Loop

Run dynamic multi-agent work through explicit contracts, Registry state, delegated authority, and evidence-backed handoffs.

For `autonomous-after-approval`, read `references/autonomous-production.md` and the approved Production Charter first. Continue within the owner's launch authorization; ordinary implementation, self-check, bounded repair and delegated independent reviews do not require another owner decision. Stop for unresolved authority boundaries, direction changes, exhausted recovery/budgets or required external authorization.

## Preflight

1. Run `../../scripts/validate_project_instance.py --project-root <root>` and stop on a blocked plugin lock, stale generated Agent adapter, invalid Registry, or missing required input.
2. Read `../../agents/pipeline-director.md`, `../../agents/department-manager.md`, `../../contracts/authority-delegation.md`, and the selected Pipeline/Loop Contract.
3. Confirm the requested work is inside an approved position's responsibility and authority. A Codex tool permission does not create organization authority.
4. If `loop_type` is `specialist-asset-production` or a deliverable has `artifact_type: specialist-asset-contract`, require `asset_contract_policy` and use `../../contracts/specialist-asset-production.loop-contract.yaml` as the minimum invariant set. Refuse an asset Loop that removes the A0/A2/A3 bindings or permits reverse writes into protected sources.
5. If `loop_type` is `art-direction-production` or a deliverable has `artifact_type: art-direction-contract`, use `../../contracts/art-direction-production.loop-contract.yaml` as the minimum invariant set. Require a valid Art Director Position/authority, D2 human direction selection, D3 representative in-engine proof, and the UI structural boundary.

## Execution

1. Bind a concrete objective, inputs, outputs, acceptance checks, budget, owner, escalation route, and failure return path before dispatch.
   In autonomous mode, register a digest-bound Execution Plan, run `validate_production_run.py`, and use `record_execution_event.py --status` to dispatch only dependency/resource-ready tasks. Preserve immutable output snapshots and actual self-check/review evidence through retries.
2. Select only generated `.codex/agents/*.toml` whose source Agent Preset and Skill bindings remain approved and digest-matched.
3. Before starting each Agent Instance, append its Registry start event with position, parent, scope, grant, budget, and expected artifacts. Never create an invisible worker.
4. Let a lower level decide within delegated authority. Resolve ordinary failures through bounded repair and independent recheck. Route delegated gates internally; escalate missing authority, unresolved cross-department conflicts, exhausted budgets, reserved gate decisions or direction-changing choices in one exception package.
5. Validate each handoff and append status/artifact events. The receiver may reject incomplete work to the named return path.
6. On interruption, persist state and evidence before recovery. Resume only from a legal state-machine transition.
7. Close instances and the loop only after acceptance checks pass; do not reinterpret approval as completed production work.

## Specialist Asset Loops

For P6 professional asset work, run the read-only gate evaluator with the project root before each relevant transition:

- `draft → ready` and `ready → active`: `evaluate_specialist_asset_gate.py --gate A0`; register the exact Contract as `INPUT-ASSET-CONTRACT-A0`.
- `active → review`: `evaluate_specialist_asset_gate.py --gate A2`; register the current Contract as `DELIVERABLE-ASSET-CONTRACT-A3`, with lifecycle still allowed to be `review`.
- `review → completed`: `evaluate_specialist_asset_gate.py --gate A3`; reject completion unless the frozen revision and all required reviews match.

Every Registry artifact reference must contain `asset_id`, integer revision, `repo://` Contract URI, file SHA-256, and `contract_subject_digest`. Record the gate result through `core.acceptance_recorded` with `acceptance_kind: asset-gate`; never copy the asset body into Registry. Run `validate_specialist_asset_loop.py` before a state transition. A0/A1/A2/A3 failures route by `REQ/SRC/RGT/IMP/PERF/REG/SCOPE`; a requested UI change returns to a separate UI workflow instead of being written by the asset Loop.

## Art Direction Loops

Run `evaluate_art_direction_gate.py` against the exact project Contract before each stage handoff:

- D0 admits a direction brief only after project facts, experience/readability goals, scope, platforms, constraints, AI policy, and brief review match.
- D1 requires fresh web/video research, non-game influences, at least three distinct directions, a recommendation, and exploration review.
- D2 is a hard human gate bound to `direction_subject_digest`; the Art Director may recommend but cannot select for the project owner.
- D3 requires the style bible, cross-domain translation, 2D/3D/UI profiles as scoped, an in-engine target-build benchmark, passing measurements, and art/technical reviews.
- D4 requires full rights clearance, QA/rights review, zero open rework, and `frozen_revision_digest=contract_subject_digest`. An approved charter may delegate baseline compliance to an independent reviewer; validate its exact `publication.gate_decision_ref` through `evaluate_production_gate.py`. Otherwise obtain the designated owner decision.

Store only `art_direction_id`, revision, Contract URI/file digest, five stage digests, gate evidence, and approval references in Registry. Keep research, bibles, images, scenes, and review bodies in their project-owned artifact paths. D3 proves the benchmark; do not start broad final-asset production until D4 releases the production baseline. A UI visual mapping may proceed inside the art loop, but Screen/Flow, layout behavior, focus, and interaction changes must enter a separate UI workflow.

## Human Gates

Route gates through `$review-game-gates`. Settle scope, core experience and initial art direction during joint inception. GATE-2/GATE-3/D4 may be explicitly delegated at launch. External publication requires a precise authorization and passing GATE-4 evidence; otherwise deliver the release package. Never fabricate a human decision or repeatedly request an unchanged approval.

Return current loop state, active and pending instances, artifacts, consumed budget, blocked reasons, escalations, next legal transitions, and any human decision required.
