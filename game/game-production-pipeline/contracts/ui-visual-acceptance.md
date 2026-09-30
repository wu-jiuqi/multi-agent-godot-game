# UI Visual Contract 验收标准

`game-production-ui-visual/v1` 是主美 UI 视觉身份的可追溯控制面。它和 UI Screen/Flow Contract 分离：前者定义视觉表达，后者定义信息架构、屏幕流程、布局行为、响应式/安全区、焦点和交互事实。UI workflow 必须同时绑定两份 Contract；缺少任一份只能做灰盒，不能进入完成验收。

## 从产品输入到 Figma 原型

UI Visual Contract 还记录产品输入到视觉系统原型的四段交付链。`workflow.stage_order` 固定为 `input_intake` → `product_identity_and_visual_direction` → `ux_flow` → `figma_visual_system`。当 `identity.lifecycle_state=production_ready` 时，四个 `workflow.stages.*.status` 必须为 `complete`；任一阶段没有输入、决定或交付记录只能停留在草稿/灰盒阶段。

1. `source_document_refs` 保存实际读取的 brief、PRD、GDD 或其他产品文档。每项需要 `document_kind`、标题、URI、SHA-256、内容摘要和用途；至少保留产品 brief，并明确需求/游戏设计输入是否存在。
2. `product_identity` 冻结稳定 `product_name`、玩家可见 `product_title`、`slogan` 和决定引用。`visual_direction.style_requirements` 记录整体视觉风格、语气和玩家感受，并绑定独立的方向决定引用。
3. `ux_flow.resolution` 必须说明流程来自 `inherited_from_prd` 还是 `derived_from_inputs`。如果 PRD 已包含 UX 流程，设置 `authoring_skipped=true` 并填写 `skip_reason`，沿用同一 `screen_flow_ref`，不得再创建第二份竞争流程；如果没有，则绑定 UX 决策引用和推导所依据的输入。
4. `figma_prototype` 必须声明 `provider=figma`、`integration=codex_figma_plugin`，并绑定 Figma 文件、原型链接、版本、关键屏幕 Frame、设计系统引用和交接证据。`handoff_status=implementation_ready` 才能进入 Godot 实现；仅有截图或没有文件/节点映射的视觉稿属于 `review_pending`。

这些阶段字段参与 `ui_visual_digest`。产品名、slogan、视觉方向、UX 来源或 Figma 文件/节点变化会使已有 benchmark capture 和主美评审过期，必须重新捕获和复审。现有自动校验继续负责核心 UI 视觉字段、资源引用、摘要和证据覆盖；阶段字段由 Contract 结构验收和交接评审共同确认。

## 主美交付范围

主美负责并冻结：

- 视觉身份、形状语言、组件轮廓、材质与表面规则；
- 色彩和语义 Token、字体层级和字体回退、图标网格与图形语言；
- 装饰纹样、边缘/框架规则、组件状态和动效语气；
- 关键屏幕 Style Frame、正例/反例、目标构建捕获中的 UI 本体视觉评审；
- 跨屏一致性、可读性和可访问性视觉约束。

主美不改变 UI Screen/Flow、布局行为、焦点顺序或交互逻辑。结构冲突通过 `UI_STRUCTURE` 返回 UI workflow；视觉问题通过 `UI_VISUAL` 返回主美。

## 最小 Contract 内容

Contract 必须有有效 `ui_visual_id`、`revision`、`art_direction_ref`、`screen_flow_ref` 和 `integrity.ui_visual_digest`，并填写 `visual_identity`、`shape_language`、`material_surface_rules`、`color_token_ref`、`typography_ref`、`iconography_ref`、`ornament_decoration_rules`、`motion_language`、`accessibility_constraints`、`owner`、`reviewers` 和 `rework_routes`。

`component_state_matrix` 对每个实际组件逐一列出 `normal / hover / pressed / focus / disabled / error` 六个状态；不适用的状态也必须保留并写 `applicable: false` 与原因。可视状态不能只改变颜色来表达关键语义，必须使用形状、图标、文字、纹样、位置或动效中的至少一个冗余通道。

`theme_resource_refs`、字体/图标引用和 Style Frame 引用必须能映射到真实资源。每个关键屏幕和主要交互状态需要 `benchmark_capture_refs`，其中记录 screen、state、目标 Build、viewport、媒体类型和绑定的 UI digest。自动校验只检查字段、引用、摘要和证据存在性，不判断美学质量。

## D3 / D4

D3 必须证明：

1. UI required domain 绑定了当前 UI Visual Contract，且 Art Direction 与 Screen/Flow 引用摘要匹配；
2. 至少一个关键屏幕有 Style Frame；
3. 组件状态矩阵完整，字体和图标方案存在，Theme/资源映射存在；
4. benchmark 覆盖所有关键屏幕和声明的主要交互状态；
5. 目标构建有截图或视频，UI 本体（组件、文字、图标、装饰和状态）而非只有背景通过主美视觉评审。

D4 在同一 UI visual/benchmark digest 上冻结主美评审、UI/UX 评审、Godot 技术集成证据及无开放返工。Contract、Style Frame、字体、图标、Theme、场景资源或目标构建变化会使相关 benchmark/review 变为 `stale`，必须重新捕获和复审。

## 返工路由

| 原因码 | 返回 | 典型问题 |
|---|---|---|
| `UI_VISUAL` | 主美 | 形状、材质、字体、图标、装饰、状态视觉与方向不一致 |
| `UI_STRUCTURE` | UI workflow | Screen/Flow、布局、响应式、安全区、焦点或交互事实错误 |
| `UI_TECH` | Godot 实现者 | Theme/StyleBox/字体/图标绑定、场景序列化或运行时实现错误 |
| `UI_READABILITY` | 主美 + UI/UX 联合复审 | 层级、对比度、状态冗余或本地化导致信息不可读 |

默认 `StyleBoxFlat`、单线边框和无视觉资产的占位控件只能作为灰盒证据，不是 UI 成品。经主美规则具体设计并有资源映射的 StyleBox 可以作为完整方案的一部分。
