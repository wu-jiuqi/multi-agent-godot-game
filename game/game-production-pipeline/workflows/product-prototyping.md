# 产品经理、六部门 P2P 与 Penpot 原型工作流

状态：`draft`。本流程把固定的六个能力槽位、项目经理主导的 P2P 咨询、产品
文档整合和 Penpot 原型串起来。六个槽位是框架能力，不是每个项目都必须运行的
六个 Agent。流程复用现有 `GATE-0`、`GATE-1`、`D2`、UI Visual 和生产闸门，
不以“原型完成”替代人类方向或视觉体验批准。

相关角色与文件：

- `../agents/pipeline-director.md`：项目级咨询发起、整合 PRD/GDD、排期和冲突升级；
- `../agents/product-manager.md`：产品身份、原型意图、咨询记录和交接包；
- `../agents/department-manager.md`：部门内部拆解、专业建议和事实源边界；
- `$product-brief-and-identity`：文档/身份/咨询交接；
- `$penpot-prototype-orchestration`：登记的 Penpot MCP 执行和证据交接；
- `../contracts/product-prototype-handoff.template.yaml`：本流程的结构化记录模板；
- `ui-production.md`：完整 UI Visual 与 Godot 实施流程。本流程只负责其前置产品包。

## 拓扑与固定槽位

```text
人类负责人
    │ 方向、范围、体验与最终 Gate
项目经理（发起咨询、协调、整合 PRD/GDD）
    ├─ 产品经理能力（身份、原型意图、Penpot 编排）
    ├─ 策划经理槽位 planning
    ├─ 美术经理槽位 art
    ├─ 程序经理槽位 programming
    ├─ 音频经理槽位 audio
    ├─ 测试经理槽位 qa
    └─ 工具经理槽位 tools
             ↕ 有记录的 P2P 依赖讨论
```

槽位的默认职责和 Preset 可以在框架中固定，但只有项目批准的激活、Position、
Preset 绑定和授权才会创建运行实例。项目可以让一个部门经理覆盖多个槽位，或
把不需要的槽位写成 `not_requested`；不因为“六个框架存在”而产生上下文或调用。

P2P 只描述沟通拓扑。所有参与者仍须遵守：项目经理负责项目级优先级与交付；
部门经理负责本域事实和初审；产品经理保留产品资料与交接引用；人类负责方向、
范围、核心体验、最终视觉/UX价值判断和批准。

## 阶段与交接矩阵

| 阶段 | 准入与输入 | 主要动作 | 输出与自动检查 | 人工判断/退出 | 失败回退 |
|---|---|---|---|---|---|
| 0. 建立基线 | 项目实例、AGENTS、brief/charter、组织 Snapshot 和工具权限可读 | 产品经理与项目经理锁定 source revision/digest，分类事实、偏好、假设、未知；创建 handoff 和 consultation ID | `source_document_refs`、权限和写入范围、六槽位激活清单；检查 ID、摘要和授权 | 缺失方向、范围或 owner 时由人类补齐；基线完整后进入咨询 | `AUTHORITY`/`PRODUCT_DIRECTION` → 项目经理与人类；不创建实例 |
| 1. 六槽位 P2P 咨询 | 项目经理已声明问题、期限、预算、激活槽位和不可变边界 | 并行请求已激活部门经理；只为命名依赖/冲突开启直接 peer 讨论；每轮结构化记录建议、证据、风险、替代方案 | 每个槽位 `responded`、`not_applicable` 或 `blocked`；peer 记录、冲突和 decision matrix；检查无未登记调用 | 项目经理判断跨范围/优先级/资源冲突是否升级；覆盖足够后进入整合 | `DOMAIN_FACT` → 部门 manager；`P2P_CONFLICT` → 项目经理；无响应保留并标阻塞 |
| 2. PRD/GDD 与产品身份草案 | P2P 响应及现有文档摘要齐全 | 产品经理整理身份候选、产品价值、支柱、范围、核心循环引用和 prototype intent；项目经理整合 PRD/GDD | 草案、来源/决定引用、开放问题、风险、原型目标；检查每项结论可追溯 | `GATE-0` 审批产品名/标题/slogan、目标、范围、Charter；`GATE-1` 审批核心体验/切片假设 | `PRODUCT_DIRECTION` → 人类；`PRODUCT_DOCUMENT` → 产品经理；冲突不能静默覆盖 |
| 3. 原型意图与 UI/视觉输入 | GATE-0/1 通过，或明确批准的 bounded prototype 假设 | 绑定 Screen/Flow、Art Direction/UI Visual（已有则继承），定义关键屏幕、成功/错误/返回、目标 viewport、排除项 | `prototype_intent`、UI/UX/视觉 refs、实现边界；检查稳定 screen/flow ID 和 gate digest | UI/UX 确认结构事实，主美确认视觉输入；方向性变化回到人类/D2 | `UI_STRUCTURE` → UI/UX；`UI_VISUAL` → 主美；`PRODUCT_DIRECTION` → 人类 |
| 4. Penpot 编排 | handoff digest 未变、工具 registry 存在、`tool:penpot-mcp` 能力已验证 | 只读检查画布 → 建立/更新 Foundations、Components、Screens、Prototype → 走查关键 flow → 捕获快照与映射 | Penpot file/page/shape ID、变量/样式、prototype link、截图/flow 证据、工具输入 digest；检查链接可解析、无重复竞品 flow | UI/UX 审结构与可读性，主美审视觉；通过后可置 `implementation_ready`，这不等于 Godot/D3/D4 | `PENPOT_TOOL` → 工具负责人；失败先查画布、保留部分证据再局部重试 |
| 5. 交接与后续实施 | 阶段 4 证据完整且评审结论可见 | 产品经理更新 handoff，发给 UI/UX、主美、Godot 与项目经理；Godot 若执行则转 `ui-production.md` 阶段 B | UI Visual/Screen/Flow 引用、交接摘要、未验证项和下一动作 | 需要最终视觉或体验价值时由人类/已批准 reviewer 判断；外部发布仍需 GATE-4 | `HANDOFF_TRACEABILITY` → 产品经理；任何契约变化使受影响阶段回退 |

## P2P 请求与响应格式

请求必须至少包含：

```yaml
consultation_id: con:<project>:<26 位 ULID>
question_id: question:<project>:<ulid>
objective: <要回答的产品或原型问题>
input_refs: [<stable artifact ids and digests>]
active_slots: [slot:planning, slot:art, slot:programming, slot:audio, slot:qa, slot:tools]
constraints: [<scope, platform, budget, deadline, frozen decisions>]
response_schema: [recommendation, evidence, assumptions, risks, alternatives, owner, acceptance]
deadline: <timestamp or null>
```

每个部门回复必须逐项填写 `recommendation`、依据、假设、风险、替代方案、预估
成本/影响、建议 owner、验收证据和需要人类判断的问题。直接 peer 讨论必须填
`trigger=dependency|conflict|missing-evidence`，不能以“大家同意”替代记录。

项目经理的整合摘要至少包含：

- 各槽位的实际激活状态和响应引用；
- `agreement/conflict/missing_evidence/not_applicable` 分类；
- 选择的方案、被放弃的方案及其影响；
- 未解决冲突、负责人、截止时间和回退路径；
- PRD/GDD 章节与领域事实源的映射；
- 需要 GATE-0/GATE-1/D2 或人类体验判断的问题。

## 人工闸门与事实边界

`GATE-0` 绑定产品身份、范围、目标、预算与 Charter；`GATE-1` 绑定核心体验、
核心循环和垂直切片假设。原型阶段若改变视觉方向，使用现有 `D2`/UI Visual
评审；若改变 Screen/Flow，返回 UI/UX 事实 owner。所有批准必须绑定当前 handoff
revision 和 subject digest。`implementation_ready` 只代表 Penpot 设计交接可供
实现，不代表人类已批准“好看/好玩”，也不代表 Godot 构建可运行。

Penpot 执行仅可使用项目 Tool Registry 的 `tool:penpot-mcp`，并且必须先做只读
画布检查。User token、远程秘密 URL、猜测版本和未验证 rollback 不进入仓库。若
工具无法访问，保留产品意图、来源和待恢复动作，不制作虚假的 file/prototype URL。

## 退出条件与回退

流程只有在以下条件同时满足时才能向下游交接：

1. 需要响应的部门槽位都有回复，或有明确的 `not_applicable/blocked` 理由；
2. PRD/GDD 和产品身份草案逐项引用来源，冲突没有被摘要隐去；
3. 所需 GATE-0/GATE-1（以及必要的 D2/UI Visual 评审）已绑定当前摘要；
4. prototype intent、屏幕/流程 ID、Penpot 映射和证据可复查；
5. 未验证交互、工具限制、风险、回退和下一动作已列出。

任何源文档、组织授权、UI/Visual Contract 或工具注册摘要变化，都使受影响
阶段回到最近的审阅节点；不要重做不受影响的咨询。重复失败、预算耗尽、权限
越界或需要改变项目方向时，集中上报项目经理和人类；保存事件、证据和恢复点。

## 完成报告

报告 handoff 路径与 revision、参与的槽位/Instance、PRD/GDD 草案、产品身份
决定、prototype intent、Penpot file/page/shape 映射、工具和源摘要、Gate/评审
状态、未解决问题、失败路由与下一步。原型链接和截图应作为证据引用，不能替代
结构化记录。
