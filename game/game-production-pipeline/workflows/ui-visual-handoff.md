# UI Visual 双契约交接

## 输入

UI workflow 先取得产品 brief/PRD/GDD 中至少一份可用来源，并形成产品身份、整体视觉要求和 UX 复用/补齐记录；再取得已批准且摘要有效的 UI Screen/Flow Contract，并建立或更新 `game-production-ui-visual/v1` 草案。前者提供 screen/flow、布局、响应式、安全区、焦点和交互事实；后者由主美提供视觉身份、组件状态、字体/图标、Style Frame、Theme 映射和可访问性视觉规则。

当项目使用 Penpot MCP 制作视觉系统时，交接必须先完成
[`ui-ux-pro-max` 的 Codex Penpot handoff reference](../../../skills/ui-ux-pro-max/references/penpot-handoff.md)
规定的四段顺序：读取 brief/PRD/GDD，确定产品名/标题/slogan 与视觉方向，确认或推导 UX
流程，再通过已批准的 `tool:penpot-mcp` 生成视觉系统原型。UI Visual Contract
中的 `penpot_prototype` 必须绑定 `provider: penpot`、`integration: penpot_mcp`、
文件/版本、页面/形状节点、设计系统和证据；没有这些绑定只能 `review_pending`。

## 交接顺序

1. 项目经理读取产品文档，整理来源、标题、slogan 和产品名候选；所有者确认产品身份，主美记录整体视觉要求。
2. UI/UX 判断 PRD 是否已有 UX；已有则绑定原流程并跳过重复编写，否则补齐 Screen/Flow、布局、响应式、安全区、焦点和交互事实。
3. 主美从已确认的产品身份与 Art Direction 推导 UI 视觉方向；先运行 `scripts/validate_penpot_connection.py`，只有 `state=connected` 才通过 Penpot MCP 建立变量、样式、组件状态、关键屏幕和原型链接，并将文件/页面/形状/本地快照摘要与 `penpot_mcp_status` 写入 Contract。本地项目不直接控制浏览器。
4. UI/UX 与主美共同评审 Penpot 原型；交互路径、可读性或视觉规则不成立时分别按 `UI_STRUCTURE`、`UI_READABILITY`、`UI_VISUAL` 返回。`implementation_ready` 只代表 Penpot 可交接。
5. 需要引擎实现时，Godot 实现者在既定 `.tscn` Control/Container/PanelContainer/Button/HSlider/ProgressBar/Toast 结构中绑定已批准资源。固定结构和资源序列化到 `.tscn` / `.tres`；脚本只切换已声明的状态资源和动效。
6. 目标构建捕获关键屏幕与主要状态，由主美检查 UI 本体；UI/UX 检查结构/可读性，Godot 实现者检查资源/场景/运行时。D3/D4 绑定同一 UI visual/benchmark digest。

## 失败返回

视觉身份或组件资产不成立：`UI_VISUAL` 返回主美；Screen/Flow、布局或交互不成立：`UI_STRUCTURE` 返回 UI workflow；资源绑定、场景序列化或运行时错误：`UI_TECH` 返回 Godot 实现者；对比度、层级或状态表达冲突：`UI_READABILITY` 返回主美与 UI/UX 联合复审。MCP 状态为 `disconnected`/`error`、权限或超时失败：`BRIDGE` 路由到工具负责人并保留状态校验结果；需要方向、权限或不可逆决定时路由 `HUMAN_REVIEW`。不得把未执行操作标为成功。

线框、默认控件、单线边框和无资产占位内容只能记录为灰盒，不得作为最终 UI 的视觉输入或 D3/D4 成品证据。实现者不得从文字描述自行补定主美的形状、字体、图标或状态语气。
