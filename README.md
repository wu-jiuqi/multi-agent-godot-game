# muti-agent

用于设计、验证和维护可复用的 Codex Agent、多 Agent 工作流与插件。

## 当前版本

当前发布候选为 `v0.4.0-alpha.2`：在 `alpha.1` 的项目经理启动模式、项目简报和 UTF-8 中文编码回归保护基础上，新增从已发行 `v0.3.0-alpha.1` 项目到 v0.4 的显式迁移器。迁移必须先 dry-run、批准精确计划摘要并建立逐字节备份，失败会自动回退；该版本仍是 Alpha，不是 Production Ready。

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
