# 机制与玩法策划：研究依据与使用方法

研究日期：2026-09-09。以下为阅读一手论文、公开幻灯片和官方演讲简介后的整理。流程、方案数量、ID、表格及验收约定是本仓库的设计，不是原作者原文，也不意味着这些方法保证趣味性。

## 可追溯来源

| ID | 资料与实际阅读范围 | 支持的原则 | 本角色的使用方式与边界 |
|---|---|---|---|
| SRC-MDA | Hunicke、LeBlanc、Zubek，[MDA: A Formal Approach to Game Design and Game Research](https://www.cs.northwestern.edu/~hunicke/MDA.pdf)，2004；论文，重点第 2–3 页 | 规则、运行中的行为与体验相互关联；可以从设计者与玩家两侧审视 | 把体验目标落到行为、规则和观察点；不把 A 限定为美术，也不把体验因果当确定性公式 |
| SRC-DECISIONS | Sid Meier，[Interesting Decisions](https://www.gdcvault.com/play/1015756/interesting)，GDC 2012；官方简介，未观看视频 | 决策类别、节奏、信息和反馈是检查玩法的入口 | 问“此刻有哪些选择、为何不同情境下选择会变化”；不把纯表演、探索或放松玩法强行改成竞争策略游戏 |
| SRC-PROTOTYPE | Kyle Gabler、Kyle Gray，[How to Prototype a Game in Under 7 Days](https://www.gdcvault.com/play/1013294/How-to-Prototype-a-Game)，GDC 2006；官方简介，未观看视频 | Experimental Gameplay Project 用主题、单人和七天限制开展小型原型 | 提出受预算约束的最小原型；七天是该项目规则，不是本 Agent 给所有项目的强制工期 |
| SRC-PLAYTEST | David Speyrer、Brian Jacobson，[Valve’s Design Process for Creating Half-Life 2](https://cdn.cloudflare.steamstatic.com/apps/valve/2006/GDC2006_HL2DesignProcess.pdf)；公开幻灯片，重点第 3–16 页；文件路径含 2006，页内版权为 2007，不据此断言演讲年份 | 明确目标和约束、进行实验、评价实验与想法并迭代；早期试玩、外部玩家、非引导提问 | 记录玩家真实行动，尽量减少主持人提示；同时审视实验是否有效、玩家是否理解以及体验是否值得追求 |
| SRC-COUNTERPLAY | Riot Scruffy，[Quick Gameplay Thoughts: May 14](https://www.leagueoflegends.com/en-us/news/dev/quick-gameplay-thoughts-may-14/)，2021-05-14；官方开发文章全文 | 反制包含战术响应与战略准备；清晰有效的应对影响公平感和深度；并非每个技能都需要相同反制窗口 | 给高影响威胁写可感知信号、可用应对和失败解释；PvP 经验迁移至其他类型前先检验适用性 |

联网研究记录应包含：来源 ID、作者/机构、标题、链接、发表日期或未知、查阅日期、实际读到的范围、支持的结论、拟迁移部分、不适用条件。网络无法访问时写明缺口，可以继续规则推演，不能虚构查证结果。具体游戏当前版本的规则、数值、市场结论需重新查证。

## 从体验到规则

先把“爽、耐玩、有深度”改成可讨论的体验。例如“在退出与继续之间犹豫，但能解释自己为何承担风险”。再给可能产生该体验的行动、信息和规则，最后设计能推翻这一解释的观察。

检查局部机制是否改变核心循环中的行动或选择。背景设定和奖励包装不能替代可操作的规则。循环可以包含感知 → 判断 → 行动 → 反馈 → 新局面，但不要求所有游戏有同样的时长、战斗或养成结构。

## 方案比较与数值

新方向默认三案是本仓库的工作约定。每案至少改变行动、信息、资源、风险或节奏中的一个关键关系，并比较目标体验、学习成本、制作成本、可扩展性、最坏失败和最快验证方式。推荐时说出代价，不用未经定义的精确分数制造客观性。

数值写出单位、边界、公式、取整和结算顺序。概率需说明独立性或条件依赖，期望值不能替代方差、极端连续失败与玩家感知。时间投入、可用信息、熟练度和敌我响应会改变纸面收益。先定位退化策略是否来自信息/收益结构，再决定调参或换规则。

## 最小原型与证据

每次聚焦一项最大风险，允许同时保留必要的反馈和可读性。优先纸面、表格或预置灰盒场景；只有手感、空间或实时反馈本身是风险时，才需要对应的引擎原型。

分开三类结论：规则按规格运行、玩家理解了规则、玩家产生了目标体验。程序测试适合第一类；后两类需要适当对象的观察与访谈。设计者纸面推演必须标为推演；Agent 模拟玩家不能充当真实玩家样本。

试玩记录固定设计 revision、build、条件、参与者背景、操作事件和观察者帮助。先观察行为，再用非引导问题询问理由。没有样本量、构建或对照信息时报告证据限制；小规模质性测试用于发现问题，不外推总体留存率或全体玩家偏好。

## 现有 Skill 的可选复用

本角色不新增或自动绑定 Skill。需要且当前环境确实可用时，可按问题读取现有能力：

- 核心循环不清：`game-design-core-loop-extractor`；
- 方案缺乏差异：`game-design-option-generation`；
- 不知道原型验证什么：`game-design-prototype-intent-audit`；
- 失败令人困惑：`game-design-failure-loop-audit` 或 `game-design-fairness-frustration-audit`；
- 随机体验与纸面概率不一致：`game-design-perceived-randomness-audit`。

这些是可选资源名，不是插件依赖。正式项目绑定遵守现有独立审批流程；缺少资源时继续使用本角色、模板和公开资料，不阻断基础策划。
