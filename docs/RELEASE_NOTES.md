# AsterPDF 1.2.1

## 中文 · 相比 1.2.0

- 修复打开 Markdown 时出现“正在等待连接打印机”：改为直接生成 PDF，不再初始化系统打印机。
- 支持离线数学公式：行内 `$...$`、独立 `$$...$$` 与 `math` 代码块，包含常见分式、积分、向量、上下标及矩阵。公式在导出的 PDF 中保留矢量质量。
- 改善 GitHub 风格 Markdown 排版：嵌套列表、列表内代码块、表格、任务列表、链接和图片比例；代码中的美元符号保持原文。
- 使用用户提供的 FastQSL2 README 验证：123 处公式全部成功排版，并检查实际页面效果。

## English · Changes since 1.2.0

- Open Markdown without initializing the system printer, eliminating the wait-for-printer path.
- Offline inline/display TeX and fenced `math` blocks: fractions, integrals, vectors, scripts and matrices, preserved as vector paths in PDF exports.
- Improved GitHub-style nested lists/code, tables, tasks, links and image proportions. Dollar signs inside code remain literal.
- Validated all 123 formula occurrences in the supplied FastQSL2 README and inspected the rendered pages.

No browser engine, Node.js runtime or LaTeX installation required. Formulas become vector outlines; surrounding text remains searchable. Unsupported TeX shows a visible source fallback. Browser CSS, TikZ and arbitrary LaTeX packages are not supported; PDF pagination and fonts differ from GitHub's web page.

无需浏览器引擎、Node.js 或 LaTeX。公式导出为矢量轮廓，正文仍可搜索；不支持的公式会显示原文提示。分页和字体与 GitHub 网页存在差异，不支持完整网页 CSS、TikZ 或任意 LaTeX 宏包。

## Downloads / 下载

- Windows x64: unzip completely, run `AsterPDF/AsterPDF.exe`.
- macOS Apple Silicon: unpack, open `AsterPDF.app` (unsigned / 未签名).
- Linux x64: unpack, run `./AsterPDF/AsterPDF`.
- Matching source ZIP included. No separate per-platform SHA attachments.

[Build / 安装与构建](https://github.com/eternitylzt/AsterPDF/blob/main/docs/BUILDING.md) · [Compatibility / 兼容性](https://github.com/eternitylzt/AsterPDF/blob/main/docs/COMPATIBILITY.md)
