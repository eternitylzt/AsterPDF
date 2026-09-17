# 0.2 usability changes / 本次可用性改进

This records delivered behavior, including remaining limits. 这里区分实际改动与仍然存在的边界。

| 用户反馈 | 0.2 处理结果 |
| --- | --- |
| 单页不翻页、滚轮/方向键失效 | 修复布局和滚动回调冲突；左右/PageUp/PageDown 翻页，上下滚动，单页边界滚轮翻页。实际输入事件已测。 |
| 演示模式难以操作/退出 | 修复焦点控件拦截；方向键/空格翻页，Escape 退出。原位媒体控制仍可使用。 |
| 阅读栏目、选择与手形、栏目关系 | 删除阅读栏目；上层放选择/手形，下层四个模块。选中模块与子工具区同背景色。 |
| 批注闪动、列表、字符选择、样式、作者 | 保留旧渲染直到新页图到达；按字符选文；侧栏显示当前页批注；可设置颜色、宽度、透明度、文本字体/字号、箭头端点/虚线和作者。单击不生成零长度形状。 |
| 对象编辑绕弯 | 进入即识别，翻页继续识别；去掉长列表和必需的识别按钮。文字双击就地编辑；自动匹配系统字体并显示替代提示。拖动移动、右下角缩放、Delete 删除；修改后自动更新识别。 |
| 裁剪顺序 | 先选择裁剪，再画区域；提交前保留裁剪语义说明。 |
| 缩略图跟随与留白 | 跟随当前页并滚入可见区域；缩略图居中，侧栏缩窄，导航页签用图标和提示。 |
| 撤销/重做与工具栏 | 独立快捷按钮；“⋯”按需添加保存、区域复制、原图提取、媒体等工具，保存在本机设置。 |
| 动画/媒体栏目 | 不占四个主栏目；控制放在文档原位、菜单和可选快捷工具栏。 |
| 更新、作者 | 关于加入 Zhentong Li 和联系信息，参考用户指定的 EPS Live Viewer 项目。更新地址等上传后配置；版本比较和下载按钮已实现，本项目真实 Release 网络查询未验证。 |
| 四种视图 | 单页、连续、双页、连续双页。双页左右翻动一个跨页组。 |
| 原图提取难定位 | 本页实际出现的栅格图片描边；点击提取原始数据。选择工具也可选中图片后右键提取。 |
| 精确选文与编辑菜单 | 字符边界选择，不再按整行；编辑菜单改为 PDF 对象编辑与批注设置等操作。 |
| 修改标记、合并和提取 | 文件名加 `*`；合并文件队列含首页预览，可拖入/排序/移除，按序追加到当前文档。提取支持一个 PDF 或每页独立 PDF；界面移除独立拆分命令。 |
| 接近常见 PDF 编辑器的操作 | 编辑状态持续、直接鼠标操作、键盘删除、输入前后明确状态；采用相近操作逻辑，不宣称完整 Acrobat 兼容。 |

## 仍有限制 / Remaining boundaries

- “整个文件进入编辑模式”通过访问页面时自动识别实现，不在进入时阻塞扫描全文件。很密集的页面仍可能需要等待，可取消。
- 只编辑可识别的顶层单元；不能递归进入任意嵌套 Form 修改内部文字。文字输入限水平局部块；多种内部样式替换后采用所选样式，没有全文重排。
- 文本选择限单页、有文字层的内容。批注列表当前按页显示；没有完整评论线程、任意批注顶点编辑或多批注整体变换。
- 批注文本可选标准拉丁/CJK 字体。任意系统字体选择适用于 PDF 内容编辑；不是所有字体格式、字形和嵌入权限都可用。
- 快捷工具栏自定义为显示/隐藏已提供的快捷操作，不支持拖动任意菜单项或任意位置重排。
- 合并队列控制追加文件的次序。当前打开文档保留在前；已有页面仍可通过缩略图重排。
- macOS/Linux 配置未在实际系统执行。Acrobat 本次未启动；用户已反馈旧版批注在 Acrobat 正常，本次使用保存重开和独立渲染验证。

## 实用测试路径

`tests/test_practical_ui.py` covers actual Qt input sequences:

1. Four view modes → wheel/key paging → thumbnail tracking → presentation → Escape → hand pan.
2. Drag four characters from the middle of a word → clipboard → partial highlight → author/sidebar → arrow drag → save/reopen/delete.
3. Enter Edit → double-click label → type → commit → drag → image resize → Delete → undo → another page → return → save/reopen.
4. Original image outline/click → crop-first drag → merge file preview/order/remove.
5. Paste Chinese plus a newline using a system font → page-change commit → re-edit the newly embedded text → Save with active editor → reopen.
6. Chinese FreeText style change and styled arrow → save/reopen and appearance inspection.

The original twelve tests continue to cover extraction, page operations, vector/group preservation, recovery, untouched media streams and search/language behavior. Detailed run results are in [VALIDATION.md](VALIDATION.md).
