# AsterPDF 0.2.0 validation / 实测记录

Date: **2026-09-15**. Host: **Windows 11 x64 build 26200**, Python 3.12.10, PySide6 6.10.2, PyMuPDF 1.27.1, pikepdf 10.3.0. This is an executed workflow record, not a compatibility guarantee for arbitrary PDFs.

## Practical desktop tests / 实际操作

Full suite: **18 passed in 23.92 seconds**. After the final draft-close, selection-state and font-embedding refinements, the affected six practical tests were rerun: **6 passed in 16.34 seconds**. Windows tests use the native Qt platform, not the Windows offscreen font substitute.

- Single-page Right/Left, wheel boundary turns, Up/Down scrolling; four layouts; current-page thumbnail tracking; presentation navigation and Escape; hand panning.
- Select **four characters inside a word**, copy exactly that substring, highlight just that range, preserve author, list comments, ignore an arrow click without dragging, drag a real arrow, delete and reopen.
- Enter object editing without an Inspect button; double-click and type a new label; commit; drag the new object; resize an image with its handle; Delete; Ctrl+Z; visit another page and return; save/reopen. The old text is absent, replacement searchable, images and vector drawings remain.
- Outline and click the embedded image; choose Crop before drawing; inspect merge file previews, change queue order and remove an entry.
- Paste Chinese and a newline using Microsoft YaHei, cancel closing the unfinished draft, change pages to commit, edit the newly embedded text again, Save with the inline editor active, and reopen the saved file.
- Chinese FreeText content/size/color change and a dashed closed arrow with custom author/width survive save/reopen.

The original twelve tests continue to cover original-image extraction/replacement, page operations, recovery, vector/group transforms, unknown catalog preservation, untouched media streams, search and language changes. This is a small workflow suite, not a broad PDF standards conformance framework.

## Actual Windows bundle / 打包程序

Built with PyInstaller 6.22.3. The GUI executable was started directly with no Python entry script.

[Combined frozen run](evidence/windows-0.2.json):

- Successful native startup; per-document single-page Right key, presentation Left key and Escape all passed.
- The frozen process read an installed font, replaced PDF text, added a standard arrow, saved and reopened the result; old text was absent and new text searchable.
- During a **4.01-second diagnostic including initialization**, the real animate sample produced **48 animation frame presentations**, and the MP4 fixture produced **64 video frames** with playback position **2583 ms**. No player errors were reported.

[Single-document frozen run](evidence/windows-animation-0.2.json): **54 animation frame presentations in 4.03 seconds**, with the animation visible on its document page. Its screenshot was inspected privately; the private research content is not distributed. The diagnostic page-cache counter is a snapshot and can read zero after invalidation while a retained page image and live animation overlay are visible; it is not used as evidence of successful reading.

## Real animation in presentation / 演示中的真实动画

A separate native Windows run used the user's actual `E:\tempdata\testpage.pdf`:

- Displayed the page and waited for its base render.
- Advanced at least eight frames in reading mode.
- Entered presentation, **clicked the original PDF's PlayRight/PlayPauseRight button by its page coordinates**, and observed at least eight additional frames.
- Right advanced to page 3 and paused the prior page's animation; Left returned to page 2; Escape exited presentation.

[Machine-readable record](evidence/presentation-0.2.json). Observed base-page readiness was about **0.906 seconds in this one run**; it is not a startup benchmark or FPS guarantee.

## Save and media preservation / 保存保留

Private sample: 89,588,667 bytes, 3 pages; page 2 has **180 icon animation frames**, 18 declared fps and 13 original button widgets.

SHA-256: `add246f1c7b278c3cbe499c3e4ec5d4009dbf2275f239ab7c95a7d29796c159d`.

Repeated for 0.2: add an annotation on page 1, rotate page 3, save a separate PDF, rediscover the animation and compare **all 180 original frame-stream hashes**. All remain unchanged. Samples 0/30/90/179 render differently. The input file hash remains unchanged. Seven sequences in the official animate manual again produced different first/last frames. [Record](evidence/real-pdf-0.2.json).

## Visual checks / 显示检查

Native Windows screenshots of the reader, inline editor and annotation list were reviewed. This exposed and fixed a dark native QTextEdit background in the light UI.

- [Reader](evidence/reader-0.2.png)
- [Inline editor](evidence/inline-editor-0.2.png)
- [Annotation list](evidence/annotations-0.2.png)
- [Independent Poppler annotation render](evidence/independent-annotations-0.2.png)

Poppler independently rendered edited Chinese/English FreeText. Its local font resolver emitted substitution notices for standard PDF fonts; the text remained visible. Standard annotation fonts can differ in appearance across readers. Content-edit replacement fonts are embedded. Acrobat itself was not launched in this delivery; the user reported that prior annotations were visible there.

## Explicitly not verified / 未验证

- macOS/Linux native runtime, package startup, fonts and codecs. Build configurations are supplied, not reported as tested platforms.
- Real AsterPDF GitHub update requests: the repository is still unset. Stable-version comparison was checked locally; the configured network/download flow awaits a published repository.
- Every animate version/option, OCG animation, arbitrary JavaScript/3D, or every media codec.
- Universal editing of nested Form internals, clipping text, arbitrary scripts or complex text shaping.

See [compatibility](COMPATIBILITY.md) and [the feedback/change mapping](USABILITY-0.2.md). Historical 0.1 results are retained separately in [VALIDATION-0.1.md](VALIDATION-0.1.md).
