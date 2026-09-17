# AsterPDF 0.5 validation / 实测记录

Date: 2026-09-16. Windows 11 x64 build 26200, Python 3.12.10, PySide6 6.10.2, PyMuPDF 1.27.1, pikepdf 10.3.0.

## Practical tests / 常用流程

The full suite passed **37 tests in 366.79 seconds**. Following the final localized refresh, original text-transform and compact editor refinements, the **5 affected interaction/presentation tests passed again in 17.95 seconds**. These are practical workflows, not a claim that every PDF structure is editable.

- Actual Qt Ctrl+C in a missing-font editor, click-away with no mutation, partial deletion without resolving any font, Cancel and retained original font/color/size after save/reopen.
- Selected-character bold/italic with original color; original fonts remain on the rest of the text. New inline text boxes and delayed commit.
- Image tool activation independently of text, background object scan does not switch it off, click placement, original-resolution clipboard copy/paste, aspect/free resize and repeated moves.
- Toggle modules off, toolbar/subbar overlay, draggable customization ordering, star-only bookmark action.
- Arrowhead size and line width, selection/sidebar style changes, independent note border, single-click content and standard annotation save/reopen.
- Existing reading layouts/navigation, search, presentation/Escape, page organization, vector edits, image/region extraction, native print-to-PDF, recovery and media preservation remain covered.

## Actual displays / 实际屏幕

Three attached displays were used: laptop DPR 2.5, landscape external DPR 1, portrait external DPR 1. Each underwent two normal-window and two maximized minimize/restore cycles: **12/12 restored to the original monitor**. The test drove native Qt window states, not physical taskbar clicks. Monitor hot-plug/topology changes remain untested. [Raw report](evidence/screens-0.5.json).

## User's real PDF / 用户测试文档

On the 89,588,667-byte private PDF, removed part of a Chinese text block on page 3 without providing any local font. Reopened text retained its original font, size and color. All **180 animation appearance streams remained byte-identical**, including after adding an arrow and saving. The original file hash remained unchanged.

Measured on this host: object scan **0.047 s**, partial-text commit **0.234 s**, new annotation commit **0.125 s**. These are backend transaction durations, excluding UI input, tile repaint and disk performance on other systems. MuPDF emitted warnings about generating Screen-annotation appearances while inspecting the source; the existing media dictionaries/streams were preserved. [Sanitized report](evidence/private-edit-0.5.json). The private PDF and its screenshots are excluded from distribution.

## Visual review / 外观复核

Native screenshots were inspected for rich text, annotation selection/styles, compact controls, opacity and bilingual switching. The saved public example was also rendered with Poppler independently of MuPDF, including partial bold/italic, original-font text, solid arrow and separately colored FreeText border.

## Scope of evidence

Windows desktop is tested. macOS/Linux build configurations are provided, **not run or packaged here**. Acrobat and physical printers were not run. Animation FPS and memory measurements from 0.4 are historical evidence in [VALIDATION-0.4.md](VALIDATION-0.4.md), not new benchmarks for 0.5. The repository update endpoint remains unset until publication.

## Packaged Windows build / 实际打包程序

The **0.5.0 frozen executable** passed the desktop diagnostic in **18.72 seconds**, with exit code 0 and no reported errors. It opened the private research PDF and public H.264/AAC fixture, painted native page tiles, displayed **47 animation frames** and decoded **65 video frames** (2625 ms). Single-page navigation, presentation turning/Escape, the new character-range editing backend with save/reopen, and three-page print-to-PDF/reopen all passed.

[Raw packaged-build report](evidence/windows-0.5.json). `rendered_pages` is the diagnostic's historical field name for cached **tile count** (6 / 4), not unique page count. The run includes hidden-start viewport painting; ordinary visible UI was reviewed separately. The delivered executable is checked against the tested executable by SHA-256, and both release archives undergo CRC validation.
