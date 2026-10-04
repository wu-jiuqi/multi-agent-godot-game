# 六部门、P2P 与产品原型工作流验证运行报告

运行日期：2026-10-04  
验证状态：`blocked_for_live_pilot`

本轮完成了验证设施和受控沙盒验证，但没有把沙盒结果升级为真实试点结论。V0 的本地检查通过，V1/V2 只通过了受控子集，V3 因 Penpot 没有连接实例而阻塞，V4 的真实 P2P 成本对照未运行。

## 证据与结果

| 阶段 | 结果 | 证据 | 结论边界 |
|---|---|---|---|
| V0 基线与设施 | `pass` | 完整回归 `250` 项测试通过；有效/无效咨询事件、产品交接实例、摘要链和故障替身均有测试 | 证明本地设施可运行，不证明宿主权限、真实 Registry 或真实审批 |
| V1 槽位与生命周期 | `synthetic_subset` | F01、F06 通过；未启用槽位拒绝物化/调用，跨域覆盖 QA 事实被拒绝且摘要不变 | 只证明 `OrganizationSandbox` 的受控行为，未验证真实调度器和 Registry |
| V2 咨询到产品包 | `synthetic` | 咨询事件实例校验、确定性重放、幂等和 QA 审批边界测试通过 | 未运行真实部门经理、真实项目经理整合或人类审批 |
| V3 Penpot 纵切片 | `blocked` | `mcp__penpot__execute_code` 返回 `No Penpot instance connected for user token` | 不能声称已生成可编辑 Penpot 产物或完成真实交接 |
| V4 恢复与对照 | `partial` | F11、F12、F13 通过；写后响应超时可读回确认、断连/只读拒写、重复同步保持稳定 ID | 真实 P2P 与非 P2P 成本/质量对照未运行，未得出效率收益结论 |

受控运行报告为 [`synthetic-report.json`](./synthetic-report.json)。报告中的 `overall: pass` 只适用于声明的 F01/F06/F11/F12/F13 沙盒用例，`claim_scope` 明确排除了 V1-V4 真实试点。

## 已实现的验证设施

- [`validate_consultation_event.py`](../../../game/game-production-pipeline/scripts/validate_consultation_event.py)：校验单条咨询事件、摘要链、sequence、水位、参与者、审批边界，并提供无模型/无工具调用的确定性重放。
- [`validate_product_prototype_handoff.py`](../../../game/game-production-pipeline/scripts/validate_product_prototype_handoff.py)：校验具体项目交接实例的本地来源、摘要、外部审批主体、工具能力、Screen/Flow 映射和读前/写后证据；模板文件不能直接作为实例通过。
- [`validation_sandbox.py`](../../../game/game-production-pipeline/scripts/validation_sandbox.py)：提供受控组织和 Penpot 工具替身，覆盖未启用槽位、越权事实写入、断连、只读、写入后超时和重复同步。
- [`run_organization_prototype_validation.py`](../../../game/game-production-pipeline/scripts/run_organization_prototype_validation.py)：生成带有前后摘要、审计记录、失败范围和限制说明的 JSON 运行报告。

## 本轮命令

```text
python -m unittest discover -s game/game-production-pipeline/tests -p 'test_*.py' -v
python game/game-production-pipeline/scripts/validate_organization_extensions.py
python game/game-production-pipeline/scripts/validate_consultation_event.py game/game-production-pipeline/contracts/examples/consultation-event-valid.yaml
python game/game-production-pipeline/scripts/run_organization_prototype_validation.py --output docs/validation-runs/2026-10-04-six-department-product-prototype/synthetic-report.json
```

完整回归退出码为 `0`，共 `250` 项通过。Penpot 连接探针是唯一阻塞 V3 的外部条件，不应通过增加沙盒测试来绕过。

## 下一步

1. 在专用测试项目中连接当前用户令牌可访问的 Penpot 实例，提供具体项目根目录和交接实例。
2. 运行产品交接校验器的 `--require-ready` 模式，补齐真实外部审批记录、工具能力快照、Screen/Flow 映射和专业评审。
3. 在同一输入、相同模型/额度/时限下运行 P2P 与集中转述两组对照，记录质量、转述次数、token/费用、墙钟和返工，并由独立评审者复核。
4. 只有 V3 的远端证据和 V4 的真实对照完成后，才重新判断是否把这版组织架构标为试点通过或进入下一轮迭代。

未解决问题：真实 Registry 是否在宿主层强制阻断越权、真实人类审批记录如何与摘要绑定、Penpot MCP 的连接与权限范围，以及六部门经理在真实任务下的并发和成本上限。
