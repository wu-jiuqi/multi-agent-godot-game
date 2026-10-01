# Codex Figma UI 管线变更

## 问题

原 UI 管线以 Godot 场景和运行时证据为主要入口，产品命名、视觉方向、UX 来源和视觉原型之间没有固定的前置顺序，容易让实现者在缺少产品决定时自行补视觉事实。

## 结论

UI 默认采用四个前置阶段：

1. 读取可用的 brief、PRD、GDD 等资料，记录来源并整理产品标题与 slogan；
2. 确认产品名、玩家可见标题、slogan 和整体视觉风格要求；
3. PRD 已包含 UX 时复用原流程，否则只补齐缺失的 Screen/Flow、状态和恢复路径；
4. 使用 Codex Figma 插件制作视觉系统、组件状态、关键屏幕和可点击原型。

Figma 交接通过后，才按需要进入 Godot 实施。Figma-only 任务不需要 Godot 工程、目标构建或十段引擎交付。

## 关键理由

- 产品身份和视觉方向必须先于视觉系统写入；
- PRD 已有 UX 时重复设计会产生竞争事实源；
- Figma 文件与节点映射能让视觉系统可复查、可评审、可交接；
- Figma 云端 URL 不是可验证文件摘要，Contract 改为要求项目本地快照的 SHA-256；
- Godot 固定 UI 仍优先使用编辑器预置节点并序列化到 `.tscn`/`.tres`，运行时不重建固定树。

## 做出的决定

- `figma_prototype` 成为 UI Visual Contract 的视觉系统交接记录，包含 `file_key`、Frame node ID、设计系统、本地快照、原型链接和评审证据。
- 工具以项目可选的 `tool:figma-codex-plugin` 绑定登记；默认 fixture 工具注册表不伪造宿主插件版本、来源摘要或回滚能力。
- `--ui-figma-only` 只检查完整 Figma 交接就绪度；`implementation_ready` 不等于 Godot 或 D3/D4 完成。
- UI 生产 Agent 同时承担 Figma 前置流程协调和后续 Godot 实施交接，不新增固定岗位。

## 后续行动

- 在真实项目中验证 Figma 文件创建/编辑、组件库、原型走查、本地快照和评审证据的可重复性；
- 使用 `--ui-figma-only` 完成设计交接后，再运行 Godot 场景、输入、可访问性、性能和目标构建检查；
- 真实项目验证后再决定是否将工作流从 `draft` 提升为稳定版本并制作 alpha.11 发布包。

## 未解决问题

- 宿主 Codex Figma 工具的实际版本和权限快照由项目实例记录，当前通用模板不预设具体版本；
- Figma 云端文件的远程可访问性和视觉质量仍需人工评审，结构化校验不能替代审美判断。

## 关联项目/笔记

- `game/game-production-pipeline/workflows/ui-production.md`
- `game/game-production-pipeline/contracts/ui-visual-contract.template.yaml`
- `skills/ui-ux-pro-max/references/figma-handoff.md`
- `D:\NOTE\NOTE\muti-agent\项目决策\2026-10-01-Codex-Figma-UI四步流程.md`
