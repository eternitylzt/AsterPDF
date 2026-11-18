# AsterPDF 1.3.8

相比 1.3.7 / Changes since 1.3.7

## 中文

- 修复终端被占用与重复开窗：命令立即返回，文件在已有窗口中新建标签页，原有未保存修改保持不变。
- 界面改用系统字体，消除 macOS 查找缺失 Windows 字体的提示及额外等待。
- 改善命令安装说明与旧脚本升级；当前用户安装无需 sudo。

macOS 更新：先退出旧版，将新版 AsterPDF.app 放入 Applications，启动后在 Settings → 安装 asterpdf 命令中注册。重新打开终端即可使用 `asterpdf a.pdf`，无需 sudo 或手动添加 `&`。若系统禁止 Terminal 访问 Downloads/Desktop，请改用软件内安装入口，或授予对应文件夹访问权限。

## English

- Terminal commands return immediately and forward files to tabs in the existing window, preserving unsaved work.
- Use the native interface font, avoiding missing Windows-font lookup on macOS.
- Clearer per-user command installation and automatic same-path launcher migration. No sudo required.

After updating macOS, quit the older version, place the new app in Applications, then use Settings → Install asterpdf command. Reopen the terminal and run `asterpdf a.pdf`; no sudo or trailing `&` is needed. If macOS denies Terminal access to Downloads/Desktop, use the in-app installer or grant access to the relevant folder.

Windows x64 · macOS Apple Silicon · Linux x86_64 (deb / rpm / tar.gz).
