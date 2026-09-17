# AsterPDF 0.6 validation / 实测记录

Date: 2026-09-16. Windows 11 x64 build 26200, Python 3.12.10, PySide6 6.10.2, PyMuPDF 1.27.1, pikepdf 10.3.0.

## Practical workflows

The full suite passed **44 tests in 528.93 seconds**. Following the final annotation-border control and in-place language/list synchronization refinements, **4 affected control tests passed in 13.36 seconds**. [Summary](evidence/tests-0.6.json).

- Actual Qt copy/paste, glyph-aligned mouse/caret geometry, PDF draft preview, original-font bold/slant/color, baseline alignment of appended text, repeated editing and undo/cancel.
- CFF and TrueType fonts with PDF text positioning; original font resources retained after styling, partial deletion and save/reopen. A second edit after reopening with a different input font preserves earlier embedded font resources.
- Chinese multiline paste, removing a line break and editing again, save from an active editor; unavailable-font drafts can undo, switch tools and cancel. Unsupported mappings remain conservative failures, not guessed replacements.
- Dragging actual main-toolbar buttons without triggering their action; persistent order, module toggle, transparent-toolbar inset, centered single/two-page views and 1.5625%–6400% zoom.
- Double-click FreeText creation, automatic height, drag boundary resize/reflow, editable border width, timestamps, whole-document sorting/navigation, hidden page annotations with unchanged list/PDF, and named region export.
- Page-range/all-page/region color replacement and one-step undo; region rendering changes only the selected area and retains text/vectors.
- Existing image placement/clipboard/transforms, reading/navigation, search, presentation, page tools, extraction, recovery, standard annotations and native print-to-PDF workflows remain covered.

## Real document / 实际测试 PDF

Used the private 89,588,667-byte PDF provided by the user. On page 3, partial deletion retained the original font, size and color; bold/slant/color were then changed without loading a local replacement font. All **180 animation appearance streams remained byte-identical**, including after annotation and save. The original file hash remained unchanged. [Sanitized report](evidence/private-edit-0.6.json).

Measured backend transactions: object scan **0.063 s**, partial deletion **0.266 s**, style change **0.156 s**, annotation addition **0.140 s**. These exclude UI typing, tile repaint and other machines' storage performance. MuPDF reports unsupported Screen-annotation appearance generation during inspection; existing media streams were verified preserved. The private PDF and screenshots are excluded from all release archives.

## Displays and independent rendering

Three actual displays were exercised: laptop DPR 2.5 and two external DPR 1 displays. At 100%, the rendering scale matched each monitor's reported physical DPI/72. [Report](evidence/physical-zoom-0.6.json). This checks the software calculation, not the accuracy of EDID or a physical ruler measurement. Remote-display dimensions and hot-plug changes are unverified.

Reviewed native Chinese/English UI, PDF draft previews, annotation handles and transparent toolbar layout. Independently rendered the saved public example with Poppler: selected bold/slant text, solid arrow and colored FreeText border are visible. Poppler emitted missing display-font notices for Symbol/ArialUnicode; these were not the edited Latin text. [Independent render](evidence/poppler-edited-0.6.png), [reader](evidence/reader-zh-0.6.png), [draft preview](evidence/text-preview-0.6.png).

## Packaged Windows executable

The **0.6.0 frozen executable** passed the desktop diagnostic in **19.52 seconds**, exit 0. It opened the private research document and public H.264/AAC fixture, painted native page tiles, displayed **45 animation frames** and decoded **64 video frames**. Single-page turning, presentation navigation/Escape, text edit/save/reopen and **3-page** print-to-PDF/reopen passed. [Raw report](evidence/windows-0.6.json).

`rendered_pages` in the diagnostic report is the historical field name for cached tile count, not unique page count. Hidden-start diagnostics explicitly request viewport painting. Ordinary visible UI was reviewed separately. The delivered EXE is checked against this tested binary by SHA-256; both archives undergo CRC checks and source files are compiled for syntax validation.

## Limits of evidence

Windows x64 is tested. **macOS/Linux build configurations are supplied but not run or packaged on those platforms here.** Acrobat itself and physical printers were not tested. CFF/TrueType cases and the real LaTeX document are evidence for these workflows, not a claim of universal Word/LaTeX editing or arbitrary PDF compatibility. Complex encodings, clipping text, ambiguous glyph mappings and general paragraph reflow remain restricted; see [compatibility](COMPATIBILITY.md).

Region color changes use vector clipping groups: clipping-ignorant text extraction can duplicate text crossing the boundary. This is disclosed in the operation dialog. Annotation visibility is view-only; export/print/save still include annotations.

Minimize/restore results from 0.5 and memory/FPS measurements from 0.4 are historical reports, not newly measured 0.6 benchmarks. No remote repository was created or GitHub release published. The update repository remains unset until the user configures it.
