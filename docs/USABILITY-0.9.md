# AsterPDF 0.9 操作说明 / Release notes

[中文首页](../README.zh-CN.md) · [English home](../README.md) · [实测记录 / Validation](VALIDATION.md)

## 页面操作

进入页面组织后，“当前页”以平铺预览里当前选中的页面为准。旋转栏提供旋转按钮和角度；翻转栏提供翻转按钮，点击便写入当前工作副本并刷新预览，无需再按“应用”。可先设置当前页、全部、范围或多选再操作。

退出该栏保留结果；同一栏的“取消”撤回该栏此次旋转/翻转。取消等待正在执行的操作完成后一起撤回。切换到另一操作栏或执行撤销/重做后，先前栏的操作不再属于当前取消范围。普通操作可继续使用全局撤销；原文件只有保存时才被更新。镜像仍拒绝带批注、链接或媒体的页面。

## 文字编辑与文本框

文字栏与通用属性栏独立显示，切换不会留下零宽度或空白分栏。进入编辑默认显示文字设置；双击原文后按字符选择调整样式。仅进入再退出不会重写原字形。原文的复杂字体、合字和嵌套结构仍有兼容边界，见兼容性说明。

“插入文本框”后在页面单击/双击放置，可立即输入。起始宽度仅约一个光标，随输入扩展；拖动放置也可预先给定宽度。拖动文本框边缘或八个控制点设置宽度后自动换行，内容超出高度时向下扩展。上方圆点可旋转，文字栏的宽度（PDF 点）与角度可精确调整。中文使用可嵌入字体，文字保持可检索，不将文本框栅格化。

应用或 `Ctrl+Enter` 写入 PDF；取消或 `Esc` 放弃草稿。已有文档中的任意文字块不自动变成可全文重排的文本框；自动换行与旋转控制针对本软件新增的文本框。长文档对象识别按访问页执行。

选中图形后，方向键按一个屏幕逻辑像素微移，Shift＋方向键移动十个。没有选中对象时方向键继续用于阅读。

## 设置

**设置 → 首选项**（`Ctrl+,`）分为常规、阅读/工具栏、速览窗、批注、对象/页面、导出/播放、恢复。保存后同步到已打开文档及对应控件，不用重新打开文件。文字草稿保留，不因为进入设置而自动提交。参数作为工具默认值，不自动改写已存在的 PDF 对象或批注。

- 界面字体：小、中、大三档。
- 首页：可显示或隐藏最近文件。
- 工具栏：可显示/隐藏、自动隐藏、调不透明度、自定义按钮。透明的是背景，图标/文字保持可读；页面初始排在工具栏下方。
- 速览窗：显示开关、位置、比例、尺寸、不透明度。
- 批注：作者、文本字体/字号、颜色、线宽、透明度、箭头样式与大小、虚线、文本边框、显示和排序。
- 对象/页面：新文本框默认字体/大小、图片宽高比、图形样式、换色默认值、旋转角度、裁剪与提取选项。
- 导出/播放：DPI、宽度、格式、JPG 质量、动画画质、循环和默认倍速。
- 恢复：目录用于新打开文档；已有文档保留原恢复位置直到关闭。

设置中的值在保存时覆盖相应局部默认值。文件页码范围、所选对象、裁剪框和替换源颜色是当前操作的选区，在对应并排栏内设置；不会保存为跨文档选区。

发布默认工具：指针、手形、四模块、页码、缩放、撤销、重做、保存、宽度、整页、书签、连续滚动和速览窗。已有自定义配置继续保留，可右键重新选择。

## 速览窗与书签

速览窗自动适应缩略图宽度和全部页面的总高度，但不超过当前屏幕可用高度的一半及阅读区高度。20 页内默认 10%，超过 20 页默认 5%。手动调整尺寸后可在右键菜单恢复自动尺寸。默认不透明度为 80%。

悬停速览窗后，Ctrl＋滚轮每格调整约 1 个百分点，范围 0.5%–20%；普通滚轮继续浏览预览。双页阅读时显示双页。点击缩略图定位，拖蓝框浏览，按住右键拖动预览。

当前页有阅读书签时，主工具栏显示实心星。书签列表支持右键重命名；右侧淡色标明页码和该页顶部相对于整个文档累计页高的百分比。这是页面位置，不是目录层级或当前滚动条百分比。阅读书签存在本机阅读状态中，不写为 PDF 批注。

## English summary

- Page transforms operate on the current organizer item; the Rotate/Flip controls take effect immediately. Cancel rolls back that tool session, including an in-flight operation. Leaving keeps changes. Saving writes the original file.
- The text pane reliably reappears. Newly authored native PDF text boxes start at caret width, grow while typing, wrap after border resizing, and rotate via the circular handle or angle control. Existing arbitrary PDF paragraphs are not automatically reflowable.
- Arrow keys nudge selected objects by one logical display pixel; Shift nudges ten.
- `Ctrl+,` opens categorized preferences. Saving synchronizes defaults and controls across open documents while preserving text drafts. Selection-specific page ranges/regions remain in their local operation panes.
- Overview fits content with a half-screen height cap, uses 80% default opacity, and changes scale by one percentage point per Ctrl+wheel notch. Manual sizing can be reset to automatic.
- Home offers recent files; named bookmarks show page/vertical-document position and a filled toolbar star. Interface text has three sizes, and the toolbar uses repaint-safe translucent backgrounds.

本版是发布准备版本。Windows 已实测；macOS/Linux、真实 Acrobat 和物理打印机仍未实测。不执行 PDF 任意脚本，不承诺任意动画、复杂排版或所有编码兼容。
