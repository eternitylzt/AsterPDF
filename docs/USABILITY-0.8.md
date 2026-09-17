# AsterPDF 0.8 操作变化

## 页面组织拖放

在“页面 → 组织”中拖动缩略图，蓝色插入线表示新位置，松开后插入该位置。支持向前/向后移动、多选页面整体移动、跨行与边缘滚动。移动后保留所选页，支持撤销和保存。左侧缩略图采用相同逻辑。

## 页面操作侧栏

裁剪、旋转、水平/垂直翻转、删除、插入空白页、提取页面和合并均使用页面旁的设置栏。范围可选当前页、全部、指定范围或已选页面；“应用”执行，“取消”关闭。文件选择、保存位置仍使用系统文件对话框。

裁剪先进入工具再拖框，可拖八个调节点或边框，也可输入位置/宽高。框选和调整均不写入 PDF，点击应用才生效。跨页应用使用相同比例，适应不同尺寸及旋转的页面。

**“保留框外内容”默认不勾选：** 真正删除框外文字、路径和图片像素。跨边界的文字或矢量对象会整项移除，可能影响边界内的部分；这在应用前的侧栏中说明。图片框外像素会被清除并重新无损编码，不把整页栅格化。框外或跨边界批注/链接移除，框内批注/链接保留。目标页有表单、动画或媒体时明确拒绝删除式裁剪，可改用保留模式；整批操作失败不会留下半成品。

勾选保留后只改变页面可见框，原内容仍在。两种模式均可撤销。删除仅针对目标页，不是文档全局隐私清理：其它页、附件以及本机撤销/恢复历史仍可能包含相同信息。

旋转可选顺/逆时针 90° 或 180°，应用后保留选择，可继续旋转。空白页在范围内每一页前/后插入同尺寸新页。提取可输出一个 PDF 或每页一个 PDF。合并侧栏可添加文件、已打开文件，排序或移除，输出新文件。首页的独立合并窗口保留。

## 速览窗

原“便捷浏览”更名为“速览窗”。正文切换双页并排时，速览窗也显示双页行。20 页以内默认 10%，超过 20 页默认 5%；右键可切换自动比例或自定义 0.5%–20%。已有手动比例保留。宽度不足时适应窗宽，因此实际显示可能小于设定比例。

移除“单页视图启用整篇文档滚动条”设置；非连续模式的滚动条滚动当前页/双页，跨页可使用速览窗、键盘、页码框或滚轮到边界翻页。

更早的编辑、批注、恢复改进见 [0.7 操作说明](USABILITY-0.7.md)；以上说明取代其中旧的滚动条与速览比例规则。

## English summary

Organizer drag/drop now accepts explicit insertion targets, forward/backward and multi-page moves. Page operations use docked Apply/Cancel settings. Crop supports an adjustable rectangle and current/all/range/selected scopes; outside content is removed by default, with explicit limitations for boundary-crossing objects and interactive pages. Keep-outside mode only changes CropBox. Quick overview mirrors one/two-page layouts and defaults to 10% for up to 20 pages, 5% for longer documents. Single-page scrolling again stays within the current spread.
