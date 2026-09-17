# AsterPDF 0.3.0 validation / 实测记录

Date: **2026-09-16**. Host: **Windows 11 x64 build 26200**, native Qt, Python 3.12.10, PySide6 6.10.2, PyMuPDF 1.27.1, pikepdf 10.3.0.

## Executed practical tests

**24 passed in 69.74 seconds**. This includes the previous 18 workflows and six new 0.3 tests. After the final sidebar label/width and image-help refinements, the two affected tests passed again in 4.13 seconds. It is a focused user-workflow suite, not a general PDF conformance claim.

- Enter a missing-font text object, click elsewhere without editing, verify identical revision bytes and no font access. Move it, clear its text without consulting fonts, save/reopen and verify removal.
- Verify Home has no close button. Add an open unsaved document and another file, preview and reorder, merge into a new PDF; unsaved annotation survives and original source hash is unchanged.
- Draw a region, click elsewhere to clear it; change persistent export defaults; copy at 144 DPI with measured output width; export without a DPI prompt.
- Insert overlapping raster images; select either in the sidebar, multi-select/extract, select on the page, and navigate to a page with no images and verify its empty-state message.
- Save/reopen a closed arrow with matching stroke/fill; verify explicit width/opacity labels.
- Switch languages while retaining documents; check English visible UI has no Chinese labels and Chinese navigation returns to text labels.
- Previous workflows continue to cover reading layouts/wheel/keyboard/presentation, character selection, annotations, direct object editing, Unicode, undo, media preservation and genuine content edits.

## Font search, download and offline cache

Executed a real request to the official Google Fonts repository: **2,001 OFL families** in the returned catalog. Searched for **Lato**, downloaded its family files and OFL license, loaded them through Qt and obtained a valid embeddable font buffer. Helvetica lookup proposed Arimo as a similar candidate rather than identifying it as the original font.

In a **new process**, registered the cached Lato files, matched `Lato-Regular`, replaced an existing label, saved and reopened it. The old text was absent, replacement searchable and Lato embedded. This validates the cache-to-edit path, not availability or compatibility of every font in the catalog.

[Download record](evidence/font-download-0.3.json) · [Cache/edit round trip](evidence/font-roundtrip-0.3.json).

## Actual packaged Windows executable

The PyInstaller GUI executable launched directly and exited successfully. [Frozen record](evidence/windows-0.3.json):

- Single-page Right key, presentation Left key and Escape passed for both documents.
- Installed-font text replacement, standard arrow addition, save/reopen passed.
- In a **4.01-second diagnostic including initialization**, the actual research PDF produced **48 animation frame presentations** and the MP4 fixture **64 video frames**, position **2583 ms**, with no player errors.

The page-cache count is an instantaneous cache snapshot after invalidation; retained page pixels and separate animation overlays can be visible while this count reads zero. Reading was also checked in the independent native run below.

## Actual PDF animation and preservation

Used the user's private `E:\tempdata\testpage.pdf`: 89,588,667 bytes, 3 pages, 180 icon animation frames on page 2, 18 declared FPS, 13 original controls.

- Displayed the base page; advanced eight frames in reading mode.
- Entered presentation, clicked the **original PDF playback button** and observed eight additional frames.
- Right/Left turned pages, leaving the animation page paused it, and Escape exited presentation.
- Added an annotation, rotated another page, saved separately, and compared all **180 frame-stream hashes**: unchanged. Original input hash unchanged. Four sampled frames rendered differently.
- Seven sequences from the official animate manual had different first/last frame renders.

[Presentation record](evidence/presentation-0.3.json) · [Save/media preservation](evidence/real-pdf-0.3.json).

Private input and its screenshots are not redistributed. SHA-256: `add246f1c7b278c3cbe499c3e4ec5d4009dbf2275f239ab7c95a7d29796c159d`.

## Visual inspection

Native Windows screenshots were inspected for Home, merge queue, original glyphs on edit entry, image thumbnails, solid arrows, fonts dialog and separate language UI. All distributed screenshots use the project's public demo.

[Home](evidence/home-zh-0.3.png) · [Unchanged editor](evidence/inline-unchanged-0.3.png) · [Image list](evidence/images-zh-0.3.png) · [Solid arrow](evidence/arrow-zh-0.3.png) · [Merge queue](evidence/merge-zh-0.3.png) · [English UI](evidence/objects-en-0.3.png).

## Not verified or unsupported

- macOS/Linux native runtime, fonts, packaging startup and codecs remain unverified. Configurations are provided.
- Acrobat itself was not launched. Standard annotation round trips and native/previous independent Poppler rendering are evidence, not an Acrobat application test.
- The unpublished AsterPDF repository remains unset; its actual release-check endpoint is not tested.
- Every Google Fonts family, commercial font availability, complex script shaping, exact font version matching, and all media codecs are not claimed.
- OCG animation, arbitrary JavaScript/3D, recursive Form text editing and general paragraph layout remain unsupported.

[Compatibility](COMPATIBILITY.md) · [0.3 feedback mapping](USABILITY-0.3.md) · [Historical 0.2 validation](VALIDATION-0.2.md).
