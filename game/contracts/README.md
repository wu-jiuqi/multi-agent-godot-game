# Loop Registry 契约

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
python game/scripts/validate_loop_registry.py --snapshot game/contracts/loop-registry-record.template.yaml --event game/contracts/loop-registry-event.template.yaml --contract game/contracts/loop-contract.template.yaml --state-machine game/contracts/loop-state-machine.default.yaml
```

校验实际 Snapshot 与 Event History 时追加：

```powershell
python game/scripts/validate_loop_registry.py --snapshot <snapshot.yaml> --history <event-history.yaml> --event game/contracts/loop-registry-event.template.yaml --contract <bound-contract.yaml> --state-machine <bound-state-machine.yaml>
```

校验器检查模板结构、Contract 输入/交付 ID、状态集合、轮次规则和事件边界；提供 `--history` 时还会重算每个 Event 摘要、检查哈希链、`sequence`、`record_revision`、`mutation_id`，按状态机重放状态与轮次，并核对 Snapshot 水位。所选存储适配器仍必须实现原子事务和幂等写入。
