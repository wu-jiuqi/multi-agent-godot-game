---
schema_version: game-production-agent-preset/v1
preset_id: preset:project:<project-id>:<agent-slug>
slug: <agent-slug>
name: <显示名称>
description: <何时使用该 Agent，包含清晰的职责边界>
version: 0.1.0
status: pending
preset_digest: null
approval_id: null
skills:
  - <skill-id>
sandbox_mode: workspace-write
---

# 职责

说明该 Agent 负责什么、不负责什么，以及何时必须上报。

## 输入

- 只列出可验证的输入及其事实源。

## 输出与验收

- 列出产物、自动检查、人工判断与失败退回路径。

## 协作和授权

- 说明上级、下游、可自主决定的范围，以及创建临时 Agent Instance 所需的授权。
