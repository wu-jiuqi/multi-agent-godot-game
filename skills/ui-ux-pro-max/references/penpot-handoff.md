# Codex Penpot UI handoff

Penpot is the default editable visual-system source for this repository. The Codex host must expose the official remote Penpot MCP server before any write operation. Configure the server URL and token in the host or project secret store; never commit either value, an access token, or a guessed capability snapshot to this repository. The public endpoint has the form `https://<your-penpot-domain>/mcp/stream?userToken=YOUR_MCP_KEY` (copy the URL shown by Penpot; the token is a secret), and the project records only the non-secret server identity and local schema snapshot. A connected host is not assumed: if setup, login, or capability verification is missing, keep the handoff at `blocked`/`review_pending` and record the recovery action.

Before any Penpot operation, run the repository's single read-only connection
status checker at `game/game-production-pipeline/scripts/validate_penpot_connection.py`.
It accepts an injected probe result or JSON input and returns `connected`,
`disconnected`, or `error`. Continue only for `connected`; retain the state and a
recovery action for the other states. The checker does not open a browser, call
MCP, write Penpot, or read credentials. Never put credentials in a contract, and
never treat a URL or screenshot alone as proof of a connected MCP session or a
completed Penpot operation.


Use this reference when a product will have its visual system and prototype made in
the Penpot MCP server before it is implemented in Godot. It is an extension of the
UI Visual Contract; it does not replace the Screen/Flow Contract or the project's
approval and evidence rules.

## Required intake and stage order

Complete these stages in order and record the source and decision evidence in the UI
Visual Contract's `workflow` fields:

1. **Input intake (`input_intake`)** — read the available product brief, PRD, GDD,
   research, and platform constraints. At least one of a brief, PRD, or GDD is enough
   to start; do not block on all three being present. Record the documents actually
   used in `source_document_refs` with kind, title, URI, digest, and role. A missing
   product input that changes direction is a human question; do not invent product
   facts.
2. **Product identity and visual direction
   (`product_identity_and_visual_direction`)** — agree on the stable `product_name`,
   player-facing `product_title`, `slogan`, and `visual_direction.style_requirements`.
   Keep the decision references and rationale with the contract before opening a Penpot
   write session.
3. **UX flow (`ux_flow`)** — if the PRD already defines the flow, set
   `resolution: inherited_from_prd`, set `authoring_skipped: true`, and reference the
   existing flow. Otherwise set `resolution: derived_from_inputs` and record the UX
   decision and unresolved questions. Do not create a competing flow silently.
4. **Penpot visual system (`penpot_visual_system`)** — use the approved
   `tool:penpot-mcp` binding to create the visual system prototype, component
   states, design tokens, and key-screen frames. The handoff is not implementation
   ready until `penpot_prototype` has `provider: penpot`,
   `integration: penpot_mcp`, a versioned `file_ref`, `file_url`,
   `prototype_url`, `screen_refs`, `design_system_ref`, and evidence references.

The first three stages are product and UX decisions. Penpot expresses those decisions;
it must not be used to silently change the brief, title, slogan, or Screen/Flow facts.

## Approved Codex Penpot binding

The UI Agent Preset declares the project tool registry and tool ID together:

```yaml
tool_registry_ref:
  path: game-pipeline/execution/tools.yaml
  sha256: <tool-registry-digest>
tool_ids:
  - tool:penpot-mcp
```

The project-local UI dispatcher records the installed Codex Penpot prerequisites; it
must not invent a path, version, capability, or digest for a host plugin outside this
repository. Use the optional
[`penpot-tool-registry-entry.template.yaml`](../../../game/game-production-pipeline/assets/penpot-tool-registry-entry.template.yaml)
only after the project captures a local adapter/schema snapshot and verifies its
capabilities. The tool registry remains the authority for the approved Penpot scope.

The repository does not provide a separate Penpot client skill or guarantee a particular
MCP tool name. Follow the capabilities exposed by the connected
Penpot MCP server: inspect the focused page first, then use the server's documented
read/write operations. The tool binding is an approved scope record, not a host
permission grant and not an approval to publish.

## Existing files, new files, and retry boundaries

For an existing Penpot file, run a read-only inspection first: record the `file_id`, current `page_id`, relevant pages/shapes, components, variables, styles, and naming
conventions before mutating anything. Reuse compatible foundations and return the IDs
from every mutation. Never guess a page or node ID.

For a new file, use the connected Penpot MCP server's documented file-creation path
when available, save the returned `file_id` outside the canvas state, and record each `page_id`. A
`screen_refs` entry records each stable `shape_id`; a screenshot or node capture
records the visual evidence for that exact frame.

Penpot MCP calls are retryable only within the loaded skill's recovery rule. After an error,
retry locally when `safeToRetryWithoutCanvasRead` permits it; otherwise inspect the
canvas and use the returned IDs to determine what already changed before retrying. Do
not recreate a page or component after a partial success, and return all affected IDs
and relevant counts/bounds from every successful write.

## Penpot output and evidence

Return enough stable data for a later implementation or review to find the exact visual
source:

- Penpot `file_id`, `file_url`, prototype URL, and version/revision;
- one `screen_refs` entry per required screen, including `screen_id`, `shape_id`,
  and shape URL;
- a `design_system_ref` for tokens/components;
- screenshots or other review evidence tied to the same revision;
- local source snapshots or evidence files whose SHA-256 values make the handoff
  reproducible;
- open visual decisions, owner, and the handoff status
  (`draft`, `review_pending`, or `implementation_ready`).

Penpot URLs (`file_url`, `prototype_url`, `shape_url`, and design-system URLs) are
provenance and must not be presented as files with URL-derived SHA-256 values. Any
`sha256` in the handoff points to a project-local snapshot or evidence file whose bytes
are available to the validator. Screenshots are evidence of a visual target, not runtime
proof. A missing frame mapping, design-system reference, or review record keeps the
handoff at `review_pending`.

## Godot implementation boundary

Penpot is the authored visual-system source. Godot implementation binds it to the approved
Screen/Flow and UI Visual Contracts using editor-authored `Control`/`Container`/semantic
control nodes and serialized `.tscn`/`.tres` resources. Map tokens, components, states,
assets, and motion into those scenes and resources, then capture the real benchmark page.

Do not export a Penpot frame as a runtime UI and do not reconstruct a fixed UI tree from a
script. Runtime creation is limited to data-sized content or instantiation of an existing
`PackedScene` when the project has approved that boundary; the component tree itself stays
authored and serialised. This preserves the Penpot-to-Godot trace while keeping layout,
focus, localization, accessibility, and input behavior testable in the engine.

## Acceptance and return routes

`implementation_ready` means the Penpot handoff is complete enough for Godot binding; it
does not approve the visual direction or the final runtime page. Keep `functional`,
`visual`, and `motion_export` evidence separate. Human visual review is required before
`approved`.

For a Penpot-only request (for example, a visual system, token set, component library,
or prototype), stop at the Penpot acceptance evidence. Do not require Godot scenes,
target builds, runtime screenshots, the ten-part Godot handoff, or `functional` /
`motion_export` rows unless the user also requests engine implementation. The Penpot
deliverable still needs its own structural/visual checks and human review.

- Invalid style, token, component state, or Penpot evidence → `UI_VISUAL`;
- missing or conflicting UX flow → `UI_STRUCTURE`;
- missing node/resource binding, scene serialization, or runtime evidence → `UI_TECH`;
- contrast, hierarchy, or state readability conflict → `UI_READABILITY`.
