# Palette Knife Impasto · 刮刀厚涂油画

一个用于 Codex 的生图 Skill，也是 `direct-game-art` 主美技能下的可选画风方向模块。提供色卡、参考图片、文字描述，或将它们组合，Agent 会整理视觉规格并调用内置 `image_gen` 生成图像。

视觉基线提炼自《心界 Mindrift》：有体积的厚颜料、方向性刮刀笔触、粗画布局部露底、冷暖层次和手绘空间。题材、情绪、构图和颜色均可替换；不必画成暗色悲剧。

## 输入与使用

在已加载本 Skill、且提供内置 `image_gen` 的 Codex 环境中使用：

```text
使用 $palette-knife-impasto，画一间雨后清晨的厨房，暖黄和灰蓝，16:9。
```

```text
使用 $palette-knife-impasto，按 #2B3A67、#E8D5B7、#C36F57 生成抽象厚涂习作。
```

```text
使用 $palette-knife-impasto，图一只参考构图，图二只参考颜色，生成一张厚涂油画。
```

```text
使用 $palette-knife-impasto，把这张房间图改成深夜，家具和机位保持不变。
```

```text
使用 $palette-knife-impasto，做一只陶杯透明道具图，保留奶油白刮刀笔触。
```

- 仅提供色卡：默认生成抽象厚涂配色习作。
- 仅提供图片：默认保留可见主体题材生成油画新作；明确要求局部修改时按编辑处理。
- 混合输入：分别标注配色、风格、主体、构图与编辑目标；颜色由指定色卡控制。
- 信息足够时直接生图；无法读取必要图片或硬约束互斥时才补充询问。
- 普通生图使用内置工具，不需要 `OPENAI_API_KEY`。Skill 本身不会安装或提供图像模型；没有图像工具时会说明限制。

## 集成与来源

在本仓库中，本目录由 `direct-game-art` 作为可选画风方向路由读取；只有项目在 D1/D2 方向探索或开发中选择“刮刀厚涂油画”时才加载本目录，不会自动覆盖项目简报、Art Direction Contract、已冻结的风格圣经或 D2 人审结果。调用时应由主美技能先读取本目录的 `SKILL.md`，再按请求读取 `references/` 中的对应规范。

该模块同步自 [wu-jiuqi/palette-knife-impasto](https://github.com/wu-jiuqi/palette-knife-impasto)，来源提交 `097e9d4bb864ccd1ca3eef3f240bdad0ab212ac9`（`feat: 明确通用风格与项目题材边界`）。同步只携带工作流、风格规则和示例；不会自动授予项目资产生成、发布或版权清权权限，仍须遵守主美技能的权利、技术、可读性和人工关卡要求。

若要在独立 Codex 技能目录中使用原始版本，请按上游仓库自身说明操作；本集成目录不负责重新注册顶层 `$palette-knife-impasto` 技能。

## 文件

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | 触发、输入解释、提示词整理、工具调用、验收与交付 |
| [agents/openai.yaml](agents/openai.yaml) | Codex 展示名称和默认调用提示 |
| [references/style-bible.md](references/style-bible.md) | 可覆盖的厚涂视觉基线 |
| [references/input-and-prompt-guide.md](references/input-and-prompt-guide.md) | 图片角色、配色规则与使用示例 |
| [references/mindrift-profile.md](references/mindrift-profile.md) | 仅《心界》项目启用的附加约束 |
| [evals/scenarios.md](evals/scenarios.md) | 维护者使用的行为验收场景 |

## 交付与边界

生成后展示图片，提供最终提示词，并在有文件输出时给出实际路径。项目资源复制进目标项目，默认采用新版本文件名；预览图可保留在工具的输出位置。不会因为生成一张背景就自行改写项目代码。

色号是生成约束，不保证逐像素限色；编辑也不保证几何完全不变。角色连续性、精确尺寸、透明通道、无缝拼接必须实际检查。游戏正式 UI 文字默认交给引擎排版。

通用风格不携带《心界》的剧情禁令。为《心界》工作时才读取独立附加规范，并以当前项目文档为准。

## 验证

使用宿主安装的 `skill-creator/scripts/quick_validate.py` 检查 Skill 元数据和占位符；再按 [行为验收场景](evals/scenarios.md) 做隔离演练。静态校验与不调用生图的演练只能验证工作流，不能证明图像质量。

该仓库包含工作流、风格规则和示例，不包含原游戏图片、角色素材、项目源码或凭据，也不依赖原项目的本机路径。
