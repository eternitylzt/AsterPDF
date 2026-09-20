# AsterPDF 1.2.0

**Read · Edit · Animate · Annotate · Extract**

## 中文 · 相比已发布的 1.0.1

- 打开 Markdown，支持常见表格、本地及链接图片，并可另存为 PDF；通过可选 Ghostscript 打开 EPS/PS。
- 插入视频或用视频替换图片；新插入与已有媒体可在列表和页面中选择、置顶/置底。右键保存内嵌音视频、导出动画帧、呼出悬浮播放控件。
- 新形状面板，绘制后可选择、自由调整和设置样式；文字、图片、图形支持层级调整。
- 独立的批注样式设置、批量选中修改，支持删除并添加文字的替换批注。
- 区域换色覆盖文字、矢量和图片；多个颜色对按列表顺序生效，可仅应用选中项、保存及复用方案。
- 改善页面操作时的预览复用、原位粘贴、透明图片复制、最近文件、文档链接、工具状态和关闭保存体验。

## English · Changes since published 1.0.1

- Read Markdown with common tables and local/linked images; save as PDF. Open EPS/PS with optional Ghostscript.
- Insert video or replace images with video. Select existing/inserted media on the page or in a list and arrange its stacking order. Right-click to save embedded media, export animation frames or show floating playback controls.
- Draw from a shape palette, select and resize shapes, and change their styles. Arrange text, images and shapes.
- Independent inline annotation presets, batch styling and replacement-text comments.
- Regional recoloring of text, vectors and images, ordered color pairs, selected-pair application and reusable schemes.
- Improved page-preview reuse, paste-in-place, transparent-image copying, recent files, document links, tool states and save-on-close behavior.

## Downloads / 下载

- **Windows x64**: unzip the entire archive and run `AsterPDF/AsterPDF.exe`.
- **macOS Apple Silicon**: unpack the archive and open `AsterPDF.app`. Unsigned / 未签名。
- **Linux x64**: unpack the archive, then run `./AsterPDF/AsterPDF`; see [Linux setup](https://github.com/eternitylzt/AsterPDF/blob/main/docs/BUILDING.md) for system libraries.
- Matching source ZIP is included / 同时提供对应源码 ZIP。无需逐平台 SHA 附件。

Media stacking changes annotation order; interactive video remains above page content. Animation export is a vector-frame PDF plus timing metadata. Codec support varies. / 媒体层级指批注叠放顺序，交互播放层仍在正文之上；动画导出为矢量帧 PDF 和帧率信息，编码支持因平台而异。

Windows desktop playback and save/reopen workflows were tested. Native builds and regression checks run on all three platforms; macOS/Linux interactive desktop use still needs user verification. / 已实测 Windows 桌面播放及保存重开；三个平台均执行原生构建与回归检查，macOS/Linux 真机交互仍需用户验证。

[Compatibility / 兼容性](https://github.com/eternitylzt/AsterPDF/blob/main/docs/COMPATIBILITY.md) · [Validation / 验证](https://github.com/eternitylzt/AsterPDF/blob/main/docs/VALIDATION.md)
