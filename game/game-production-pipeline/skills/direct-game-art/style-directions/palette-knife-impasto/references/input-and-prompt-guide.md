# 输入映射与提示词例子

## 图像角色

| 角色 | 采纳 | 不自动采纳 |
| --- | --- | --- |
| palette reference | 颜色与冷暖、比例关系 | 色卡边框、标签、版式 |
| style reference | 笔触、材质、边缘与形体概括 | 原图角色、故事、配色 |
| composition reference | 机位、透视、物件空间关系 | 所有装饰细节、画风 |
| subject / identity reference | 指定主体的特征、比例、服装 | 背景或不相关人物 |
| edit target | 需要被修改的原图和明确保留项 | 未经要求的内容重构 |

角色可以复合，但必须写清。例如原房间图同时是编辑目标和构图依据，而另一张色卡只控制颜色。不要把“参考某图”自动解释为必须像素级复刻。

## 色卡解释

- HEX/RGB 明确值原样进入提示词；允许颜色名称，不强迫用户查色号。
- 色卡图片带有明确可读色号时保留标注；没有色号时描述可见颜色，注明近似。
- 先分明度与用途再配色：大面积底色、主体中间色、小面积强调、深暗与高光。色卡没有比例时，可依据当前主体决定，不能把任意比例宣称为用户规定。
- 用户说“只用这些颜色”时不擅自加入黑、白或金色；提醒油画光照/混色的生成结果仍可能超出精确离散色集。像素级限色是额外后处理任务，需另行明确后才执行。
- 高饱和色卡也能保留刮刀笔触。低饱和是本 skill 的默认方向，不能否决用户鲜亮配色。
- 只给色卡且无主题：做抽象厚涂习作，以大小色面、方向性刀痕和留白展示配色，不补固定房间、人物或玫瑰。

## 文字示例：一般新图

用户：画一间雨后清晨的厨房，暖黄和灰蓝，16:9，安静明亮。

```text
Use case: stylized-concept
Asset type: 16:9 landscape illustration
Primary request: A quiet, bright kitchen after a rainy morning.
Style/medium: Palette-knife impasto oil painting with opaque paint planes, directional knife ridges, and selective coarse canvas exposure.
Composition: A coherent, inhabitable interior with a clear visual focus and restrained peripheral detail.
Lighting/mood: Gentle morning light; calm, airy atmosphere.
Color palette: Warm yellow and gray-blue dominate; preserve their warm/cool relationship.
Materials/textures: Paint thickness follows object planes, with broken edges and small scraped passages rather than uniform grain.
Constraints: No added text, signature, logo, watermark, people, or symbolic narrative objects.
```

这里只补足表现方式；不固定左窗、右桌、羊玩偶或项目故事。

## 色卡示例：只有颜色

用户：#2B3A67、#E8D5B7、#C36F57，用这张色卡生成。

简短说明默认做抽象厚涂色彩习作后直接生成。下列色号来自这个示例用户输入，不是从《心界》资源取样：

```text
Use case: stylized-concept
Asset type: Abstract palette study, square composition
Primary request: An abstract oil-paint study exploring only the supplied palette.
Style/medium: Tactile palette-knife impasto, broad opaque strokes, compressed paint edges and sparse canvas exposure.
Color palette: #2B3A67 as a deep anchor, #E8D5B7 as a broad light field, #C36F57 as a smaller warm accent. Aim to stay within these hues.
Composition: Unequal interlocking paint masses, varied stroke scale, deliberate quiet areas.
Constraints: No recognizable objects, characters, swatch labels, text, logos or added decorative colors.
```

## 图片示例：主体参考

用户上传一张猫的照片：用这个 skill 生一张。

把照片作为主体参考，生成猫的厚涂油画新作；不必追问全部参数。先观察可见毛色和形态，勿预填示例猫的品种或颜色。提示词清楚写 `Image 1: subject reference`，要求保留观察到的核心特征，不要求保留摄影质感。用户如果另说“背景也不变”，改按编辑处理并列出背景保留项。

## 混合输入示例：编辑与配色分离

用户：图一是我房间，只改成图二色卡，家具和机位别动，保留厚涂。

```text
Use case: precise-object-edit
Input images: Image 1 is the edit target and composition source. Image 2 is palette-only guidance.
Primary request: Recolor the room in Image 1 using Image 2, retaining its existing impasto oil-paint treatment.
Color palette: Use the actual visible palette from Image 2; do not copy its layout or labels.
Invariants: Preserve camera, perspective, furniture count and positions, object silhouettes, crop, and existing brushwork. Change color relationships only.
Constraints: No added or removed objects, new symbols, lettering, frames or watermarks. Do not redraw the palette card inside the room.
```

必须真的把两张图传给工具，顺序以实际引用为准。输出要目视复核家具与透视，不承诺工具能像素级保持。

## 透明道具示例

用户：一只奶油白陶杯，道具图，透明背景。

请求单个居中陶杯、完整轮廓和留边、真实 alpha；用较少的刀面交代杯壁曲率，不让纹理吞掉杯把孔洞。不要增加桌面、绿幕、棋盘格或投影底板。若实际文件不透明，应明确检查失败，再针对透明背景修订，而非直接宣称可用。

## 冲突与边界

- 色卡与风格图颜色不一致：按用户指定色卡配色，借风格图的笔触。
- 编辑“只换灯光”且又要移动家具：询问是否允许改变布局，不自动选一条。
- 给了无效文件路径：请求可访问的图；不根据文件名假装观察。
- 用户只要 prompt：输出提示词，不调用工具。
- 用户要 4 张不同场景：4 个独立规格和调用，不生成单张四宫格代替交付。
- 用户明确要非油画风格：服从本次意图，必要时转交其他图像工作流，不强制厚涂。
