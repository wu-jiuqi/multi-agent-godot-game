# Native and mobile interface checks

Read for native/mobile work alongside [shared acceptance](acceptance.md). These are platform heuristics, not a substitute for verifying the target platform's current requirements. Do not require mobile-only features or new themes for a desktop-only task.

| Area | Inspect on the supported devices |
|---|---|
| Hit regions | Follow the platform's touch guidance (commonly 44×44pt on iOS and 48×48dp on Android); distinguish logical units from physical pixels. Extend small icons' hit regions without overlapping neighboring controls. These are not WCAG web minimums. |
| System chrome | Keep essential content and actions clear of safe areas, notches, system bars, and gesture regions. Scroll insets must account for fixed bars. |
| On-screen keyboard | Focused fields, validation messages, and the next action remain reachable when the keyboard opens; dismissal preserves entered values. |
| Text scaling | Exercise supported large text settings and real localized strings. Let labels wrap or layouts adapt; do not shrink all text to preserve a mockup. |
| Navigation | Follow the platform's back behavior. Preserve drafts, selection, filters, and scroll position where expected. Avoid competing nested tap/drag/swipe regions. |
| Feedback | Show press feedback promptly; use native easing and haptics only where helpful. Instant transitions and reduced motion are valid choices. |
| Semantics | Prefer platform controls with accessible names, roles, values, and states. Check accessibility traversal and focus restoration after dismissing a modal. |
| Adaptive layout | Test supported phone/tablet widths and orientations relevant to the change. Reflow content rather than merely scaling the phone view. |
| Themes | Inspect every supported theme affected by the change, including overlay surfaces and error/focus states. Do not add dark mode just to satisfy a checklist. |
| Assets | Keep icon weight, optical alignment, and selection treatment coherent. Use official supplied brand assets and appropriate raster resolutions; custom and pixel-art interfaces need not use vector-only assets. |

Use the contrast distinctions in [shared acceptance](acceptance.md): secondary text is not automatically exempt from ordinary text contrast, and non-text icons do not use small-text versus large-text thresholds.

For delivery, record the actual device/simulator, orientation, text setting, and flow exercised. A responsive browser viewport alone does not prove native safe-area, keyboard, or screen-reader behavior.
