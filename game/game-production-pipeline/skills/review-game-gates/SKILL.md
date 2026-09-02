---
name: review-game-gates
description: Review game-production evidence against automatic and human gates. Use when a milestone, vertical slice, content freeze, exception, rollback, or release decision needs independent evaluation and explicit routing.
---

# Review Game Gates

Evaluate evidence independently, distinguish machine-verifiable checks from judgment, and never self-approve a human gate.

## Workflow

1. Read `../../agents/qa-release.md`, `../../contracts/human-gates.md`, the bound Pipeline/Loop Contract, and the referenced evidence. Do not accept a summary in place of required source artifacts.
2. Verify identity and freshness: contract ID/version, artifact path, producer, target build, timestamp, acceptance baseline, and relevant Registry event.
3. Run deterministic validators first. Record their commands, exit status, and output as automatic evidence.
4. Evaluate qualitative evidence only against criteria approved before execution. Separate observed facts, inferences, unresolved questions, and recommendations.
5. Classify the outcome:
   - `pass`: every automatic requirement passed and no human judgment is required.
   - `revise`: evidence is valid but acceptance criteria are unmet; return to the named owner.
   - `blocked`: required input, authority, environment, or reliable evidence is absent.
   - `awaiting_human`: automatic checks passed but a human gate remains.
6. For `awaiting_human`, present the decision scope, evidence index, risks, reversible options, recommendation, and approval digest. Only the designated human may record approve/reject/revise.
7. Append the resulting event without rewriting history. An approval never changes a failed automatic check into a pass.

## Specialist Asset Gates

When the review target is a `game-production-specialist-asset/v1` Contract, run `../../scripts/evaluate_specialist_asset_gate.py <contract> --gate A0|A1|A2|A3 --project-root <root>` before interpreting evidence. Preserve its four outcomes: `pass`, `revise`, `blocked`, or `awaiting_human`.

- A0 requires the requester-bound demand review and only allows formal production to start.
- A1 requires current Source plus producer and rights review; it does not imply Runtime readiness.
- A2 requires Runtime, recipe, target-scenario measurements, automated checks, and technical review.
- A3 requires every review, zero open rework, frozen subject digest, attribution when applicable, and approval references.

Store the evaluator output as evidence and bind its `approval_digest` to any subsequent decision. The evaluator is read-only: it never writes a human decision. A project-level `GATE-3` may require all scoped assets to have A3, but one asset's A3 does not itself approve project content freeze.

## Art Direction Gates

For `game-production-art-direction/v1`, run `../../scripts/evaluate_art_direction_gate.py <contract> --gate D0|D1|D2|D3|D4 --project-root <root>` and preserve its outcome without writing approval.

- D0 checks that the visual problem is grounded in approved experience, readability, platform, scope, and rights constraints.
- D1 checks research provenance and whether at least three options differ in more than palette or surface treatment.
- D2 always requires the designated human to approve the current `direction_subject_digest`.
- D3 checks a representative in-engine target build, every required domain, readability, technical profiles, budgets, and independent art/technical reviews.
- D4 checks full rights/AI provenance, QA, resolved rework, owner approval, and the frozen `contract_subject_digest`.

Evaluate image quality against the recorded visual language and player effect, not taste alone. Screenshots can prove appearance, but executable target-build evidence is still required where the Contract names interaction, motion, import, or performance. D4 does not replace project GATE-3/GATE-4.

## Guardrails

- The producing Agent cannot be the sole reviewer of its own deliverable.
- Never substitute a screenshot for executable evidence when the contract requires a build, test, or data file.
- Keep approval authority, Codex permission, and technical validation as three separate facts.
- Expired, mismatched, or post-edited evidence returns to `blocked` or `revise`.

Return the gate result, evidence table, failed criteria, responsible return path, approval digest when applicable, and next legal action.
