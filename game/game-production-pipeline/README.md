# Game Production Pipeline

`game-production-pipeline` 是面向 Codex 的可审计游戏制作多 Agent 管线插件。它提供可复用的组织、授权、审批、生产循环和引擎适配框架，再由每个游戏项目保存自己的剧情、美术风格、玩法决策、验收阈值、项目 Agent Presets 与项目 Skills。

当前版本：`v0.4.0`。它新增项目经理启动模式、项目简报审批边界和中文编码回归保护。功能仍需通过更多真实游戏项目验证，不应仅凭版本号视为 Production Ready。

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

## 六个入口 Skills

- `$bootstrap-game-pipeline`：先生成影响计划和摘要，经确认后初始化项目控制面。
- `$prepare-game-project-brief`：由项目经理启动工作流把人类确定的玩法、美术方向、实现概要和约束整理为可供编制设计的项目简报。
- `$design-game-organization`：设计部门、岗位、Agent Presets、Skill 绑定与组织图。
- `$operate-game-production-loop`：按 Contract、授权和 Registry 运行或恢复生产循环。
- `$review-game-gates`：独立检查证据，区分自动结果与必须由人类做出的决定。
- `$adapt-godot-production`：把通用产物映射为 Godot 场景、资源、节点、测试与构建证据。

## 项目实例

初始化不会创建任何已生效部门或 Agent，只建立空 Registry 基线、blocked 项目简报草案和待补全的初始编制草案：

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
    ├── project-definition/
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

## 项目文档基线

初始化后先使用 `$prepare-game-project-brief`。项目所有者提供已有规划，例如核心玩法、美术方向、大致实现方案、目标平台和范围约束；项目经理只负责结构化、追溯、标记 `confirmed / preference / hypothesis / unknown`、发现矛盾并追问缺口，不得补写人类尚未决定的方向。

项目简报位于 `game-pipeline/project-definition/project-brief.yaml`。运行：

```powershell
python scripts/validate_project_brief.py `
  D:\Game\MyProject\game-pipeline\project-definition\project-brief.yaml `
  --project-id my-project
```

只有简报为 staffing-ready、当前 `subject_digest` 得到项目所有者确认，并存在摘要匹配的不可变审批记录时，才能进入 `$design-game-organization`。编制获批后，游戏设计、美术、技术和 QA 等领域 Agent 再分别深化 GDD、美术规范、技术设计和测试计划。

## 项目 Agent Preset

项目 Preset 使用 [`assets/project-agent-preset.template.md`](assets/project-agent-preset.template.md)。工作顺序是：

1. 确认项目简报已获人工确认并且 staffing-ready；
2. 以 `pending` 创建 Preset 和 Skill Binding 提案；
3. 运行生成器计划，取得当前 `preset_digest`；
4. 人类批准 Organization Change Set、Preset 摘要与 Skill Binding；
5. 写入不可变审批记录，把 Preset 标记为 `approved`；
6. 执行 `python scripts/generate_codex_agents.py --project-root <project> --apply`；
7. 执行 `python scripts/validate_project_instance.py --project-root <project>`。

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

先确认 Codex 已发现个人 Marketplace 和插件源：

```powershell
codex plugin marketplace list
codex plugin list
```

首次安装必须从已发现的个人 Marketplace 执行：

```powershell
codex plugin add game-production-pipeline@personal
codex plugin list
```

第二次 `plugin list` 应显示 `game-production-pipeline@personal` 为 `installed, enabled`。在首次安装前，Codex 设置页的插件搜索可能不会显示尚未安装的个人插件，因此不能把 UI 搜索结果作为 Marketplace 发现或安装状态的判据。

安装后新建 Codex 任务，再检查六个 `$skill-name` 是否可发现；当前任务不会热刷新插件能力。正常使用直接描述“初始化项目”“整理项目简报”“设计团队”或“继续生产”等目标即可，只有强制路由和发现性测试才需要显式 Skill 名。Codex 能力目录可能显示带插件命名空间的长名，这是防重名标识，不要求每次输入。更新本地插件时应使用构建元数据 cache-buster，并再次执行同一个 `codex plugin add game-production-pipeline@personal` 命令，不要依赖 UI 搜索或当前任务热刷新。

## 中文文本编码

插件源码、Markdown、YAML、JSON、TOML、Python、文本模板、bootstrap 生成文件和发布 ZIP 内文本统一使用 **UTF-8 无 BOM**。生成器显式以 UTF-8 和 LF 写入；编码校验只读文件并报告损坏，不会自动转码或掩盖问题。

编码校验器和发布构建器输出 ASCII-safe JSON；中文错误消息使用标准 `\u` 转义，JSON 解析后仍是原中文，从而避免 PowerShell 5.1 代码页影响自动化结果。

Windows PowerShell 5.1 的无参数 `Get-Content` 可能按本地 ANSI 代码页读取无 BOM UTF-8，导致中文只在终端中显示为乱码。请显式指定 UTF-8：

```powershell
Get-Content -LiteralPath "文件路径" -Encoding UTF8
```

`chcp 65001` 只调整控制台代码页，不保证 `Get-Content` 使用 UTF-8。PowerShell 7 或明确配置为 UTF-8 的编辑器一般可以直接读取。看到乱码时，应先按 UTF-8 重新读取并运行编码校验；不要直接覆盖 managed block、`game-pipeline/plugin-lock.yaml` 或批量转码项目文件。

## 验证

从插件根目录运行：

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/validate_pipeline_contract.py contracts/examples/vertical-slice-greybox.yaml
python scripts/validate_project_brief.py contracts/examples/sample-project-brief.yaml --project-id sample-game
python scripts/validate_organization_registry.py --templates --snapshot contracts/examples/organization-alpha-snapshot.yaml --change-set contracts/examples/organization-alpha-change-set.yaml
python scripts/render_organization.py --snapshot contracts/examples/organization-alpha-snapshot.yaml --change-set contracts/examples/organization-alpha-change-set.yaml --view change --scope dept:sample-game:design --format mermaid
python scripts/validate_text_encoding.py --plugin-root .
python scripts/build_release.py --plugin-root . --output-dir ..\..\dist
```

## 当前限制

- 治理层仍是文件契约与确定性校验器，没有强制拦截所有手工文件修改的 MCP 或 Hook。
- Registry 没有数据库事务适配器；脚本会预检和原子写单文件，但不能提供跨文件数据库级事务。
- 尚未提供从 `v0.3.0-alpha.1` 到 `v0.4.0` 的实际 migrator；现有项目继续锁定旧版本，迁移预检会 fail closed，禁止只改 `plugin-lock.yaml`。
- 目前只有 Godot 适配层，Unity 和其他引擎尚未验证。
- The Nameless Vessel 当前锁定 `v0.3.0-alpha.1+codex.20260814152940`，本次升级不会自动修改或迁移该项目；需要另行制定、审批并验证迁移计划。
