# Codex Figma UI handoff

Use this reference when a product will have its visual system and prototype made in
the Codex Figma plugin before it is implemented in Godot. It is an extension of the
UI Visual Contract; it does not replace the Screen/Flow Contract or the project's
approval and evidence rules.

## Required intake and stage order

Complete these stages in order and record the source and decision evidence in the UI
Visual Contract's `workflow` fields:

1. **Input intake (`input_intake`)** — read the available product brief, PRD, GDD,
   research, and platform constraints. Record each document in `source_document_refs`
   with its kind, title, URI, digest, and role. A missing brief or a document that
   changes product direction is a human question; do not invent product facts.
2. **Product identity and visual direction
   (`product_identity_and_visual_direction`)** — agree on the stable `product_name`,
   player-facing `product_title`, `slogan`, and `visual_direction.style_requirements`.
   Keep the decision references and rationale with the contract before opening a Figma
   write session.
3. **UX flow (`ux_flow`)** — if the PRD already defines the flow, set
   `resolution: inherited_from_prd`, set `authoring_skipped: true`, and reference the
   existing flow. Otherwise set `resolution: derived_from_inputs` and record the UX
   decision and unresolved questions. Do not create a competing flow silently.
4. **Figma visual system (`figma_visual_system`)** — use the approved
   `tool:figma-codex-plugin` binding to create the visual system prototype, component
   states, design tokens, and key-screen frames. The handoff is not implementation
   ready until `figma_prototype` has `provider: figma`,
   `integration: codex_figma_plugin`, a versioned `file_ref`, `file_url`,
   `prototype_url`, `screen_refs`, `design_system_ref`, and evidence references.

The first three stages are product and UX decisions. Figma expresses those decisions;
it must not be used to silently change the brief, title, slogan, or Screen/Flow facts.

## Approved Codex Figma binding

The UI Agent Preset declares the project tool registry and tool ID together:

```yaml
tool_registry_ref:
  path: game-pipeline/execution/tools.yaml
  sha256: <tool-registry-digest>
tool_ids:
  - tool:figma-codex-plugin
```

Its Skill Binding includes the installed Codex Figma skills that describe the operation
(normally `figma:figma-use`, and `figma:figma-generate-design` for a full page). The
project resolves each skill's actual plugin path and digest when the binding is
approved; the tool registry remains the authority for the allowed Figma scope.

Before a Figma write, load the `figma-use` skill. For a complete page or multi-section
layout, also load `figma-generate-design`. Follow those skills' inspect-first,
return-node-IDs, screenshot, and human-review requirements. The tool binding is an
approved scope record, not a host permission grant and not an approval to publish.

## Figma output and evidence

Return enough stable data for a later implementation or review to find the exact visual
source:

- Figma file key, `file_url`, prototype URL, version/revision, and file digest;
- one `screen_refs` entry per required screen, including `screen_id`, `frame_node_id`,
  and frame URL;
- a `design_system_ref` for tokens/components and its digest;
- screenshots or other review evidence tied to the same revision;
- open visual decisions, owner, and the handoff status
  (`draft`, `review_pending`, or `implementation_ready`).

Screenshots are evidence of a visual target, not runtime proof. A missing frame mapping,
design-system reference, or review record keeps the handoff at `review_pending`.

## Godot implementation boundary

Figma is the authored visual-system source. Godot implementation binds it to the approved
Screen/Flow and UI Visual Contracts using editor-authored `Control`/`Container`/semantic
control nodes and serialized `.tscn`/`.tres` resources. Map tokens, components, states,
assets, and motion into those scenes and resources, then capture the real benchmark page.

Do not export a Figma frame as a runtime UI and do not reconstruct a fixed UI tree from a
script. Runtime creation is limited to data-sized content or instantiation of an existing
`PackedScene` when the project has approved that boundary; the component tree itself stays
authored and serialised. This preserves the Figma-to-Godot trace while keeping layout,
focus, localization, accessibility, and input behavior testable in the engine.

## Acceptance and return routes

`implementation_ready` means the Figma handoff is complete enough for Godot binding; it
does not approve the visual direction or the final runtime page. Keep `functional`,
`visual`, and `motion_export` evidence separate. Human visual review is required before
`approved`.

- Invalid style, token, component state, or Figma evidence → `UI_VISUAL`;
- missing or conflicting UX flow → `UI_STRUCTURE`;
- missing node/resource binding, scene serialization, or runtime evidence → `UI_TECH`;
- contrast, hierarchy, or state readability conflict → `UI_READABILITY`.

