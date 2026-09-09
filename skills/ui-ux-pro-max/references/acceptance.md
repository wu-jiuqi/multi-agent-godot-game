# UI/UX acceptance

Read before handing off changed UI or reporting a review. Select checks based on the affected surface, supported platforms, and agreed scope; a button fix does not require auditing the entire app.

## Evidence and completion

Use the project's available browser, app runtime, simulator, and existing tests. For substantial visual work, inspect the rendered surface at a representative wide and narrow size, then exercise its main path and a relevant failure/recovery path. For a small fix, reproduce the reported state and inspect the neighboring behavior it can affect.

Record which viewport/device, theme, input method, state, and action you actually checked. Distinguish **passed**, **failed**, **not tested**, and **not applicable**. A lint/build result is not visual evidence; a screenshot is not proof of keyboard operation; an automated accessibility scan is not full conformance testing.

Fix concrete failures within scope, rerun affected checks, and finish when the stated criteria pass. If a runtime or service is unavailable, state the precise limit and a reproducible manual check. Do not label an unavailable check as passed or block a useful source review indefinitely.

## Shared interaction and visual checks

- The main action is discoverable, performs the represented operation, and produces a truthful result. Relevant empty/loading/error/success states offer appropriate next steps.
- Navigation, cancellation, retry, and repeated activation behave predictably. Forms retain correct input after failure. Modal focus enters appropriately, stays within the modal while open, and returns to a sensible control on close; dismissal follows platform expectations.
- Controls have meaningful names, roles, values, and states; labels persist where needed. Keyboard users can complete the web/desktop task with visible, unobscured focus and no trap.
- Real content fits: long titles, Chinese and Latin text where relevant, large values, missing values, and selected/disabled/error states. Supplied assets load and remain legible.
- Hierarchy, spacing, token use, icon treatment, and density match the reference or existing system. Check the whole changed surface, not just its first viewport.
- Supported themes and reduced-motion settings remain usable. Do not add unrequested themes or mandatory animation to satisfy a checklist.
- Relevant build/type/lint checks pass if code changed. Inspect runtime errors and broken assets where runtime access exists; broaden testing only for a concrete remaining concern.

## Web-specific baselines

These checks support accessible implementation; they are not a claim of comprehensive WCAG conformance. Verify the applicable standard when formal compliance is requested.

| Concern | Check |
|---|---|
| Text contrast | Normal text, including secondary/helper text, needs at least 4.5:1 at WCAG AA. The 3:1 threshold applies to large text (at least 18pt regular or 14pt bold), not to lower visual importance. Account for actual backgrounds/opacity and applicable exceptions. |
| Non-text contrast | Essential visual information identifying controls, states, and graphical objects generally needs 3:1 against adjacent colors under SC 1.4.11, subject to its exceptions. Icon size does not turn this into the text-contrast rule. |
| Pointer targets | WCAG 2.2 AA SC 2.5.8 uses 24×24 CSS px or an applicable exception, including specified spacing conditions. Larger targets can improve touch usability; do not present 44px as the universal AA minimum or treat an arbitrary 8px gap as automatically sufficient. |
| Reflow | For horizontally written content, check at 320 CSS px width (or equivalent zoom) without loss or two-dimensional page scrolling. Content that requires two-dimensional layout, such as some tables/maps, has exceptions; preserve usable contained scrolling. |
| Responsive behavior | Test near breakpoints and with realistic content. Fixed bars must not obscure actions or focused controls. Keep zoom enabled; test text enlargement as relevant. |
| Motion and latency | Input feedback is prompt; reduced-motion preferences are respected. Avoid unnecessary layout shifts. Measure performance before claiming metric thresholds are met. |

Use semantic HTML first. Add ARIA only where the native element does not express the required behavior; do not invent custom keyboard widgets when an existing accessible component fits.

## Sources

Official W3C explanations checked on 2026-09-09. Recheck for the standard/version required by the project:

- [SC 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [SC 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
- [SC 2.5.8 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
- [SC 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)

For native mobile devices, add [platform checks](pro-rules.md); web CSS pixels and native logical units are not interchangeable.
