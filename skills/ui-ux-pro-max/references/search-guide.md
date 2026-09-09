# Search and persistence

The bundled Python scripts use the standard library. Resolve the skill root from the actual installed `SKILL.md`; the script resolves its data relative to itself and can run from any working directory. Try `python`, `python3`, or `py -3` if needed. If no interpreter is available, report that limitation and use relevant references; do not pretend a search ran.

## Invocation

For a standard Codex installation, these examples resolve the configured location. If the skill is loaded from a repository or another directory, replace the root with that actual absolute directory.

PowerShell:

```powershell
$uiSkillRoot = if ($env:CODEX_HOME) {
    Join-Path $env:CODEX_HOME 'skills/ui-ux-pro-max'
} else {
    Join-Path $env:USERPROFILE '.codex/skills/ui-ux-pro-max'
}
python (Join-Path $uiSkillRoot 'scripts/search.py') 'form validation error recovery' --domain ux -n 3
```

POSIX shell:

```sh
ui_skill_root="${CODEX_HOME:-$HOME/.codex}/skills/ui-ux-pro-max"
python3 "$ui_skill_root/scripts/search.py" 'form validation error recovery' --domain ux -n 3
```

The remaining PowerShell commands reuse `$uiSkillRoot`. Run `--help` for actual supported flags rather than assuming a feature exists.

## Choose a useful query

Use English product/task/tone keywords, for example a Chinese request for a dense operations dashboard becomes `internal operations dashboard dense clear`. Preserve business meaning; English retrieval does not change the deliverable language. A few focused queries are usually more informative than one query containing every desired quality.

| Need | Domain |
|---|---|
| Product patterns or style candidates | `product`, `style` |
| Semantic palette or font pairing | `color`, `typography` |
| Individual font families and coverage metadata | `google-fonts` |
| Forms, focus, navigation, feedback, accessibility | `ux` |
| Landing structure | `landing` |
| Data encoding | `chart` |
| Icon candidates | `icons` |
| GSAP presets when GSAP is actually relevant | `gsap` |
| React performance hints | `react` |
| App/native interface rules | `web` (historical name; reads `app-interface.csv`, not exclusively web guidance) |

Use `--domain` and `--stack` in separate calls; the current CLI gives stack mode precedence if both are supplied. `--design-system` also takes precedence and is not filtered by `--stack`.

For zero or irrelevant matches, retry once with broader terms or a different explicit domain. If still unhelpful, state that the recommendation is a reasoned fallback. Result ranking is not a confidence score or user research.

## Stack-specific search

Read the actual project manifests before selecting a stack. Available identifiers:

`react`, `nextjs`, `vue`, `svelte`, `astro`, `nuxtjs`, `nuxt-ui`, `angular`, `laravel`, `swiftui`, `react-native`, `flutter`, `jetpack-compose`, `html-tailwind`, `shadcn`, `threejs`, `javafx`, `wpf`, `winui`, `avalonia`, `uno`, `uwp`.

```powershell
python (Join-Path $uiSkillRoot 'scripts/search.py') 'form focus keyboard' --stack nextjs -n 3
```

For an unsupported engine such as Godot, use platform-neutral design guidance plus the project's engine conventions; do not claim a `godot` search exists. For unknown stacks, continue design reasoning and ask only when the implementation choice becomes necessary.

## Design-system candidates

Use when a new system is needed or the user requests alternatives. Read any existing tokens and design-system decisions first.

```powershell
python (Join-Path $uiSkillRoot 'scripts/search.py') 'internal analytics dashboard clear dense' --design-system -p 'Ops Console' -f markdown
```

Optional 1–10 dials: `--variance` biases style, `--motion` attaches a GSAP preset, and `--density` changes spacing recommendations. They are candidate tuning controls, not quality scores. A motion preset does not require installing GSAP, and a density choice must preserve usable hit regions and legibility.

Search output supports `--json` and `--full` (untruncated domain/stack text). Design-system mode supports `-f ascii`, `-f markdown`, or `--json`; its JSON has `design_system` and `persistence` fields.

## Save deliberately

Persist only when a project design artifact helps the requested work. Set `$uiProjectRoot` to the actual absolute project directory and always pass it explicitly:

```powershell
$uiProjectRoot = 'D:/Projects/ops-console'
python (Join-Path $uiSkillRoot 'scripts/search.py') 'internal analytics dashboard clear dense' --design-system --persist -p 'ops-console' --output-dir $uiProjectRoot --page 'dashboard'
```

The tool creates `design-system/<project-slug>/MASTER.md` and, with `--page`, `pages/<page-slug>.md`. Reconcile the generated draft with actual requirements before treating it as authoritative.

Important current behavior:

- Existing `MASTER.md` without `--force` causes the **entire persistence operation to skip**, including a requested new page. Read and edit the relevant page file directly from the existing system; do not use `--force` merely to create a page.
- `--force` overwrites the master and the requested page if it exists. Use it only when replacement is within the user's authorized scope and the existing decisions have been reconciled. Prefer a targeted edit for small updates.
- Slugs preserve only ASCII letters, digits, underscores, and hyphens. Chinese-only project names fall back to `default`, and Chinese-only page names to `page`; different names can collide. Use an explicit stable ASCII project/page identifier and inspect returned paths. Keep the human-facing Chinese title in the document if needed.
- Read `MASTER.md`, then the relevant `pages/<page-slug>.md`. Only explicit page differences override the master; everything else inherits. Some generated prose has legacy paths omitting the project slug; use the actual returned `design_system_dir` and file paths.

Do not silently retry a failed write in another directory. Explain the failed path, retain the candidate in the response when useful, and resolve the destination before writing again.
