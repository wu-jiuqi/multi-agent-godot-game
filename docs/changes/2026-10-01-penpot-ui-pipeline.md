# Penpot UI 管线迁移

## 目的

把 UI 视觉系统与原型的默认来源从 Codex Figma 插件切换为 Penpot MCP，同时保留 alpha11 Figma 合约的只读兼容能力。

## 默认流程

1. 读取 brief、PRD、GDD 或等效产品输入，提取标题和 slogan。
2. 确认产品名、对外标题、slogan 与整体视觉方向。
3. 复用 PRD 已有 UX；只有缺口存在时才补齐 Screen/Flow 事实。
4. 通过 Penpot MCP 创建或修改视觉系统、组件状态、关键页面和原型，并将 `file_id`、`page_id`、`shape_id`、本地快照和评审证据写入 `penpot_prototype`。

Penpot 设计交接与 Godot 运行验收分开。`implementation_ready` 只表示视觉交接可以交给 Godot，不代表目标构建或 D3/D4 通过。Godot 固定 UI 继续优先使用编辑器预置 Control/Container 节点并序列化到 `.tscn/.tres`。

## 工具与安全边界

- 项目工具绑定使用 `tool:penpot-mcp`，交接字段使用 `provider: penpot`、`integration: penpot_mcp`。
- 官方远程 MCP URL 由 Penpot 账户的 Integrations → MCP Server 页面提供，形如 `https://<domain>/mcp/stream?userToken=...`；URL、token 和宿主版本不得写入仓库。
- 连接失败、权限缺失或能力未核实时，交接保持 `blocked`/`review_pending`，不得编造文件、页面、形状或评审链接。
- `--ui-penpot-only` 检查完整 Penpot 交接；`--ui-figma-only` 作为旧项目兼容别名保留。

## 影响范围

UI Visual Contract 的 canonical 字段为 `penpot_visual_system` 与 `penpot_prototype`；校验器验证安全 HTTPS Penpot URL、非空文件/页面/形状 ID、本地快照 SHA-256 和证据覆盖。原有 Figma 字段仍按旧规则读取，便于迁移已有 alpha11 项目。

## 待验证事项

- 在真实 Codex 主机中启用 Penpot MCP，使用只读提示确认当前聚焦页面和可用能力。
- 在真实 Penpot 文件中完成组件、页面、原型走查和本地快照，再运行 `--ui-penpot-only`。
- Penpot 视觉评审通过后，再执行 Godot 场景、输入、可访问性、性能和目标构建验证。
