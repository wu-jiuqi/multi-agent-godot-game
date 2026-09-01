# P0 专业资产公共底座 Contract 提案

状态：`draft-proposal`

适用阶段：P2/P4/P5 需求定义、P6 专业资产生产、P7 集成、P8 验收、P9 发布

适用资产：UI、美术、3D、动画、VFX、音频、字体、视频及其他进入运行时或发布包的专业内容

## 问题

现有通用 Pipeline Contract 能描述工作项，但不能完整表达专业资产的需求来源、可编辑源文件、运行时文件、权利链、不可变版本、导入配方、平台性能预算和返修历史。垂直切片工作流虽然要求“需求单、源文件、运行时文件、技术规格、使用位置和许可信息”，但缺少统一 Schema、机器门禁和失效传播规则。

直接后果包括：

- 预览图、DCC 源文件、交换格式、引擎资源和生成缓存容易混为同一类“资产”；
- 文件名或路径承担身份，重命名后引用、授权和历史难以追踪；
- 运行时文件可以脱离其源文件、导入设置和工具版本，无法稳定重建；
- 授权只保存一个链接或文字备注，无法阻止来源不明、授权过期或禁止原始文件再分发的内容进入发布包；
- 只检查“导入成功”，不检查目标平台内存、显存、包体、加载、Draw Call、LOD、响度或流式播放等预算；
- 返修会覆盖旧文件，无法回答哪个版本被谁因何原因退回、哪些下游需要重验。

## 外部资料归纳

- Unity Asset Manager 将资产定义为“文件 + 元数据”，并区分 Source、Game Ready、Preview 数据集；冻结版本不可继续修改，修改必须产生新版本。
- O3DE 明确区分 Source Asset、Intermediate Asset、Runtime Product Asset 和可再生 Asset Cache，并用稳定标识追踪依赖。
- Godot 根据源文件摘要触发重新导入；`<asset>.import` 保存导入配置并应进入版本控制，`.godot/imported/` 是可再生缓存，不应提交。
- SPDX License Expression 可表达标准许可证、组合许可证和项目自定义 `LicenseRef-*`，适合做机器可读的授权入口；商业授权仍需同时保存合同或购买证明。
- B 站的 Blender→Godot、纹理导入检查和 LOD 实践材料说明，真实制作问题通常发生在 DCC 输出、引擎导入设置和目标平台表现的连接处；视频适合发现现场问题，但最终门禁应以引擎官方规范和项目实测为准。

## 决策

新增独立的 `Specialist Asset Contract`，作为所有专业资产的横向交付信封。它不替代 UI Spec、美术需求、动画状态表或音频 Cue Sheet 等领域事实源，只负责把一个已批准需求安全地送到可发布运行时资产。

每份 Contract 必须满足十二条不变量：

1. `asset_id` 是稳定身份，不随文件名、目录或展示名称变化。
2. 需求必须引用已登记的上游事实源、使用场景和玩家可感知目标。
3. 可编辑 Source、交换/中间文件、Runtime/Product 和 Cache 必须分层登记。
4. 冻结版本不可原地修改；文件或关键元数据变化必须创建新 `revision`。
5. 每个文件使用仓库相对路径或受控 URI，并绑定 SHA-256。
6. Runtime 必须绑定 Source digest、导入配方 digest、工具链版本和目标平台。
7. 权利状态为 `unknown`、`blocked`、证据缺失或已过期时，发布必须 fail closed。
8. 性能预算必须绑定目标平台、硬件档位、测试场景和测量证据，不设置脱离项目的全局万能数值。
9. 生产者自检、内容意图验收、技术集成验收和独立 QA 分开记录；小团队可由同一人兼任，但不得合并成一个无对象摘要的“已确认”。
10. 源文件、导入配方、依赖或权利发生变化时，相关 Runtime、性能证据和批准自动变为 stale。
11. 返修创建新版本并保留旧版本、退回原因、责任人、修复目标和所需复检，不覆盖已批准证据。
12. 任何 Preview 都不能代替 Source、Runtime、授权或目标平台验收。

## 建议 Schema

```yaml
specialist_asset_contract:
  schema_version: game-production-specialist-asset/v1
  identity:
    asset_id: asset:<project>:<domain>:<name>
    project_id: <project>
    asset_kind: ui|2d-art|3d-model|animation|vfx|audio|font|video|other
    display_name: <name>
    revision: 1
    lifecycle_state: draft
    variant_of: null

  demand:
    request_id: request:<project>:<id>
    upstream_refs: []
    use_contexts: []
    player_facing_outcome: <observable outcome>
    acceptance_intent: []
    target_milestone: <milestone>
    priority: p0|p1|p2

  responsibility:
    requester: <position-or-human-id>
    producer: <position-or-human-id>
    intent_reviewer: <position-or-human-id>
    technical_integrator: <position-or-human-id>
    qa_reviewer: <position-or-human-id>
    rights_reviewer: <position-or-human-id>

  consumer_boundary:
    authoritative_source_refs: []
    access: read_only
    generated_output_paths: []
    protected_paths: []
    reverse_write_requires_separate_workflow: true

  source_package:
    editable_truth:
      - file_id: source:<asset-id>:master
        path: <repo-relative-path-or-controlled-uri>
        sha256: <64-lowercase-hex>
        format: blend|psd|kra|wav|svg|other
        tool: {name: <dcc>, version: <pinned-version>}
    dependencies: []
    version_control:
      backend: git|git-lfs|perforce|external-dam
      immutable_revision_ref: <commit-or-version-id>
      exclusive_lock_required: false

  rights:
    provenance: original|commissioned|marketplace|open-license|generated|mixed
    creator_or_supplier: <identity>
    source_uri: <uri>
    license_expression: <SPDX-expression-or-LicenseRef-id>
    license_text_or_contract_ref: <evidence-ref>
    acquisition_proof_ref: <evidence-ref>
    commercial_use: allowed|conditional|forbidden|unknown
    modification: allowed|conditional|forbidden|unknown
    compiled_distribution: allowed|conditional|forbidden|unknown
    raw_redistribution: allowed|conditional|forbidden|unknown
    attribution_required: false
    attribution_text: null
    platform_scope: []
    territory_scope: []
    expires_at: null
    ai_use_restrictions: []
    clearance_state: cleared|conditional|blocked|unknown

  import_recipe:
    engine_adapter: generic|godot
    engine_version: <pinned-version>
    interchange_format: <format>
    preset_ref: <path-and-digest>
    sidecar_refs: []
    postprocess_ref: null
    toolchain_lock_ref: <path-and-digest>
    reproducibility: deterministic|best-effort
    non_determinism_reason: null

  runtime_package:
    source_subject_digest: <digest>
    recipe_digest: <digest>
    outputs:
      - file_id: runtime:<asset-id>:<platform>:<role>
        path: <repo-relative-path>
        platform: <platform-profile>
        role: primary|lod|collision|material|texture|stream|scene|other
        format: <runtime-format>
        sha256: <64-lowercase-hex>
    cache_paths: []

  performance:
    budget_profile_ref: <approved-project-budget>
    measurement_context:
      platform: <platform>
      hardware_profile: <profile>
      scenario_ref: <repeatable-test-scene>
      build_ref: <build>
    metrics:
      - metric_id: <metric>
        comparison: lte|gte|eq
        limit: <number>
        unit: bytes|ms|count|db_lufs|kbps|other
        measured: <number>
        evidence_ref: <report>

  verification:
    automated_checks: []
    producer_self_check: {status: pending, subject_digest: null, evidence_refs: []}
    intent_review: {status: pending, subject_digest: null, evidence_refs: []}
    technical_review: {status: pending, subject_digest: null, evidence_refs: []}
    qa_review: {status: pending, subject_digest: null, evidence_refs: []}
    rights_review: {status: pending, subject_digest: null, evidence_refs: []}

  rework:
    current_issue_refs: []
    history: []
    allowed_reason_codes: [REQ, SRC, RGT, IMP, PERF, REG, SCOPE]

  publication:
    release_state: not-ready|candidate|approved|withdrawn
    frozen_revision_digest: null
    approval_refs: []
    attribution_manifest_ref: null

  integrity:
    contract_subject_digest: null
```

Schema 保持资产类型无关；2D、3D、动画、VFX、音频和 UI 的专属规格通过 `domain_extension` 或上游领域文档扩展，不把所有领域字段塞进公共核心。

## 状态机与门禁

```text
draft
  -> ready               需求、责任、权利可行性和预算已定义
  -> in_production       冻结生产输入
  -> source_submitted    Source 包、依赖和权利证据齐全
  -> runtime_built       Runtime 与导入配方绑定
  -> integrated          目标场景/系统成功消费
  -> review              意图、技术、权利和 QA 复核
  -> approved            绑定当前 subject digest 的批准成立
  -> released            进入已登记构建
```

任何非终态都可以进入：

- `rework_required`：输入仍可修正，必须登记原因代码和返回责任人；
- `blocked`：权利、依赖、预算或决策缺失，无法在现有授权内继续；
- `withdrawn`：已批准或已发布版本因权利、质量或兼容性问题撤回。

### 退回路由

| 原因码 | 问题 | 默认返回 |
| --- | --- | --- |
| `REQ` | 需求、表达目标或使用场景不清 | 原需求定义阶段与 requester |
| `SRC` | 源文件质量、内容或可编辑性失败 | P6 producer |
| `RGT` | 来源、授权、署名或分发权失败 | rights reviewer；未解除前 blocked |
| `IMP` | 导入、依赖、格式或工具链失败 | P7 technical integrator / 工具管线 |
| `PERF` | 目标平台预算失败 | P6 producer + P7 integrator |
| `REG` | 集成回归、引用或下游消费失败 | 变更责任方 + QA |
| `SCOPE` | 新需求改变已批准范围 | 原定义阶段；必要时回 P0 和人工决策 |

## Godot 适配规则

- 原始 DCC Master 不默认直接作为运行时事实源；3D 优先使用明确导出的 glTF/GLB 交换文件，除非项目批准直接 `.blend` 导入并锁定 Blender 版本。
- 需要导入的源文件和 `<asset>.import` 一同进入版本控制；`.godot/imported/` 仅登记为 cache，不提交、不人工编辑。
- 导入设置、Advanced Import Settings、名称后缀和 `EditorScenePostImport` 脚本都属于 `import_recipe`，变化必须使 Runtime 和相关验收 stale。
- 3D 资产按项目预算记录 LOD、材质、贴图、碰撞、骨骼/动画和代表性场景测量；UI、2D、音频和字体使用各自预算指标，不能只套用三角面数。
- 固定可复用资产优先交付预置 `.tscn` / `.tres` 场景或资源；运行时动态生成只在已批准的技术理由下使用。

## UI 回写隔离

本提案不得改变现有 UI 方案的事实源、布局数据或回写协议。

- UI 需求、Screen/Flow、布局和视觉规则仍由 UI 工作流拥有。
- 资产 Contract 仅通过 `authoritative_source_refs` 和 `consumer_refs` 读取 UI 事实。
- `consumer_boundary.access` 对 UI 默认固定为 `read_only`。
- 只有 `generated_output_paths` 可以由资产管线写入；UI 源路径必须进入 `protected_paths`。
- 如果资产返修需要改变 UI 布局、组件状态或交互意图，必须新开 UI 变更工作流，不能由资产返修直接反向覆盖。
- 首个回放测试必须在执行前后比较 UI protected paths 的摘要，证明零写入。

## P0 落地顺序

1. 固化 Schema、状态机、原因码和摘要规范，生成 `specialist-asset-contract.template.yaml`。
2. 实现只读校验器，先检查稳定 ID、路径、SHA-256、Source/Runtime 分层、授权 fail-closed、版本失效、预算证据和角色分离。
3. 增加一份非 UI 的 3D 静态道具合法样例，以及缺授权、配方漂移、性能超预算、覆盖冻结版本等失败夹具。
4. 在 Godot 适配层登记 `.import`/`.godot`、glTF/GLB、预置场景、导入脚本和目标平台测量规则。
5. 将垂直切片 P6 改为消费 Asset Contract 的 ID、版本和 digest；不改 P0～P5 领域事实源。
6. 完成端到端回放：需求 → Source → Runtime → 导入 → 测量 → 四方复核 → 批准 → 修改 Source → 自动 stale → 返修 → 再批准。
7. 最后增加一个 UI 只读消费夹具，验证资产流程不会改动 UI protected paths；它不是 UI 回写方案的替代实现。

## P0 验收标准

- 合法样例通过，缺字段和不变量破坏均以非零退出码失败。
- `unknown/blocked` 权利、缺少授权原文/合同或购买证明、授权过期时不得进入 release candidate。
- Source、依赖、导入配方或权利变化会让 Runtime、性能数据和批准 stale。
- 每个 Runtime 输出都能追到 Source digest、recipe digest、工具链版本和目标平台。
- 预算同时存在“批准阈值”和“目标场景实测”，仅填写估算值不能通过技术验收。
- 返修不会覆盖冻结版本，历史能重建退回原因、责任和复检范围。
- 端到端回放能证明错误被送回正确责任方，而不是统一退给技术人员。
- UI 隔离测试证明公共资产流程执行前后 UI protected paths 摘要不变。

## 不纳入本次 P0

- 不立即创建美术、动画、VFX、音频或 UI 的长期 Agent；先用 Contract 和真实回放验证责任边界。
- 不建立重型 DAM 服务或数据库；先采用仓库内 YAML + 受控大文件后端。
- 不给所有项目写死统一三角面、贴图、内存、响度或加载阈值；阈值由项目预算 Profile 决定。
- 不实现 UI 双向合并或回写；UI 保持独立事实源和工作流。

## 参考资料

- [Godot Import process](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/import_process.html)
- [Godot Import configuration](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html)
- [Godot Visibility ranges (HLOD)](https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html)
- [Open 3D Engine Asset Pipeline](https://docs.o3de.org/docs/user-guide/assets/pipeline/)
- [Unity Asset Manager Basic concepts](https://docs.unity.com/en-us/cloud/asset-manager/basic-concepts)
- [Unity Asset Versioning](https://docs.unity.com/en-us/cloud/asset-manager/asset-versioning)
- [SPDX License Expressions 3.0.1](https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/)
- [Khronos glTF Runtime 3D Asset Delivery](https://www.khronos.org/gltf/)
- [Git Large File Storage](https://git-lfs.com/)
- [B 站：Blender 到 Godot 完整工作流](https://www.bilibili.com/video/BV1XKNAePEnX/)
- [B 站：纹理导入设置检查与优化](https://www.bilibili.com/video/BV1gT4y1C7yS/)
- [B 站：Blender 到 Godot 游戏就绪资产与 LOD](https://www.bilibili.com/video/BV1Jqxpz2E89/)
