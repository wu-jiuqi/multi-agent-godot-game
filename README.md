# muti-agent

用于设计、验证和维护可复用 Codex Agent 与多 Agent 工作管线。

## 当前状态

`v0.1.0-alpha.1` 发布候选：游戏制作多 Agent 核心框架已经形成，可以开始真实项目的前向试运行；在完成真实项目闭环、Registry 持久化适配器和跨样本复盘之前，不视为稳定版本。

## 目录

- `game/`：游戏制作流程相关的 Agent、管线契约、共享规范与验证资源。
- `docs/releases/`：各版本的发布说明与已知限制。

仓库会从真实任务和垂直切片开始迭代；只有经过重复验证的流程，才会沉淀为稳定 Agent 或 Skill。

## 验证

```powershell
python -m unittest discover -s game/tests -p 'test_*.py' -v
python game/scripts/validate_pipeline_contract.py game/contracts/examples/vertical-slice-greybox.yaml
```
