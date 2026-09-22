# Third-party notices and source locations

Copyright (c) 2026 AsterPDF contributors. AsterPDF code, original logos/icons and original example PDFs are AGPL-3.0-only. The full license is in `LICENSE`.

This software includes or links the following independently licensed components. Choosing AsterPDF's license does not replace these components' notices or rights. `licenses/inventory.json` records the installed runtime versions used for this build; `scripts/collect_licenses.py` copies license files supplied by their wheels.

| Component | License used / notice | Corresponding upstream source |
| --- | --- | --- |
| Python 3.12 | Python Software Foundation license and incorporated notices | https://github.com/python/cpython/tree/3.12 ; full license in `licenses/PYTHON-LICENSE.txt` |
| PySide6, Shiboken6, Qt 6.10.2 | LGPL-3.0 option; Qt/PySide modules may also offer GPL/commercial alternatives | https://code.qt.io/cgit/pyside/pyside-setup.git/ ; https://download.qt.io/official_releases/qt/6.10/6.10.2/single/ |
| PyMuPDF 1.27.1 / MuPDF | GNU AGPL v3 option, copyright Artifex Software, Inc. and contributors | https://github.com/pymupdf/PyMuPDF/tree/1.27.1 ; https://mupdf.com/releases/ ; https://github.com/ArtifexSoftware/mupdf |
| pikepdf 10.3.0 | MPL-2.0, copyright pikepdf contributors | https://github.com/pikepdf/pikepdf/tree/v10.3.0 |
| qpdf, compiled into/distributed with pikepdf wheel | Apache-2.0; wheel-specific third-party list included | https://github.com/qpdf/qpdf ; see `licenses/pikepdf/licenses/licenses-for-wheels.txt` |
| Pillow | HPND/PIL license and bundled imaging-library notices | https://github.com/python-pillow/Pillow ; license texts collected from the wheel |
| lxml | BSD-3-Clause; incorporated libxml2/libxslt notices | https://github.com/lxml/lxml ; license texts collected from the wheel |
| Deprecated | MIT | https://github.com/laurent-laporte-pro/deprecated |
| wrapt | BSD-2-Clause | https://github.com/GrahamDumpleton/wrapt |
| packaging | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| FFmpeg libraries provided with Qt Multimedia | Qt's build uses LGPL components; exact compiled codecs depend on platform | https://ffmpeg.org/download.html ; https://code.qt.io/cgit/qt/qtmultimedia.git/ ; https://doc.qt.io/qt-6.10/licenses-used-in-qt.html |

Full AGPL-3.0, GPL-3.0, LGPL-3.0 and LGPL-2.1 texts are included. Qt wheel metadata declares its open-source license options even when a wheel only supplies a `LicenseRef-Qt-Commercial.txt`; that file is retained as supplied and is **not** a commercial license grant to AsterPDF.

Qt incorporates additional third-party components (fonts/shaping, image codecs, compression and platform helpers). Consult the Qt 6.10.2 source distribution's `LICENSES` and `qt_attribution.json` files for the build's incorporated notices, and the bundled Qt attribution HTML in `licenses/qt-attributions/`. MuPDF similarly includes third-party libraries under their own licenses, documented in its source distribution. No third-party source is modified by this project.

## Shared libraries and rebuilding

Qt/FFmpeg and other native libraries are shipped in replaceable directory form. AsterPDF does not restrict debugging or replacing LGPL libraries for the user's own use. The application source and complete build scripts are supplied with the distribution; use the upstream matching source versions when rebuilding third-party libraries. Source archives produced by `scripts/package.py` contain AsterPDF source, not copies of every upstream library's source tree; upstream source locations are above.

Public distributors should retain these notices, ship the matching AsterPDF source artifact with binaries, preserve third-party notices from their exact platform wheels and satisfy the applicable corresponding-source requirements. The provided draft-release flow is intentionally separate from public publication and code signing.

## Build/test tools

PyInstaller: GPL-2.0-or-later with bootloader exception (https://pyinstaller.org/en/stable/license.html). The exception permits the generated bundle to use AsterPDF's own license. Pytest (MIT), ReportLab (BSD-style) and imageio-ffmpeg (BSD plus its FFmpeg build notices) are development/fixture tools, not imported into the application bundle. PyInstaller's bootloader notice is included under `licenses/build-tools/`.

The CTAN animate package/manual is used as a compatibility reference and externally downloaded validation sample, under the LaTeX Project Public License. No animate source code is embedded in AsterPDF. The adapter independently reads PDF structures and a bounded set of literal parameters; it never executes the package's JavaScript.

The private user test PDF is not redistributed. The project does not include third-party trademarks as its logo.

## Installed fonts used during editing

AsterPDF 0.2 reads the font chosen by the user through Qt and embeds a subset for replacement content. It does not bundle Windows, macOS or other proprietary system fonts with the application. OS/2 restricted/no-embedding flags are checked where present; installed fonts remain subject to their own licenses. Font selection and PDF embedding happen locally.

## Optional downloaded fonts

No Google Fonts binaries are bundled. The optional font lookup connects to https://github.com/google/fonts and downloads only families with an OFL.txt license. Each downloaded family's license and a source/sha256 record remain in the app-private font cache. Font copyrights remain with their respective authors. Local font imports retain the user's responsibility to use the font under its license; embedding restrictions continue to be checked. The application does not install fonts system-wide.


## Optional local EPS / PostScript conversion (0.7)

Ghostscript is **not bundled, downloaded or installed by AsterPDF**. If the user has installed it, the image pane can invoke its console executable with `-dSAFER` to convert a user-chosen EPS/PS file to a temporary PDF, then insert the vector content. The external installation retains its own copyright and license terms. No proprietary fonts from the user's PDF or system are included in the software distribution; clipboard PDF/font data stays in the local workflow.


## Markdown and offline mathematics

- markdown-it-py 4.0.0, mdit-py-plugins 0.5.0, linkify-it-py 2.0.3, mdurl and uc-micro-py: MIT; license texts under `licenses/` and versions in `licenses/inventory.json`.
- MathJax 3.2.2: Apache-2.0, copyright The MathJax Consortium. [License](licenses/MathJax-LICENSE.txt). A custom bundle contains the TeX base/AMS/newcommand packages, LiteAdaptor and SVG output with TeX glyph paths. Upstream: https://github.com/mathjax/MathJax-src/tree/3.2.2 . Reproducible build entry and dependency lock: `scripts/mathjax/`.
- quickjs-ng 0.16.2.1 and its embedded QuickJS-NG engine: MIT; distribution license texts under `licenses/quickjs-ng/` and [engine license](licenses/QuickJS-NG-LICENSE.txt). Used only for the bundled math renderer, without filesystem, network or document-script bindings.

No browser, Node.js runtime, LaTeX installation or system printer is required to read Markdown or render mathematics. Externally linked images may use the network. Formula output is vector outlines; ordinary Markdown text remains searchable.
