# AsterPDF 1.3.7

相比 1.3.6 / Changes since 1.3.6

## 中文

- 支持以鼠标指针为中心的触控板双指缩放。
- 新增刷新按钮及 Ctrl+R（macOS 为 Command+R），外部更新 PDF 后保留阅读位置；未保存编辑会先提示确认。
- 支持 `asterpdf a.pdf` 命令。Linux deb/rpm 安装后自动可用；其它包可通过 Settings → 安装 asterpdf 命令或随包脚本注册，重新打开终端后使用。

## English

- Pointer-centered trackpad pinch zoom.
- Refresh externally updated PDFs with the toolbar or Ctrl+R (Command+R on macOS), retaining your reading position and prompting before discarding unsaved edits.
- Open documents with `asterpdf a.pdf`. Linux deb/rpm installs the command automatically; other packages offer registration through Settings or the included installer. Reopen your terminal after registration.

Windows x64 · macOS Apple Silicon · Linux x86_64 (deb / rpm / tar.gz).

各平台实体触控板尚未逐一实测；自动化手势验证与跨平台构建不能代替实体设备测试。
Physical trackpads have not been tested across all platforms; automated gesture checks and platform builds do not replace device testing.
