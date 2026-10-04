---
name: penpot-prototype-orchestration
description: Turn an approved product prototype intent into an editable Penpot visual system and clickable prototype with auditable mappings, evidence, and review handoff.
---

# Penpot Prototype Orchestration

Use this Skill after product identity and the relevant direction/UX inputs are
approved or explicitly marked as a bounded prototype hypothesis. It orchestrates the
official Penpot MCP; it is not the owner of product, visual or UX decisions.

## Required context

Read:

- the project instance `AGENTS.md`, Production Charter and current write scope;
- the `product-prototype-handoff` instance produced by
  `$product-brief-and-identity`;
- the approved or inherited Screen/Flow and UI Visual/Art Direction references;
- the project-local Tool Registry entry for `tool:penpot-mcp` and its local schema/
  source snapshot. The default plugin registry does not imply that a host is connected.

If the product handoff is stale, product identity is unapproved when approval is
required, or the Penpot registry/capability verification is absent, stop before a
write and return `blocked` with the required recovery action.

## Inputs and outputs

Inputs include the handoff revision/digest, source document refs, product identity,
prototype intent, Screen/Flow facts, visual direction, target platforms/viewports,
existing Penpot file (optional), and the approved Penpot tool scope.

Outputs include:

- a Penpot file or an update to an explicitly referenced file;
- Foundations, Components, Screens and Prototype pages where the existing file allows;
- variables/styles, component states, key frames and clickable links;
- stable screen/page/shape mappings and a local snapshot/evidence record;
- a handoff status of `draft`, `review_pending` or `implementation_ready`, plus the
  UI/UX and art-direction review findings;
- an updated `product-prototype-handoff`/UI Visual Contract reference. A Penpot URL
  alone is not evidence of completion.

## Procedure

1. **Verify authorization.** Resolve the exact tool registry entry, source digest,
   capability list and allowed scope (`read:penpot`, `write:penpot`, `capture:penpot`).
   Confirm the project write paths and current handoff digest. Never copy a user token
   or secret URL into a file.
2. **Read before writing.** Inspect the existing file, page and relevant nodes when a
   file is supplied. If the canvas or tool state is unknown, perform a read-only
   check. A retry is safe only after the check proves which nodes exist; otherwise
   preserve the failed call and ask the tool owner to recover.
3. **Build the visual system.** Create or update only the approved prototype scope:
   variables, styles, typography, semantic colors, spacing and reusable components.
   Link every visual choice to the visual-direction or prototype-intent reference.
   A proposed styling choice is labelled a proposal and routed to the art/UI reviewer.
4. **Author representative screens.** Start with one representative screen, verify
   readability and component states, then expand to the agreed key screens. Preserve
   existing stable IDs when updating. Do not create a second competing Screen/Flow.
5. **Wire and walk the prototype.** Link entry, primary action, success feedback,
   back/cancel and applicable error recovery. Record start frame, action, target frame
   and observed result for each flow. Unsupported interactions remain explicitly
   unverified.
6. **Capture evidence and mappings.** Store file/page/shape IDs, version/revision,
   snapshots, viewport, flow records and tool evidence in the project-local handoff.
   Check that the links resolve and that each screen ID maps to one intended frame.
7. **Review and hand off.** Route visual findings to the art/UI Visual owner,
   structure/readability findings to UI/UX, and tool/permission failures to the tool
   owner. Set `implementation_ready` only after required professional reviews and
   automatic checks pass. This status means design handoff readiness only; it does not
   mean Godot implementation, D3/D4, or release approval.

## Authority and boundary

The Skill may operate the approved Penpot file and capture evidence within the listed
scope. It may not:

- decide or freeze product name, slogan, scope, core fantasy or player value;
- change the authoritative Screen/Flow, Art Direction or UI Visual Contract;
- approve its own visual/UX work, sign `GATE-0/GATE-1/D2/GATE-4`, or publish;
- export a Penpot frame as a runtime UI or replace a Godot scene/Theme with a bitmap;
- write outside the project-local Penpot snapshot/evidence and approved design paths;
- infer a missing tool capability, version, rollback procedure or remote URL.

The final visual decision belongs to the human/approved art-direction owner, the
interaction structure belongs to UI/UX, product identity belongs to the product owner,
and runtime implementation belongs to the Godot role.

## Acceptance and fallback

Automatic acceptance requires a valid tool binding, unchanged input digests, complete
screen/page/shape mappings, readable key screens, resolvable prototype links, captured
version evidence and no unlabelled unsupported flow. Professional review must record
`UI_VISUAL`, `UI_STRUCTURE` and `UI_READABILITY` findings as applicable.

Return `PRODUCT_DIRECTION` to the product manager/owner; `UI_VISUAL` to the art/UI
Visual owner; `UI_STRUCTURE` to UI/UX; `PENPOT_TOOL` to the tool owner; and
`HANDOFF_TRACEABILITY` to the producing Skill. On a failed write, inspect the canvas,
retain the partial snapshot, avoid duplicate nodes, and retry only the affected
operation within the approved budget. If the host is unavailable, keep a reviewable
intent and local input evidence but do not claim a Penpot prototype or fabricate URLs.

## Completion report

Return the handoff and UI Visual paths, file/page/shape mappings, tool registry and
input digests, viewport/flow evidence, review status, unresolved/unsupported items,
failure route and the next Godot or review action.
