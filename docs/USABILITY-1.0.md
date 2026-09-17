# AsterPDF 1.0 — 使用与更新

[English](#english)

## 换色

在“对象编辑 → 换色”中选择本页、全部页面、页码范围或框选区域。源颜色自动跟随范围刷新，按采样得到的可见面积比例排序；最多显示 64 个代表色，比例为估计值，并非 PDF 操作符数量。渐变与抗锯齿颜色会聚合；小面积颜色可用“取源色”在页面上点击选择，并调整容差。

选择源色、目标色后可直接应用，或“添加对”组成多个替换对。列表中的所有对只匹配原始颜色，按列表顺序取第一次匹配，不发生连锁替换。选中列表项可更新或移除。输入方案名后保存，其他页或文件打开换色面板即可载入；同名保存会覆盖该方案。方案保存替换对、图片开关、反色和容差，不绑定原文件或页码范围。

“同时修改栅格图片”用于真正的内嵌图片。新安装默认启用，原有偏好会保留。关闭它仅修改支持的文字和矢量纯色。图片保持原始像素尺寸，修改后以无损 RGB 像素保存；不保证保留原 JPEG 压缩流或 CMYK 色彩空间。区域外内容保持原显示；“展示换色区域边界”控制最近应用区域的辅助框，辅助框不会写入 PDF。

**限制**：矢量渐变着色、图案填充、批注和动画帧不参加换色；模板/颜色键蒙版等图片会明确拒绝处理。区域换色使用保留矢量的裁剪组，跨边界文字在部分第三方提取器中可能重复。采样色不是所有 PDF 内部颜色的穷举。

## 搜索与阅读

- 已应用或保存的新文字可搜索。文本编辑中发起搜索会先应用当前草稿；无法应用时保留草稿并说明原因。
- “上一条 / 下一条”、`Shift+F3 / F3` 循环定位结果；当前结果颜色更突出。
- 速览窗以半透明发光色带显示匹配位置，不依赖微缩文字是否能看清。
- 速览窗底部显示当前可见内容末端的文档进度；按页数和页内位置计算。小文件自动适配预览高度。
- 默认书签名为页码；仍可右键重命名。

## 日常体验

新安装默认深色。已有用户的显式偏好不改变。“Settings → 语言/Language”固定显示，方便跨语言查找。首页“最近文件”增加打开时间、文件大小和所在目录；旧历史中没有记录的时间会明确显示未记录，不伪造打开时间。

全程序关闭按文档逐个处理，先跳到待保存文档，再提示保存、放弃或取消。保存失败会停止关闭并保留文档。动画画质、播放、图片、页面及换色等重复设置从首选项同步到打开的工具区。

## 性能与验证

密集图表的对象识别不再反复压缩临时流，复用不绘制内容的解析背景；纯数字参数避免创建临时 PDF 解析器。图片换色使用 Pillow 通道查找表与蒙版，避免 Python 逐像素循环。换色面板不会触发无关的对象重新识别。

在用户提供的三页科研 PDF 上验证了识别、移动、多对换色、保存重开与原文件未改动。具体耗时和发布包实测见 [验证记录](VALIDATION.md)。密集页首次对象识别仍可能耗时数秒；这不是完整 Acrobat 兼容声明。

## English

Version 1.0 adds scope-aware sampled palettes (at most 64 representative colors), image/region recoloring, simultaneous first-match replacement pairs and named reusable schemes. The eyedropper and tolerance handle colors absent from the palette. Schemes retain all pairs, tolerance, inversion and image settings, while the scope remains document-specific. Recolored raster images retain pixel dimensions and are stored losslessly as RGB, rather than retaining their original compressed stream/color space.

Applied text is searchable; F3 / Shift+F3 navigate matches, and translucent overview bands reveal their locations. The overview footer reports reading progress, bookmarks default to page numbers, and Home adds recent-file metadata. New installations default to dark mode. Settings → 语言/Language remains discoverable in either language.

Closing the app visits each modified document and handles Save / Discard / Cancel sequentially. Failed saves stop closing. Central preferences synchronize duplicated controls, including animation quality.

Object discovery avoids repeated scratch-stream compression; image replacement uses native Pillow masks instead of Python pixel loops. Vector gradients, pattern fills, annotations and animation frames are not recolored. Stencil/color-key images and complex unsupported streams fail explicitly. A sampled palette is an estimate of visible coverage, not an exhaustive PDF color inventory. See [validation](VALIDATION.md) for measured results and untested platforms.
