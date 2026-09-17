# AsterPDF 1.0.1

本版只针对四项反馈修改。

- **速览窗**：每个新打开的 PDF 都按自己的页面数量、页面尺寸和并排列数重新适配。鼠标拖动调整尺寸只影响当前文档，不再把高度写入其他文档的默认值。首选项中的手动尺寸设置仍可调整当前已打开窗口。
- **最近文件**：首页改成“最近文件 / 大小 / 打开时间”三列表格，大小与时间按列对齐。文件所在目录显示在名称下方，完整路径可悬停查看。
- **源颜色**：改成横 4 × 纵 8 的色块矩阵，最多 32 色；相近颜色按当前容差聚合，仍按占比由多到少排列，但不显示百分比。选中色块显示色号，仍支持页面取色和多对方案。默认容差为 8%；从旧版默认 2% 升级时一次性调整为 8%，其他已有自定义值保留。
- **图形**：绘制完成后自动回到选择状态，不再需要“选择/移动”按钮。单击实际路径或实心内部可选中，空白处拖框可多选；拖动移动、右下角缩放、上方圆柄旋转（Shift 按 15° 对齐），橙色节点可调整路径端点。变换写入原生 PDF 矢量内容，可保存重开。

## English

Each newly opened PDF fits its own overview; manual resizing stays local to that tab. Home now aligns file name/path, size and opened time in columns. Source colors use a four-column, eight-row palette (up to 32 swatches), with tolerance-based clustering and an 8% default. Color codes, picking and saved schemes remain available.

Drawing returns directly to selection. Click a path/filled interior, marquee multiple shapes, drag to move, resize at the lower-right corner or rotate with the upper handle. Shift snaps rotation to 15°. Changes retain native vector content when saved.

Validation is limited to these affected workflows; unrelated features are not exhaustively retested for this patch.
