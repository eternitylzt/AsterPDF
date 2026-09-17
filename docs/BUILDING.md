# Run, build and publish

## Environment

Recommended: Python 3.12. Supported source range: 3.11–3.13. Runtime dependencies are pinned in `pyproject.toml` except Pillow's compatible major range. `requirements-lock-windows.txt` records the development/verification environment. Do not install its Windows-only packages on other platforms.

```sh
python -m venv .venv
# Activate: Windows .\.venv\Scripts\Activate.ps1; Unix source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m asterpdf
python -m pytest -q
```

On Debian/Ubuntu, install Qt platform dependencies if unavailable:

```sh
sudo apt-get install libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0
```

Use an actual desktop session to verify video, audio and clipboard. `QT_QPA_PLATFORM=offscreen` is suitable for automated UI checks but is not proof of desktop behavior or installed fonts.

## Build each platform on itself

```sh
python scripts/collect_licenses.py
python -m PyInstaller --noconfirm AsterPDF.spec
python scripts/package.py
```

| Target | Output | Additional notes |
| --- | --- | --- |
| Windows x64 | `dist/AsterPDF/AsterPDF.exe`, directory zip | Run from the complete folder. Optional installer: open `packaging/windows/AsterPDF.iss` in Inno Setup 6 and compile after packaging. Installer configuration is provided but Inno Setup has not been run here. |
| macOS | `dist/AsterPDF.app`, tar.gz | Build with native Python on intended architecture. Code signing/notarization requires the publisher's Apple credentials and has not been performed. |
| Linux x64 | `dist/AsterPDF/AsterPDF`, tar.gz | Verify Qt platform and FFmpeg libraries on a clean target. Install the `.desktop` file/icon only when configuring a system install. The portable archive does not alter default PDF associations. |

PyInstaller is not a cross-compiler. A Windows build is not a macOS/Linux binary. CI config exists for all three systems; only completed jobs and actual target tests establish compatibility. The bundled Qt Multimedia backend may have different codec availability per OS. Linux FFmpeg dependency deployment needs target verification.

The directory bundle is intentional: it avoids one-file extraction at every launch and keeps shared libraries replaceable. Executables are unsigned. The full source zip is included alongside the Windows/Linux executable, and also emitted as a separate release artifact; publish the source artifact with every binary release.

## Original assets and tests

```sh
python scripts/make_assets.py
python scripts/make_demo.py
# Optional: recreate the embedded MP4/WAV fixture
python -m pip install imageio-ffmpeg==0.6.0
python scripts/make_media_fixture.py
```

`imageio-ffmpeg` is only a fixture-generation tool; it is excluded from the desktop bundle. Its FFmpeg build generates a short original test pattern and sine tones. Qt's own FFmpeg shared libraries perform application playback.

The user's `E:\tempdata\testpage.pdf` is an external validation input. It is **not** included in the repository or binary package. The upstream animate manual is also not redistributed as an AsterPDF asset.

## GitHub setup and releases

The public repository is `eternitylzt/AsterPDF`. A `v*` tag runs tests and native PyInstaller builds on Windows, macOS Apple Silicon and Linux, then publishes the matching archives, source and SHA-256 files as a GitHub Release. A manual workflow run builds downloadable CI artifacts without creating a Release.

Build completion establishes that the project packaged on that runner. It does not replace the real-desktop checks in `docs/VALIDATION.md`, especially multimedia playback, clipboard integration, fonts, signing and platform codec availability. Published binaries are unsigned; add signing/notarization credentials separately when available.

`asterpdf/release.py` points the in-app update checker at the stable Releases page. The application offers the download page and never installs an update automatically.

## User data and recovery

Settings use Qt's native `QSettings` location for `AsterPDF/AsterPDF`. Session snapshots and recovery manifests use Qt's `AppLocalDataLocation/recovery`. Override the data directory for isolated testing with `--data-dir PATH`; this also uses a separate `settings.ini` in that directory.

Normal explicit close after save/discard removes that session's revision directory. A crashed dirty revision is offered at next startup. Recovery must save to a new filename. Unclaimed crash directories can be removed manually after their contents have been reviewed; the app does not automatically delete unknown recovery files.

## Development smoke test

```sh
python -m asterpdf --smoke-test --data-dir ./test-data examples/AsterPDF-demo.pdf
```

This opens the desktop window and exits after four seconds. It proves startup only, not animation or video success. Dedicated workflow/decoder evidence is recorded separately.
