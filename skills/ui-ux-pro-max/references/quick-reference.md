# Focused rule index

Read only the categories relevant to the task. This is a curated decision guide, not a verbatim mirror of the CSVs. Database examples and numeric heuristics need checking against the platform, project constraints, and [acceptance guidance](acceptance.md).

| Category | Decisions that matter | Search domain and English keywords |
|---|---|---|
| Accessibility | Semantic controls; useful names; logical focus order; visible focus; text alternatives; meaning beyond color. Use measured contrast, not guesses from a palette name. | `ux`: `keyboard focus contrast labels` |
| Interaction | Reachable hit regions; no hover-only essential action; immediate feedback; duplicate-submit prevention; visible recovery from failure. | `ux`: `touch target loading error feedback` |
| Performance | Reserve media dimensions; prioritize visible critical media; lazy-load offscreen media; measure before adding virtualization or animation libraries. Avoid lazy-loading the primary above-the-fold image by default. | `ux`: `image layout shift virtualize` |
| Visual direction | Fit the content, audience, and reference. Preserve an existing system. Distinctiveness can come from typography and composition rather than extra effects. | `style` / `product`: product and tone keywords |
| Layout | Reflow at narrow widths and zoom; keep actions visible; handle long strings and content growth. Horizontal scrolling can be appropriate inside a labeled data table or intentional gallery. | `ux`: `responsive overflow breakpoint` |
| Typography and color | Semantic roles and predictable hierarchy; real language coverage; readable measure and density; independently checked supported themes. Base size and spacing scales are starting choices, not universal standards. | `typography` / `color`: audience, language, tone |
| Motion | Explain change and preserve spatial continuity. Avoid layout jank and unnecessary waiting. Respect reduced motion; an instant update can be correct. | `ux`: `reduced motion animation`; `gsap` only for an actual GSAP need |
| Forms | Persistent labels; suitable input types; timely validation; actionable errors tied to fields; retain input and offer retry. Do not interrupt every keystroke with premature errors. | `ux`: `form validation error recovery` |
| Navigation | Clear current location; predictable back; meaningful labels; appropriate URL/state restoration. Choose tabs, sidebar, or bottom navigation based on actual hierarchy and platform. | `ux`: `navigation back state preservation` |
| Charts and tables | Match encoding to the comparison/task; label units and time range; distinguish zero, missing, loading, and error. Provide accessible values/summaries and keyboard access to interactive details. | `chart`: `comparison trend distribution`; `ux`: `table sorting` |

Prioritize by actual user impact: a misleading chart can be a blocker, and a minor color inconsistency can be cosmetic. Do not assign severity solely from a fixed category ranking.

For native conventions use [platform checks](pro-rules.md). For new flows or diagnosis use [UX workflow](ux-workflow.md). Runtime checks and standards sources live in [acceptance](acceptance.md).
