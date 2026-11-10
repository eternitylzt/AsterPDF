# 图形与图片编辑研究 · 2026-11-09

本轮对照本机 Acrobat Pro DC 32-bit 与 AsterPDF，检查已有 PDF 内容中的图片、矢量路径和 Form 对象。使用受控样例与独立几何检查，不修改用户原始文档；没有反编译或复刻 Adobe 的内部算法。

## REA 证据

REA MCP 6.8.0 正常连接。复用并导入上轮完整证据，重新核对本机 AdobePDFL.dll SHA-256 与证据完全一致，避免重复扫描。

- `AdobePDFL.dll` 的导出包括 `PDEElementGetMatrix/SetMatrix`、`PDEElementGetClip/SetClip`、`PDEElementGetGState/SetGState`、`PDEImageSetData`、`PDEImageGetSMask/SetSMask`、`PDEPathGetData/SetData`、`PDEPathGetPaintOp/SetPaintOp`。证据：`ev_e67d8ef680e8b5061038f540db9afad1c6554768a89468abed70623adcbbfe9b`。
- 新扫描 `AGM.dll` 的完整 PE 导出表只有 `AGMGetVersion`、`AGMInitialize`、`AGMTerminate` 三个入口。证据：`ev_52edd5e2133efc2dff746967a7e17fa53e8d1f44abfce6cadc89ff9a76b516cd`，SHA-256 `e79bdafd339de2f0fb88d41369b95eaea86612fd29ca98e2f6bab2951753b507`。

这些静态声明表明公开接口分别表达对象变换、裁剪、绘制状态、像素和透明蒙版，不能证明某次界面操作调用了哪个函数。Adobe 官方的 [PDEElement 文档](https://opensource.adobe.com/dc-acrobat-sdk-docs/acrobatsdk/apireference/PDFEdit_Layer/PDEElement.html) 与 [PDEImage 文档](https://opensource.adobe.com/dc-acrobat-sdk-docs/acrobatsdk/apireference/PDFEdit_Layer/PDEImage.html) 用于核对这些接口语义。完整 REA 证据保存在本次任务 `outputs/graphics-image-research/rea-graphics-evidence.json`。

## 实际对照与修复

| 问题 | 修复及证据 |
| --- | --- |
| 图片新资源名与已有 `/AsterImageN` 冲突，替换一张时另一张也被改掉 | 为每次替换分配唯一页面资源名，只重写所选实例的 `Do`。共享 XObject、连续保存重开、资源冲突样例均有回归。 |
| 不同长宽比图片替换后被拉伸 | 按原实例两条变换轴等比居中适配，保留朝向、斜切和透明蒙版。沿用图片面板“保持原比例”；取消勾选时可按原框拉伸。Acrobat 将旋转后的 110×180 pt 框替换为方图时得到居中的约 110×110 pt 图片，AsterPDF 对照矩阵最大差 0.001221 pt。 |
| CropBox 偏移叠加 90/180/270° 页旋转后，缩放和旋转中心错误 | 使用完整的裁剪及页面旋转坐标映射。原探针缩放偏移 20–25 pt、旋转偏移 90 pt；修复后对应样例误差为 0。 |
| 路径内部设置的颜色、线宽、虚线等状态在变换后被 q/Q 吞掉，改变后续图形 | 变换或删除所选路径后回放原状态；独立探针覆盖 ExtGState、CMYK、透明度、混合模式及虚线，邻近图形像素保持。 |
| 粗描边图形缩放后的缓存边界不等于真实绘制边界 | 缩放或旋转后重新发现对象；9 例独立连续编辑探针的缓存与重开边界差均为 0。 |
| 图片没有对象旋转入口，图形旋转使用另一套逻辑 | “移动 / 缩放…”属性窗口增加顺时针角度，负数逆时针；图片、路径、Form 与图形圆柄使用同一变换路径。先按左上角缩放、平移，再绕新中心旋转。 |
| 改样式时丢失偶奇填充孔洞或隐式闭合边 | 保留 f*/B*/b* 的填充规则与 s/b/b* 的闭合语义，并保持后续状态。 |

Acrobat 中实际完成图片平移、顺时针旋转、等比替换，以及矢量路径逆时针旋转和平移，逐步保存为独立文件。对照结果中 AsterPDF 的矢量几何边界与 Acrobat 完全一致，未选中的重复图片及邻近图形保持。Acrobat 的自动拖动缩放没有得到确认变化，因此不把该动作记为成功；缩放另由 AsterPDF 的独立回归及安装版操作验证。

## 验证范围与边界

最终测试、安装与保存重开结果见 [VALIDATION.md](VALIDATION.md)；证据含两个页面，其中第二页为 90° 旋转页。检查原生路径、图像像素与透明度、邻近内容、撤销重做，以及保存后重新读取的矩阵和边界，不只检查截图。

- 路径构建过程中插入 `cm/q/Q` 的复杂内容明确拒绝独立编辑，保留文档，避免猜测顶点坐标。
- 嵌套 Form 内的图片仍作为整个 Form 处理；本轮未实现组内任意子对象编辑。
- 复制/粘贴旋转或斜切图片的朝向保留仍是已有边界；本轮修复的是原对象的变换与替换。
- 此次没有声称恢复 Acrobat 内部渲染或对象选择算法。现有静态接口、受控行为与源码已经足够定位并验证修复，暂不配置 Ghidra。需要追踪复杂剪裁、透明组或组内选取的原生决策时再评估。
