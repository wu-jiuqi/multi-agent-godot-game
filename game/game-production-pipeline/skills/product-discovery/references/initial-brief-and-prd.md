# Initial brief and PRD shape

This is a writing guide for `$product-discovery`, not an approval or a production
contract. Store the two documents in project-owned paths and give each a stable ID and
SHA-256 digest in the later prototype handoff.

## Initial project brief

Start from `contracts/project-brief.template.yaml` and keep its schema. The discovery
version should have:

- a source for the owner's idea or conversation record; if there is no external file,
  use a project-owned conversation record and state who supplied it;
- all six required domains (`project-goal`, `gameplay`, `art-direction`,
  `implementation`, `platform-engine`, `scope-constraints`);
- `confirmed` only for facts the owner explicitly supplied, `preference` for an owner
  taste, `hypothesis` for a testable proposal, and `unknown` for missing information;
- blocking `open_questions` for unresolved direction, scope, owner, or acceptance;
- `staffing_input.readiness: blocked` while any blocking question or required domain is
  unknown, with every blocker listed in `blocker_refs`;
- `review.status: draft` (or `in_review` after the owner sees it), never `confirmed`
  without a digest-matched human approval record.

A valid draft is useful even when it is blocked. A validator's `valid` result means the
shape is safe to review; it does not mean the project is ready to staff, prototype, or
ship.

## Initial PRD

Use Markdown with this minimum structure. Prefix every statement with one status and a
stable ID, for example `[proposal] prd:demo:audience` or `[unknown]
prd:demo:platform`.

1. **Product identity candidates**: candidate names/titles/slogans, rationale,
   alternatives, and `decision_owner: human:<id>`; no candidate is confirmed.
2. **Player and value**: target player, desired outcome, situation, and why it may
   matter. Mark missing evidence as `unknown`.
3. **Experience hypothesis**: core fantasy, first-session moment, core-loop sketch,
   key screens/flows, and measurable success criteria.
4. **Scope and constraints**: must/should/won't, platform/engine, time/budget/team,
   accessibility/localization/rights, with proposal versus confirmed labels.
5. **Assumptions, risks, and questions**: owner, impact, evidence needed, experiment,
   stop condition, and fallback for each unresolved item.
6. **Prototype intent**: what the first prototype should learn, audience, states,
   exclusions (including runtime/release claims), and the next human decision.

The PRD may be short. It must be honest about unknowns and should link each conclusion
back to a brief statement, conversation record, or research source. Do not copy a
placeholder into the product handoff and call it a GDD.
