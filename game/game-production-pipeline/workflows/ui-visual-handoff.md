# UI Visual 双契约交接

## 输入

UI workflow 先取得已批准且摘要有效的 UI Screen/Flow Contract 与 `game-production-ui-visual/v1`。前者提供 screen/flow、布局、响应式、安全区、焦点和交互事实；后者由主美提供视觉身份、组件状态、字体/图标、Style Frame、Theme 映射和可访问性视觉规则。

## 交接顺序

1. 主美从 Art Direction Contract 推导 UI 视觉方向，建立 UI Visual Contract 和关键屏幕 Style Frame；不得改写 Screen/Flow。
2. UI/UX 绑定 Screen/Flow 与 UI Visual Contract，确认组件清单、状态覆盖和结构边界。
3. UI Visual 执行能力制作 Theme、StyleBox、字体、图标、装饰与组件变体，并将资源路径和 digest 写回 Contract 引用；它执行主美方向，不创建新的视觉方向。
4. Godot 实现者在既定 `.tscn` Control/Container/PanelContainer/Button/HSlider/ProgressBar/Toast 结构中绑定已批准资源。固定结构和资源序列化到 `.tscn` / `.tres`；脚本只切换已声明的状态资源和动效。
5. 目标构建捕获关键屏幕与主要状态，由主美检查 UI 本体；UI/UX 检查结构/可读性，Godot 实现者检查资源/场景/运行时。
6. D3/D4 绑定同一 UI visual/benchmark digest。任何视觉资源、合同、场景或构建变化都触发影响屏幕的重新捕获与评审。

## 失败返回

视觉身份或组件资产不成立：`UI_VISUAL` 返回主美；Screen/Flow、布局或交互不成立：`UI_STRUCTURE` 返回 UI workflow；资源绑定、场景序列化或运行时错误：`UI_TECH` 返回 Godot 实现者；对比度、层级或状态表达冲突：`UI_READABILITY` 返回主美与 UI/UX 联合复审。

线框、默认控件、单线边框和无资产占位内容只能记录为灰盒，不得作为最终 UI 的视觉输入或 D3/D4 成品证据。实现者不得从文字描述自行补定主美的形状、字体、图标或状态语气。

