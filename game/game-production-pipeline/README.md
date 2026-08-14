# Game Production Pipeline

`game-production-pipeline` 是面向 Codex 的可审计游戏制作多 Agent 管线插件。它提供可复用的组织、授权、审批、生产循环和引擎适配框架，再由每个游戏项目保存自己的剧情、美术风格、玩法决策、验收阈值、项目 Agent Presets 与项目 Skills。

当前版本：`v0.3.0-alpha.1`。它可用于隔离项目试运行，但尚未通过真实游戏项目的完整生产闭环，不是稳定版本。

## 层级

```text
Codex Plugin
├── Skills                         可执行工作流
├── 通用 Agent / Contract 模板     职责与协作规则
└── 项目实例
    ├── 项目 Agent Preset          经审批的项目角色定义
    ├── .codex/agents/*.toml       确定性生成的 Codex 适配器
    └── Agent Instance             实际运行、登记和回收的实例
```

插件不会保存某个游戏的设计答案。把通用插件更新与项目内容演化分离，才能让同一框架被多个游戏复用。

## 五个入口 Skills

- `$bootstrap-game-pipeline`：先生成影响计划和摘要，经确认后初始化项目控制面。
- `$design-game-organization`：设计部门、岗位、Agent Presets、Skill 绑定与组织图。
- `$operate-game-production-loop`：按 Contract、授权和 Registry 运行或恢复生产循环。
- `$review-game-gates`：独立检查证据，区分自动结果与必须由人类做出的决定。
- `$adapt-godot-production`：把通用产物映射为 Godot 场景、资源、节点、测试与构建证据。

## 项目实例

初始化不会创建任何已生效部门或 Agent，只建立空 Registry 基线和待补全的初始编制草案：

```text
<game-project>/
├── .agents/skills/                 项目专属 Skills
├── .codex/agents/                  已批准 Preset 的生成适配器
└── game-pipeline/
    ├── project.yaml
    ├── plugin-lock.yaml
    ├── agents/
    ├── approvals/
    ├── bindings/
    ├── loops/
    └── organization/
```

`game-pipeline/` 应进入项目 Git。只有 `.runtime/`、`.cache/`、`tmp/`、临时原始证据和生成 SVG 被托管 `.gitignore` 区块忽略。

## 初始化

先输出不写文件的计划，并保存其中的 `created_at` 和 `approval_digest`：

```powershell
python scripts/bootstrap_game_pipeline.py `
  --project-root D:\Game\MyProject `
  --project-id my-project `
  --project-name "My Project" `
  --engine Godot
```

人类确认完整影响计划和精确摘要后，才可应用：

```powershell
python scripts/bootstrap_game_pipeline.py `
  --project-root D:\Game\MyProject `
  --project-id my-project `
  --project-name "My Project" `
  --engine Godot `
  --created-at <计划中的时间> `
  --apply `
  --approval-digest <确认的摘要>

python scripts/validate_project_instance.py --project-root D:\Game\MyProject
```

脚本拒绝覆盖现有非托管文件。版本不一致进入 `read_only`，相同版本但框架摘要不一致进入 `blocked`；不得手工改写 `plugin-lock.yaml` 绕过迁移。

## 项目 Agent Preset

项目 Preset 使用 [`assets/project-agent-preset.template.md`](assets/project-agent-preset.template.md)。工作顺序是：

1. 以 `pending` 创建 Preset 和 Skill Binding 提案；
2. 运行生成器计划，取得当前 `preset_digest`；
3. 人类批准 Organization Change Set、Preset 摘要与 Skill Binding；
4. 写入不可变审批记录，把 Preset 标记为 `approved`；
5. 执行 `python scripts/generate_codex_agents.py --project-root <project> --apply`；
6. 执行 `python scripts/validate_project_instance.py --project-root <project>`。

生成器只覆盖带有插件托管标记的 TOML。缺少审批、摘要过期、Skill 漂移、插件锁异常或目标文件由用户维护时都会停止。

## 人工审批边界

- 长期 Department、Position、Agent Preset、Skill Binding、授权上限和独立验收关系的变化都要人工批准。
- 已批准且未过期的 Temporary Grant 可以允许额度内运行实例免逐个审批，但每个实例仍须先登记并保持可见。
- 自动校验只能给出证据和建议，不能写入人工决定。
- 插件治理授权、Codex 沙箱/文件权限、技术验收是三个独立条件。

## 安装到个人 Marketplace

把此目录复制到 `~/plugins/game-production-pipeline/`，并在 `~/.agents/plugins/marketplace.json` 添加：

```json
{
  "name": "game-production-pipeline",
  "source": {"source": "local", "path": "./plugins/game-production-pipeline"},
  "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
  "category": "Productivity"
}
```

重新打开一个 Codex 任务，从个人 Marketplace 安装或启用插件，再检查五个 `$skill-name` 是否可发现。更新本地插件时应使用新的 SemVer 或构建元数据 cache-buster，并重新安装；不要依赖当前任务热刷新。

## 验证

从插件根目录运行：

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/validate_pipeline_contract.py contracts/examples/vertical-slice-greybox.yaml
python scripts/validate_organization_registry.py --templates --snapshot contracts/examples/organization-alpha-snapshot.yaml --change-set contracts/examples/organization-alpha-change-set.yaml
python scripts/render_organization.py --snapshot contracts/examples/organization-alpha-snapshot.yaml --change-set contracts/examples/organization-alpha-change-set.yaml --view change --scope dept:sample-game:design --format mermaid
```

## 当前限制

- 治理层仍是文件契约与确定性校验器，没有强制拦截所有手工文件修改的 MCP 或 Hook。
- Registry 没有数据库事务适配器；脚本会预检和原子写单文件，但不能提供跨文件数据库级事务。
- `v0.3.0-alpha.1` 是第一个插件锁版本，没有提供从未来版本迁移的实际 migrator；迁移预检会 fail closed。
- 目前只有 Godot 适配层，Unity 和其他引擎尚未验证。
- The Nameless Vessel 前向样本尚未执行；完成后才能判断哪些 Skills 可进入稳定层。
