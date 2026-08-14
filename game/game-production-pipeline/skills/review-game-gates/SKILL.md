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

## Guardrails

- The producing Agent cannot be the sole reviewer of its own deliverable.
- Never substitute a screenshot for executable evidence when the contract requires a build, test, or data file.
- Keep approval authority, Codex permission, and technical validation as three separate facts.
- Expired, mismatched, or post-edited evidence returns to `blocked` or `revise`.

Return the gate result, evidence table, failed criteria, responsible return path, approval digest when applicable, and next legal action.
