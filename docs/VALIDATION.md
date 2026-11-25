# AsterPDF 1.3.9 verification / 验证

在同一台 Windows x64 电脑上交替运行 1.3.8 与 1.3.9。每次使用独立设置与恢复目录，程序打开后开始计时。下表为每版三次的中位数，使用同一 Qt 离屏窗口和相同缩放。首次显示要求阅读区已经画出文档像素。文字测试在已有文本中间退格，提交耗时包含重新进入可选择对象的状态。

| 文档和操作 | 1.3.8 | 1.3.9 |
| --- | ---: | ---: |
| 360 页图文样本首次显示 | 1.78 s | 0.49 s |
| 557 页实书首次显示 | 1.37 s | 0.69 s |
| 360 页样本进入对象编辑 | 0.89 s | 0.39 s |
| 360 页样本行中删除一字后显示精确预览 | 0.54 s | 0.10 s |
| 360 页样本提交删除后可继续编辑 | 2.29 s | 0.18 s |
| 360 页样本移动图形 | 1.09 s | 0.17 s |
| 360 页样本缩放图形 | 1.78 s | 0.15 s |
| 17 页论文行中删除一字后显示精确预览 | 0.22 s | 0.10 s |
| 17 页论文提交删除后可继续编辑 | 0.58 s | 0.48 s |

360 页样本的每页有 44 段文字和 160 条矢量线。557 页样本为一本实际的 PDF 书籍，17 页样本为一篇 Science 论文。文件均从本地磁盘读取。冷启动程序、磁盘缓存和网络磁盘会影响实际等待时间。独立资源、复杂字形、字体嵌入和整份文件保存仍有各自的处理成本。

**Windows 验证**。桌面回归运行有 281 项通过、2 项跳过、4 项失败。局部内容检查另外覆盖行首、行中和行尾删除、撤销重做、保存重开、页面共享内容流、旋转裁剪和矢量边界。Windows 便携程序实测通过文字编辑与保存重开、批注、翻页、演示、打印和动画/内嵌视频播放。macOS 和 Linux 本轮未运行。

**已有的检查差异**。4 项在原版 1.3.8 上也能复现，涉及取消旋转后再次旋转的目标页、速览窗高度断言、单击后是否保留框选，以及双击文本批注的交互。以上计时与桌面程序验证独立于这 4 项检查。

## AsterPDF 1.3.8

Focused Windows regression: **27 passed, 2 skipped in 53.70 seconds**. The skipped checks execute POSIX shell scripts and are included in macOS/Linux CI.

- Real subprocess tests launch the desktop through a registered-style command. The caller exits while the GUI remains open; relative paths, Chinese names and spaces are preserved.
- A second command adds a tab in the same process, restores a minimized window and preserves the first tab's unsaved annotation. Reopening the same file does not duplicate its tab.
- Simultaneous cold starts produce one window with both files. Per-profile test sessions remain isolated from a user's running application.
- Installer checks cover sudo refusal before configuration writes, same-path legacy launcher migration, custom-command preservation and existing idempotence/conflict/rollback behavior.
- Previous PDF refresh, fullscreen/presentation, toolbar stability and Markdown reading/export checks remain passing. The theme no longer specifies missing Windows font families.

The release CI repeats these workflows on macOS and Linux alongside the existing PDF editing/preservation suite. Local IPC and shell behavior are tested on those OS runners; macOS privacy dialogs, real Terminal permissions and physical desktop activation still need end-user verification. macOS can reject a script before it executes; the application cannot override that system permission. The in-app installer avoids depending on Terminal access to the downloaded installer folder.

No new runtime dependency or browser engine was added.

The frozen Windows bundle also passed the real command workflow: command invocations returned in 0.610 / 0.297 / 0.328 seconds while one GUI process retained two tabs. Duplicate-file reuse and a clean normal window close were checked. [Packaged report](evidence/cli-1.3.8.json). Release CI runs an additional frozen-bundle command check on all three platforms before packaging.
