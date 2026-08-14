# 项目启动与编制准入工作流

## 目标

把项目所有者已经规划的玩法、美术方向、大致实现方案和约束转换为可追溯的项目文档基线，再由项目编制设计 Agent 提出团队方案。工作流不要求完整 GDD，也不允许 Agent 替代人类决定项目方向。

## 顺序

1. `$bootstrap-game-pipeline` 建立项目控制面、空组织基线和 blocked 项目简报草案。
2. 项目所有者提交已有规划、文档、资产引用、硬约束和明确未知项。
3. `$prepare-game-project-brief` 以项目经理启动模式整理事实源、结论状态、问题、风险与责任需求。
4. 自动校验项目简报结构、引用、staffing readiness 和摘要。
5. 项目所有者审阅完整内容并批准精确 `subject_digest`；内容变化使旧批准失效。
6. `$design-game-organization` 只消费 confirmed、digest-matched、staffing-ready 的项目简报，生成待审批组织 Change Set、Agent Presets、Skill Bindings 和组织图。
7. 项目所有者批准编制后才生成 `.codex/agents/*.toml`，生产循环随后才能启动。

## 输入

- 已初始化项目实例及正常插件锁；
- 项目所有者提供的核心玩法、美术方向、大致实现方案、目标平台和约束；
- 已有项目资料、版本或摘要、事实源所有者；
- 对尚未决定内容的明确说明。

## 输出

- `game-pipeline/project-definition/project-brief.yaml`；
- 项目简报校验结果与当前 `subject_digest`；
- 摘要匹配的人工确认记录；
- 编制责任需求、风险、开放问题和准入结论；
- 后续 Organization Change Set 的可追溯输入。

## 自动验收

- 六类必要领域全部显式记录，未知项不得隐藏；
- 非未知结论全部引用登记来源；
- staffing-ready 时不存在阻断问题或未知必要领域；
- confirmed 简报的内部摘要与人工审批记录一致；
- 项目实例总校验通过。

## 人工判断

项目所有者确认项目简报是否准确表达自己的方向、偏好、假设、约束和未知项。该确认不等于批准团队编制，也不等于批准详细 GDD、美术规范或技术方案。

## 失败回退

- 来源冲突、方向缺失或表达错误：返回项目所有者与项目经理启动工作流；
- 摘要过期、审批缺失或结构无效：返回 `$prepare-game-project-brief`；
- 责任覆盖不足或编制方案越权：返回 `$design-game-organization`；
- 项目方向改变：项目简报升版、重新确认，再重建组织提案，不允许下游静默修正。
