# 插件项目迁移工作流

## 目标

把版本不一致的已初始化项目从一个明确支持的插件版本迁移到当前版本，同时保护项目事实、managed block、人工审批和 plugin lock 的可审计性。迁移器只处理自己的显式路径，不进行“尽力猜测”的跨版本补丁。

## 准入条件

- 项目包含可解析的 `game-pipeline/plugin-lock.yaml`；
- 源基础版本和 framework digest 位于迁移器支持范围；
- 当前插件版本与迁移器目标版本一致；
- v0.3 公共基线文件存在且是严格 UTF-8；
- managed block 起止标记唯一、正文摘要匹配；
- 计划中的新文件没有用户拥有的冲突内容；
- 项目所有者能审阅完整计划并批准精确 `plan_digest`。

任一条件不满足时输出 `migration_blocked` 或 `reinstall_required`，不得写项目文件。

## 输入

- 项目根目录；
- 当前插件根目录；
- 迁移时间 `migration_at`；
- apply 阶段的人类批准摘要与批准者；
- Skill Binding 发生变化时，其独立批准摘要与批准者；
- rollback 阶段的计划摘要和重复确认摘要。

## dry-run 输出

`game-production-plugin-migration-plan/v3` 至少包含：

- 项目路径和项目 ID；
- 源/目标插件版本；
- 源/目标 framework digest；
- 显式 migrator 路径；
- 每个目标文件的动作、写入前摘要和写入后摘要；
- 每个插件 Skill 的旧/新摘要、Skill Binding 新 subject digest 与独立审批记录路径；
- 全部受影响 `.codex/agents/*.toml` 的重建动作；
- 冲突、错误、警告与后置验证；
- `migration_at`、`plan_digest` 和备份位置。

dry-run 不创建目录、备份、审批或项目文件。

## apply 顺序

1. 以相同 `migration_at` 重新生成计划；
2. 比较人工提供的 `approval_digest` 与当前 `plan_digest`；
3. 若 Skill Binding 改变，独立比较 `binding_approval_digest` 与新的绑定 subject digest；
4. 复核所有目标文件的当前字节摘要；
5. 在 `game-pipeline/.cache/migrations/<plan_digest>/` 保存逐字节备份和清单；
6. 写入控制面、Skill Binding 与全部受影响的托管 Agent Adapter；
7. 更新摘要验证通过的 managed block；
8. 分别写入迁移计划和 Skill Binding 的不可变人工审批记录；
9. 最后更新 plugin lock；
10. 要求 plugin lock 和项目实例校验均为 `normal`；
11. 再次规划必须返回 `no_change`；
12. 把备份清单标记为 `applied`。

步骤 6～11 任一失败时，执行器自动从备份按字节恢复，并把清单标记为 `auto_rolled_back`。

## 人工判断

人类必须判断：

- 当前项目是否应该升级；
- 计划列出的文件影响是否可接受；
- 当前 Git 状态和项目外部备份是否足够；
- 项目所有者身份是否正确；
- Skill Binding 的新摘要是否应获得独立批准；
- 迁移后 blocked 项目简报应如何补全；
- 是否保留迁移，还是在继续编辑前回退。

自动校验不能代替这些决定。

## 显式回退

回退必须同时提供 `plan_digest` 与相同的 `confirm_rollback`。执行器先验证所有迁移目标仍等于迁移后的摘要；任何目标在迁移后又被修改时都停止，避免覆盖新工作。验证通过后恢复旧文件的原始字节，删除迁移创建的文件和空目录，并把 plugin lock 最后恢复。

备份目录保留回退结果，不替代 Git 或独立磁盘备份。禁止只回写 plugin lock。

## v0.3→v0.4 的失败退回

- 未知 v0.3 framework digest：返回项目所有者，确认安装来源或重新安装对应旧版本；
- managed block 摘要损坏：停止并人工审查，不自动修复；
- 已有项目简报或事实源 ID 冲突：停止并人工合并，不覆盖；
- 计划后文件漂移：重新 dry-run 和审批；
- apply 后验证失败：自动回退，再检查备份清单和错误；
- 强制终止造成状态不明：停止生产写入，依据备份清单核对每个目标并显式回退。
