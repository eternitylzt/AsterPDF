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
