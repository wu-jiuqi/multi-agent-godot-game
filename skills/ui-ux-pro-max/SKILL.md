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
