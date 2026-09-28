# 填写 PDF 表单 / Fill PDF forms

## 使用

1. 打开带标准 AcroForm 字段的 PDF，使用指针工具；可填写区域默认淡蓝高亮。
2. 点击文字、多行、下拉或列表字段原位填写；点击复选框或单选按钮选择。日期字段右侧的日历按钮用于选择日期。
3. Tab / Shift+Tab 切换字段，空格切换获得焦点的复选框/单选按钮。Tab 到达按钮只获得焦点，不自动改变值。Enter 完成单行输入；Esc 取消尚未提交的当前字段输入。
4. 输入稍作停顿后自动记入当前文档的临时修改；**不会自动覆盖原文件**。Ctrl+S 保存，或“另存为”创建副本。未保存修改有星号，关闭时仍会询问保存。
5. 编辑框中 Ctrl+Z/Ctrl+Y 撤销/重做输入，退出字段后可使用文档撤销/重做。恢复副本同时记录尚未提交的表单草稿。

“视图 → 高亮 / 隐藏可填写区域”可切换高亮；“Settings → 首选项 → 阅读 / 工具栏”中也可设置。高亮只用于阅读，不写入 PDF。原个人阅读书签现统一称为“收藏”，原有本地记录和自定义名称不变。

## 支持与边界

- 标准文字、单/多行、字符长度限制、密码显示、按格输入、复选、单选、下拉、可编辑下拉、列表及多选列表。列表显示名称与保存的值分别处理；同名字段同步更新。
- 识别常见 `AFDate_FormatEx` 日期格式，如 `dd.mm.yyyy`、`dd/mm/yyyy`、`mm/dd/yyyy`、`yyyy-mm-dd`；使用本机日历，不执行文档脚本。无效日期会在页内提示，保留输入供修改。
- 保存保留可交互的字段树、字段值、按钮状态和显示外观；不把表单压平。中文等新增字形使用嵌入字体外观，字体仅嵌入使用的字形，尽量保持原字号和颜色。原字体缺字时使用内置后备字体；无法显示的字符会提示。
- 只进入字段或复制文字不会修改文档。富文本字段修改时按纯文本保存，进入字段时会提示；原样访问不修改样式。
- 自定义计算、校验和格式化脚本不执行，相关字段会提示人工核对；必填标志会显示，但允许保存未完成的草稿。
- XFA、已签名文档的填写、创建/验证数字签名、脚本按钮与自动提交不在本轮支持范围。普通画线表格或扫描图片不是可交互表单，仍可用文本批注手工填写。

## 验证范围

Windows 原生 Qt 已验证原位输入、Tab/Shift+Tab 路径、空格选择、日历选择、列表键盘操作、草稿恢复、关闭保存、撤销/重做和保存后重新打开。标准测试文件覆盖所有本轮字段类型；用户提供的 16 页问卷验证了文字、中文、日期和单选修改，其他字段与原文件保持不变，四个签名字段保留。字段值和 PDF 显示外观分别检查。没有在 Adobe Acrobat 或 macOS/Linux 实际桌面上进行本轮交互验证，不声称这些测试已通过。用户问卷不随项目分发。

## English

Use the pointer to fill the highlighted AcroForm fields directly. Tab/Shift+Tab moves between fields; Space selects a focused check/radio button, without changing a value merely by tabbing to it. Use the calendar for recognized date formats. Paused input is committed to local recovery revisions, not the original PDF; Save/Save As writes an interactive PDF. Ctrl+Z/Y edits input while a text control is active and uses document history after leaving it. Uncommitted input is also recoverable.

Text, check/radio buttons, editable/noneditable combos, single/multiple lists and common dates are supported. Linked names, choice export values, read-only flags, maximum length and appearances are preserved. Font fallback is used for missing glyphs; rich-text edits are plain text with an inline notice. Arbitrary PDF JavaScript, XFA, signing/verification and editing already-signed documents are excluded. This release does not execute form scripts or automatically submit data. Required fields are marked, but incomplete drafts can be saved. Form highlights are display-only. Tested on Windows; Acrobat and physical macOS/Linux interoperability remain unverified.
