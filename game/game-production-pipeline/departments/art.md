# 美术部门模板

## 存在条件

当项目需要持续的视觉方向、跨多类资产的一致性、专业制作管线或独立视觉验收时，可在批准的 Organization Change Set 中实例化本部门。小型项目可由一个主美 Position 同时承担方向与有限制作；不要为了形式完整强制增加管理层。

## 部门责任

- 由主美维护 Art Direction Contract、风格圣经、基准和视觉验收；
- UI 在范围内时，由同一主美维护 UI Visual Contract、关键屏幕 Style Frame、组件视觉样例、字体/图标方案、语义 Token 和组件状态矩阵；
- 根据实际范围配置概念、2D、3D、角色、环境、动画、VFX、技术美术和 UI 视觉执行能力；
- 把游戏/内容/UI 功能需求转化为专业资产 brief，并使用 Specialist Asset Contract 交付；
- 与技术集成者共同维护导入规格、性能预算、工具和目标平台证据；
- 与权利审查者维护来源、许可、署名和生成式 AI 记录；
- 向 QA 提供可观察的表现标准，不自行替代独立验收。

## 关键边界

- 主美拥有 UI 的视觉签名，不拥有 UI 信息架构、Screen/Flow、布局行为与交互逻辑；
- UI/UX 拥有响应式、安全区和焦点导航；主美的视觉调整若触及这些事实，必须走 `UI_STRUCTURE` 返工或变更请求；
- UI Visual 是受主美指导的执行能力，负责把 UI Screen/Flow Contract 与 UI Visual Contract 映射为 Theme、字体、图标、StyleBox、组件变体与场景资源，不新增争夺视觉方向的岗位；
- UI 工作流同时接收两份已批准且摘要有效的 Contract。Godot 实现者只消费这些输入与视觉交付物，不能从线框自行补定最终画风；
- 技术美术可提出引擎方案和工具需求，不拥有核心玩法或最终技术架构；
- 美术资产生产不能反向改写上游设计意图；冲突通过变更请求处理；
- D3 先证明代表性引擎基准，D4 冻结生产基线后才允许批量最终资产生产。

## 最小交接

每次交接包含 Contract ID/revision/digest、目标域、源文件与运行时引用、视觉规则、技术 Profile、预算、权利状态、评审证据、开放返工和下一 Gate。

UI 交接额外包含 UI Visual ID/revision/file digest/subject digest、只读 Screen/Flow 引用、关键屏幕 Style Frame、正反例、完整状态矩阵、字体/图标及 Theme 资源映射。D3 检查目标构建中 UI 本体及主要状态；D4 冻结同一基线并关闭 `UI_VISUAL / UI_STRUCTURE / UI_TECH / UI_READABILITY` 返工。默认平面矩形、单线边框或无视觉资产的占位控件只能作为灰盒。自动校验检查结构、引用、摘要和证据存在性；视觉质量由主美负责判断。
