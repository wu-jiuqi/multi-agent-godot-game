# UX workflow and diagnosis

Use for new flows, substantial redesigns, or UX reviews. A small visual fix only needs the affected task and states.

## Ground the task

Extract from the brief and actual product:

- Who is acting, in what context, and with which input method?
- What are they trying to finish, and what visibly confirms completion?
- What content, prerequisites, permissions, and existing routes constrain that task?
- Which evidence is available: code, reference screens, observed behavior, user reports, or research?

Keep assumptions separate from observations. Do not fabricate personas, research participants, conversion rates, testimonials, or business claims to make a design feel complete. If users' goals are unknown and would change the flow, ask the consequential question and proceed with independent inspection.

## Trace the minimum complete journey

For example: order list → find an order → inspect details → edit address → save → see updated address. Identify the entry point, information needed at each step, action, state change, exit/back path, and recovery after interruption. The example illustrates completeness; do not add this workflow to unrelated products.

Check where the user must remember hidden information, repeat entry, infer an unlabeled action, wait without feedback, or recover without instructions. Simplify those specific burdens before choosing decorative styles.

## Cover applicable states

Use this table as a planning aid; omit irrelevant states and do not generate a separate artifact unless it helps the task.

| State | Required design decision | Observable check |
|---|---|---|
| Default/success | Clear next action and visible result | User can identify what to do and confirm completion |
| Initial empty | Explain absence and a legitimate first step | No fake records or success metrics |
| No search results | Retain query/filters and offer a useful adjustment | User can recover without restarting the task |
| Loading/submitting | Feedback, stable layout, repeat-action policy | Slow response does not look like a dead control or cause duplicate submission |
| Validation/server error | Specific explanation, retained input, correction/retry path | A failed attempt can be corrected and completed |
| Disabled/no permission | Explain availability when needed; reflect actual capability | No enabled-looking dead action or misleading success |
| Interrupted/offline | Preserve useful state and communicate recovery limits | No silent loss of drafts or false saved indicator |
| Destructive action | Choose undo or confirmation appropriate to reversibility and cost | User understands consequence and can recover where supported |

## Shape the information hierarchy

Group content by user task, give sections meaningful labels, and distinguish navigation from actions. Use explicit action labels such as “Save address” where an ambiguous “Continue” hides the result. Show essential price, status, units, prerequisites, and errors where the decision is made. Explain unavailable actions rather than manufacturing functionality.

For dashboards, preserve comparability, density, sorting/filter context, and data definitions. For marketing pages, prioritize a truthful offer and the requested conversion path. For tools, prioritize the working area and frequent actions. Do not turn every surface into a landing-page composition.

## Review findings and design handoff

For each material finding record:

`location + state → evidence/reproduction → user impact → proposed change → acceptance check`

Classify blockers first (task cannot complete, important information inaccessible, or loss/misrepresentation of user work), then significant friction, then polish. Mark screenshot-only inferences as hypotheses until behavior is exercised. Do not promise a conversion increase without evidence.

A design handoff should make the primary flow, component behavior, relevant responsive/state differences, and unresolved decisions implementable. If evidence contradicts the proposed structure, return to the flow/hierarchy; if only spacing fails, revise the local layout. Ask the user to resolve conflicting product requirements, not ordinary token choices.
