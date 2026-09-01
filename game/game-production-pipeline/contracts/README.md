# Registry 契约

## P0 专业资产公共底座

`game-production-specialist-asset/v1` 已形成可执行基线，用统一 Contract 串起需求、Source、Runtime、权利、版本、导入配方、性能证据与返修路由：

- [`specialist-asset-acceptance.md`](specialist-asset-acceptance.md)：四级门禁、P0 验收标准、失败返回与回放路径；
- [`specialist-asset-contract.template.yaml`](specialist-asset-contract.template.yaml)：项目可直接复制的 Contract 模板；
- [`examples/specialist-asset-static-prop.yaml`](examples/specialist-asset-static-prop.yaml)：已通过四道门的 Godot 3D 静态道具样例；
- [`../scripts/validate_specialist_asset_contract.py`](../scripts/validate_specialist_asset_contract.py)：只读机器校验器；
- [`specialist-asset-foundation.proposal.md`](specialist-asset-foundation.proposal.md)：问题研究、外部依据和方案决策记录。

项目 Contract 放入 `game-pipeline/assets/contracts/` 后，`validate_project_instance.py` 会自动发现并检查。公共资产管线对 UI 与其他领域事实源固定为只读；只有声明的 generated outputs 可写，任何受保护路径重叠、摘要漂移或反向回写都会阻断验收。

## Project Brief

[`project-brief.template.yaml`](project-brief.template.yaml) 定义项目经理启动工作流整理的项目文档基线。它保存事实源、`confirmed / preference / hypothesis / unknown` 结论、开放问题、风险和责任需求；只有 staffing-ready、摘要匹配且有人类审批记录的简报才能进入组织设计。

项目简报不替代 GDD、美术规范、技术设计或测试计划。编制获批后，这些专业文档仍由对应领域角色拥有和深化。

## Organization Registry

Organization Registry 用一个可由不可变事件历史重建的 Snapshot 保存项目当前正式编制、运行实例、临时授权与治理引用。四份可执行契约分别承担不同职责：

- `organization-snapshot.template.yaml`：当前权威组织事实与稳定 ID 索引；
- `organization-event.template.yaml`：全局事件信封、类型化 Payload 与摘要链；
- `organization-change-set.template.yaml`：尚未生效的长期组织变更及人工审批对象；
- `organization-validation.template.yaml`：绑定特定 Snapshot 水位的派生校验与可视化数据。

审批不绑定 Mermaid 或 SVG，而绑定 `change_set_id + change_set_digest + base revision + base snapshot_digest`。图片可随时由相同结构化输入重新生成；正式组织只能由批准后的类型化 Event 改变。

## Loop Registry

Loop Registry 保存具体 Loop 实例的运行事实，与可复用规则分离：

- [Loop Contract 模板](loop-contract.template.yaml) 定义目标、职责、预算、验收与允许的协作关系。
- [默认状态机](loop-state-machine.default.yaml) 定义合法状态和转换。
- [Registry Snapshot 模板](loop-registry-record.template.yaml) 保存实例的当前物化视图。
- [Registry Event 模板](loop-registry-event.template.yaml) 保存不可变的事实历史。

## 核心原则

1. Snapshot 回答“现在是什么”，Event 回答“为什么变成这样”。
2. 完整 Event History 是权威历史，Snapshot 必须能够从事件重建。
3. 一个原子修改由一个 `mutation_id` 标识，恰好追加一个类型化 Event，并同步更新 Snapshot。
4. Event 与 Snapshot 更新必须全部成功或全部失败；并发写入通过 `record_revision` 拒绝。
5. Registry 不保存实际 PRD、图片、代码或报告正文，只保存不可变版本、URI 和 SHA-256。
6. Contract 与状态机以 `ID + version + digest` 绑定；进入 `ready` 后不得静默漂移，迁移分别使用 `core.contract_migrated` 和 `core.state_machine_migrated`。
7. 管理父链与依赖关系分离；Owner、Executor、Reviewer 和 Approver 分离。
8. 审批只授予动作权限，不代替专业验收或恢复复检。
9. Event 使用实例内连续序号和摘要链检测丢失、重排或篡改。
10. 物理存储可由项目选择，但必须保持上述事务、顺序和不可变语义。

## Snapshot 字段组

| 字段组 | 作用 |
| --- | --- |
| `identity` 与绑定 | 固定实例身份、项目归属、创建授权、Contract 与状态机版本 |
| `topology` | 记录唯一直接父 Loop 和多条依赖，不重复保存子列表 |
| `responsibility` | 记录当前具体任命；角色要求仍由 Contract 定义 |
| `runtime` 与 `budget` | 保存状态、轮次、预算消耗、并发版本和事件水位 |
| `resources` | 保存 Contract 输入槽和交付项对应的不可变产物引用 |
| `acceptance_snapshot` | 分离自动检查、专业审查和人工 Gate，并绑定 subject digest |
| `interruption` | 仅在中断期间保存首次现场、当前原因和最近复检 |
| `pending_approvals` | 保存当前相关请求；完整申请和决定历史进入 Event |

## 轮次与预算

- 新实例的 `current_iteration` 为 0。
- `ready → active` 初始化为 1。
- 只有 `review → active` 返工时增加轮次。
- 中断、恢复和审批不增加轮次。
- `completed_iterations` 只统计已经提交到 `review` 的轮次。
- `active_time_seconds` 不累计 `blocked`、`paused` 或 `waiting_approval` 时间。
- 任一种已配置预算耗尽都按 Contract 进入暂停复审或升级。
- 预算扩展必须产生带审批依据的 `core.budget_extended`。

## 事件边界

`core.state_transitioned` 处理没有更专用核心事件的状态变化。下列事件自身携带状态语义，同一 mutation 不得再重复写一条通用状态转换事件：

- `core.loop_started`
- `core.interruption_entered`
- `core.interruption_rerouted`
- `core.resume_revalidation_recorded`（复检通过时携带恢复目标）
- `core.loop_completed`
- `core.loop_cancelled`

项目可增加 `project.<project_id>.*` 事件，但不能覆盖核心状态、授权、验收与哈希语义。

## 一致性验收

运行：

```powershell
python scripts/validate_loop_registry.py --snapshot contracts/loop-registry-record.template.yaml --event contracts/loop-registry-event.template.yaml --contract contracts/loop-contract.template.yaml --state-machine contracts/loop-state-machine.default.yaml
```

校验实际 Snapshot 与 Event History 时，`--history` 会明确切换到运行态模式；`--snapshot` 只表示当前物化视图，不再执行 draft 注册基线规则。建议用独立的 `--record-template` 同时校验官方 record template：

```powershell
python scripts/validate_loop_registry.py --snapshot <snapshot.yaml> --history <event-history.yaml> --record-template contracts/loop-registry-record.template.yaml --event contracts/loop-registry-event.template.yaml --contract <bound-contract.yaml> --state-machine <bound-state-machine.yaml>
```

运行态模式分别执行：Event/Contract/状态机静态契约检查、可选独立 Record Template 的 draft 结构检查、Snapshot 资源 ID 检查，以及 Event History 的摘要链、并发修订、水位、状态和 iteration 重放。为了兼容 alpha.2 已记录的命令，运行态仍允许省略 `--record-template`；此时不会跳过 Event、Contract、状态机、资源 ID 或历史重放检查，只是不额外校验独立 Record Template。无 `--history` 的原模板校验命令保持兼容。

校验器检查模板结构、Contract 输入/交付 ID、状态集合、轮次规则和事件边界；提供 `--history` 时还会重算每个 Event 摘要、检查哈希链、`sequence`、`record_revision`、`mutation_id`，按状态机重放状态与轮次，并核对 Snapshot 水位。所选存储适配器仍必须实现原子事务和幂等写入。
