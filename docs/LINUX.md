# Linux 安装 / Linux installation

AsterPDF **1.2.1** Linux packaging revision 1. x86-64, glibc **2.28 or newer**. Includes its own Python and Qt; no Python setup required.

旧 Linux 压缩包在较新的系统上构建，可能报 `GLIBC_2.38 not found`。修订包改用 glibc 2.28 构建基线，并为 Linux 选择 Qt/PySide 6.8.3；Windows/macOS 版本不变。deb/rpm 会声明运行依赖、安装菜单图标并支持正常卸载。不要通过手工替换系统 glibc 来运行旧包。

## Debian / Ubuntu / Linux Mint

Download `asterpdf_1.2.1-1_amd64.deb` from [Release 1.2.1](https://github.com/eternitylzt/AsterPDF/releases/tag/v1.2.1). In its download folder:

```sh
sudo apt install ./asterpdf_1.2.1-1_amd64.deb
asterpdf
```

也可从应用菜单打开 **AsterPDF**。卸载 / uninstall:

```sh
sudo apt remove asterpdf
```

## Rocky / AlmaLinux / CentOS Stream / Fedora

Download `asterpdf-1.2.1-1.x86_64.rpm`:

```sh
sudo dnf install ./asterpdf-1.2.1-1.x86_64.rpm
asterpdf
```

卸载 / uninstall:

```sh
sudo dnf remove asterpdf
```

## Portable tar.gz / 免安装压缩包

Download the revised `AsterPDF-1.2.1-linux-x86_64.tar.gz`. Extract into a new folder to avoid mixing old runtime libraries:

```sh
tar -xzf AsterPDF-1.2.1-linux-x86_64.tar.gz
./AsterPDF/AsterPDF
```

The native package is recommended: it installs required desktop libraries automatically. The portable build requires equivalent system libraries; see package dependency declarations in `scripts/linux_packages.py`.

## Compatibility / 兼容性边界

- Build baseline: AlmaLinux 8, glibc 2.28, Python 3.11, Qt/PySide 6.8.3. Every bundled ELF binary is checked for its GLIBC symbol requirements.
- Automated installation/X11 launch/removal checks: Ubuntu 20.04, Ubuntu 22.04, Debian 12, Rocky Linux 8 and 9. See the [Linux workflow](https://github.com/eternitylzt/AsterPDF/actions/workflows/linux-release.yml) for completed results.
- Distribution families alone do not guarantee compatibility. CentOS 7 (glibc 2.17), Alpine/musl and ARM machines are not supported by these x86-64 packages. Kernel version from `uname` alone does not establish the glibc version; use `ldd --version`.
- Container/Xvfb checks cover package management and X11 startup, not physical GPU, audio, Wayland or all multimedia codecs. These still require real-desktop verification.
- Install under `/opt/asterpdf`; launcher `/usr/bin/asterpdf`. User settings and recovery data are retained when uninstalling. Existing default PDF associations are not forcibly changed.
- Linux-specific matching source is attached as `AsterPDF-1.2.1-linux-source.zip` and included in the package. Existing Windows/macOS/common-source assets and the version tag remain unchanged.
