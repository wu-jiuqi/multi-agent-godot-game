# 10～15 分钟垂直切片工作流 v0.1

## 目的

用最小但完整的体验验证核心玩法、内容表达、Godot 实现、测试和发布链路。垂直切片不是缩小版完整游戏，而是对最大项目风险的集中实验。

## 最小范围

- 一个核心玩法和明确的 Player Verbs；
- 一个关键剧情节点；
- 一个可完成的小关卡；
- 三到五种可交互对象；
- 一套完成关键路径所需的简单 UI；
- 一次存档与读档；
- 一个可在目标平台运行的构建。

## 流程

### 1. 定义范围与最大风险

主责：`AGT-GD`；协作：`AGT-DIR`。

产物：项目简报、设计支柱、`MUST / SHOULD / WON'T`、最大风险、切片成功标准。

完成后进入 `GATE-0`。未通过返回 P0，不创建高成本内容。

### 2. 定义核心体验假设

主责：`AGT-GD`；协作：`AGT-GODOT`。

产物：核心循环、Player Verbs、系统边界、胜败与恢复、技术 Spike 证据、切片简报。

完成后进入 `GATE-1`。玩法不成立返回 P1；范围不成立返回 P0。

### 3. 设计内容和交互

主责：`AGT-CD`；协作：`AGT-GD`、`AGT-GODOT`。

产物：剧情节点、关卡简报、节拍表、流程图、交互规格、占位资产清单和试玩用例。

此阶段只要求足够支持灰盒的信息。详细对白、最终美术和完整世界观可以继续迭代。

### 4. 构建 Godot 灰盒

主责：`AGT-GODOT`；验证：`AGT-QA`。

产物：使用预置节点与占位资源组成的可玩 `.tscn`、必要系统、简单 UI、存档闭环和技术检查证据。

`AGT-QA` 执行无提示试玩并区分：规格失败、实现缺陷、可用性问题和体验风险。

完成后进入 `GATE-2`。失败按下表返回；未通过不得批量生产最终环境资产。

### 5. 建立主美方向与引擎基准

主责：项目批准的主美 Position / `$direct-game-art`；协作：`AGT-GD`、`AGT-CD`、`AGT-GODOT`、`AGT-QA` 与项目所有者。

如果切片需要证明最终视觉质量或多类资产一致性，从 [`art-direction-contract.template.yaml`](../contracts/art-direction-contract.template.yaml) 建立项目 Contract：

- D0 把玩家体验、玩法可读性、范围、平台和权利政策固定为方向问题；
- D1 先联网研究权威资料、视频与非游戏来源，再给出至少三条实质不同的方向和推荐；
- D2 由项目所有者批准当前 `direction_subject_digest`，主美不能替代选向；
- D3 在 Godot 代表性预置场景中覆盖所有 required domains，提交目标构建、可读性、技术 Profile 和性能实测；
- D4 绑定完整风格圣经、跨域翻译、权利、QA、零开放返工和生产冻结审批。

D3 只证明方向可行，D4 才允许据此规模化生产最终资产。UI 在本阶段只验证视觉语言、Theme/token、图标/字体/动效如何与世界观一致；Screen/Flow、布局行为和交互仍保持只读，待独立 UI workflow 验证。

### 6. 按需生产资产并集成

主责：按需专业 Agent；集成：`AGT-GODOT`；意图验收：`AGT-CD`。

每项资产必须从 [`specialist-asset-contract.template.yaml`](../contracts/specialist-asset-contract.template.yaml) 建立 Contract，并按 [`specialist-asset-acceptance.md`](../contracts/specialist-asset-acceptance.md) 执行：

- 正式生产前通过 `ASSET-GATE-A0`，消费已批准需求、预算 Profile 与只读领域事实源；
- 导出或转换前通过 `ASSET-GATE-A1`，提交可编辑 Source、版本、依赖与完整权利链；
- 集成前通过 `ASSET-GATE-A2`，提交绑定 Source/Recipe digest 的 Runtime、Godot 导入证据和目标场景性能实测；
- 进入 `GATE-3` 前通过 `ASSET-GATE-A3`，由 demand、producer、intent、technical、QA 和 rights 六类记录批准同一 subject digest。

跨 Loop 交接必须传递 `asset_id + revision + contract_subject_digest`，不能只传路径。程序继续支持占位资源，不等待所有最终资产才开始。公共资产流程对 UI Screen/Flow、布局和交互事实源只读；若返修需要改变 UI，必须启动独立 UI 变更工作流。

每项最终资产必须引用当前已通过 D4 的 `art_direction_id + revision + contract_subject_digest`；若该项目明确没有持续主美方向需求，项目 Contract 必须记录原因和替代的视觉验收事实源。

完成后由 `AGT-QA` 执行集成回归，进入 `GATE-3`。

### 7. 试玩、修订与发布候选

主责：`AGT-QA`；修订由相应责任 Agent 执行。

产物：试玩记录、缺陷与风险、回归结果、目标平台构建、版本说明和回滚方案。

通过 `GATE-4` 后才能对外发布。未批准的构建只能标记为内部测试版本。

## 失败路由

| 观察到的问题 | 返回阶段 | 责任 Agent |
|---|---|---|
| 核心循环没有吸引力或无法支撑目标体验 | P1；必要时 P0 | `AGT-GD` |
| 剧情信息与玩家行为冲突 | P2 | `AGT-CD` |
| 关卡目标、路线、节奏或引导不成立 | P4 | `AGT-CD` |
| 交互状态、反馈或持久化规则不完整 | P5 | `AGT-CD` |
| 节点、代码、存档、性能或平台实现失败 | P3/P7 | `AGT-GODOT` |
| 资产不符合表达需求 | P6 | 对应专业 Agent |
| 多类资产视觉漂移或 UI 与世界风格割裂 | D3/D4 | 主美 + 对应专业 Agent；UI 结构问题另开 UI workflow |
| 方向只有表面差异、缺研究或未获人类选向 | D1/D2 | 主美 + 项目所有者 |
| 基准在目标构建不可读或超预算 | D3 | 主美 + `AGT-GODOT` |
| 资产来源、许可、合同或再分发权不成立 | P6 / `RGT` 阻塞 | 权利复核者 + 项目所有者 |
| Source、导入配方或 Runtime 摘要不一致 | P6/P7 / `SRC` 或 `IMP` | 对应专业 Agent + `AGT-GODOT` |
| 资产超过目标场景预算 | P6/P7 / `PERF` | 对应专业 Agent + `AGT-GODOT` |
| 资产流程触碰 UI 等受保护事实源 | 原领域工作流 / `REG` | 原事实源 Owner + `AGT-QA` |
| 验收条件不清楚或无法测试 | X0 与原定义阶段 | `AGT-DIR` + 原责任 Agent |
| 新需求扩大已批准范围 | P0 | `AGT-GD` + 人类 |

## Skill 提取规则

每轮结束后由 `AGT-DIR` 记录：重复步骤、重复错误、稳定输入输出、可脚本化检查和能力缺口。满足以下条件才创建 Skill：

- 相似步骤至少在两个真实工作项中出现；
- 输入、输出和失败模式已经稳定；
- 抽取后能被多个工作流或 Agent 复用；
- 已有代表性任务可用于前向验证。
