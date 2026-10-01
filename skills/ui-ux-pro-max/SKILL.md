---
name: ui-ux-pro-max
description: "Design, improve, implement, or review web, mobile, and desktop UI/UX: user flows, information hierarchy, interaction states, responsive layouts, and visual systems. Uses a local searchable design database when recommendations are needed. Apply to interface work, not backend-only changes or general graphic design."
---

# UI/UX Pro Max

Help users complete the intended task with a clear, coherent interface. Treat database matches as design candidates, not requirements or evidence that an implementation works.

## Establish scope

Read the request, relevant screens/components, existing tokens, and project instructions. Identify the primary user task, affected surface, platform/input methods, actual stack, and what success looks like. Use supplied content and references; label missing product facts as assumptions rather than inventing claims, metrics, or research.

Ask only when a missing decision materially changes the product direction, workflow, or acceptance criteria. Continue independent work while waiting. Resolve routine layout and implementation choices from context.

| Request | Work to perform | Read as needed |
|---|---|---|
| Small component/style/interaction fix | Preserve the existing system; fix the affected state and inspect adjacent behavior. No full design-system generation. | [Acceptance](references/acceptance.md), relevant [rule category](references/quick-reference.md) |
| UI/UX review | Trace the main task; report reproducible problems, impact, evidence, and fixes. A review alone does not imply implementation. | [UX workflow](references/ux-workflow.md), [acceptance](references/acceptance.md) |
| New page in an existing product | Reuse its navigation, components, and tokens; define missing states and local additions. | [UX workflow](references/ux-workflow.md); [search guide](references/search-guide.md) only for gaps |
| New product or requested redesign | Establish the main flow and a coherent visual direction; produce the requested design or implementation and validate it. | [UX workflow](references/ux-workflow.md), [search guide](references/search-guide.md), [acceptance](references/acceptance.md) |

## Codex Figma mode

When the requested deliverable is a Figma visual system, prototype, component, or token
library, use the [Codex Figma handoff reference](references/figma-handoff.md) as the
entry point. Load `figma-use` before every `use_figma` call; load
`figma-create-new-file` before `create_new_file`, `figma-generate-design` for a full
page, and `figma-generate-library` for components, tokens, or libraries. Inspect an
existing file before editing, or resolve the host plan/editor type before creating a new
file. Keep the returned file key, node IDs, screenshots, and local evidence snapshots.

Figma-only work ends with Figma structural/visual review and does not require Godot
scenes, the ten-part Godot handoff, target builds, or runtime acceptance rows. When Godot
implementation is also requested, complete the Figma handoff before applying the Godot
production mode below.

## Godot production mode

When the target stack is Godot, keep the general UI/UX guidance above and also apply the
[Godot production reference](references/godot-production.md). This mode turns a design
recommendation into an auditable Godot handoff; it does not replace the project's own
contracts or approve a visual direction.

When the visual system is produced in Codex through the Figma plugin, follow the
[Codex Figma handoff reference](references/figma-handoff.md) before Godot implementation.
It fixes the product-input → identity/visual-direction → UX-flow → Figma-prototype order,
binds `tool:figma-codex-plugin` to the approved UI Agent Preset, and keeps the Figma source
traceable to `figma_prototype` fields. Figma is a visual-system source; fixed Godot UI trees
remain editor-authored and serialized.

- Select exactly one task level: `prototype`, `greybox`, `style-pass`, or `final`. A small,
  reversible fix may stay at its current level; do not impose a full `final` gate on it.
- Before implementation, read `project.godot`, the locked Godot version, the current UI
  scenes/theme/resources, target platform and resolution policy, plus the UI Screen/Flow,
  UI Visual and Art Direction Contracts when they exist. Ask at most five questions when a
  missing fact would change scope, direction or acceptance. Use reversible defaults for the
  rest and list them as assumptions.
- Keep the two contracts separate: UI/UX owns Screen/Flow, layout, safe areas, focus and
  interaction; UI Visual owns visual identity, tokens, assets, component states, motion tone
  and visual acceptance. Godot implementation binds both to authored scenes and resources.
  Without a UI Visual Contract, label work `greybox` or `style proposal` and never claim a
  final visual result.
- Prefer editor-authored `Control`/`Container` scenes and serialized `.tscn`/`.tres` resources.
  Runtime code may instantiate an existing `PackedScene` for data-driven content, but must
  not rebuild a fixed UI tree. Record every asset in a manifest and give components an API,
  state matrix, fallback, motion token and reduced-motion behavior.
- Preserve evidence for scene loading, declared interaction states, input devices,
  responsive/localized/accessibility checks, resource replacement, performance and target
  build captures. Automation can check structure, references, digests and evidence; human
  review still decides visual quality.
- Use the fixed ten-part output and one of the five acceptance states
  `greybox` / `implementation_ready` / `review_pending` / `approved` / `blocked`. A failure
  must route to `UI_VISUAL`, `UI_STRUCTURE`, `UI_TECH` or `UI_READABILITY` as described in
  the reference.

### Godot page-first production loop

For a substantial UI task, produce one page that proves the player task before extracting a
component library. Keep a **component lab** when it is useful for checking states, typography,
Theme parameters, sliders, panels, and motion tokens, but label it as a development tool. It is
not evidence that the game UI is complete. The acceptance target is a **real-use page** from the
game (for example, a main menu, pause screen, settings screen, or inventory). If there is no
gameplay yet, use a clearly labelled themed sample and state the task it represents; do not imply
that invented content is an existing game feature.

Use these production outputs in order:

1. **Task definition:** page purpose, player goal, information priority, main action, and the
   shortest operation path including success and recovery.
2. **Visual target:** concrete reference observations, a static target frame, and a small sample
   consisting of one content panel, one primary button, one secondary button, and heading/body
   text at the final display size. Keep the visual-direction confirmation separate from the later
   full-page confirmation.
3. **Asset preparation:** real resources plus an asset usage note (purpose, display size,
   transparent area, text-safe area, stretchable region, fixed corners/ornaments, provenance and
   license, and placeholder/confirmed status).
4. **Benchmark page:** one complete, runnable real-use page with the declared task, before making
   the result a reusable component set.
5. **Feedback implementation:** state, interruption, motion, sound, and reduced-motion behavior
   for the benchmark page.
6. **Evidence and acceptance:** actual runtime screenshots and an interaction recording. Keep
   function, visual, and motion/export acceptance as separate conclusions; an export success or
   static screenshot cannot stand in for the other two.

After the benchmark page passes, extract only the patterns that proved useful. Limit each visual
revision to the three most visible problems, run at least two comparison passes when the task is
substantial, and stop when the agreed criteria pass instead of adding decoration indefinitely.

The page-first loop is a release requirement, not a request to make a larger component gallery.
A component lab may contain state swatches and animation controls, but its captures must be
labelled `component-lab` and cannot be the only visual acceptance evidence. Every benchmark page
records the task it represents, target viewport, static target frame, runtime build, and owner of
any open visual decision. Native `Button`, `Panel`, `Label` and other semantic controls remain
allowed when their Theme and state behavior express the visual direction; the workflow rejects
an unthemed default appearance, not the node type.

## Resolve UX before styling

For substantial work, describe the user's entry point, goal, minimum steps, success signal, and recovery path. Inventory the requested content and actions; prioritize the primary action within each task context. Use progressive disclosure for genuinely secondary complexity, without hiding essential information.

Account for applicable loading, empty, success, error, disabled, permission, and interrupted states. Preserve input after errors, explain how to recover, and make navigation/back behavior predictable. Scale this work to the changed surface rather than producing an exhaustive document for every button.

## Build a visual system from context

Use explicit user constraints and accepted references first, then the existing product system, then local database candidates. If these conflict in a way that affects usability or the product direction, explain the concrete issue and resolve it with the user; do not silently change the brief.

- Reuse semantic color, typography, spacing, radius, elevation, and motion tokens. Page overrides contain justified differences and inherit everything else.
- Give new surfaces a coherent direction tied to their content and audience. Avoid automatically applying the same hero, card grid, gradient, or decorative badges to every product; use them when they serve the actual brief.
- Test realistic text and data density, including Chinese glyph coverage, long labels, units, and empty values where relevant. Font pairings in the database may cover only Latin text.
- Use existing assets and component libraries when suitable. Keep icon families consistent; allow supplied raster/pixel-art styles instead of imposing vector-only artwork.
- Provide immediate input feedback. Motion should clarify state or continuity, respect reduced-motion preferences, and never delay basic feedback solely to satisfy a duration rule.

## Use the database selectively

The executable is `scripts/search.py` **relative to this SKILL.md**. Resolve that to an absolute path from the installed skill location; do not use the project working directory or a Claude-specific environment variable. See [search guide](references/search-guide.md) for runnable examples, domains, stack choices, and persistence behavior.

- Search only where it answers an unresolved design question. For a new system without a suitable existing one, `--design-system` gives a starting candidate; small fixes and existing-product pages do not require it.
- Infer the stack from project files. If unsupported or still unknown, use platform-neutral guidance and clarify only if implementation depends on the choice; do not silently default to Tailwind or map a game engine to a web stack.
- The CSV data is primarily English. Translate a Chinese request into short English product/task/style keywords for search while preserving the user's intent and response language.
- Prefer explicit `--domain` or `--stack`. For zero/irrelevant results, retry once with broader terms, then explain that the fallback is your recommendation rather than a database match.
- Check library/API examples against the actual project version before use. Search results do not authorize installing dependencies, changing frameworks, or introducing GSAP.
- Read existing design-system files before writing. Generated candidates become project decisions only after reconciliation with the brief and existing system; do not overwrite decisions merely to generate a page file.

## Implement and verify

Use the existing platform and project conventions. Keep behavior in semantic controls and appropriate framework components. In Godot projects, prefer authored scenes and Control nodes under the project's rules; this database supplies design guidance, not a Godot implementation API.

Use [acceptance](references/acceptance.md) for the affected surface. Native/mobile work also uses [platform checks](references/pro-rules.md). Inspect the actual rendered result when runtime access is available, exercise the main task and relevant failures, then fix concrete problems and recheck the affected behavior. A screenshot cannot verify keyboard semantics or an error recovery path.

If runtime access is unavailable, perform the useful source review and name the unverified interactions. Stop when the scoped acceptance criteria pass; report unresolved blockers instead of claiming an arbitrary perfect score or iterating on taste indefinitely.

## Handoff

Match the requested deliverable and keep the response proportional:

- **Implementation:** what changed and why, relevant files/preview, actual checks and outcomes, remaining limitations.
- **Design:** main flow, visual/component decisions and applicable states, rationale and assumptions, how implementation will be accepted.
- **Review:** prioritize task blockers and accessibility failures before secondary friction and cosmetic consistency. For each material finding give location/state, reproduction or observed evidence, user impact, proposed fix, and a recheck criterion. Distinguish observed defects from hypotheses.

User judgment is needed for unresolved product goals, conflicting requirements, or consequential tradeoffs; routine reversible improvements within the brief should proceed. When another installed skill is needed for browser operation, Figma, or asset generation, use that capability for the actual task without automatically starting a second full design workflow.
