# Penpot UI 设计与 Godot 生产工作流

状态：draft；此工作流配合 [`AGT-UI-PRODUCTION-TEMPLATE`](../agents/ui-production.md) 与
顶层 [`ui-ux-pro-max`](../../../skills/ui-ux-pro-max/SKILL.md) 使用。它先把产品输入、身份、UX
与 Penpot 视觉系统整理成可追溯交接，再在需要时把 UI Screen/Flow 和 UI Visual 双契约交给 Godot 实现；不新增机器 Contract、Gate 或运行时状态。

## 使用入口

本工作流默认先通过 Codex 中的 Penpot MCP完成产品视觉系统和原型，再将 UI Screen/Flow 与 UI Visual 双契约交给 Godot 实现。Penpot 设计阶段不要求存在 `project.godot`；Godot 是设计交接之后的实施阶段。本工作流复用现有 Contract、Gate 和运行时状态。

输入可来自产品 brief、PRD、GDD、已有品牌规范、已批准的 Art Direction、UI/UX 事实和现有 Penpot 文件。先提取产品标题与 slogan，再确认产品名及整体视觉风格，复用或补齐 UX，最后通过 Penpot MCP 制作视觉系统与页面原型。

```text
请读取 game/game-production-pipeline/agents/ui-production.md 和
skills/ui-ux-pro-max/references/penpot-handoff.md，按四步 UI 流程执行。
输入：可用 brief/PRD/GDD、已有品牌和视觉要求、已有 UX、目标平台和 Penpot 文件（如有）。
先提取标题与 slogan，再确认名称和视觉方向；PRD 已有 UX 就复用，只补缺口。
使用 Penpot MCP 交付可编辑视觉系统、关键页面与可点击原型。
仅当任务包含 Godot 实施时，再加载 godot-production.md 并执行阶段 B 的十段交付。
已有有效决定直接沿用；缺少会改变方向的事实时，集中提出不超过五个问题。
```

正式项目岗位仍须使用已批准的 Organization、Position、Preset 和 Skill Binding；本文件不会自动创建持久 Agent。

## 阶段 A：文档到 Penpot 原型

四步顺序对应 UI Visual Contract 的 `workflow.stage_order`，项目记录复用 Contract 已有字段。来源不足时先形成可审阅提案；已有确认的产品名、slogan、视觉方向和 UX 不重复索要确认，也不重新发明。

| 步骤 | 输入与负责人 | 输出与检查 | 人工判断与退出条件 | 失败退回 |
|---|---|---|---|---|
| 1. `input_intake`：获取产品文档与文案 | brief/PRD/GDD 或等效文档；项目经理拥有产品目标与文案事实 | `source_document_refs` 记录来源、版本、摘要与角色；提取已定标题/slogan，缺失则给出有理由的候选，并区分事实与建议；检查链接、版本和缺口 | 项目经理/所有者判断定位和候选；目标、受众、范围与约束足够后进入下一步 | 文档缺失、冲突或定位不明 → 项目经理补足事实，候选保持待确认 |
| 2. `product_identity_and_visual_direction`：确认名称与视觉要求 | 第 1 步候选、现有品牌和 Art Direction；所有者定产品名，主美承接视觉方向 | 写入 `product_identity` 的 `product_name`、`product_title`、`slogan`、`decision_ref`；写入 `visual_direction.style_requirements`、决定来源与理由；检查决定引用可解析 | 确认产品名、对外标题、slogan、风格语气、字体/色彩/形状/材质及可读性要求；已有有效批准继续沿用 | 命名/定位 → 项目经理与所有者；视觉 → `UI_VISUAL`/主美；超出已批方向由所有者决定 |
| 3. `ux_flow`：复用或补齐 UX | 第 1 步 PRD 与其流程、Screen/Flow；UI/UX 拥有结构事实 | PRD 已完整覆盖时写 `resolution: inherited_from_prd`、`authoring_skipped: true`、来源与 `skip_reason`；缺失时写 `derived_from_inputs`、`authoring_skipped: false`，只补屏幕/流程/状态/失败恢复缺口；检查 stable ID 与关键路径覆盖 | UI/UX 确认沿用范围和缺口；若 PRD 只有部分流程，仅补缺口并保留已有 ID/引用，不重做已定路径 | `UI_STRUCTURE` → UI/UX；改变产品范围或核心交互 → 项目经理/所有者 |
| 4. `penpot_visual_system`：制作视觉系统与原型 | 已确认身份/视觉方向、UX 和目标尺寸；UI 生产 Agent 协调 Penpot MCP 执行 | Penpot 文件、设计系统/变量样式、组件及状态、关键屏幕、原型连线、截图与评审记录；填入 `penpot_prototype` 的文件/节点/版本/原型链接和交接证据；核对 screen ID ↔ page/shape ID、链接可访问与覆盖 | 主美判断视觉一致性，UI/UX 判断流程与可读性；设计交接通过后可设 `handoff_status: implementation_ready`，未评审为 `review_pending`；这不代表引擎或 D3/D4 通过 | 视觉 → `UI_VISUAL`；结构 → `UI_STRUCTURE`；可读性 → `UI_READABILITY`；工具/访问失败记录阻塞并恢复 Penpot 执行 |

执行第 4 步前确认宿主已连接官方 Penpot MCP，并先执行只读检查；项目工具登记为 `tool:penpot-mcp`，交接记录为 `provider: penpot`、`integration: penpot_mcp`。MCP 不可用、访问失败或页面/形状链接未返回时，保留输入与待恢复动作，不编造链接，不把本地 HTML、截图或 Godot 场景称为已完成的 Penpot 原型。

设计交付至少包含：来源文档清单；产品身份与风格决定；UX 复用/补齐记录；Penpot 文件及原型链接；screen/page/shape 映射；设计系统与组件状态；版本快照或导出证据；评审结论、owner 和下一步。远程 Penpot 的可变链接不能代替可复查版本与快照摘要。Penpot 预览证明设计产物，目标构建证明运行效果，二者分别保留。

阶段 A 的制作顺序为：检查现有文件/设计系统 → 建立必要的变量与样式 → 制作一个代表性页面 → 提炼并补齐组件状态 → 扩展关键页面与原型连线 → 结构和截图检查 → 按 UX 路径走查。组件、Token 和页面操作以当前 Penpot MCP 暴露的能力为准；可复用组件、字体层级、语义颜色、间距/尺寸和适用的响应式规则必须在真实页面中有对应使用；Penpot 页面建议分为 Foundations、Components、Screens、Prototype，已有文件沿用其命名。

原型走查至少覆盖入口、主操作、成功反馈、返回/取消和适用的错误恢复；记录每条 flow 的起点、目标 frame、动作和结果。单有原型 URL 或静态截图不证明可点击路径可用。受工具能力限制无法实现的交互单独列为未验证项，不能标成完成。Penpot 调用失败先检查实际画布变化，再对已知节点局部修复；权限/连接问题返回工具负责人，产品和视觉决定不因工具失败而重做。

设计交接可独立运行 `python scripts/validate_art_direction_contract.py <ui-contract.yaml> --ui-penpot-only --project-root <project-root>`。这是完整交接就绪检查，不验证审美，也不把未完成的草案当成已完成；Godot 验收再运行完整 Contract 校验和目标构建检查。

## 阶段 B：已确认设计到 Godot

仅当任务包含 Godot 实施时进入本阶段。先核对阶段 A 的产品、UX、Penpot 交接和双契约引用是否有效，再读取引擎工程；Penpot 页面或形状 作为设计依据，交互 UI 仍拆为预置节点、Theme 与独立组件，不能把整张 frame 贴图当作运行时 UI。

## 前置条件与模式

| 任务级别 | 准入条件 | 允许的产物 | 退出条件 |
|---|---|---|---|
| `prototype` | 有玩家目标或待验证 UI 假设；可缺真实视觉资源 | 简化节点、占位资源、流程和交互实验 | 假设可继续验证，或记录失败/下一实验；不得称视觉完成 |
| `greybox` | Screen/Flow 足以确定结构、状态和交互路径 | 完整预置节点结构、状态、占位 Manifest 和替换验收 | 结构路径可运行、占位项有 owner/原因/位置/验收 |
| `style-pass` | Screen/Flow 与 UI Visual Contract revision/digest 有效 | Theme/StyleBox/字体/图标/装饰、状态矩阵、Motion Token、关键屏幕捕获 | 资源映射可追溯，自动结构检查通过，提交专业视觉评审 |
| `final` | 两份契约、资源和目标构建都有效 | 完整证据包与十段 handoff | 交互/响应式/本地化/可访问性/性能证据齐全，人工视觉检查通过且无开放返工 |

小型可逆修改可沿用当前级别。若缺少 UI Visual Contract，只能走 `prototype`/`greybox` 或“待人类批准”的风格提案，不能进入 `final`。

## 节点与返工表

| 节点 | 准入与输入 | 输出 | 自动验证 | 人工/专业验收与退出 | 失败回退 |
|---|---|---|---|---|---|
| 0. 项目状态 | 项目路径、需求、授权范围；读取 `project.godot`、锁定版本、场景、Theme、目标平台/分辨率和输入声明 | 事实/假设/缺口、任务级别、最多五个问题 | 文件存在、版本和路径可解析、Contract revision/digest 可读 | 人类只判断方向/范围/平台等关键缺口；可逆缺口由 Agent 记录默认 | 方向/范围/验收缺失 → 用户；权限或文件所有权缺失 → 项目经理 |
| 1. 玩家目标与 Screen/Flow | UI/UX 结构事实或明确的 prototype 假设 | 屏幕、流程、状态、布局、响应式、安全区、焦点、输入、本地化/RTL 风险 | 引用和稳定 ID 可解析，状态/屏幕清单不为空 | UI/UX 确认结构和交互事实；不因视觉偏好改写 | `UI_STRUCTURE` → UI/UX |
| 2. 视觉边界 | UI Visual/Art Direction Contract，或明确的 greybox/style proposal | 视觉输入、待批准决定、视觉资源映射范围 | Contract 字段、revision/digest、Theme/StyleFrame 引用可解析 | 主美/UI Visual 保留视觉方向与视觉验收 | `UI_VISUAL` → 主美/UI Visual；缺 Contract 继续灰盒 |
| 3. Asset Manifest | 组件清单、状态矩阵、已有资源和导入规则 | 每项资源的 URI、状态、尺寸、切图、导入、权利、fallback、owner、version/digest | 文件/URI/digest/枚举字段存在；不验证审美或资源是否真实可用 | 资产 owner 确认来源、替换方案和授权；无真实资产保持 required/to-create/placeholder | 资源绑定或导入失败 → `UI_TECH`；视觉规格不成立 → `UI_VISUAL` |
| 4. 场景与组件实现 | 已确定的结构边界、可写 UI 路径、组件 API | 序列化 `.tscn`/`.tres`、预置节点、独立组件、Theme/资源绑定、信号/数据接口 | 场景解析/加载、节点路径、资源引用、固定结构序列化 | Godot 实现者确认运行时行为、输入和 fallback；组件不拥有业务数据 | `UI_TECH` → Godot 实现；结构事实冲突 → `UI_STRUCTURE` |
| 5. Motion/Effects | 状态矩阵、Motion Token、性能预算、reduced-motion 声明 | AnimationPlayer/Tween 规格、音效/Shader/Particle、质量档位、静态 fallback | Token 字段、禁用开关、引用和冲突策略可检查 | UI Visual/技术共同确认反馈、可读性和平台代价 | `UI_READABILITY` → 主美+UI/UX；性能/运行时 → `UI_TECH` |
| 6. 验证与证据 | 可加载场景、目标构建或已标记无法运行 | 工程/交互/输入/响应式/本地化/无障碍/资源替换/性能/视觉证据 | 自动测试、无头加载、引用和 digest、证据元数据 | 人工检查 UI 本体、关键状态和目标平台体验；自动结果不能替代审美验收 | 场景/资源/构建失败 → `UI_TECH`；状态/可读性 → 对应回退码 |
| 7. 交接与结论 | 当前 revision、证据和开放问题可见 | 固定十段输出、验收状态、责任人和下一动作 | handoff 必填项和状态枚举 | 人类/指定 Reviewer 决定 `approved` 或保留 `review_pending` | 任意未解决硬阻塞 → `blocked`，注明恢复路径 |

## 双契约和文件所有权

UI/UX 只拥有信息架构、Screen/Flow、布局/响应式、安全区、焦点、输入、本地化和交互逻辑；主美/UI Visual 只拥有视觉身份、
形状/材质、Token、字体/图标、装饰、组件状态、动效语气、Style Frame 和视觉验收；Godot Agent 绑定两者并拥有场景、资源、
组件、运行时状态、测试和构建证据。任何跨边界请求必须回写对应 owner，不以代码偷偷修改上游事实。

固定 UI 优先使用编辑器预置 Control/Container/Panel/Button/Label/Texture/Progress/Slider/Scroll/Tab/Animation/Audio 节点并序列化到
`.tscn`/`.tres`；只在数据驱动数量、通知/掉落、对象池、已批准程序生成或实例化现有 PackedScene 明显更合适时动态创建。动态创建也
必须实例化已定义组件，不能在运行时拼出固定树。Manifest、组件 API、六个基础状态和 fallback 随交接保存。

## 标杆页面门槛

正式进入可复用组件提炼前，必须在项目证据目录留下以下顺序产物：

1. **任务定义**：页面用途、玩家目标、信息优先级、主操作、最短操作路径、成功和恢复路径；
2. **视觉目标**：参考图的具体借鉴点、静态目标稿、最终显示尺寸下的面板/主按钮/次按钮/标题正文小样；
3. **素材约定**：用途、显示尺寸、透明区、文字安全区、可拉伸区、固定角饰、来源许可和占位/确认状态；
4. **真实使用页面**：真实游戏页面，或明确标注任务的主题样例；组件实验场只能作为辅助检查页；
5. **反馈实现**：normal/hover/focus/pressed/selected/disabled/error 的状态、按压与有效激活的区别、Tween/AnimationPlayer、声音和 reduced-motion；
6. **三类验收**：`functional`、`visual`、`motion_export` 分开记录真实运行截图/录屏、目标构建和未验证项。

每轮视觉返工最多优先处理三个最明显的问题，至少完成两轮对照后再决定是否提炼组件。没有真实运行截图或录制能力时，结论必须是
`review_pending`/`blocked`，不得把目标稿、编辑器预览或导出成功冒充为视觉通过。

Godot 4.7.1 的悬停和按压微动优先使用 `offset_transform_*`，并显式记录
`offset_transform_visual_only` 对输入区域的选择。`button_down`/`button_up`/`pressed` 与业务成功反馈分开验证；旧版本或属性不可用时，使用外层布局控件和内层表现控件。

## 证据最低集合

根据项目声明记录未测项，至少包含：场景导入/加载/启动、节点与资源引用、状态（normal/hover/pressed/focus/disabled/error 及适用的
loading/empty/success）、声明的输入设备、基准/宽屏/窄高/最小分辨率、长文本/CJK/RTL/fallback/文本缩放、焦点/对比度/触控目标/
reduced-motion/非颜色冗余、合法主题资源替换、Shader/Particle/透明 overdraw/UI 批次/目标帧时间，以及关键屏幕状态的目标 build 截图或录屏。
截图元数据写明分辨率、build、状态、UI Visual revision 和 benchmark digest。自动检查只证明结构、引用、摘要、资源和证据存在性。

## 固定交付和验收状态

交付必须按以下十段且不增删主段：

1. UI 任务级别；2. 输入和假设；3. UI 视觉方案；4. Screen / Flow 方案；5. 资产 Manifest；
6. Godot 节点结构；7. 组件 API；8. 动画和特效；9. 实现和测试；10. 验收结论。

验收结论只能使用 `greybox`、`implementation_ready`、`review_pending`、`approved`、`blocked`。
`implementation_ready` 只代表结构/绑定可交专业复核，`review_pending` 代表证据齐但人类复核未完成，`approved` 需要契约/证据最新且无开放返工，
`blocked` 必须写阻塞原因、owner 和下一动作。失败路由固定为 `UI_VISUAL`、`UI_STRUCTURE`、`UI_TECH`、`UI_READABILITY`。

## 交接边界

实现者把稳定 ID、revision/digest、修改文件、运行版本、目标平台、未测平台、证据 URI、限制和下一动作交给生产 Loop。主美/UI/UX/QA
仍按现有审批和 Gate 机制做专业判断；本工作流没有真实项目重复验证前保持 `draft`，不把文档完整当作商业 UI 或 D3/D4 通过。
