---
name: prepare-game-project-brief
description: Collaboratively develop a game idea into a confirmed project brief and bounded production charter. Use during inception to research options, resolve cross-domain trade-offs with the owner, prepare staffing and acceptance, and authorize low-intervention production; also use when an approved direction needs revision.
---

# Prepare Game Project Brief

Help the owner reach a considered project decision. The owner may arrive with only an idea; do not require them to supply a finished design, art direction, or technical plan.

## Required Context

Validate the project instance and read its `AGENTS.md`, registered facts, `project-brief.yaml`, and `production-charter.yaml` under `game-pipeline/project-definition/` when present. Read `../../agents/pipeline-director.md` and [the inception workshop](references/inception-workshop.md). Existing projects without a charter retain their current approval rules until a charter is explicitly confirmed.

## Inception

1. Register sources, contradictions, constraints, and unknowns. Distinguish owner-confirmed facts, preferences, Agent proposals, and testable hypotheses. An Agent recommendation never becomes a human decision by inference.
2. Cover the workshop's player, design, content, art, UI, audio, technology, scope, cost, testing, distribution, and autonomy concerns. Mark irrelevant domains with a reason. Consult bounded specialist subagents for independent research and critique; these are inception consultations, not unapproved persistent production positions.
3. For consequential choices, present a recommendation and credible alternatives with effects on player experience, feasibility, cost, and risk. Ask a few related questions per round; continue independent research while answers are pending. Do not turn the coverage matrix into an unfiltered questionnaire.
4. Resolve high-impact uncertainty through a small prototype or representative sample when it is within the current research authorization. Name its learning goal, cost cap, acceptance, and disposal/reuse boundary. A mockup does not prove runtime behavior or player enjoyment.
5. Prepare the brief, scope exclusions, acceptance examples, risk/fallback register, and responsibility needs. Direction, acceptance thresholds, and scope trade-offs remain the owner's decisions. Implementation details may be delegated inside those decisions.
6. Draft a project-owned Production Charter from `../../contracts/production-charter.template.yaml`: frozen direction references, production bounds, delegated reviews, reserved decisions, budgets, retry limits, tool permissions, write scope, and exception reporting. A desire for autonomy is not an unlimited spending or publishing grant.

## Launch review

1. Prepare the organization and Skill Binding proposals with $design-game-organization. During inception it may draft from the current brief without applying unapproved changes. Prepare all reviewable subjects before requesting the launch decision.
2. Run `validate_project_brief.py` and `validate_production_charter.py` from `../../scripts/`; resolve blockers, bind current digests, and show one launch packet linking the brief, charter, staffing/Skill proposals, representative experience and visual choices, limits, remaining bounded experiments, and finish criteria.
3. Obtain explicit approval of each named subject in the packet; one owner response may approve the listed subjects together. Record the actual response reference separately for each approval. Missing answers, elapsed time, or a script's success cannot supply consent.
4. Record immutable digest-matched approvals, mark the brief confirmed and the charter approved, update the fact-source bindings, then apply only the approved staffing and Skill changes. Run the full project validator and regenerate approved adapters.
5. Hand the authorized scope to $operate-game-production-loop. Do not ask the owner to reconfirm routine decisions already covered by the launch packet.

## Revision and failure

Unresolved direction choices or contradictory constraints block launch. Unknown production details may remain only with a named Agent owner, experiment, budget, deadline/stop condition, and fallback already accepted in the charter. Changed approved content invalidates its digest-bound approval; increment the revision and return only the affected decisions to inception. Keep unrelated authorized production moving.

Return the brief and charter paths, validation and approval states, remaining blockers, delegated scope, and next executable action.
