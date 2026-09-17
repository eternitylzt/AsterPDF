# 0.5 操作改进 / Editing improvements

## 文字与图片

双击文字块后可以用光标选取部分文字，在左侧调整样式。单纯选择、复制或退出不会写入 PDF；取消关闭编辑器和文字属性面板。空白处新增文字：文字 → 插入文本框 → 单击/拖动页面 → 输入 → 应用。草稿原地显示选区样式，打字时不会逐字生成 PDF 或刷新页面。

保存时，未改动字符继续使用原有 PDF 字体资源、编码、颜色、字号和变换。删除字符不要求本机安装字体。只有新增或明确修改样式的字符才需要可用输入字体，优先检查内嵌字体，再使用本地匹配或替代字体。字体名与替代建议保留在属性面板。不能可靠映射的字体/字形会保留草稿并说明限制，仍可取消、移动或删除整个对象。

**限制：**文字输入针对水平局部文字块。逐字编辑支持可靠映射的单字节字体和 Identity-H CID 编码；合字、描边/裁剪字、其它 CID 编码、嵌套 Form 内文字可能不支持。按基线调整局部间距，不提供段落自动重排。编辑预览使用 Qt 富文本；系统没有原字型时，预览可能与保存后的原 PDF 字形有所不同。

图片：点击图片按钮立即选文件，然后单击放置或拖出大小。选中图片可以 Ctrl+C，页面上 Ctrl+V。移动和右下角缩放直接拖动；“保持比例”可关闭，Shift 临时切换。复制按原图分辨率，软蒙版合成到剪贴板图像；可用时保留压缩原图数据用于本程序内粘贴。

## 批注

- 当前工具保持选中背景；单击批注在侧栏选择，再改颜色、线宽和透明度。“样式”中的参数也能应用到选中的自有批注。
- 实心/空心箭头大小与线宽分开设置；拖动椭圆时即显示椭圆预览。
- 便笺/文本单击查看、双击修改；文本批注默认无边框，可单独设置边框颜色、线宽、虚线。
- 高亮、下划线、删除线先显示临时预览，随后替换为保存到 PDF 的标准批注。
- 修正不透明度未显式写入 PDF 时被误读为 5% 的问题；默认不透明度正确按 100% 读取。

## 工具与窗口

- 批注、编辑、页面、提取：再次点击当前模块即可回到普通阅读。
- 工具栏透明度同时作用于主栏与子栏，文档显示在下面；100% 恢复独立工具栏区域。
- 右键工具栏 → 自定义：勾选显示，拖动列表项调整排列。不是直接拖动工具栏上的按钮。
- 书签仅显示星形图标；浅色图标加深；链接悬停为手指光标；导航空白区域可右键收起/自动隐藏。
- 最小化记录原屏幕，恢复时纠正意外的跨屏迁移。

## 响应速度

小操作只更新改动页，保留其它页面缓存及当前页清晰的过渡图。进度条延迟 450 毫秒显示；输入草稿和拖动预览不保存 PDF，应用或结束拖动后才提交一次。新增图片/批注使用小的临时页导入，避免再次序列化整份媒体文档。完整恢复副本仍需写入，较大的文档并非零等待。

## English summary

0.5 fixes no-op text mutation and retains original glyph resources for unchanged characters, including partial deletion without local fonts. Rich drafts support character selections, explicit Apply/Cancel, inline text boxes and input-only font fallback. Images have independent placement, clipboard copy/paste and aspect/free drag resizing. Annotation styles, independent arrowhead size, optional text borders and note selection are integrated into the sidebar. Modules toggle off, toolbars overlay transparently, customization rows reorder tools, links have a hand cursor, and monitor restoration is checked on real Windows displays.

See [compatibility boundaries](COMPATIBILITY.md) and [actual validation](VALIDATION.md). These changes do not claim full Acrobat editing compatibility.
