# AsterPDF 1.3.0 · Forms and Favorites / 表单与收藏

## Release revision · Markdown and page-gap correction

The final 1.3.0 replaces the earlier local build of the same version. Markdown code-block overlay widgets and their settings have been removed; code is rendered once using the original PDF document layout. The continuous/A4 export choices and heading outlines remain. Compact pages now show a faint separator with directional collapse/expand hover cursors. First-click handling reserves the separator so a real double-click cannot pan, select text or activate media before expansion.

**49 tests passed, 1 deselected, in 96.32 seconds on Windows.** This includes the release regressions plus forms, Markdown reading/export and document fullscreen/gaps. New practical tests repeat collapse/expand with pointer and hand tools in single/two-column layouts, check rendered separator visibility, and verify that saved legacy code-scroll settings cannot re-enable overlays. The deselected media selection test is outside these changes; it was already excluded in the release build workflow. Earlier scrolling-code checks below describe the withdrawn local implementation, not the released feature set.

Native screenshots were inspected: code appears once with its original monospaced document layout and the page joins show faint lines. The user's README opened as one page with 32 outline entries and no overlay controls. A freshly rebuilt Windows executable passed the packaged diagnostic in 11.36 seconds, including Markdown rendering, page/presentation navigation, 36 observed animation frames and edit/save/reopen. [Packaged report](evidence/desktop-1.3.0.json). Release packages are rebuilt from this corrected source, not reused from the earlier local 1.3.0 package.

2026-09-28, Windows native Qt. Focused tests cover in-place text input, Tab/Shift+Tab without unwanted toggling, checkbox/radio groups, lists, calendar selection, undo/redo, Save As/reopen, close-with-pending-input and crash draft recovery. Values and appearance streams are checked separately, including Chinese glyphs. Merely entering a field makes no edit. Existing animation controls retain click playback, and filling a field preserves unrelated page streams and animation structures. Favorites labels and star tooltips were checked in both languages; existing settings keys remain compatible.

**17 focused tests passed in 76.55 seconds**, covering `test_forms.py`, `test_document_reading.py`, `test_markdown_reading.py`, `test_desktop.py`, recovery and multi-document close/save regressions. The older close-all test was updated to disable the subsequently introduced current/all choice, allowing it to continue testing save prompts. A native form-editing screenshot was also inspected for editor placement, visible cursor, field highlighting and the Favorites sidebar.

The supplied questionnaire contains 16 pages and 108 widgets. On a private recovery copy, text (including Chinese), a common date and a radio choice were changed and saved. Values and appearances were correct; all other field values stayed unchanged, all four unsigned signature fields remained, and the original file hash stayed unchanged. A cropped field render was visually inspected. The three-field backend operation took approximately 0.83 seconds locally after font subsetting (one sample, not a general benchmark). The questionnaire and filled output are not redistributed.

No new dependency was added. This delivery is local; no GitHub upload was requested. Acrobat and physical macOS/Linux interaction are unverified. Signed documents and XFA are read-only/unsupported; arbitrary form scripts are not run.

The rebuilt Windows 1.3.0 executable opened the synthetic form PDF and passed its packaged desktop diagnostic in 10.08 seconds with no errors (rendering, navigation, presentation exit, print-to-PDF and existing content edit/save/reopen). Form-specific fill/appearance/recovery checks above ran under the native source runtime, not external Acrobat.

---

# AsterPDF 1.2.1 · Markdown verification

## Local reading update · 2026-09-28

Follow-up Markdown checks cover native code-block horizontal scrolling and clipboard copying, hiding overlays during region selection, the A4-default Save As dialog, A4/long-page export with full code and heading outlines, export from the opened snapshot after the source changes on disk, and preserving annotations when saving edited Markdown-derived PDFs. Reading and export layouts are independently configured in the Markdown preferences section. No browser engine or new runtime dependency was added. PDF form filling was initially assessed in this stage and is now implemented in 1.3.0: [current scope](FORMS.md).

Nine focused native Windows Qt tests passed for document-only fullscreen (F11/Esc, restored maximized state, retained/hidden media controls and Quick overview), existing presentation/navigation, Markdown math and printer-free conversion, long-page/A4 layouts, nested/repeated heading destinations, outline navigation and save/reopen, and double-click page-gap toggling in single/two-column layouts without PDF edits. Command: `python -m pytest tests/test_document_reading.py tests/test_release_121.py tests/test_practical_ui.py::test_reading_wheel_keys_four_views_and_presentation -q`.

The local user-supplied `Downloads/README.md` now renders as one long page with 32 outline entries. The project README also renders as one page. A 900-paragraph document preserves its final heading and ending text on a single 24,486-point-high page. Native screenshots of fullscreen and Markdown outline were inspected locally; user documents/screenshots are not redistributed. This update has not been tested on macOS/Linux or published to GitHub. Earlier release results below describe the previous paginated behavior.

## Published 1.2.1 checks

2026-09-22, Windows native Qt. Six focused checks passed: vector formula PDF output, code-dollar preservation, nested lists and tables, visible unsupported-formula fallback, background import/save, image resources, and absence of system-printer initialization. The printer constructor is replaced with a failing stub in import regressions.

The user-supplied FastQSL2 README (https://github.com/el2718/FastQSL2/blob/main/README.md) was opened locally: all 123 math occurrences converted successfully. Native rendered pages were inspected for inline fractions/vectors, nested code, tables containing formulas and a longer solar-wind equation. The user's file is not redistributed.

Math rendering uses a checked-in MathJax SVG bundle and a bounded local JS context, without browser or OS/network bindings. Formula paths remain vector content in exported PDFs; ordinary text remains searchable. Markdown paging/fonts are not pixel-identical to a GitHub browser page. Release CI runs native builds and regression tests on Windows, macOS and Linux; physical macOS/Linux desktop behavior remains unverified here.

The Windows 1.2.1 frozen executable passed the desktop check in 18.70 seconds: the supplied README produced 18 pages, 35,144 searchable text characters, one linked image and 1,942 vector drawing records, with zero formula-error markers. The original math example produced one page and 94 vector drawing records without raster images. Save/reopen, navigation and decoded video playback checks also passed. [Report](evidence/desktop-1.2.1.json) · [Original example screenshot](evidence/markdown-1.2.1.png).

---

# AsterPDF 1.2.0 · Validation / 验证

Windows native Qt validation, 2026-09-20. Cross-platform automated regression checks and native packaging run in the release workflow; this is separate from physical macOS/Linux desktop validation, which has not been performed here.

**Current release regression run: 47 passed (Windows native Qt), 105.69 seconds.** One Pillow deprecation warning, no test failures.

## Practical checks

- New media-layer tests: Screen/Movie/RichMedia annotation ordering, undo, save/reopen, original streams and text geometry preservation; overlapping real video players, page/list selection and stacking masks.
- Regional text/vector/image recoloring, sequential color pairs and selected-pair application; unchanged outside pixels; text/shape arrangement after editing.
- Actual context-menu media export and byte comparison, animation frame export, extraction-list image copying, unchanged-page preview reuse after rotate/reorder/delete, and single-document close/save prompts.
- Native Markdown imports with HTML tables, SVG and linked images. The supplied README fixture produced three pages, 5,159 text characters and six image resources. No WebEngine added.
- Earlier targeted native regression runs cover independent annotation presets, batch edits, replacement comments, shape drawing/styles, transparent clipboard images, recent-file selection and multi-document closing.
- Windows frozen-app checks cover decoded video frames, LaTeX animation advancement, Markdown rendering, text edits saved and reopened, and PDF printing. Machine-readable evidence is stored in `docs/evidence/`.

## Limits

Movie/RichMedia media-layer tests use structural fixtures; they do not prove every Acrobat media variant can play. Screen/Rendition video has actual decoder testing. No claim of full Acrobat JavaScript compatibility. Linux headless Qt may outline fonts, so native font editing is separately verified on Windows. macOS/Linux interactive playback, OS file-open behavior and unsigned-app installation still require physical-desktop verification.

## Packaged Windows result

The 1.2.0 executable completed desktop verification in 20.95 seconds: 42 animation frames rendered, 60 video frames decoded, Markdown text/images rendered, edited text saved/reopened, and three-page PDF print output verified. No reported errors. [Machine-readable report](evidence/desktop-1.2.0.json).
