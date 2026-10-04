---
name: product-brief-and-identity
description: Coordinate a project-manager-led, peer-to-peer consultation with the six department manager slots, then prepare traceable product identity, PRD/GDD sections, and a human-reviewable prototype intent.
---

# Product Brief and Identity

Use this Skill during inception or a bounded product revision. It turns an idea and
cross-department advice into a reviewable product packet. It does not silently create
departments, approve a project, or replace a domain owner.

## Role in the framework

The framework keeps six department slots available as capability templates:

```text
planning · art · programming · audio · qa · tools
```

The slots are not six running Agents. The project manager activates only the slots
needed for the consultation, and may use one manager for more than one slot when the
approved organization permits it. A consultation is peer-to-peer communication, not a
transfer of authority. A department manager may give a recommendation and cite its
facts; it cannot approve another department's facts or change a project boundary.

The project manager owns the consultation request and the integrated PRD/GDD packet.
This Skill may be run by a dedicated `AGT-PM` Position or by an authorized project
manager instance. In either case, product identity, scope, player value and final
experience remain human decisions; a generated recommendation is never confirmation.

## Required context

Read before starting:

- the project instance `AGENTS.md`, project brief, Production Charter and current
  Organization Registry/Snapshot when present;
- `../../agents/pipeline-director.md`, `../../agents/department-manager.md` and
  `../../agents/product-manager.md`;
- the active department-manager Preset versions, tool registry and fact-source
  bindings;
- any existing brief, PRD, GDD, brand/product decision or Penpot handoff. One adequate
  source document is enough; do not demand all three document types.

If the project instance, authority, source digest, or ownership is missing, stop at
`blocked` and return the exact missing item to the project manager.

## Inputs

- owner request, existing project brief and approved constraints;
- active or candidate department slots and their manager Preset versions;
- domain facts, open questions, risks, cost/time bounds and known dependencies;
- existing product name/title/slogan and decision references, if any;
- optional previous `product-prototype-handoff` revision.

## Procedure

1. **Intake and classify.** Record each statement as `confirmed`, `preference`,
   `hypothesis` or `unknown`, with a source reference and stable question/decision ID.
   Keep contradictions visible. Do not turn a preference or a manager recommendation
   into a confirmed fact.
2. **Plan the consultation.** The project manager declares the objective, deadline,
   active slots, questions, response shape, budget and write scope. Inactive slots are
   recorded as `not_requested` with a reason; they are not instantiated.
3. **Run the P2P round.** Ask each active department manager the same structured
   question set when possible. Managers may open a direct peer discussion only for a
   named dependency or conflict. Record participants, input digests, alternatives,
   assumptions, risks, evidence and a proposed owner. All responses are append-only
   consultation records.
4. **Synthesize.** Prepare product identity candidates, a PRD/GDD draft, a decision
   matrix and a `prototype_intent`. The project manager integrates cross-domain
   sections and reports unresolved conflicts; this Skill never edits a department's
   source-of-truth file to make the summary look consistent.
5. **Run automatic checks.** Verify stable IDs, source/digest references, response
   coverage, unresolved conflict routing, authority limits, and that no inactive slot
   was called. Verify that the proposed name/title/slogan and scope each have a
   decision owner and a gate reference.
6. **Request the existing human gates.** Use `GATE-0` for project direction, scope,
   identity and charter decisions and `GATE-1` for the core experience/vertical-slice
   hypothesis. Use `D2` or the UI Visual review for visual direction when relevant.
   Approval must bind the packet revision and digest. Silence, tool success or a
   department response cannot supply approval.
7. **Handoff.** On approval, emit the `product-prototype-handoff` Contract for the
   Penpot Skill and the downstream UI/UX, art and Godot roles. On rejection or stale
   source digests, increment the revision and return only the affected decisions to
   intake/consultation.

## Outputs

- a project-manager-owned PRD/GDD integration draft with source and decision refs;
- product identity candidates and, after the human gate, the confirmed name/title/
  slogan decision reference;
- consultation records for every activated department manager and any P2P peer round;
- conflict, risk, assumption and open-question registers with owners and routes;
- a stable `prototype_intent` describing goals, screens/flows, success criteria,
  visual/UX inputs and exclusions;
- a versioned `contracts/product-prototype-handoff.template.yaml` instance or a
  project-local contract derived from it;
- an approval packet that names `GATE-0`, `GATE-1` and any D2/UI Visual review still
  required.

## Authority and tool boundary

This Skill may read project sources, write its project-owned draft/consultation and
handoff records, and message authorized department-manager instances. It may not:

- change project scope, budget, schedule, core fantasy, product identity or final UX;
- create, remove, merge or bind a persistent Department, Position, Preset or Skill;
- overwrite a department fact source, sign a human approval, approve a gate or publish;
- call Penpot as an implicit side effect. Penpot work is the separate
  `$penpot-prototype-orchestration` Skill and requires a project registry entry for
  `tool:penpot-mcp`.

Use only project-approved read/write/test tools and the approved agent-message route.
Do not place a Penpot user token, remote secret URL or unverified host version in a
repository contract.

## Acceptance and failure return

The packet is `review_pending` only when every activated slot has a response or an
explicit `not_applicable`/`blocked` record, every decision has a source and owner, all
conflicts have a route, and the PRD/GDD summary can be rebuilt from the records. It is
`approved` only after digest-matched human records for the required gates.

Return `PRODUCT_DIRECTION` to the human/project manager for identity, scope, player
value or core-experience choices; `DOMAIN_FACT` to the owning department manager;
`P2P_CONFLICT` to the project manager with both responses preserved;
`PRODUCT_DOCUMENT` to the synthesizer for traceability or completeness; and
`AUTHORITY` to the project manager/organization owner. A failed or unavailable manager
does not justify inventing an answer: preserve the partial packet, record the retry
budget and next action, and mark the affected slot blocked.

## Completion report

Return the handoff path and revision, consulted slot/instance IDs, source and subject
digests, automatic checks, gate status, unresolved questions, rework route and the
next executable action. Keep the report separate from the domain documents it cites.
