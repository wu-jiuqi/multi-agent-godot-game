# 游戏制作多 Agent 管线

本目录用于设计、验证和维护面向所有游戏项目的可复用 Codex Agent 根框架与协作管线。

根框架覆盖游戏制作的完整流程和必要扩展点，但不写死任何具体游戏的玩法、内容、验收阈值或项目事实。复制或安装到具体项目后，通过项目配置、模块选择和覆盖层完成裁剪与特化；项目特有内容不得反向成为通用核心的默认规则。

当前处于架构讨论阶段。第一版实现仍以一个 10～15 分钟垂直切片跑通“定义 → 设计 → 实现 → 试玩 → 回退”的最小闭环，再逐步验证完整流程。

## 分层约定

- `agents/`：承担明确职责、拥有决策边界的角色定义。
- `skills/`：可被一个或多个 Agent 复用的单项能力和工作方法。
- `workflows/`：描述 Agent、Skill、人工审批和产物之间的执行顺序与回退路径。
- `contracts/`：统一输入、输出、状态、ID、验收条件和交接格式。
- `departments/`：项目可选部门的职责、成立条件、边界和撤销模板，不代表默认常驻编制。
- `tests/`：用于验证 Agent、Skill、契约和完整工作流的代表性任务。

## 当前架构

- [多 Agent 架构](architecture.md)：通用核心、默认参考编制、项目专属编制规则和阶段映射。
- [统一管线契约](contracts/pipeline-contract.template.yaml)：所有工作流节点的输入、输出、验证、审批和回退格式。
- [人工审批闸门](contracts/human-gates.md)：范围、核心体验、灰盒、内容冻结和发布五个决策点。
- [分级授权与例外升级契约](contracts/authority-delegation.md)：定义权力如何下放、边界内如何自主决定，以及越权事项如何逐级上报。
- [Loop Contract 模板](contracts/loop-contract.template.yaml)：定义可复用循环的目标、职责、迭代、预算、验收、状态机引用、退出和协调规则，不保存具体实例的运行状态。
- [默认 Loop 状态机](contracts/loop-state-machine.default.yaml)：定义正常状态、中断状态、合法转换、恢复复检，以及审批不能直接完成循环的约束。
- `agents/`：项目经理、游戏设计、内容设计、Godot 实现、测试发布五个默认角色的参考职责契约；具体项目可以在责任完整映射的前提下拆分、合并、替换或新增 Agent。
- [项目编制设计 Agent](agents/project-agent-architect.md)：根据项目资料和通用责任地图提出项目专属编制方案，经人工批准后才能实例化或改变长期 Agent。
- [通用部门经理 Agent](agents/department-manager.md)：项目按需实例化的承上启下角色，负责部门内拆解、协作、整合和向项目经理汇报，不预设具体部门名称。
- [工具与生产管线部门模板](departments/tools-and-production-pipeline.md)：按需提供编辑、转换、导入导出和往返验证能力；小型项目可将其职责并入技术部门。
- [Godot 适配层](adapters/godot.md)：把通用产物映射为 Godot 场景、资源、节点和工程证据。
- [垂直切片工作流](workflows/vertical-slice.md)：第一版用于验证整条多 Agent 链路的代表性流程。
- [灰盒 Contract 示例](contracts/examples/vertical-slice-greybox.yaml)：统一契约在真实工作项中的填写方式。
- [第一轮双样本试点章程](pilots/dual-sample-pilot.md)：使用回放校准与前向验证检验判断可信度和实际生产能力，`GATE-0` 已批准。
- [Endshift Protocol P0-A 回放校准](pilots/reports/endshift-p0a-replay-calibration.md)：样本 A 的证据分类、实际闸门判断与责任路由。

具体 Agent 和 Skill 会在职责、触发场景、输入、输出、验收标准、失败回退以及人工决策点被确认后再创建。

## 当前讨论基线

引用对话提出了 P0～P9 的生产阶段和贯穿全程的 X0 元管线。后续需要先回答一个更基础的问题：哪些内容应当成为长期存在的 Agent 角色，哪些只是 Agent 调用的 Skill，哪些只属于工作流节点或共享契约。
