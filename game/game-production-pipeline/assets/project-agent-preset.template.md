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

## 工具绑定（使用时加入 frontmatter）

可选 `tool_registry_ref: {path: game-pipeline/execution/tools.yaml, sha256: <文件摘要>}` 和 `tool_ids: [tool:<工具名>]` 必须成对提供。它们纳入 Preset 审批摘要，生成时验证实际工具来源；不声明时保留旧版行为。UI 视觉原型若通过 Penpot MCP 制作，应明确声明 `tool:penpot-mcp`，并由项目内 UI dispatcher Skill 记录项目实际核实的 MCP 能力。Penpot MCP server URL 形态为 `https://<your-penpot-domain>/mcp/stream?userToken=YOUR_MCP_KEY`；URL 和 token 只在宿主配置，不能写入仓库。实际宿主版本、来源快照和能力核实写入可选 Penpot tool registry entry，不得猜测；当前宿主未连接时不得声称已可写。该绑定不能代替宿主权限或 Production Charter 的执行授权。

## 美术槽位默认 Skill 链路示例

当 Preset 的 `slot_id` 为 `slot:art` 且项目明确需要厚涂 UI 时，Skill Binding 可以声明以下固定顺序。这里是待审批的绑定示例，不会因为复制模板而注册部门或授予运行权限：

```yaml
slot_id: "slot:art"
skill_call_order:
  - palette-knife-impasto       # D1：风格方向候选输入
  - palette-knife-impasto-ui    # D3：静态 UI 组件与材质/状态交付
  - impasto-tween-animation     # D3：静态拼装完成后的补间与状态交付
```

三项由 `slot:art` 管理；后续 `slot:programming` 只消费带版本与摘要的 Art Direction/UI Visual Contract、资产/状态 manifest、运行时资源引用、motion manifest 和 Godot 映射。程序部门不能调用或改绑这些 Skill，也不能自行冻结画风、UI Visual、动效语义或权利结论；技术集成失败回到美术交接或程序实现责任边界，并保留独立 QA 与 D2/D3/D4 人工关卡。

## 组织注册请求入口

产品经理需要新增或调整长期组织时，应提交
[`contracts/organization-registration-request.template.yaml`](../contracts/organization-registration-request.template.yaml)
定义的 `organization_registration_request`。PM 只能提供责任需求与证据；`AGT-ORG` 校验当前 Snapshot 后生成绑定决策基线的 Organization Change Set，不能代替人类批准。批准只产生 `approved_pending_apply`，必须由独立的 `core.change_set_applied` Event 原子应用；审批缺失、摘要漂移或 stale 提案一律阻断。
