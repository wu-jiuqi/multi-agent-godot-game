# Technical Profiles and Acceptance

## Benchmark before scale

The benchmark is the smallest representative, playable or inspectable in-engine scene that can disprove the direction. It is not a polished isolated render. Cover the hardest relevant combination of camera distance, character/environment, interactive props, VFX, animation, lighting, and UI overlay. Record the target build, hardware/platform, scenario, captures, and measurements.

Pass D3 only when:

- every required visual domain appears or has a justified equivalent;
- gameplay targets, hazards, interactables, feedback, and hierarchy remain readable in motion;
- representative source assets survive the actual import path;
- measured budgets pass on the declared target context;
- the Art Director and Technical Integrator review the same contract digest;
- failure modes and rework ownership are explicit.

## 2D profile

Freeze source and runtime formats, color space, premultiplied/straight alpha policy, filtering, mipmaps, compression, maximum dimensions, atlas policy, pixels-per-unit or logical scale, trimming/pivot rules, and naming/versioning. Distinguish pixel art from filtered illustration. Test fringing, bleeding, scaling, texture memory, and readability at the actual camera/UI scale.

## 3D profile

Freeze units, axes, origin/pivot, source/interchange formats, mesh density by screen role, material/texture limits, UV and texel-density rules, normals/tangents, rig/skeleton constraints, LOD/HLOD/visibility policy, collision policy, and animation export. Validate silhouette and shading after import, not only in the DCC tool.

## UI profile

Freeze reference viewports, scale and safe-area policy, typography and fallback references, visual token source, icon-grid/raster policy, component visual states, contrast policy, localization/RTL constraints, and motion limits. This profile does not replace a UI Screen/Flow Contract.

## Budgets

Budgets must be named, measurable, scenario-bound, and owned. Useful metrics include texture memory, texture dimension, triangle/vertex count, material or shader count, draw calls, transparent overdraw, bone count, particles, VFX fill cost, animation memory, UI batches, font atlas memory, and frame time. A generic “optimized” label is not evidence.

## Godot evidence

- Commit authored source assets and required `.import` sidecars when they carry import configuration; treat `.godot/imported/` as cache.
- Use the correct texture import mode for 2D versus 3D and account for mipmap memory.
- Store benchmark structure in preset `.tscn` scenes and `.tres` resources when practical; avoid reconstructing a whole benchmark tree dynamically.
- Use Theme resources for shared UI visual tokens and styles. Keep UI scene layout and interaction ownership separate.
- For 3D, validate import configuration, material overrides, LOD/visibility ranges, lighting, and target-renderer behavior in engine.

Official Godot references:

- Import process: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/import_process.html
- Image import: https://docs.godotengine.org/en/latest/tutorials/assets_pipeline/importing_images.html
- 3D import configuration: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html
- Visibility ranges/HLOD: https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html
- GUI skinning and Theme Editor: https://docs.godotengine.org/en/latest/tutorials/ui/gui_skinning.html and https://docs.godotengine.org/en/stable/tutorials/ui/gui_using_theme_editor.html
- GPU optimization: https://docs.godotengine.org/en/latest/tutorials/performance/gpu_optimization.html
