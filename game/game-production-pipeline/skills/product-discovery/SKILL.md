---
name: product-discovery
description: Start a traceable product conversation when a game has no usable brief, GDD, PRD, or slogan, then produce proposal/unknown inception documents before prototype handoff.
---

# Product Discovery

Use this Skill as the explicit no-document entry point. It is for a project owner who
has an idea, a sketch, or an empty repository but no usable product brief, GDD, PRD,
product name, or slogan. It supplements `$prepare-game-project-brief`; it does not
replace the project bootstrap, human direction gates, or Penpot orchestration.

## Entry and boundaries

- Trigger when the available brief/GDD/PRD is absent, empty, stale, or only a
  placeholder. A missing slogan is a discovery gap, not a reason to invent one.
- Read the project `AGENTS.md` and bootstrap control plane first. If project identity,
  owner, write scope, or authority is missing, stop at `blocked` and report the exact
  item; do not create a fake handoff.
- Treat every statement as `confirmed`, `preference`, `hypothesis`, or `unknown` and
  keep its source. Agent suggestions and generated copy remain `proposal` until the
  owner decides. Do not silently infer a genre, audience, platform, budget, or name.
- This Skill may write only the project-owned discovery draft, initial brief/PRD, open
  questions, and handoff proposal in the approved paths. It cannot approve a gate,
  create persistent departments, call Penpot, publish, or start production.

## Conversation loop

1. **Inventory.** Record available files and conversation facts. Mark each expected
   input as `confirmed`, `proposal`, `hypothesis`, or `unknown`; preserve an empty
   source list as a blocker rather than treating it as a complete packet.
2. **Ask in small rounds.** Explain the recommended direction and alternatives, then
   ask only the few questions that change player value, core loop, audience, scope,
   platform, constraints, or acceptance. If the owner does not know, record `unknown`
   and propose a bounded experiment or a follow-up question with an owner.
3. **Draft the initial brief.** Write a project-brief-shaped YAML document using the
   template in `references/initial-brief-and-prd.md`. Unknown required domains stay
   `unknown`; proposals use `preference` or `hypothesis`; blocking questions make
   `staffing_input.readiness: blocked`. Never mark it `confirmed` or `ready` merely
   because validation passes.
4. **Draft the initial PRD.** Write a short, traceable Markdown PRD beside the brief.
   Label identity candidates, player value, design pillars, scope, core-loop sketch,
   assumptions, risks, and open questions with `proposal`/`unknown` statuses and
   source IDs. A candidate slogan is copy to review, never an approved slogan.
5. **Review the discovery packet.** Run `validate_project_brief.py` and the relevant
   handoff validator. Resolve malformed references and duplicate IDs. Report what is
   still unknown, who owns each decision, and which questions block staffing or a
   prototype. Validation proves structure only.
6. **Human direction decision.** Present the packet and alternatives for `GATE-0`
   (identity, player, scope and constraints) and `GATE-1` (core experience and the
   vertical-slice hypothesis). Keep the packet at `review_pending` until the owner
   provides the required decision; no silence, generated digest, or test pass is an
   approval.
7. **Prototype handoff.** Once the owner chooses a bounded direction, create or update
   the `product-prototype-handoff` with the initial brief/PRD references, proposal and
   unknown statuses, stable screen/flow IDs, success criteria, exclusions, and a
   next-action list. Route it to `$product-brief-and-identity` and then
   `$penpot-prototype-orchestration`. Penpot may only run after the handoff's approved
   scope and tool registry are present; `implementation_ready` still requires its
   independent evidence and reviews.

## Outputs and return paths

Outputs are a proposal packet, an initial project brief, an initial PRD, a question and
risk register, and (when direction is bounded) a traceable prototype-handoff proposal.
Use stable IDs and SHA-256 refs for files. Return `PRODUCT_DIRECTION` to the owner,
`PRODUCT_DOCUMENT` for traceability or missing sections, `AUTHORITY` for missing
permissions, and `PENPOT_TOOL` only after a valid handoff exists. Preserve partial work
and the next question when the owner is unavailable; do not skip discovery by emitting
an empty or fabricated handoff.

See [`workflows/product-discovery.md`](../../workflows/product-discovery.md) for the
stage contract and [`references/initial-brief-and-prd.md`](references/initial-brief-and-prd.md)
for the smallest reviewable document shape.
