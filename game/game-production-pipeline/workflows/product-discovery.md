# 无文档项目发现（Product Discovery）

状态：`draft`。这是产品原型链路的明确前置入口：当用户只有一个想法，或仓库
没有可用的 brief/GDD/PRD/slogan 时，先进行可回溯的对话和提案写作，再进入
`product-prototype-handoff`。它不把空文件、自动摘要或候选文案当成产品决定。

入口与下游：

- `$product-discovery`：盘点现有事实、与项目所有者分轮对话，写 proposal/unknown
  的 initial brief 和 PRD；
- `$product-brief-and-identity`：在有了可追溯资料后组织六槽位咨询和身份候选；
- `$penpot-prototype-orchestration`：只消费已绑定范围、工具权限和审阅中的 handoff；
- `workflows/product-prototyping.md`：发现完成后继续产品咨询、原型意图和 Penpot 交接。

## 阶段契约

| 阶段 | 准入与输入 | 主要动作 | 输出/自动检查 | 人工判断与退出 | 失败回退 |
|---|---|---|---|---|---|
| 0. 文档盘点 | 项目身份、owner、写入范围和 AGENTS 可读；文档可不存在 | 列出 brief/GDD/PRD/brand/slogan；对空、占位或过期来源标记缺失，不伪造来源 | 缺口清单、source 状态、权限摘要；项目/路径可读性检查 | 缺 owner/权限 → 项目经理补齐；可写草案后进入对话 | `AUTHORITY` → 项目经理；不要创建空 handoff |
| 1. 发现对话 | 用户提供想法、草图或一句话，或明确“不知道” | 先给建议和取舍，再问少量改变方向的问题；记录 confirmed/preference/hypothesis/unknown | conversation record、稳定 question/decision ID、风险与替代方案 | 用户决定哪些方向、哪些问题可保留 unknown；没有回答就保持 blocked | `PRODUCT_DIRECTION` → 用户；保留部分记录和下一问 |
| 2. 初始文档 | 阶段 1 记录可读 | 从 project-brief 模板写 initial brief；并列写短 PRD；身份和 slogan 仅为 proposal | `staffing_input.readiness: blocked`（若有阻断未知）；`review: draft/in_review`；运行简报校验和 ID/摘要检查 | 用户审阅目标、受众、范围和核心体验；通过后进入 handoff 提案 | `PRODUCT_DOCUMENT` → 产品经理；修订文档，不把未知填成 confirmed |
| 3. 原型意图包 | 至少一份非空、可追溯 brief/PRD；项目 owner 和写入范围已确认 | 生成 handoff proposal，引用 initial brief/PRD，填写屏幕/流程、成功标准、失败/返回状态和排除项 | source/prd SHA-256、prototype intent、open questions、六槽位激活状态；handoff validator 必须拒绝空引用 | `GATE-0` 方向/身份/范围、`GATE-1` 核心体验/切片假设；批准后才可交给原型工作流 | `PRODUCT_DIRECTION` 或 `HANDOFF_TRACEABILITY`；返回阶段 1/2 |
| 4. 产品咨询与原型交接 | handoff revision/digest 稳定，咨询和工具权限明确 | 进入 `product-prototyping.md`：P2P 咨询、身份整合、UX/视觉输入，然后按需交给 Penpot | 所有激活槽位有响应/明确 blocked；稳定 screen/flow 映射与证据 | UI/UX、主美和用户按各自 Gate 审阅；`implementation_ready` 需要独立证据 | `DOMAIN_FACT`/`P2P_CONFLICT`/`PENPOT_TOOL` 路由并保留证据 |

## 发现产物的最低要求

- brief 和 PRD 都有 stable ID、revision、owner、来源和 status；文档为空或只有
  `<placeholder>` 时不能作为 source；
- 六个必需领域逐项标记状态；未知项有问题、owner、是否阻断和后续实验/停止条件；
- 至少一个身份候选可以留空，slogan 可以是 `unknown`；建议文案不能写成确认；
- prototype intent 说明“要学习什么”和“不主张什么”，不能以原型替代好玩/好看或
  Godot 运行验收；
- handoff 验证通过表示结构/摘要/证据引用可复查，不表示 `GATE-0/GATE-1` 已通过；
  空输入、空引用或仅有模板占位必须 fail closed。

## 完成报告

报告 discovery packet、initial brief/PRD 路径与 revision、来源摘要、已确认/提案/
未知项、阻断问题、Gate 状态、handoff revision、失败回退和下一问题。文档写入并不
等于批准；方向仍由项目所有者决定。
