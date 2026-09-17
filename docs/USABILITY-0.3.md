# 0.3 交互改进 / Interaction changes

| 本次反馈 | 已实现与验证 |
| --- | --- |
| 首页改为 Home，独立合并 | 固定首页无关闭按钮；合并新文件/已打开文档，队列可继续添加、预览、重排和删除。已打开文档使用当前编辑快照，输出新 PDF，原文件不变。 |
| 缺字体时进入编辑就变化，无法退出 | 无内容或样式修改时不调用字体嵌入、不产生新修订，继续显示 PDF 原字形。单击外部退出；移动、Delete 和清空文字不依赖字体。 |
| 自动相近字体 / 搜索下载 | 系统字体优先，缺失时自动选近似族并显示名称。新增“查找字体”，按识别名称搜索 Google Fonts 的 OFL 字体、下载到固定应用缓存目录、导入本地字体；启动时复用。实测 Lato 搜索、下载、缓存跨进程加载、真正修改文字与保存重开。 |
| 实心箭头和参数含义 | ClosedArrow 使用同色填充；两个参数明确标注线宽和不透明度（百分比）。箭头尺寸按线宽变化。 |
| 取消框选、固定 DPI | 单击其它位置取消选框；“导出设置”持久保存 DPI、像素宽度、PNG/JPG、质量，页面/区域/复制复用。 |
| 图片列表双向定位 | 当前页原图缩略图列表；页面与列表联动，多选批量提取。重叠图层从列表选择；资源中存在但无法定位的图像有“未定位”标记，无图片时明确提示。 |
| 图标与导航 | 指针、手形、撤销、重做、翻页和缩放使用清晰矢量图标；导航默认文字标签。 |
| 单一界面语言 | 中文/英文菜单、工具、内置提示、Qt 标准按钮和帮助各自本地化；PDF 内容、字体名与文件名保持原样。第三方引擎原始异常可能仍用技术英文。 |

## 字体策略与边界

无需原字体也可保留原有字形、选择、移动和删除。只有真正修改内容/样式才重新生成所选文字块。输入采用安装或缓存的字体，自动匹配会明确显示替代名称；不会把替代字体当作原字体。当前没有复制 Adobe 的专有字体合成算法。

下载缓存默认位于 `QStandardPaths.AppLocalDataLocation/fonts`；Windows 通常为 `%LOCALAPPDATA%/AsterPDF/AsterPDF/fonts`，以“查找字体”窗口显示的实际路径为准。每个字体族保存原始字体、`OFL.txt`、来源和 SHA-256 记录。不安装系统字体；不需要账户，不上传 PDF 内容。只有用户点击搜索或下载时联网，已下载字体可离线复用。

Google Fonts 不能保证提供商业字体、所有 LaTeX 字体或 PDF Type 3 自定义字形。同名字体也可能不是原版本。匹配不足时可选择系统替代字体或导入已获得的字体文件。缺字、禁止嵌入、非水平/裁剪文字等限制会明确提示，保留输入草稿。修改后检查局部排版。

## 当前保留的限制

- 图片列表按当前页加载；翻页自动更新。软蒙版不自动合成到原图提取结果。
- 合并导入页级对象，不合并文档级目录、脚本和表单树；检测到相关内容会先提示。输出另存新文件。
- OCG 动画、任意 Acrobat JavaScript、复杂全文排版及嵌套 Form 内部文字编辑仍不支持。
- Windows 已实测；macOS/Linux 仅提供构建配置，未在实际环境验证。

## English summary

Home now merges files or current open-document snapshots into a new PDF. Unchanged text editors retain the PDF's glyphs and bytes; deletion/movement do not require fonts. Find fonts supports explicit OFL search/download, private persistent cache and local font import. Similar fonts remain identified as substitutes. Image extraction provides linked thumbnails and page selection, including overlapping images and multi-selection. Export defaults persist, clicks clear regions, arrows have solid fill, quick icons are larger, and Chinese/English interfaces have separate strings and help. See [validation](VALIDATION.md) for executed tests and platform boundaries.
