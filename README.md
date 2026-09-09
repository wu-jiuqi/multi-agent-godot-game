# muti-agent

用于设计、验证和维护可复用的 Codex Agent、多 Agent 工作流与插件。

## 当前版本

当前发布候选为 `v0.5.0-alpha.3`：保留可选主美 Agent、多方向探索、跨 2D/3D/VFX/UI 风格圣经、D0–D4 Gate、Godot 基准、技术预算、权利溯源和可复现发布，并补齐 Skill Binding 独立审批与 Agent Adapter 同事务迁移；该版本仍是 Alpha，不是 Production Ready。

## 目录

- `game/game-production-pipeline/`：游戏制作多 Agent 管线的 Codex 插件源码。
- `skills/ui-ux-pro-max/`：UI/UX Skill 的可维护源码，包含任务分流、体验流程、设计检索库及分平台验收规范；本机安装目录为 `~/.codex/skills/ui-ux-pro-max/`（或 `$CODEX_HOME/skills/ui-ux-pro-max/`）。
- `docs/releases/`：版本发布说明、测试手册与已知限制。
- `dist/`：本地生成的发布附件，已由 Git 忽略。

新增未发布角色：[游戏机制与玩法策划 Agent](game/game-production-pipeline/agents/gameplay-designer.md)，附研究依据、规则规格模板、原型任务书和代表性验收场景。当前为待真实项目验证的初稿。

通用插件只保存框架、契约、角色模板和可执行工作流；剧情、美术风格、玩法答案与项目专属 Agent 保存在目标游戏项目中。

## 验证

```powershell
python -m unittest discover -s game/game-production-pipeline/tests -p 'test_*.py' -v
python game/game-production-pipeline/scripts/validate_pipeline_contract.py game/game-production-pipeline/contracts/examples/vertical-slice-greybox.yaml
python game/game-production-pipeline/scripts/validate_project_brief.py game/game-production-pipeline/contracts/examples/sample-project-brief.yaml --project-id sample-game
python game/game-production-pipeline/scripts/validate_art_direction_contract.py game/game-production-pipeline/contracts/examples/art-direction-clockwork-garden.yaml --gate D4
python game/game-production-pipeline/scripts/evaluate_art_direction_gate.py game/game-production-pipeline/contracts/examples/art-direction-clockwork-garden.yaml --gate D4
python game/game-production-pipeline/scripts/validate_organization_registry.py --templates --snapshot game/game-production-pipeline/contracts/examples/organization-alpha-snapshot.yaml --change-set game/game-production-pipeline/contracts/examples/organization-alpha-change-set.yaml
python game/game-production-pipeline/scripts/validate_text_encoding.py --plugin-root game/game-production-pipeline
python skills/ui-ux-pro-max/scripts/validate_data.py
python -m unittest discover -s skills/ui-ux-pro-max/scripts/tests -p 'test_*.py'
```
