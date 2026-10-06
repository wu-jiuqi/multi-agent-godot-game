# Penpot 本地请求桥接契约

`penpot-browser-bridge.template.yaml` 是一个可提交、可审计的文件契约。它把本地项目请求与 dot 的云端浏览器执行分开；它不是浏览器驱动，也不声称本地项目能够直接控制浏览器。

## 角色与回写顺序

1. 本地项目生成 `request`，写入唯一 `task_id`/`request_id`、目标 Penpot URL 或稳定 ID、输入快照摘要和只读/能力约束。请求只包含普通项目数据，不能包含 token、cookie、密码或一次性验证码。
2. dot/云端浏览器接收文件后先检查请求摘要，再回写 `ack`。`ack.status=accepted` 只表示请求已接收并且连接检查通过；它不表示已经执行 Penpot 写入。
3. 云端执行器按已授权的浏览器工具能力完成检查/捕获/变更，并回写 `result`。`succeeded` 必须带本地证据快照和稳定的 `file_id/page_id/shape_ids`；远程 URL 不能代替证据。
4. 连接或执行失败时回写 `failed`/`blocked` 及 `failure.code/detail/retryable/route`，不要伪造成功结果。修复后应创建新 `revision` 或新的 request，保留旧记录供回放。

`validate_penpot_browser_bridge.py` 会验证 request、ack、result 的 ID、时间、摘要链、状态转移、连接证据和失败路由；它只检查记录，不会打开浏览器、登录 Penpot 或调用 MCP。

## 状态与失败路由

合法主线为 `requested -> acknowledged -> completed`，失败可以从 `ack` 进入 `failed`/`blocked`，或从 `result` 进入 `failed`/`blocked`。`cloud_browser_open` 请求若没有 `connection_evidence.status=verified`，不得将结果标为 `succeeded`。

- 连接未建立、origin 不符、登录/权限等待、超时：`BRIDGE`，由 dot/工具负责人恢复
- 视觉系统、组件、Penpot 证据不成立：`UI_VISUAL`
- Screen/Flow、页面或交互路径不成立：`UI_STRUCTURE`
- 快照、节点绑定、运行时或导出证据失败：`UI_TECH`
- 对比度、层级、状态可读性冲突：`UI_READABILITY`
- 需要产品/视觉方向或权限的人类决定：`HUMAN_REVIEW`

失败路由只标记责任归属，不授予浏览器权限；人类批准和产品/视觉验收仍按现有 UI workflow 执行。

## 最小 CLI 示例

```sh
python scripts/validate_penpot_browser_bridge.py \
  game-pipeline/ui/evidence/penpot-task.yaml \
  --project-root .
```

本地生成请求后，将记录交给 dot 的任务入口；dot 回写同一记录（或按项目约定回写不可变 revision），再运行同一命令。验证器输出 JSON 的 `state`、摘要和错误列表，返回码 `0` 表示记录自洽，`2` 表示失败。
