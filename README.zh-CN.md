<p align="center"><img src="assets/wordmark.svg" width="500" alt="AsterPDF"></p>

# AsterPDF

**Read · Edit · Animate · Annotate · Extract**

面向科研与技术文档的离线 PDF 桌面工具。

**中文 | [English](README.md)** · [兼容性](docs/COMPATIBILITY.md) · [构建说明](docs/BUILDING.md) · [验证记录](docs/VALIDATION.md)

<table><tr>
<td><a href="docs/evidence/overview-1.0.png"><img src="docs/evidence/overview-1.0.png" width="290" alt="搜索与速览窗"></a><br>搜索定位 · 速览窗</td>
<td><a href="docs/evidence/extract-1.0.png"><img src="docs/evidence/extract-1.0.png" width="290" alt="提取矢量科研图片"></a><br>区域提取 · 保留矢量</td>
<td><a href="docs/evidence/tools-1.0.png"><img src="docs/evidence/tools-1.0.png" width="290" alt="自定义工具栏"></a><br>自定义工具 · 舒适阅读</td>
</tr></table>

## 特色

- **阅读动态论文**：在文档原位播放已识别的 LaTeX `animate` 动画及内嵌音视频，演示模式同样可用。
- **提取科研图**：按指定分辨率导出局部高清图片、提取原始内嵌图片，或导出保留文字与矢量的局部 PDF。
- **真实内容编辑**：修改可识别的文字、图片和矢量对象；保留未改动字形，支持移动、缩放、删除和跨文档原位粘贴，也可插入矢量 PDF 图。
- **批注与页面整理**：标准 PDF 批注、逐字高亮、可换行文本批注，页面拖动排序、文件合并队列、页面提取、旋转和可调边框裁剪。
- **便捷阅读**：多标签、搜索、目录、命名书签和悬浮速览窗；适配高 DPI 显示，支持深浅界面、中英切换、自定义工具栏和本地意外退出恢复。

无需账户，不依赖云服务，PDF 处理在本机完成。

## 1.2.0 · 相比已发布的 1.0.1

- **更多文档格式**：打开 Markdown（含本地/链接图片、表格），可另存为 PDF；通过可选的 Ghostscript 导入 EPS/PS。
- **视频融入文档**：插入视频、用视频替换图片；右键保存内嵌媒体或导出动画帧。新插入和已有媒体支持列表选择、置顶与置底。
- **绘图和批注更直接**：形状面板、独立批注样式、批量样式修改，以及删除并添加文字的替换批注。
- **区域换色与对象整理**：文字、矢量和图片的区域换色，按顺序应用多个颜色对、保存方案；文字、图片和图形支持层级调整。
- **日常操作更顺畅**：保留未改页面的预览，完善原位粘贴、透明图片复制、最近文件、多媒体控件和关闭保存流程。

[完整发布说明](docs/RELEASE_NOTES.md)

## 运行

**Windows x64**：完整解压 `AsterPDF-1.2.0-windows-amd64.zip`，运行 `AsterPDF/AsterPDF.exe`。请保留同目录的 `_internal` 文件夹，无需安装 Python。当前程序未签名。

**macOS / Linux**：请从 GitHub Release 下载相应平台的原生构建。自动化任务验证各平台打包是否成功；真实桌面功能的实测范围见验证记录与兼容性说明。

源码运行（建议 Python 3.12）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m asterpdf examples/AsterPDF-demo.pdf
```

安装依赖需要联网；可选的在线字体查找、检查更新和 Markdown 关联的网络图片也会联网。

## 快速上手

打开 PDF 后，用指针选择文字或图片，用手形平移。四个功能区按需展开批注、编辑、页面和提取工具。**设置 → 首选项**（`Ctrl+,`）集中管理默认参数，右键工具栏可自定义工具。

双击可编辑文字块进入编辑，选中文字后修改样式；`Ctrl+Enter` 应用，`Esc` 取消。“插入文本框”可创建独立文字，拖动边框调整换行宽度，拖动圆形控制点旋转；文字设置栏也提供精确宽度与角度。文件名中的 `*` 表示尚未保存。

`examples/` 包含两个原创示例 PDF。[详细操作](docs/USABILITY-1.0.md) · [快捷键与帮助](asterpdf/resources/HELP.zh-CN.md)

## 能力边界

AsterPDF 不承诺完整替代 Acrobat。文字编辑依赖可识别结构和可靠的字形映射；不支持复杂文字塑形、任意段落重排，也不能进入所有嵌套 Form 编辑内部标签。无法可靠修改时会说明原因并保留草稿。未改动文字保留原字体资源；新增文字可能使用明确提示的本地替代字体。

动画支持基于已测试的 icon/widget 样例，不等同于通用 Acrobat JavaScript 兼容。OCG 动画、Flash、PDF 3D 不支持；音视频编码支持随平台变化。导入页面不转移文档级脚本或表单树；含批注、链接或媒体的页面暂不支持整体镜像。详见[兼容性说明](docs/COMPATIBILITY.md)。

不含 OCR、PDF 转 Word、AI 服务、证书签名和移动端。

## 构建与发布

项目包含 PyInstaller 打包配置、平台图标、GitHub Actions、第三方许可证与公开测试样例。[构建及发布步骤](docs/BUILDING.md)。

源码与 Windows/macOS/Linux 原生构建发布在 [GitHub Releases](https://github.com/eternitylzt/AsterPDF/releases)。**帮助 → 检查 GitHub 更新**会比较当前版本与最新正式 Release，并打开下载页面。

**GitHub 简介：** 面向科研的离线 PDF 编辑器，支持 LaTeX 动画、视频插入、Markdown 阅读与保留矢量的科研图提取。

**作者：** Zhentong Li · eternitylzt@gmail.com

**许可证：** [AGPL-3.0-only](LICENSE)。各依赖保留自身许可证，见[第三方声明](THIRD_PARTY_NOTICES.md)。发布二进制时应同时提供对应源码。

### 格式与媒体说明

Markdown 使用轻量解析器生成可搜索 PDF，支持常见表格及图片，不等同于完整浏览器排版；无需引入 WebEngine。EPS/PS 需要另外安装 Ghostscript。视频层级调整的是同页媒体批注的叠放顺序，播放层位于正文内容之上；不会把视频压平为图片。动画导出为矢量帧 PDF 与帧率信息，非转码 MP4。各阅读器、系统和编码的媒体支持有差异。
