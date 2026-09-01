# 专业资产公共底座验收标准

版本：`game-production-specialist-asset/v1`  
状态：`p0-executable-baseline`

## 目的

本标准回答一项专业资产何时可以开始生产、何时可以被技术接收、何时可以进入运行时、何时可以进入发布版本。它适用于 UI、美术、3D、动画、VFX、音频、字体、视频及其他运行时内容，但不替代这些领域自己的设计事实源。

公共底座只接受不可变引用和证据，不拥有视觉方向、布局意图、动画表演、混音审美或玩法决定。

## 项目实例落点

项目采用以下目录；大文件可由 Git LFS、Perforce 或外部 DAM 保存，但 Contract 必须保留受控 URI、版本和 SHA-256：

```text
game-pipeline/
└── assets/
    ├── contracts/                 # 每项资产每个 revision 的 Contract
    ├── budgets/                   # 项目批准的平台/资产类型预算 Profile
    ├── evidence/                  # 检查、评审、授权和性能报告
    ├── rights/                    # 许可证正文、采购证明、合同或授权记录
    └── protected-path-snapshots/  # UI 等只读事实源的变更前后摘要
```

文件建议命名为 `<asset-id-safe>.r0001.yaml`。`asset_id` 不随路径、文件名或展示名称变化；冻结 revision 不得覆盖，修订必须创建新文件。

## 四级门禁

| 门禁 | 通过后允许 | 自动验收 | 人工/专业验收 | 失败返回 |
| --- | --- | --- | --- | --- |
| `ASSET-GATE-A0 demand-ready` | 开始投入正式制作成本 | 稳定 ID、上游需求引用、使用场景、验收意图、责任、预算 Profile、消费边界和授权可行性齐全 | requester 确认需求可生产；rights reviewer 确认权利路径可成立 | `REQ` 返回需求方；`RGT` 进入权利阻塞；`SCOPE` 回原定义阶段或 P0 |
| `ASSET-GATE-A1 source-ready` | Source 包进入导出/转换 | 可编辑 Master、依赖、工具版本、VCS revision、URI、SHA-256、许可正文/合同和采购证明齐全 | producer 确认源文件可继续编辑；rights reviewer 将状态标为 `cleared` | `SRC` 返回专业生产者；`RGT` 阻止后续导入和发布 |
| `ASSET-GATE-A2 runtime-ready` | 集成到目标场景、系统和构建 | Source digest、recipe digest、Runtime 输出、Godot sidecar、自动检查、预算阈值与实测均匹配 | producer self-check 与 technical review 绑定当前 subject digest | `IMP` 返回技术集成/工具管线；`PERF` 返回生产者与技术集成者；`REG` 返回变更责任方 |
| `ASSET-GATE-A3 release-ready` | 标记 `approved` 并进入发布候选 | A0～A2 全部通过、无开放返修、冻结摘要与审批引用匹配、署名清单齐全 | demand、producer、intent、technical、QA、rights 六类记录全部批准；自动结果不能代替人类表达判断 | 按 `REQ/SRC/RGT/IMP/PERF/REG/SCOPE` 定向返修；不允许统一退给程序 |

`released` 还必须提供实际 Build 引用和发布时间。`withdrawn` 必须保留撤回原因，不能删除历史版本。

## P0 必过清单

### 身份与需求

- `asset_id`、`project_id`、`asset_kind`、`revision` 和生命周期状态合法。
- 至少一个已登记上游事实源，引用版本与 SHA-256；仅有聊天描述或文件名不通过。
- 明确玩家可感知结果、实际使用场景、可观察验收意图、里程碑和优先级。
- requester、producer、intent reviewer、technical integrator、QA、rights reviewer 均有明确身份。

### UI 与其他事实源隔离

- `consumer_boundary.access` 固定为 `read_only`。
- 资产管线只能写 `generated_output_paths`；它不得与 `protected_paths` 相同、互为父目录或子目录。
- UI Screen/Flow、布局、组件状态和交互规则继续由 UI 工作流拥有。
- 涉及 UI 时必须提交 protected-path snapshot 证据；执行前后摘要不一致则 `ASSET-GATE-A3` 失败并按 `REG` 退回。
- 资产返修若要求改变 UI 意图，必须新开 UI 变更工作流，不得直接回写。

### Source、版本与依赖

- 可编辑 Master 与中间/交换文件分开登记；Preview 不能充当 Master。
- 每个文件记录稳定 file ID、受控 URI、格式和 SHA-256；Master 还要记录 DCC 名称与精确版本。
- 二进制不可合并文件必须声明 VCS 后端和是否独占锁；公共仓库存放禁止原文件再分发的第三方 Source 时直接失败。
- 冻结版本内容发生变化必须将 revision 加一，并通过 `previous_revision_digest` 绑定上一版本。
- Source、依赖、rights、recipe 或 runtime 发生变化后，复制来的旧评审摘要必须被识别为 stale。

### 权利与发布

- 使用 SPDX License Expression；商业合同、平台商店许可等非标准条款使用 `LicenseRef-*`。
- 同时保存许可正文或合同、采购/取得证明、创作者/供应方、来源 URI、平台与地域范围、期限、署名和 AI 使用限制。
- `commercial_use`、`modification`、`compiled_distribution` 为 `forbidden/unknown` 时不得开始正式生产或发布。
- `clearance_state` 未达到 `cleared` 时不得通过 Source Gate。
- 需要署名时必须绑定 attribution manifest；授权过期、来源不明或证据缺失一律 fail closed。

### 导入与 Runtime

- Runtime 输出必须绑定当前 Source digest 和 import recipe digest。
- Recipe 至少包含引擎及版本、导入器及版本、交换格式、Preset、sidecar、后处理脚本、工具链锁和确定性说明。
- Godot 的非原生导入资产必须登记 `<asset>.import`；`.godot/imported/` 只能登记为 cache，不得充当 Source 或手工交付物。
- 可重复构建应满足相同 Source + 相同 Recipe 产生相同输出摘要；无法字节确定时必须标为 `best-effort`，说明原因并以等价性检查补证。
- 固定可复用运行时对象优先交付预置 `.tscn` / `.tres`；动态生成必须有批准的技术理由。

### 性能

- 预算必须引用项目批准的 budget Profile，不在公共模板里写死万能阈值。
- 每个 metric 同时具有比较符、限制值、单位、实测值、结果和证据。
- 测量上下文必须绑定目标平台、硬件档位、可重复场景和 Build。
- 3D 常见指标：三角形/顶点、材质槽、纹理尺寸与显存、LOD、碰撞复杂度、骨骼/蒙皮、Draw Call 贡献、加载时间。
- 2D/UI 常见指标：纹理尺寸、Atlas、显存、过度绘制、字体页、Draw Call、加载时间；这些指标不能反向修改 UI 布局事实源。
- 音频常见指标：编码码率、解码内存、流式策略、响度、峰值、循环接缝和并发 Voice。
- VFX 常见指标：峰值粒子、透明过绘、材质/贴图采样、GPU/CPU 时间和同时实例数。
- 预算只有估算而没有目标场景实测，不能通过 Runtime Gate。

### 评审与返修

- 自动检查至少覆盖结构、导入/加载和项目定义的性能检查。
- demand、producer、intent、technical、QA、rights 六份记录分别绑定当前 subject digest；A0/A1/A2 分别前置要求 demand、producer+rights、technical 记录。
- 小团队允许同一人兼任，但仍必须保留不同评审对象、问题和证据。
- `rework_required` 或 `blocked` 必须至少有一个开放 issue，包含原因码、责任人、修复目标和所需复检。
- 返修原因码固定为：`REQ` 需求、`SRC` 源资产、`RGT` 权利、`IMP` 导入、`PERF` 性能、`REG` 回归、`SCOPE` 范围。
- 返修不得覆盖旧 revision；已发布资产的问题使用 `withdrawn`，保留受影响 Build 与替换计划。

## 可执行校验

复制模板、填写项目事实并计算摘要：

```powershell
python scripts/validate_specialist_asset_contract.py `
  game-pipeline/assets/contracts/<asset>.r0001.yaml
```

进入 Runtime/Release Gate 时必须同时检查仓库内文件真实摘要：

```powershell
python scripts/validate_specialist_asset_contract.py `
  game-pipeline/assets/contracts/<asset>.r0001.yaml `
  --project-root <project-root>
```

创建下一 revision 时绑定旧版本，防止覆盖冻结内容或断开历史：

```powershell
python scripts/validate_specialist_asset_contract.py `
  game-pipeline/assets/contracts/<asset>.r0002.yaml `
  --previous game-pipeline/assets/contracts/<asset>.r0001.yaml `
  --project-root <project-root>
```

校验器是只读工具：它报告预期的 Source、Recipe 和 Subject digest，不自动改写 Contract，也不代替人工审批。

独立评估某一道 Gate，并区分 `pass / revise / blocked / awaiting_human`：

```powershell
python scripts/evaluate_specialist_asset_gate.py `
  game-pipeline/assets/contracts/<asset>.r0001.yaml `
  --gate A0 `
  --project-root <project-root>
```

专业资产 Loop 必须使用 `specialist-asset-production.loop-contract.yaml` 的最小策略，并在状态转换前交叉检查 Registry 引用：

```powershell
python scripts/validate_specialist_asset_loop.py `
  --loop-contract game-pipeline/loops/contracts/<contract>.yaml `
  --snapshot game-pipeline/loops/registry/<loop-id>/snapshot.yaml `
  --project-root <project-root>
```

## 最小端到端回放

P0 完成必须能重放：

```text
批准需求
  -> A0 demand-ready
  -> 生产并提交 Source
  -> A1 source-ready
  -> 构建 Runtime、Godot 导入、目标平台测量
  -> A2 runtime-ready
  -> 意图/技术/QA/权利复核
  -> A3 release-ready
  -> 修改 Source 或 Recipe
  -> 旧 Runtime 与评审自动 stale
  -> 创建新 revision 并返修
  -> 再次通过 A1～A3
```

另需一条 UI 隔离回放：公共资产流程执行前后，UI protected paths 的摘要完全一致。

## 外部依据

- Godot 官方把 `<asset>.import` 视为应提交的重要导入元数据，把 `.godot/imported/` 视为可再生缓存。
- O3DE 区分 Source、Intermediate、Product 和 Cache，并建议相同 Source 与 Builder 版本产生确定性 Product。
- Unity Asset Manager 将资产建模为文件加元数据，区分 Source/Game Ready/Preview，并用不可变 Frozen version 承载版本状态。
- SPDX 提供标准许可证表达式和项目自定义 `LicenseRef-*`。
- B 站技术美术资源规范、资产审计、纹理导入与 LOD 资料显示，规范应前置并同时覆盖内容、导入与性能；具体阈值仍须由项目实测决定。
