# muti-agent

用于设计、验证和维护可复用的 Codex Agent、多 Agent 工作流与插件。

## 当前版本

当前发布候选为 `v0.4.0-alpha.3`：修复 Loop Registry 官方 CLI 把 active Snapshot 同时按 draft 模板校验的问题，将静态契约、draft 注册模板和运行态历史重放分为独立路径，并提供从 `v0.4.0-alpha.2` 到本候选版的只读规划与受控迁移器；该版本仍是 Alpha，不是 Production Ready。

## 目录

- `game/game-production-pipeline/`：游戏制作多 Agent 管线的 Codex 插件源码。
- `docs/releases/`：版本发布说明、测试手册与已知限制。
- `dist/`：本地生成的发布附件，已由 Git 忽略。

通用插件只保存框架、契约、角色模板和可执行工作流；剧情、美术风格、玩法答案与项目专属 Agent 保存在目标游戏项目中。

## 验证

```powershell
python -m unittest discover -s game/game-production-pipeline/tests -p 'test_*.py' -v
python game/game-production-pipeline/scripts/validate_pipeline_contract.py game/game-production-pipeline/contracts/examples/vertical-slice-greybox.yaml
python game/game-production-pipeline/scripts/validate_project_brief.py game/game-production-pipeline/contracts/examples/sample-project-brief.yaml --project-id sample-game
python game/game-production-pipeline/scripts/validate_organization_registry.py --templates --snapshot game/game-production-pipeline/contracts/examples/organization-alpha-snapshot.yaml --change-set game/game-production-pipeline/contracts/examples/organization-alpha-change-set.yaml
python game/game-production-pipeline/scripts/validate_text_encoding.py --plugin-root game/game-production-pipeline
```
