# <机制名称>策划包

> 这是人工可读模板，不是已实现的机器 Contract，不可直接交给 Loop 执行器。只填写本次任务需要的部分；未决项标记 unknown，不适用项写明理由。项目实际文件保存于获授权路径。

## 1. 身份、问题与依据

- mechanism_id：MECH-<slug>
- revision：1
- owner：<唯一写入负责人>
- status：draft / ready-for-prototype / evidence-incomplete / reviewed
- task_scope / writable_paths：<本次授权及路径>
- source_refs：<项目简报/规则/反馈的 ID、路径与 revision>
- 玩家情境、行动与目标体验：
- 当前问题及本次最大风险：
- 已确认约束、禁止项与原型预算：
- confirmed / preference / hypothesis / unknown：<逐条附来源>

## 2. 方案与推荐

| 方案 ID | 玩家做什么 | 规则和选择差异 | 预期体验 | 代价/风险 | 最快验证 |
|---|---|---|---|---|---|
| OPT-A | | | | | |
| OPT-B | | | | | |
| OPT-C | | | | | |

推荐、理由、舍弃代价及待人工判断项：

selected_option / decision_ref：<未知则不写已批准；方向已由用户指定时直接引用>

## 3. 核心循环与规则

- 玩家可用动作、短循环、如何返回下一次行动：
- 与其他系统/长循环的关系；无长循环时说明：
- 目标感受 → 玩家行为 → 支撑规则 → 观察信号：

| 规则 ID | 触发与前置 | 输入/目标 | 消耗及结算顺序 | 状态前 → 后 | 玩家反馈 | 边界/取消/失败/恢复 |
|---|---|---|---|---|---|---|
| RULE-001 | | | | | | |

- 初始状态、胜败或自定目标、终局、退出/重试、跨局保留：
- 多事件同时发生、重复输入、目标失效、暂停/退出时的规则语义：
- 随机分布、抽取时点、独立性、玩家可见/隐藏信息及概率反馈：
- 一个正常回合和一个失败回合的逐步推演：<明确标注纸面推演>

## 4. 参数与策略风险

| 参数 ID | 含义/单位 | 初值或区间 | 公式/取整/上限 | 调整方向与理由 | 依据及证据状态 |
|---|---|---|---|---|---|
| PARAM-001 | | | | | hypothesis |

| 风险 | 复现场景或推演 | 影响 | 修订/实验 | 责任人 |
|---|---|---|---|---|
| 永远最优的单一行动 | | | | |
| 资源死锁/无限收益/刷取 | | | | |
| 看不懂/无法应对/失败无法恢复 | | | | |

## 5. 最小原型任务书

- experiment_id：EXP-001
- hypothesis：<一条可证伪的体验或行为假设>
- prototype_scope / excluded_scope：<最少动作、对象、场景和必要反馈>
- implementation_owner / budget / stop_condition：
- variable / constants / baseline：<测试变量、保持不变项、对照或不适用理由>
- participants / procedure：<对象、条件、步骤、主持人可提供的帮助>
- events / observations：<事件名、关键字段、观察行为>
- non_leading_questions：<例如“刚才为什么选择退出？”>
- support_criteria / rejection_criteria：<事前提出且能观察的条件，注明暂定阈值>
- technical_acceptance：<Given / When / Then 的正常、边界与失败用例>
- experience_acceptance / human_reviewer：
- fallback：<实现失败、理解失败、假设不成立、预算耗尽各退回哪里>
- Godot 项目：<预置场景原则；必要动态生成例外由实现者论证>

## 6. 证据、依赖与交接

| 证据 ID | 类型：推演/自动检查/真实试玩 | design revision / build | 条件/样本 | 文件或记录来源 | 观察与结论 | 限制 |
|---|---|---|---|---|---|---|
| EVID-001 | | | | | | |

- implementation_status / experience_status：<分别填写；未实现/未试玩不能写通过>
- dependency_refs：<上游与下游产物 ID、URI、revision、owner；中心依赖清单记录位置>
- handoff：<内容/实现/美术/UI/QA 各自收到什么>
- changed_rules / stale_evidence / recheck_tasks：<版本变化影响>
- unresolved_questions / next_action / decision_ref：
