# Art Direction Contract 与 D0–D4

`game-production-art-direction/v1` 是主美从方向定义到生产冻结的控制面。风格圣经和图像仍是人类可读/可视产物，Contract 负责身份、阶段摘要、来源、预算、评审和回退的事实。

## 分阶段摘要

- `brief_subject_digest`：身份、责任、范围、体验目标和 AI 政策；用于 D0。
- `exploration_subject_digest`：简报、研究和候选方向，不包含选中项；用于 D1。
- `direction_subject_digest`：在探索摘要上加入选中方向；用于 D2 人工选择。
- `benchmark_subject_digest`：加入风格语言、跨域翻译、技术 Profile、预算实测和引擎基准；用于 D3。
- `contract_subject_digest`：再加入完整权利结论；用于 D4、冻结和后续 revision 链。

这样，增加基准证据不会让已批准的方向选择自动失效；修改被批准的方向本身则一定会使 D2 记录过期。

## Gate

| Gate | 目的 | 自动/专业要求 | 必须由人类判断 |
|---|---|---|---|
| D0 | 方向问题可执行 | 项目简报引用、体验/可读性目标、范围、平台、约束、条件性权利结论 | 简报是否准确代表项目意图 |
| D1 | 探索充分分化 | 新鲜研究、一级/视频/非游戏来源、至少 3 条实质不同方案、成本和 UI 翻译 | 探索是否足以做选择（可委托评审） |
| D2 | 方向已选择 | 唯一选中项、推荐和当前摘要一致 | 指定项目所有者批准核心画风 |
| D3 | 方向可在项目中成立 | 所有必需域、引擎内目标构建、可读性、预算、主美和技术评审 | 可按项目授权要求增加体验复审 |
| D4 | 可规模化生产 | 风格圣经、翻译矩阵、2D/3D/UI Profile、QA、权利、零开放返工、冻结摘要 | 所有者批准，或按启动 Charter 委派独立审核者核验当前基线 |

通过 D4 不等于项目内容冻结或发行批准；方向 revision 变化会让所有绑定该摘要的下游资产决定进入影响检查。

## 返工与失败路由

- `BRIEF` 返回游戏设计/项目所有者；
- `RESEARCH`、`DIRECTION`、`STYLE`、`READABILITY` 返回主美；
- `TECH`、`PERF` 返回技术美术/实现；
- `RIGHTS` 返回权利审查者并阻止发布；
- `UI_BOUNDARY` 返回单独 UI workflow，主美不得直接改 Screen/Flow；
- `REGRESSION` 返回引入变化的资产或集成 Loop。

评估器只输出 `pass / revise / blocked / awaiting_human`、问题和审批摘要，不写审批、不更新 Registry。
