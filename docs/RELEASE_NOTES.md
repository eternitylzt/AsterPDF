# AsterPDF 1.3.0

## 中文 · 相比已发布的 1.2.1

- 新增标准 PDF 表单填写：文字、复选、单选、下拉/列表及常见日期，直接点击原位输入，支持字段高亮、Tab 切换、保存、撤销及临时恢复。保存保留交互字段和显示外观。
- 阅读“书签”统一改为“收藏”，原有记录保留，星形按钮用于添加/移除收藏。
- F11 进入仅显示文档的全屏，保留原先已开启的播放控件和速览窗；再次 F11 或 Esc 返回。
- Markdown 默认连续长页阅读，提供标题目录；另存为 PDF 可选 A4 分页（默认）或长页。代码块直接采用文档原有排版，不再叠加滚动文本框；相关设置集中到 Markdown 分类。
- 双击页间缝隙可切换紧密排列，合并后保留淡色分界线，悬停显示合并/展开光标，再双击即可恢复间距；不修改 PDF 本身。

表单首轮不执行自定义 JavaScript，不支持 XFA、签名操作或填写已签名文档。富文本字段编辑后以纯文本保存。Windows 已进行实际样例和原生界面验证；本轮尚未实测 Acrobat、macOS/Linux 桌面。详见 [表单说明](https://github.com/eternitylzt/AsterPDF/blob/v1.3.0/docs/FORMS.md) 和 [验证记录](https://github.com/eternitylzt/AsterPDF/blob/v1.3.0/docs/VALIDATION.md)。

## English · Changes since published 1.2.1

- Fill standard AcroForms in place: text, check/radio buttons, combo/list choices and common dates, with field highlighting, Tab navigation, save, undo and recovery drafts. Saved fields remain interactive and retain appearances.
- Reading bookmarks are now named Favorites; existing records are retained.
- F11 provides document-only fullscreen while retaining previously visible playback controls and Quick overview. F11/Esc restores the interface.
- Markdown opens as a continuous long page with a heading outline. Save As PDF offers A4 pagination (default) or a long page. Code blocks use the original document layout without scrollable text overlays; Markdown preferences are grouped together.
- Double-click page gaps to collapse them, then double-click the faint divider to expand them. Hover cursors indicate the available action; PDF content is unchanged.

Arbitrary form JavaScript, XFA, signing and filling already-signed documents are excluded. Rich-text field edits are plain text. Windows sample and native UI checks were performed; Acrobat and physical macOS/Linux desktop checks remain unverified. No new runtime dependency was added.
