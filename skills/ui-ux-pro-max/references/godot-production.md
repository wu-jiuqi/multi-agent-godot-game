# Godot UI production reference

If the visual system is being made in Codex through Penpot, complete
[penpot-handoff.md](penpot-handoff.md) first. That handoff resolves product inputs, identity,
visual direction, and UX ownership before Godot receives a screen or component mapping.
This reference governs the engine implementation after that handoff. A Penpot-only request
stops at Penpot structural/visual acceptance and does not require this reference's ten-part
Godot output, scenes, target build, or runtime acceptance evidence.

This reference is the Godot-specific execution contract for `ui-ux-pro-max`. It applies
when the target project is Godot and complements the project's own contracts, scene rules,
and approval records. It keeps a UI useful to players, replaceable by another artist, and
verifiable in a target build.

## 1. Choose the task level first

Select one level before writing a scene or changing a resource. State the reason and what the
level does **not** prove.

| Level | Purpose | Required boundary |
|---|---|---|
| `prototype` | Test a layout, flow, or interaction idea. | Placeholders and simplified Theme/motion are allowed; never claim visual completion. |
| `greybox` | Test the complete structure, states, and interaction path. | Placeholders are allowed only with replacement location, reason, owner, and replacement acceptance. |
| `style-pass` | Apply an approved visual direction to Theme, StyleBox, fonts, icons, ornaments, and states. | Provide visual tokens, state coverage, asset mapping, motion specification, and key-screen captures. |
| `final` | Enter formal UI acceptance. | Both contracts, resources, states, build, interaction checks, target captures, automatic checks, and human visual review must be current; all four UI rework queues must be closed. |

A small reversible fix can remain at its current level. Do not turn a local change into a
full `final` exercise unless its scope or acceptance actually changed.

## 2. Input gate and question budget

At Step 0 read, when present:

- `project.godot`, the project-locked Godot version, renderer, addons, input map and build settings;
- the current UI scenes, Theme/StyleBox/font/icon resources and import rules;
- the target platform, baseline resolution, stretch/aspect policy and minimum resolution;
- the UI Screen/Flow Contract, UI Visual Contract, Art Direction Contract and their revisions/digests;
- declared mouse, keyboard, gamepad, touch, localization, RTL and reduced-motion support;
- the performance budget and the requested task level.

If an absent fact can change project direction, scope, target platform, or acceptance, ask a
single grouped set of no more than **five** questions. Ask for the highest-impact decisions
first. If the detail is reversible, choose a project-compatible default and list it under
assumptions. Never expand scope to compensate for an unknown.

## 3. The dual-contract boundary

The UI Screen/Flow Contract and UI Visual Contract are complementary, not interchangeable:

| Owner | Owns | Must not silently change |
|---|---|---|
| UI/UX | Information architecture, Screen/Flow, layout and responsive behavior, safe areas, focus order, keyboard/gamepad/touch behavior, localization and interaction logic. | Visual identity, final shape/material/font/icon direction. |
| Art Director / UI Visual | Visual identity, shape and material language, color tokens, typography/iconography, ornaments, component states, motion tone, Style Frames and visual acceptance. | Screen/Flow, layout behavior, focus order or interaction facts. |
| Godot implementation | Authored node/scene structure, Theme/StyleBox/font/icon/resource bindings, reusable components, signals/data adapters, animation/audio/effects integration, runtime state switching, tests and target-build evidence. | Project direction, either upstream contract, or a missing approval. |

Read both contracts before a `style-pass` or `final` implementation. A missing UI Visual
Contract permits only a `prototype`, `greybox`, or explicitly labelled style proposal. A
project with no Art Director may receive a lightweight `ui_visual_brief`, but it must say
“待人类批准” and cannot freeze the final visual direction.

Route conflicts instead of hiding them in code:

- `UI_VISUAL` → Art Director / UI Visual;
- `UI_STRUCTURE` → UI/UX;
- `UI_TECH` → Godot implementation;
- `UI_READABILITY` → Art Director and UI/UX joint review.

## 4. Ordered production workflow

### Step 0 — Confirm project state

Record Godot version, renderer, target platform, baseline and minimum viewport, stretch policy,
input devices, current scenes/resources, both contract revisions, and the selected task level.
Do not use an API that is only available in another Godot version.

### Step 1 — Analyze the player task

Describe the player goal, entry point, main actions, key screens, success signal, recovery path,
loading/empty/success/error/disabled states, input methods, accessibility constraints and
localization risks. Keep structural facts with Screen/Flow.

### Step 2 — Resolve visual input

If a UI Visual Contract exists, consume its visual identity, shape/material rules, color and
typography tokens, iconography, ornaments, component state matrix, motion language, Theme
references, Style Frames and accessibility constraints. If it does not, label every visual
choice as a proposal or placeholder and list the human decision required.

### Step 3 — Design Screen/Flow

List screens, transitions, enter/exit/back behavior, normal/loading/empty/error/success paths,
keyboard focus and gamepad navigation, touch behavior, safe areas, long-text behavior, RTL
mirroring and responsive constraints. Do not invent a visual direction while doing this step.

### Step 4 — Produce the asset manifest

Do not hand off bare filenames. Every asset record has at least:

```yaml
asset_id: ui:<project>:<stable-id>
name: <human-readable-name>
category: required-production | theme-stylebox | placeholder | optional-enhancement
purpose: <player-facing use>
source_uri: <editable source or null>
runtime_uri: <imported/runtime path or null>
status: available | required | to-create | placeholder | optional
dimensions: {width: <int>, height: <int>, unit: px}
slice_or_nine_patch: <margins, regions, or null>
import: {filter: <mode>, compression: <mode>, mipmaps: <bool>, recipe: <digest>}
rights: <license/source/provenance>
fallback: <static resource, text, or explicit none>
owner: <position or person>
version: <revision or sha256>
```

Classify each item as required production, expressible by Theme/StyleBox, temporary
placeholder, or optional enhancement. If no asset tool or real source exists, leave the
status `required`/`to-create`/`placeholder`; never claim a PNG, font, sound, or icon exists.
Greybox records also include `replacement_location`, `placeholder_reason`, and
`replacement_acceptance`.

### Step 5 — Author a fixed node structure

Prefer editor-authored, serialized `.tscn`/`.tres` resources and semantic Control nodes:
`Control`, `CanvasLayer`, `Container` variants, `MarginContainer`, `PanelContainer`,
`Button`, `Label`, `RichTextLabel`, `TextureRect`, `NinePatchRect`, `TextureButton`,
`TextureProgressBar`, `HSlider`, `ScrollContainer`, `TabContainer`, `AnimationPlayer`,
`AudioStreamPlayer`, and `GPUParticles2D` where justified. Use anchors, containers and size
flags instead of hand-positioned coordinates.

Keep `Button` semantics when a Theme can provide the visual. Use `TextureButton` for an
image-driven control only when its focus, tooltip and accessibility remain explicit. Use
`NinePatchRect` for scalable texture panels, `TextureRect` for backgrounds/illustration, and
`ColorRect` for masks, placeholders and debug surfaces. `Sprite2D` is not the default for
Control UI.

Runtime creation is allowed only for data-sized lists, notifications/drops, object pools,
approved procedural generation, or instantiation of an existing `PackedScene` when it is
clearly safer. Even then instantiate the authored component; do not reconstruct its fixed
tree in a script. Keep visual, business data and global management in separate boundaries.

### Step 6 — Define component APIs

Prefer an independent `.tscn` for reusable components such as `GameButton`, `GamePanel`,
`PopupWindow`, `Tooltip`, `ProgressBar`, `Notification`, `TabButton`, `ResourceMeter`, and
`LoadingIndicator`. Each component documents:

- visual resource slots and Theme type variations;
- `@export` parameters and localization/text interfaces;
- signals, input behavior, focus/accessibility label and data methods;
- the state interface and fallback when a resource is missing;
- animation and audio hooks.

At minimum declare `normal`, `hover`, `pressed`, `focus`, `disabled`, and `error`. Add
`loading`, `selected`, `success`, `empty`, `warning`, `locked`, or `cooldown` when the task
needs them; for an inapplicable state, retain it with `applicable: false` and a reason.
Components do not own game business data. Use signals or explicit methods. For audio, emit
`ui_sound_requested(event_name, payload)`, inject an `AudioStream`, or call a project Audio
Service; never hard-code global audio paths or repeat sounds from `_process()`.

### Step 7 — Specify motion and feedback

Use `AnimationPlayer` for reusable multi-track, enter/exit, looped, designer-tuned and
audio/particle-synchronized motion. Use a `Tween` for one-shot fade, scale, offset, number
change and brief emphasis. For every meaningful interaction record a Motion Token:

```yaml
duration_ms: <int>
delay_ms: <int>
easing: <name>
overshoot: <number>
transition: <name>
interrupt: restart | reverse | blend | snap
reduced_motion: static | opacity_only | shortened
```

Cover appearance, hover (and a touch alternative), pressed, visible focus, and reward/emphasis.
Feedback must not depend on color alone. Support reduced-motion, pause, interruption, Tween
conflict handling, and a static fallback for missing effects. Animate a wrapper when changing a
Container's size/position would cause unwanted layout reflow. Never let uncontrolled Tweens
compete for one property.

### Step 8 — Gate optional effects

Shaders and particles are optional. Before adding one, record the information benefit,
readability impact, transparency/overdraw cost, low-end cost, disable switch, reduced-motion
behavior and static fallback. Expose a quality tier and enabled/disabled state, and provide a
mobile/low-end downgrade. An effect is not evidence of a completed visual direction.

### Step 9 — Capture verification evidence

Run checks that match the declared project support and mark untested platforms. Evidence should
cover:

1. **Project/scene:** import, scene load, main-scene startup, node paths, resource references,
   and fixed structure serialized.
2. **Interaction:** each declared `normal`, `hover`, `pressed`, `focus`, `disabled`, `error`,
   `loading`, `empty`, and `success` state.
3. **Input:** mouse, keyboard, gamepad and touch only where supported, with omissions recorded.
4. **Responsive:** baseline, wide (for example 21:9), narrow/tall, target minimum, and mobile
   portrait when mobile is in scope.
5. **Localization:** long text, CJK and fallback fonts, RTL, wrapping, text scaling and no
   important fixed-width truncation.
6. **Accessibility:** visible focus, non-color state redundancy, contrast, touch target size,
   reduced-motion, keyboard/gamepad operation, and redundant text/icon/shape/audio feedback.
7. **Resource replacement:** swap one legal Theme/asset resource and show that structure and
   business logic remain unchanged.
8. **Performance:** shader/particle count, UI batches/overdraw, font/icon cost, target frame
   time and animation stutter where applicable.
9. **Visual capture:** key screen/state screenshots or recordings naming target resolution,
   build, state, UI Visual Contract revision and benchmark digest.

Automation may verify structure, references, digests, assets and evidence presence. It cannot
decide aesthetic quality or replace human visual review.

### 4.1 Benchmark page and evidence contract

The first complete page is the proof of the workflow. Keep these artifacts together under the
project's UI evidence directory:

```text
task-definition.yaml       # goal, information priority, operation path, recovery
visual-target.md           # references, concrete observations, static target URI
visual-sample/             # panel, primary/secondary button, heading/body at target size
asset-usage.yaml           # display and stretch rules, safe areas, provenance, status
benchmark-page.md          # real-use page, build and target viewport
interaction-recording.*    # actual runtime interaction, not an editor mock-up
acceptance.yaml            # function / visual / motion-export conclusions separately
```

The benchmark page must be either a real game screen or a clearly labelled themed sample with a
declared task. A component lab, generated target image, headless scene load, or successful export
does not substitute for the runtime page. Capture the real build at the target resolution and
exercise at least: fast enter/exit, repeated activation, press-then-drag-out cancellation,
keyboard focus/navigation, disabling during animation, reopening after close, and window resize.
Record unsupported input devices and unavailable capture tools as unverified rather than passing
them by implication.

Keep three acceptance results independent:

| Result | Proves | Does not prove |
|---|---|---|
| `functional` | controls, focus, paths, recovery and business result | visual quality or motion polish |
| `visual` | runtime composition against the static target at the declared size | keyboard semantics or export parity |
| `motion_export` | interruption, reduced-motion, sound/effect timing and exported-build parity | that the page is visually approved |

An exported executable is a delivery artifact only after all three rows have evidence. A missing
row routes to `UI_TECH` when the evidence cannot be produced and to `UI_READABILITY` or
`UI_VISUAL` when the page fails review.

### 4.2 Godot 4.7.1 visual-only transform policy

For Godot 4.7.1, verify the actual engine API before implementation and document the choice for
each animated control:

```text
offset_transform_enabled
offset_transform_position
offset_transform_scale
offset_transform_visual_only
```

Use `offset_transform_visual_only = true` for small hover/pressed visual juice when the input
rectangle must remain stable. Use `false` only when the moved hit area is intentional and the
focus/hover path is tested at the new position. If the project targets an older engine or the
property is unavailable, put layout in an outer authored control and animate an inner visual
control. Do not let a second Tween or layout pass compete for the same property; stop/reconcile
the old tween before starting a new one.

Separate `button_down`, `button_up`, and `pressed`: the first two are physical feedback and the
last is the accepted activation according to the control's `action_mode`. A release after the
pointer leaves the button must cancel the action. A successful business result gets its own
feedback after the operation completes.

## 5. Fixed handoff output

For every UI request, return these ten sections in this order. If a section is not applicable,
write the reason instead of silently omitting it.

1. **UI 任务级别** — `prototype` / `greybox` / `style-pass` / `final` and reason.
2. **输入和假设** — known inputs, missing inputs, assumptions and human decisions.
3. **UI 视觉方案** — identity, color tokens, typography, iconography, shape/material/
   ornament, motion tone and accessibility.
4. **Screen / Flow 方案** — screens, flow, states, layout, responsive, focus and input.
5. **资产 Manifest** — required, Theme/StyleBox, placeholders, enhancements, import, rights
   and fallback.
6. **Godot 节点结构** — scene tree, sub-scenes, Theme/resources, serialized files and any
   runtime instances with their reason.
7. **组件 API** — exports, signals, states, data, audio, animation and accessibility hooks.
8. **动画和特效** — AnimationPlayer/Tween rationale, Motion Tokens, shader/particle/audio,
   reduced-motion and platform downgrade.
9. **实现和测试** — files, order, automatic checks, smoke test, resolutions, input devices
   and screenshot/recording evidence.
10. **验收结论** — exactly one `greybox`, `implementation_ready`, `review_pending`,
    `approved`, or `blocked`, plus a required failure route when applicable.

## 6. Acceptance and return routes

`implementation_ready` means the authored structure and bindings are ready for the named
review; it does not mean visual approval. `review_pending` means evidence exists and a human
or specialist review is outstanding. `approved` requires current contracts, evidence and no
open return code. `blocked` requires a concrete missing input, failed check, or exhausted
repair path; state the owner and the next action.

Never call a default Button/Panel/StyleBoxFlat, background texture, or runnable script a
commercially complete UI. Do not rebuild fixed UI at runtime, use a single UI manager for all
logic, hard-code business data or resource paths without fallback, fabricate absent assets,
force every component to use a shader/particle, ignore input/localization/accessibility, or
claim D3/D4 without a target build and human visual review.

## Legacy Figma compatibility

This engine reference is Penpot-first. Existing Figma handoffs remain readable through [figma-handoff.md](figma-handoff.md), but new visual-system work follows [penpot-handoff.md](penpot-handoff.md).
