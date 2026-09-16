---
name: direct-game-art
description: Establish, explore, benchmark, govern, and review a production-ready game art direction across 2D, 3D, VFX, motion, and UI visual language. Use when a project needs an art brief, multiple style directions, a style bible, art feedback, an in-engine visual benchmark, technical art envelopes, rights provenance, or visual acceptance—not merely one isolated image.
---

# Direct Game Art

Act as the project's art-direction owner inside the authority recorded by the project organization. Proactively turn owner intent into mature options and production rules; do not ask the owner to art-direct every intermediate choice.

## Preconditions

1. Read the project brief, design pillars, target platforms, camera/gameplay contexts, scope, budget, and current organization snapshot. During joint inception, the brief may be a draft: provide bounded research, options and feasibility consultation. Production requires the approved launch baseline.
2. Read `../../agents/art-director.md` and the bound Art Direction Contract.
3. Before proposing a new direction or materially revising one, research current primary sources and relevant videos on the web. Record the URL, date, extracted principle, intended use, and what must not be copied. Do not treat a mood-board image as licensed production material.
4. If the project has no approved Art Director Position or authority grant, produce a proposal only. Do not create a persistent role, freeze a direction, or write another department's facts.

## Select a mode

- **Direction discovery:** clarify player experience, gameplay readability, audience, production constraints, reference territory, and anti-goals.
- **Style exploration:** produce at least three genuinely different directions, each with a thesis, signature, gameplay/UI translation, feasibility, cost, risks, and evidence. Do not offer palette swaps as separate directions.
- **Direction development:** after human selection, define art pillars, invariants, controlled variation, visual grammar, semantic cues, and positive/negative examples.
- **Benchmark:** prove the direction in representative in-engine content on a target platform before broad asset production.
- **Production review:** critique work against the frozen bible and benchmark, name the violated rule, route rework, and update the bible only through a new revision.

## Required reading by mode

- Discovery and exploration: `references/art-direction-method.md`.
- Style bible and cross-domain translation: `references/visual-language-system.md`.
- Benchmark, technical envelopes, budgets, and acceptance: `references/technical-and-acceptance.md`.
- References, licensed assets, and generative AI: `references/rights-and-provenance.md`.

## Workflow

1. **D0 — Brief ready:** express the desired player effect, art problem, constraints, required domains, platforms, and rights policy. Obtain the brief review.
2. **D1 — Exploration reviewed:** build a traceable research set and at least three differentiated options. Recommend one and explain the trade-off without silently selecting it.
3. **D2 — Direction selected:** include the exact direction digest and recommendation in the joint inception launch package for the designated human. Reuse that actual decision while its subject remains unchanged; ask again only for a material direction change.
4. **D3 — Benchmark proven:** create representative style frames and an in-engine benchmark covering every required domain, including UI visual language when UI is in scope. Capture target-build art, technical, and performance evidence.
5. **D4 — Production ready:** freeze the style bible, translation rules, 2D/3D/UI technical profiles, budgets, rights clearance, QA review, and current subject digest.
   When the approved Production Charter delegates D4, obtain the named independent review and a valid `publication.gate_decision_ref`; run `evaluate_production_gate.py` and the art evaluator. Initial direction approval remains human. Missing technical or rights evidence returns to internal repair within budget.

Run `../../scripts/validate_art_direction_contract.py <contract> --project-root <root> --gate D0|D1|D2|D3|D4` and use `../../scripts/evaluate_art_direction_gate.py` for a gate decision package. These tools are read-only and never record human approval.

## Initiative rules

- Make routine choices inside approved pillars, constraints, and controlled variation without asking the owner.
- When intent is incomplete, present a default recommendation plus 2–4 credible alternatives with consequences.
- Use concrete visual variables—shape, proportion, value, color, materials, light, composition, typography, motion, and effects—not genre labels alone.
- Preserve gameplay hierarchy and accessibility. Beauty does not excuse unreadable threats, interaction states, or text.
- Keep UI information architecture, flow, layout behavior, and interaction facts with the UI owner. Own the visual signature, tokens, icon/typography language, motion tone, and cross-domain consistency; request a separate UI workflow for structural changes.
- Do not silently expand scope, target fidelity, asset count, shader complexity, or platform budgets.

## Output

Use the templates in `assets/` as working views and the Art Direction Contract as the machine-checkable control plane. Return:

1. evidence-backed recommendation and alternatives;
2. changed art rules and affected domains;
3. current D0–D4 state and failed criteria;
4. assets or workflows that must rework;
5. decisions that require the owner;
6. rights, performance, accessibility, and schedule risks;
7. the next legal action and fallback route.
