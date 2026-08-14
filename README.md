# muti-agent

用于设计、验证和维护可复用的 Codex Agent、多 Agent 工作流与插件。

## 当前版本

仓库正在准备 `v0.3.0-alpha.1`：把已验证的游戏制作多 Agent 框架封装为可被 Codex 安装和发现的 `game-production-pipeline` 插件。该版本提供项目初始化、组织设计、生产循环、门禁审查与 Godot 适配能力，但仍属于需要真实项目验证的 Alpha 版本。

## 目录

- `game/game-production-pipeline/`：游戏制作多 Agent 管线的 Codex 插件源码。
- `docs/releases/`：版本发布说明、测试手册与已知限制。

通用插件只保存框架、契约、角色模板和可执行工作流；剧情、美术风格、玩法答案与项目专属 Agent 保存在目标游戏项目中。

## 验证

```powershell
python -m unittest discover -s game/game-production-pipeline/tests -p 'test_*.py' -v
python game/game-production-pipeline/scripts/validate_pipeline_contract.py game/game-production-pipeline/contracts/examples/vertical-slice-greybox.yaml
python game/game-production-pipeline/scripts/validate_organization_registry.py --templates --snapshot game/game-production-pipeline/contracts/examples/organization-alpha-snapshot.yaml --change-set game/game-production-pipeline/contracts/examples/organization-alpha-change-set.yaml
```
