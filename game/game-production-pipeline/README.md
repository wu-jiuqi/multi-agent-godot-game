# Game Production Pipeline

`game-production-pipeline` 是面向 Codex 的可审计游戏制作多 Agent 管线插件。它提供可复用的组织、授权、审批、生产循环和引擎适配框架，再由每个游戏项目保存自己的剧情、美术风格、玩法决策、验收阈值、项目 Agent Presets 与项目 Skills。

当前版本：`v0.5.0-alpha.2`。它保留 `alpha.1` 的可选主美 Agent、联网研究、多方向探索、可扩展到 UI 的视觉语言、D0–D4、2D/3D/UI 技术 Profile、Godot 基准和权利溯源，并新增 LF 发布契约、无 zlib 差异的存储式 ZIP 与跨 `autocrlf` 回归；仍需真实项目回放，因此不是 Production Ready。

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

## 七个入口 Skills

- `$bootstrap-game-pipeline`：先生成影响计划和摘要，经确认后初始化项目控制面。
- `$prepare-game-project-brief`：由项目经理启动工作流把人类确定的玩法、美术方向、实现概要和约束整理为可供编制设计的项目简报。
- `$design-game-organization`：设计部门、岗位、Agent Presets、Skill 绑定与组织图。
- `$operate-game-production-loop`：按 Contract、授权和 Registry 运行或恢复生产循环。
- `$review-game-gates`：独立检查证据，区分自动结果与必须由人类做出的决定。
- `$adapt-godot-production`：把通用产物映射为 Godot 场景、资源、节点、测试与构建证据。
- `$direct-game-art`：先联网研究，再主动提出多条画风方向，建立风格圣经、跨 2D/3D/VFX/UI 翻译、引擎基准、预算、权利和表现验收。

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
    ├── assets/                     专业资产 Contract、预算、权利与证据
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

## 迁移到 v0.5.0-alpha.2

`v0.5.0-alpha.2` 支持从白名单内的 `v0.3.0-alpha.1`、`v0.4.0-alpha.2`、`v0.4.0-alpha.3`、`v0.4.0-alpha.4` 或 `v0.5.0-alpha.1` 显式迁移。从 v0.3/v0.4 迁移时只补齐缺失控制面和主美方向 README；从 `alpha.1` 迁移时只更新 `AGENTS.md` managed block、写审批记录并最后更新 `plugin-lock.yaml`。`alpha.1` 已知的 LF 和 CRLF 两种摘要都在显式白名单中。已有 README、美术/资产 Contract、风格圣经、图片、场景、UI、Snapshot、Event History、组织、Agent Preset 和 Skill Binding 逐字节保留；未知摘要、损坏 managed block 或计划后文件漂移都会 fail closed。

先在项目 Git 工作区干净且已有额外备份的前提下执行 dry-run。保存输出中的 `migration_at` 和 `plan_digest`：

```powershell
$plan = python scripts/migrate_plugin.py `
  --project-root D:\Game\MyProject | ConvertFrom-Json

$plan.outcome
$plan.actions
$plan.plan_digest
```

只有 `outcome` 为 `migration_ready`，并由项目所有者审阅全部动作和精确摘要后才能应用：

```powershell
python scripts/migrate_plugin.py `
  --project-root D:\Game\MyProject `
  --migration-at $plan.migration_at `
  --apply `
  --approval-digest $plan.plan_digest `
  --approved-by human:owner
```

执行器在 `game-pipeline/.cache/migrations/<plan_digest>/` 保存逐字节备份；写入项目简报、说明、事实源和审批记录后，最后更新 plugin lock，并要求 `validate_plugin_lock.py`、`validate_project_instance.py` 和重复规划全部通过。任何失败都会自动回退。

如迁移成功后尚未继续编辑目标文件，可显式回退：

```powershell
python scripts/migrate_plugin.py `
  --project-root D:\Game\MyProject `
  --rollback `
  --plan-digest $plan.plan_digest `
  --confirm-rollback $plan.plan_digest
```

回退前会验证迁移后摘要；目标文件一旦又被修改，脚本会拒绝覆盖。禁止只把 `plugin-lock.yaml` 改回旧版本。

## 项目文档基线

初始化后先使用 `$prepare-game-project-brief`。项目所有者提供已有规划，例如核心玩法、美术方向、大致实现方案、目标平台和范围约束；项目经理只负责结构化、追溯、标记 `confirmed / preference / hypothesis / unknown`、发现矛盾并追问缺口，不得补写人类尚未决定的方向。

项目简报位于 `game-pipeline/project-definition/project-brief.yaml`。运行：

```powershell
python scripts/validate_project_brief.py `
  D:\Game\MyProject\game-pipeline\project-definition\project-brief.yaml `
  --project-id my-project
```

只有简报为 staffing-ready、当前 `subject_digest` 得到项目所有者确认，并存在摘要匹配的不可变审批记录时，才能进入 `$design-game-organization`。编制获批后，游戏设计、美术、技术和 QA 等领域 Agent 再分别深化 GDD、美术规范、技术设计和测试计划。

## 主美方向闭环

主美是项目按编制需要启用的正式 Position，不是框架强制存在的常驻 Agent。批准后使用 [`agents/art-director.md`](agents/art-director.md) 与 `$direct-game-art`，把项目简报转化为 [`game-production-art-direction/v1`](contracts/art-direction-contract.template.yaml)：

1. D0 固定玩家效果、玩法可读性、范围、平台、约束和权利政策；
2. D1 必须先联网研究权威资料、视频与非游戏来源，再给出至少三条有实质差异的方案和明确推荐；
3. D2 由项目所有者批准 `direction_subject_digest`，主美不能替代核心画风选择；
4. D3 在代表性 Godot 预置场景和目标构建中证明所有 required domains、可读性、2D/3D/UI Profile 与性能预算；
5. D4 完成风格圣经、跨域翻译、权利/生成式 AI 溯源、QA、返工关闭和生产冻结。

五个阶段各有独立摘要，后续增加基准证据不会误使早先的选向失效；真正修改选中方向会让 D2 记录过期。`evaluate_art_direction_gate.py` 只输出 `pass / revise / blocked / awaiting_human` 和审批摘要，不写人工决定。

UI 在主美闭环中承担视觉语言接口：Theme/token、字体、图标、形状、材质和动效必须与世界视觉一致；Screen/Flow、布局行为、焦点、响应式规则和交互逻辑保持只读，留待独立 UI workflow 验证。

方法依据包括 GDC 的 [独特美术方向框架](https://www.gdcvault.com/play/1028954/Art-Direction-Summit-Building-a)、[AAA UI 美术指导](https://gdcvault.com/play/1025498/Art-Direction-for-AAA)、[风格化 VFX 美术指导](https://www.gdcvault.com/play/1023999/Art-Directing-VFX-for-Stylized)、Riot 的 [Game Art 教学](https://www.riotgames.com/en/artedu/intro-to-game-art) 与 Godot 官方资产导入/Theme/性能文档；详细来源和使用边界保存在 `skills/direct-game-art/references/`。

## 专业资产公共底座

项目把每项正式资产的 Contract 放入 `game-pipeline/assets/contracts/`。Contract 统一绑定批准需求、可编辑 Source、Runtime、权利链、不可变 revision、导入配方、项目预算实测、六类评审与原因码返修；详细标准见 [`contracts/specialist-asset-acceptance.md`](contracts/specialist-asset-acceptance.md)，可直接复制 [`contracts/specialist-asset-contract.template.yaml`](contracts/specialist-asset-contract.template.yaml)。

`validate_project_instance.py` 会自动发现这些 Contract，并以项目根目录核对 `repo://` 文件及 SHA-256。公共资产层仅消费 UI 等领域事实源，不拥有也不回写 UI 方案；生成路径与 protected paths 重叠时直接阻断。

P6 专业资产使用 [`contracts/specialist-asset-production.loop-contract.yaml`](contracts/specialist-asset-production.loop-contract.yaml)。Loop Registry 只保存资产 Contract 的稳定 ID、revision、URI、文件 SHA-256、subject digest 与 Asset Gate 证据；`ready/active/review/completed` 分别要求 A0/A0/A2/A3。`evaluate_specialist_asset_gate.py` 只生成证据和审批摘要，不写人工决定。

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

安装后新建 Codex 任务，再检查七个 `$skill-name` 是否可发现；当前任务不会热刷新插件能力。正常使用直接描述“初始化项目”“整理项目简报”“设计团队”“建立主美方向”或“继续生产”等目标即可，只有强制路由和发现性测试才需要显式 Skill 名。Codex 能力目录可能显示带插件命名空间的长名，这是防重名标识，不要求每次输入。更新本地插件时应使用构建元数据 cache-buster，并再次执行同一个 `codex plugin add game-production-pipeline@personal` 命令，不要依赖 UI 搜索或当前任务热刷新。

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
python scripts/validate_specialist_asset_contract.py contracts/examples/specialist-asset-static-prop.yaml
python scripts/evaluate_specialist_asset_gate.py contracts/examples/specialist-asset-static-prop.yaml --gate A3
python scripts/validate_art_direction_contract.py contracts/examples/art-direction-clockwork-garden.yaml --gate D4
python scripts/evaluate_art_direction_gate.py contracts/examples/art-direction-clockwork-garden.yaml --gate D4
python -c "import sys,yaml; from pathlib import Path; sys.path.insert(0,'scripts'); import validate_loop_registry as v; docs=[yaml.safe_load(Path(p).read_text(encoding='utf-8')) for p in ['contracts/loop-registry-event.template.yaml','contracts/specialist-asset-production.loop-contract.yaml','contracts/loop-state-machine.default.yaml']]; assert not v.validate_static_contracts(*docs)"
python scripts/validate_organization_registry.py --templates --snapshot contracts/examples/organization-alpha-snapshot.yaml --change-set contracts/examples/organization-alpha-change-set.yaml
python scripts/render_organization.py --snapshot contracts/examples/organization-alpha-snapshot.yaml --change-set contracts/examples/organization-alpha-change-set.yaml --view change --scope dept:sample-game:design --format mermaid
python scripts/validate_text_encoding.py --plugin-root .
python scripts/build_release.py --plugin-root . --output-dir ..\..\dist
```

## 当前限制

- 治理层仍是文件契约与确定性校验器，没有强制拦截所有手工文件修改的 MCP 或 Hook。
- Registry 没有数据库事务适配器；脚本会预检和原子写单文件，但不能提供跨文件数据库级事务。
- 迁移仅覆盖白名单内的 v0.3、v0.4 alpha.2/alpha.3/alpha.4 和 v0.5 alpha.1 摘要；其他开发快照和更早版本会 fail closed。
- 目前只有 Godot 适配层，Unity 和其他引擎尚未验证。
- 专业资产公共底座已形成机器闭环，但仍需要首个真实项目提供目标平台预算 Profile、真实 DCC/导入链和发布资产回放证据。
- 主美 D0–D4 已通过代表性契约纵切片和失败注入，仍需在真实项目中验证风格探索质量、团队吞吐和目标平台 benchmark；本版本只定义 UI 视觉接口，不宣称独立 UI workflow 已完成验收。
- 迁移器不会自动操作任何现有游戏项目；每个项目都必须单独在隔离副本验证、审阅计划摘要，再决定是否迁移原项目。
