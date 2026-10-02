# Visual Language System

## Style bible structure

The bible is a compact rule system. For each element, state the rule, its player-facing purpose, allowed variation, prohibited drift, and a positive/negative example reference.

Required elements:

- art pillars and player effect;
- silhouette, shape families, proportion, line/edge treatment;
- value hierarchy, palette roles, contrast, saturation, and color scripts;
- materials, texture frequency, wear, roughness, and surface storytelling;
- lighting hierarchy, atmosphere, shadow behavior, post effects, and camera/composition;
- detail-density zones, focal hierarchy, and visual noise limits;
- typography, iconography, framing, patterns, marks, and graphic composition;
- motion cadence, easing character, impact rhythm, and transition tone;
- VFX shapes, timing, color/value priority, additive coverage, and gameplay telegraphing;
- UI visual tokens, component states, hierarchy, and accessibility constraints.

Define **invariants** that never change and **controlled variables** that may change by faction, biome, rarity, time, mood, or platform. Variation without invariants becomes drift; invariants without controlled variation create repetition.

## Cross-domain translation

Every important rule needs a translation matrix. For example, a “compressed mechanical tension” pillar might appear as forward-leaning character silhouettes, interlocking environment diagonals, ratcheted UI corners, short anticipation/fast-release motion, and VFX arcs that converge before impact. The expression changes; the semantic meaning remains.

At minimum, translate each pillar into every domain declared in the Contract. A domain mapping includes:

- the source rule and intended player effect;
- the domain-specific expression;
- a positive evidence reference;
- a prohibited expression or known collision with another domain;
- a readability or accessibility safeguard.

## Semantic redundancy

Do not encode critical state in color alone. Combine at least two channels—shape, position, animation, icon, text, sound, or pattern—for threats, interactability, ownership, rarity, selection, disabled state, and success/failure. Preserve these meanings from world assets into UI.

## UI boundary

The Art Director owns UI visual language: typography family and hierarchy, color tokens, icon and illustration style, shape/edge system, surface treatment, motion tone, and visual cohesion with the game world. The UI owner retains information architecture, screen/flow facts, responsive layout behavior, controls, focus order, localization layout, and interaction logic. A visual proposal that changes those facts becomes a separate UI change request.

When UI is a required domain, record this visual language in a separate `game-production-ui-visual/v1` UI Visual Contract. It must point to the read-only Screen/Flow Contract, include component shape and surface rules, fonts, icons, ornaments, a six-state component matrix (`normal`, `hover`, `pressed`, `focus`, `disabled`, `error`), Theme/resource mappings, Style Frames, target captures, and the Art Director's review of the UI body. A background or wireframe alone is not a UI visual deliverable; default controls are greybox until these outputs exist.

## Research basis

For UI design, follow the [Penpot MCP workflow](../../../workflows/ui-production.md). The visual-system prototype is authored in Penpot after product identity, overall style and UX are resolved. Save file/page/shape links and local snapshots of tokens, component states, key screens and interaction evidence. Theme/resource mappings and target-build captures belong to the later engine stage; Penpot-only design can be accepted independently.

- GDC, *Art Direction for AAA UI*: build a coherent UI art concept from shape language, textures, signature elements, composition, and static/motion/interactive mockups. https://gdcvault.com/play/1025498/Art-Direction-for-AAA
- GDC, *Graphic Design is Key*: typography, iconography, logo, color, graphic elements, key art, motion, and menus form one visual signature. https://www.gdcvault.com/play/1023276/Art-Direction-Graphic-Design-is
- GDC, *Art Directing VFX for Stylized Games*: translate the project art direction into explicit VFX pillars instead of allowing effects to become a separate visual style. https://www.gdcvault.com/play/1023999/Art-Directing-VFX-for-Stylized
- W3C WCAG 2.2 guidance for text and non-text contrast informs the accessibility safeguard, while project/platform requirements remain authoritative. https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html and https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
