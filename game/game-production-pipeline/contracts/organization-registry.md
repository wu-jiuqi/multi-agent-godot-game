# Organization Registry 边界契约

状态：`approved-design`

Organization Registry 是单个项目当前实际组织的事实源。它保存已批准 Department、Position 与 Agent Preset 绑定，以及当前 Agent Instance 和组织治理事实；它不定义可复用组织规则，也不管理生产循环的执行状态。

对象生命周期见 `organization-lifecycle.md`；可执行数据形状由 `organization-snapshot.template.yaml`、`organization-event.template.yaml`、`organization-change-set.template.yaml` 与 `organization-validation.template.yaml` 共同定义。校验报告属于绑定水位的派生旁车，不写回权威 Snapshot。

## 一项目一 Registry

每个项目拥有独立 Organization Registry，并绑定唯一 `project_id`。根框架只提供 Contract、模板和校验规则，不保存某个项目的实际组织。复制或安装根框架到新项目时，必须建立新的 Registry，不能沿用其他项目的 Department、Position、Instance 或审批事实。

## 与其他组件的分界

| 组件 | 负责回答 | 不负责 |
|---|---|---|
| Organization Contract | 哪些组织对象、身份和变更规则合法 | 当前项目实际采用什么组织 |
| Organization Registry | 当前有哪些部门、岗位、Preset 绑定、实例和治理事实 | 生产循环的状态、轮次与验收 |
| Organization Change Set | 相对当前组织建议增加、修改或退出什么，以及等待哪项审批 | 未经批准直接改变正式组织 |
| Loop Registry | 当前有哪些 Loop、状态、轮次、预算、验收和依赖 | 定义或复制组织结构 |

Loop Contract 和 Loop Registry 可以用稳定 ID 引用负责的 Position 或执行的 Agent Instance。Loop 归属关系由 Loop Registry 单向持有，Organization Registry 不保存 Instance 到 Loop 的反向列表；运行视图需要显示当前工作时，按两个 Registry 的明确水位做确定性联合投影。任一侧都不能通过修改引用静默改写另一侧的事实。

## Snapshot 与 Event History

- Event History 是权威历史，回答组织为什么变成现在这样；
- Snapshot 是由 Event History 重建的当前物化状态，回答组织现在是什么；
- 每个原子修改使用唯一 `mutation_id`，恰好追加一个符合契约的组织事件并同步更新 Snapshot；
- Event 与 Snapshot 更新必须全部成功或全部失败；
- Snapshot 使用单调递增的 `organization_revision` 拒绝并发覆盖，并记录已经重放到的事件水位；
- 退出对象的稳定 ID 必须保留在身份索引或 tombstone 中，防止复用；完整历史不能只依赖当前 Snapshot。

一个项目只允许存在一个逻辑 Organization Snapshot 和一条全局有序 Organization Event 序列。每次成功 mutation 同时把全局 `organization_revision` 和 Event `sequence` 增加 1；不得为各部门建立相互独立、无法原子协调的组织事实源。

## 三类物化视图

三类视图来自同一份 Event History，不是三套相互独立的事实源。

### 正式编制视图

正式编制视图必须能够回答：

- 当前有哪些已批准 Department，以及它们的职责、管理边界和汇报关系；
- 每个 Department 或项目 `root` 作用域有哪些正式 Position；
- 哪个 Position 承担部门经理或其他管理责任；
- 每个 Position 绑定的准确 `preset_id + preset_version + digest`；
- Position 的长期职责、产物或文件所有权、权限上限和独立验收关系；
- Department、Position 和 Preset 绑定分别由哪项不可变人工审批建立；
- 哪些正式对象当前可用、空缺、暂停或已经退出。

正式编制视图描述经过批准的组织能力，不代表某个 Agent Instance 当前正在运行。

### 运行实例视图

运行实例视图必须能够回答：

- 当前有哪些 Agent Instance 正在运行，以及它是 Position Instance 还是 Temporary Instance；
- Position Instance 对应哪个正式 Position 和准确 Preset 版本；
- Temporary Instance 由哪个 Instance 创建，依据哪条有效授权；
- Instance 的开始时间、期限、到期或结束事实；
- 临时授权的并发、总量、成本、时间、权限、生命周期和创建深度额度使用情况；
- Instance 是否已经越过额度、授权或有效期；
- 在指定 Loop Registry 水位下，哪些 Loop ID 引用了该 Instance 或 Position。

Snapshot 只保留当前未结束实例和判断当前有效性所需的最近事实。已经结束的完整实例历史保存在 Event History 或符合本契约的历史存储中，避免 Snapshot 随运行次数无限增长。

### 治理与完整性视图

治理与完整性视图必须能够回答：

- 当前 `organization_revision` 和 Event 水位；
- 哪些稳定 ID 曾经使用、已经退出但禁止复用；
- 当前有哪些待审批 Organization Change Set 引用；
- 是否存在无 Position 的正式实例、无有效授权的临时实例、过期授权或失效 Preset 绑定；
- 最近一次成功组织变更绑定的 Change Set 摘要与人工审批；
- Snapshot 是否能由 Event History 重建，以及两者是否一致。

完整性问题必须作为可计算状态或验证结果暴露，不能只藏在自然语言报告中。

## 未批准变化

未批准的 Department、Position、Preset 绑定或退出建议不得提前写入正式编制视图。它们保存在独立 Organization Change Set 中，Registry 只保存待审批 Change Set 的稳定引用和当前审批事实。

审批图由“当前 Snapshot + 待审批 Change Set”确定性生成。建议增加、修改或退出的节点可以使用不同视觉样式，但图像不是事实源。人工批准后，Change Set 才能作为一个原子组织变更写入 Event History 并重建 Snapshot；拒绝、撤回或过期不得改变当前正式组织。

Change Set 保留创建时的完整 Snapshot 摘要用于历史审计，同时绑定排除事件水位、运行实例和审批队列的 `decision_basis_digest`。提交和决定事件可以推进全局 revision，但不会令提案因自身治理事件而失效；若正式编制、治理绑定、临时授权、ID 占用或 tombstone 已改变，提案必须标记为 `stale` 并重新确认。

## Registry 不保存的内容

- Agent Prompt、Skill 正文、工具或 Provider 实现；
- PRD、代码、美术资产、测试报告或其他交付物正文；
- Loop 状态、轮次、预算、验收结果和任务详情；
- Agent 的内部思维过程；
- 未批准组织草案的完整正文；
- Mermaid、SVG 或其他组织图文件本身。

Registry 对外部对象只保存稳定 ID、准确版本、摘要和不可变引用。依赖“最新版本”、可变路径或只有显示名称的绑定不具备审计能力，必须拒绝。

## 可视化投影

组织可视化至少提供三种投影：

1. 当前正式编制图，来自正式编制视图；
2. 当前运行实例图，来自运行实例视图；需要展示当前工作时，再与指定水位的 Loop Registry 联合投影；
3. 待审批变化图，由当前 Snapshot 与一个 Organization Change Set 计算差异。

渲染器只能读取结构化事实生成 Mermaid、SVG 或其他格式，不能通过编辑图像直接修改 Registry。所有图都必须标注所用 `project_id`、`organization_revision`、Organization Event 水位，以及 Change Set ID（若存在）；联合运行图还必须标注 Loop Registry 水位，防止用户查看或审批已经过期的投影。
