# Optional Style Direction Modules

The canonical machine-readable list is [`../style-directions/registry.yaml`](../style-directions/registry.yaml). The modules under `../style-directions/` are reusable visual hypotheses that the Art Director may bring into D1 exploration. This file explains how to interpret the list and translate a selected module into a direction option; it is not a second registry.

## Selection and governance

- Read a module only when its visual thesis fits the project brief, player effect, camera, readability needs, and production envelope.
- Read the registry before choosing a module. Treat a missing entry, duplicate ID, invalid path, stale digest, or failed registry validation as unavailable until repaired.
- Keep the module beside at least two materially different options. A module cannot satisfy the D1 research requirement by itself, replace the Art Director's recommendation, or make the D2 decision.
- Convert a module's medium rules into the Contract's direction option fields: thesis, signature, player effect, gameplay/UI translation, feasibility, cost, risks, evidence, and anti-copy boundary.
- Treat generated images as exploration or benchmark evidence until source rights, technical integration, target-platform readability, and the D3/D4 gates are complete.
- Project-specific restrictions inside a module apply only when that project is explicitly in scope. They must not become general art-direction rules.

## Registered module: palette-knife-impasto

Path: [`../style-directions/palette-knife-impasto/SKILL.md`](../style-directions/palette-knife-impasto/SKILL.md)

Source: the user's local `palette-knife-impasto` Skill, originally maintained at `https://github.com/wu-jiuqi/palette-knife-impasto`, source commit `097e9d4bb864ccd1ca3eef3f240bdad0ab212ac9` at synchronization time. The source snapshot has no `LICENSE` file, so this provenance record is not a rights-clearance decision; keep generated and reference material subject to the project's rights review.

Use this module when a project benefits from a tactile, painterly visual direction: thick paint volume, directional palette-knife planes, selective coarse-canvas exposure, clear value grouping, and concentrated detail around the focal subject. The project's approved palette, subject, mood, and composition always override the module's defaults.

For the Art Direction Contract, translate the module across the declared domains. A typical translation is:

| Domain | Directional expression | Readability safeguard |
|---|---|---|
| Characters | Broad planes and broken edges preserve a strong silhouette; fine impasto is concentrated on identity cues. | Keep pose, faction cues, and combat telegraphs legible at gameplay distance. |
| Environments | Large value masses establish space; canvas appears only in thin or scraped passages. | Keep traversal, cover, interactables, and depth layers separated by value and shape. |
| Props | Material-specific highlights remain visible inside the painted treatment. | Preserve interaction affordances and silhouette holes; do not let texture erase function. |
| VFX / animation | Paint-like arcs and impact planes follow the project's motion grammar. | Pair color with shape, timing, or iconography; never encode critical state in color alone. |
| UI | Palette, edge, surface, icon, and typography tokens echo the world without baking text into images. | UI structure, layout, focus, localization, and interaction remain with the UI owner. |

The module's `references/mindrift-profile.md` is an explicit Mindrift-only add-on. Do not load it for another project merely because the project also uses thick oil paint.
