# AsterPDF 0.7 compatibility / 兼容性

This document describes implemented behavior, not a roadmap. 此文档描述当前实现，未将计划中的功能列为完成。

## Platform status / 平台

| Platform | Source/configuration | Actual verification in this delivery |
| --- | --- | --- |
| Windows x64 | PySide6/Qt + PyInstaller directory bundle; optional Inno Setup configuration | Python 3.12 desktop UI, PDF backend, animation and video/audio workflows tested. See VALIDATION.md for packaged build result. |
| macOS | `.app` bundle + tar.gz workflow, icon and document type metadata | Not run; signing/notarization not configured or performed |
| Linux x64 | Qt directory bundle + tar.gz, `.desktop` file | Not run; FFmpeg/runtime platform dependencies must be verified on target |

## Reading / 阅读

Implemented: local PDFs, file drop, multiple tabs, recent files, position/zoom restore, thumbnails, outline, reading bookmarks, page navigation, case-insensitive MuPDF text search with result rectangles, character-caret text selection/copy, pointer image selection, hand pan, zoom/fit, single/two-page and continuous single/two-page layouts, full screen and presentation. Standard internal page links and explicit HTTP(S) links are clickable. File-launch actions and arbitrary action scripts are not run.

Selection follows individual character boundaries within one page; it requires an existing text layer and does not span pages. Single-page wheel navigation turns at the scroll boundary; arrows and Escape are routed even when the canvas has focus. Personal bookmarks are stored locally per original file path, not written into the PDF outline. Night colors affect rendered reading pages only; exports always use original page colors. Text and annotation coordinates use rotation/crop transformations.

## Animation and media / 动态内容

| Structure | Current implementation | Evidence / remaining boundary |
| --- | --- | --- |
| LaTeX animate `method=icon` | Numeric field names, inherited field hierarchy, icon appearance frames, `anmN` placement, literal FPS, native-control mapping, forward/backward, pause, stepping, replay, loop, speed | User's 89,588,667-byte PDF: page 2, 180 frames, 18 declared fps. Actual desktop frame advancement verified. Seven sequences in official animate manual inspected and frame-rendered. |
| animate `method=widget` | Ordered frame widget appearances and original placement | Original 24-frame fixture; continuous frame playback and distinct frame renders tested. No claim that every animate release/options combination works. |
| Per-frame literal rate arrays | Recognized bounded numeric `nFpsAt` arrays | Implemented; variable-rate timeline sample has not been specifically verified |
| animate OCG method | Detection and visible unsupported notice | Not played in 0.4 |
| RichMedia assets | Embedded MP4/M4V/MOV, MP3/M4A/WAV/OGG/WebM/FLAC candidates extracted to private local files and passed to Qt | H.264/AAC MP4 and PCM WAV actual decoder output tested; official animate manual MP3 asset detected. Other containers/codecs unverified and may fail explicitly. |
| Movie and Screen Rendition | Direct embedded filespec and basic rendition media clip discovery | Implemented; no independent real-world sample verification |
| Flash, raw legacy Sound, 3D, external media URLs | Explicit unsupported notice | Not played |
| General Acrobat JavaScript | No execution environment provided | Unsupported; static extraction never calls `eval` or `exec` on PDF data |

The reader retains original animation button artwork, mapping recognized button names to native commands. Arbitrary scripts attached to those buttons are ignored. Complex event timing, custom JS, interactive timeline branching and nonstandard frame names are not supported. Automatic audio/media playback is not triggered by document scripts; the user starts it.

Declared FPS is the document's requested rate. The player paces against wall time and skips late frames. Requested FPS/speed is distinct from actual displayed FPS; throughput depends on resolution and page complexity. Auto quality limits playing frames to 1280 pixels wide, Smooth to 960, and Native retains display DPI. Pausing through playback controls requests native pixels. Export/save does not freeze the source document at the current display frame. An animation preparation cache stores a separate frame PDF in the session folder and a 32 MiB frame-image cache (one oversized frame can exceed that budget, with a 12 MP hard single-frame cap).

## Page tools and preservation / 页面工具与保留

Merge through a preview/reorder/remove queue, extraction into one PDF or individual page PDFs, delete, rotate, multi-selection, reorder, blank insertion and crop are implemented. Home opens a standalone merge queue; Page operations uses a docked queue. Both produce a new PDF. Add open PDFs uses their current edited snapshots; additional files can be queued, reordered or removed. The separate Split UI has been removed; choose Crop before drawing the region. Reorder changes the page tree while retaining existing page objects; the current document catalog remains authoritative. Local reading bookmarks are page-number based.

**Operation bounds:** page reorder/import can affect absolute page-index JavaScript, destinations and forms. Selected-page import/export does not transfer the source document-level outline, script name tree, form field tree, or attachment name tree. Page annotations and embedded objects on retained/copied pages are retained by pikepdf, but cross-document navigation may require repair in the source authoring system. Keep-outside cropping can hide annotation/media controls; they remain in the file. Destructive crop removes outside/crossing annotations and refuses interactive pages.

**Crop has two modes:** default destructive crop removes outside page content, with the crossing-object limitations below. Keep-outside mode and vector-region PDF export only change visible boxes; outside data remains. Neither mode scrubs unrelated pages, attachments or local undo/recovery history.

## Annotations / 批注

Standard Highlight, Underline, StrikeOut, Text, FreeText, Ink, Line/arrow, Square and Circle annotations are written with appearance streams. Annotations can be selected and deleted in batches; style/content editing remains limited to AsterPDF-owned annotations. Stroke color, opacity and applicable border width are editable; text-note content is editable. FreeText content, supported font/size and color can be changed. Annotation text uses standard Latin/CJK PDF fonts; content editing supports installed system fonts. Closed arrow endings have matching solid fill and independently adjustable head size through a standard annotation appearance. FreeText borders default to zero and can have a separate width/color/dash style. Single-click selects a note or shape for sidebar/style editing; double-click edits note content. Author names are configurable; ownership uses an AsterPDF-prefixed annotation ID, independent of the author. Legacy AsterPDF-authored annotations are also recognized. Sticky notes move by dragging; note/shape text is previewed on hover. Marquee selection and Delete work on canvas/list. The document-wide sidebar visually separates metadata and comment, sorted by creation time or document position. A view-only checkbox hides annotations without changing the list or saved PDF. FreeText boxes can be created by double-clicking, grow to fit, and have draggable edges/corners for reflow and repositioning. Other annotation types do not offer arbitrary vertex resizing or multi-annotation group transforms.

Tests reopen written PDFs and inspect subtype, ownership, content and appearance streams. A Poppler render is also used for independent visual validation. Acrobat itself was not run in this delivery; do not interpret standards conformance as an Acrobat application test.

## Existing content objects / 已有内容

The editor retains original unselected stream bytes and replaces only selected ranges. It never uses a white overlay, redaction-and-reinsert or whole-page image conversion as existing-content editing.

| Object | Supported operations | Boundary |
| --- | --- | --- |
| Text | Double-click a block; select characters to change font/size/color/bold/italic, insert/delete text, or insert a new inline text box. Retained glyphs reuse original PDF font resources, codes and transforms; only inserted characters or explicit font-family changes require input fonts. | Horizontal input; simple one-byte fonts and Identity-H CID codes with reliable glyph mapping. Clipping text, ambiguous encodings and nested Form labels may be refused. Common ligatures remain a single PDF glyph: styling/deleting only part of one requires selecting the entire ligature. Existing text does not need installed fonts for partial deletion, whole-object deletion or transforms. An unchanged editor commits nothing. Local ranges adjust following spacing on the same baseline, without paragraph reflow. Draft preview and caret geometry use the PDF renderer. Qt stores the editable text and clipboard/undo state. Bold/slant on retained glyphs are geometric synthetic styles, not replacement fonts. Removing the weight of an intrinsically bold font requires explicitly choosing a regular face. Unsupported structures retain a cancellable draft instead of writing a guessed replacement. |
| Raster image XObject | Select, move, aspect/free scale, clipboard copy/paste, delete occurrence, replace occurrence, insert, extract | Replacement affects only selected invocation through a new resource name. Original source resolution is preserved when extracting; image masks are separately stored and not automatically composited. Inline images are not editable. |
| Painted vector path | Select one or multiple paths, move and scale as a group; drag straight-path endpoints | General Bézier handle editing and semantic figure recognition are absent. Existing page clipping stays in its original graphics scope; moving across an external clip can clip the object. |
| Form XObject | Select and transform whole group; original internal vectors and local clip retained | Nested objects are not recursively selectable/editable. This can select a whole scientific figure but not necessarily its individual internal labels. |

Pages containing inline-image syntax or unbalanced content are rejected by the object editor; reading, export and annotations remain available. Entering Edit automatically inspects the current page. Visiting another page keeps editing mode and inspects that page lazily; the entire document is not eagerly scanned. Extremely dense pages may take time to inspect: each selectable unit is measured using a scratch renderer. Cancellation is supported.

## Extraction / 导出

- Render current, selected or ranged pages to PNG/JPG at DPI or explicit width, with JPG quality. Filenames use stem + zero-padded page + optional region suffix; collisions receive a unique suffix.
- Region image and clipboard copy render the PDF at requested resolution, independent of screen zoom. Export settings persist DPI, explicit width, format and JPG quality. Clicking elsewhere clears a region.
- Native raster locations and a thumbnail sidebar support bidirectional selection and multi-selection extraction, including overlapping objects and unlocated resources; the pointer can also select images for right-click extraction. Native raster extraction uses `PdfImage.extract_to`: preserves directly extractable JPEG/JPX bytes, otherwise losslessly decodes to an appropriate image format. Not a screenshot. Separate soft masks may need subsequent compositing.
- Region PDF keeps original vectors/text via page crop boxes; it is not SVG conversion.
- Rendering is limited to 32 million pixels per output image to prevent accidental huge allocations. Batches report progress and can be canceled between pages; already completed files are kept.

## Save, recovery and settings / 保存恢复

Every successful mutation produces a separate on-disk revision and atomic recovery manifest. An operation that fails before commit does not change the current revision. Save writes and reopens a temporary sibling file, then atomically replaces the chosen destination. Crash recovery opens a new unsaved session and never automatically overwrites the original. Use Save As for a separate recovered file. Text drafts are recorded after a 350 ms pause; the most recent keystrokes can be lost if termination precedes that write. Recovery folders are configurable; a session lock avoids offering files currently used by another AsterPDF process. Revert loads the last saved original as an undoable revision (unapplied drafts are discarded after confirmation). Undo history is bounded to about 20 changes or 2 GiB, with at least the latest two revisions retained even for very large files.

Editing encrypted PDFs is refused in 0.7. Signature invalidation warnings exist for recognized signature permissions, but signatures are not created or validated. The app does not promise preservation of signed validity. The engine lock serializes MuPDF work across background tasks; queued computation does not run concurrently inside MuPDF.

Changing language translates existing controls in place, preserving documents, canvases, scroll positions, drafts and playback objects. UI labels, dialogs and built-in messages follow the selected language; raw errors from external libraries may retain their technical English text. Update checking requires `REPOSITORY` in `asterpdf/release.py` (or a previously saved setting) and user action. It compares stable numeric release versions and offers a download-page button. The repository remains unset pending upload; the network endpoint has not been live-tested for this unpublished project. Offline reading never depends on it.

## Explicitly outside this implementation

OCR, PDF-to-Word, certificate signatures, AI features, cloud accounts, mobile/web client, advanced prepress/compression, full Acrobat JS/3D, paragraph reflow, general Bézier/control-point editing, encrypted editing, comprehensive form filling and universal SVG conversion.

## Optional fonts / 可选字体查找

The Find fonts dialog searches the official Google Fonts repository using an explicit network request. Its OFL-only catalog is cached for 30 days, with cached fallback when offline. Downloaded font families keep OFL.txt and source/hash records in the app data fonts directory, registered with Qt privately at startup. Local TTF/OTF import is also available. Commercial fonts, PDF Type 3 glyph programs and exact original font versions are not guaranteed to exist there. Similar candidates are labelled; users review input with the chosen substitute. System embedding restrictions and glyph coverage remain checked. Unmodified glyphs, movement and deletion do not need the font files. No claim of reproducing Acrobat's proprietary font synthesis is made.

Reference: [Google Fonts repository and licensing layout](https://github.com/google/fonts#readme). Tests include a real Lato download, new-process cache registration, genuine content replacement and save/reopen. Network lookup is optional; PDFs and their contents are not uploaded.


## 0.4 display, resource and editing boundaries

Page rendering uses 1024-physical-pixel tiles at the current device pixel ratio, a 64 MiB pixmap budget, small transition previews and at most two retained display lists per active document. Inactive tabs release render/media caches; closed tabs cancel pending work and release decoder state. Engine resources are periodically trimmed. Process RSS can remain above startup due to allocator, font and Qt caches; this is not a fixed process-memory cap.

Text properties edit the selected characters in a horizontal top-level text block, regenerating that block as searchable PDF text. No-op entry does not rewrite or paint fallback glyphs. Unsupported input retains a draft with undo/cancel and tool switching. If PDF contents change while a failed draft is suspended, applying its stale byte offsets is refused; copy the draft and select the current block again. New input may use a local font of a different version/metrics; original font synthesis and complex shaping are not promised.

Shape editing exposes existing straight-path m/l vertices. It retains vector commands and transforms PDF coordinates, but does not infer a compound arrow's semantic head/shaft or edit Bézier handles. Images and groups retain whole-object transforms. Page-local color changes support explicit DeviceGray/RGB/CMYK solid operators and cloned nested Form resources; raster images are opt-in. Patterns, gradients, spot/ICC paint operators, annotations and animation frames are excluded, with a visible dialog notice. Inversion adds a black page background and rewrites supported color operators; it is separate from display-only night mode. Image-mask/color-key behavior can require manual review.

File information reads local metadata. Native printing serially renders pages (default 300 DPI, maximum 32 MP per page); it does not preserve vector print commands. PDF region/page extraction remains vector preserving. Qt PrintSupport is included; physical devices, duplex options and platform printer drivers remain untested.


## 0.5 interaction and validation boundaries

- Toolbar and subbar opacity uses a real overlay over the document. At reduced opacity, underlying content can reduce label contrast; use 100% for a reserved opaque toolbar. Reordering is by dragging visible main-toolbar icons. The customization dialog only controls visibility. Initial page placement and fit calculations reserve space below the overlay; scrolling can move content behind it.
- Editing drafts stay in memory until Apply, Ctrl+Enter, navigation or leaving the editor. Cancel closes the editor/property pane. Long writes still take time for the recovery revision; progress appears after 450 ms. Native page tiles remain visible until updated tiles arrive, with a 24 MiB temporary local-edit fallback budget.
- New notes/images are authored on a small temporary page and imported into the authoritative document, avoiding serialization of a second complete multimedia PDF. Other edits still write complete on-disk recovery revisions. There is no claim of zero latency or eliminating all allocator retention.
- Three actual Windows displays were tested for normal and maximized minimize/restore. Restore was driven through Qt window-state calls; manual taskbar clicking and hot-plug/display-topology changes were not separately verified.
- MacOS/Linux and Acrobat itself were not run for this release. Standards and independent Poppler rendering are verified separately from application compatibility.


## 0.6 bounds

- Zoom uses logical pixels per PDF point internally. The displayed percentage is relative to the current screen's reported physical DPI, refreshed when moving screens; 1.5625%–6400% is supported. Incorrect EDID/remote-desktop physical dimensions can make 100% inaccurate. No ruler calibration or physical ruler measurement is claimed.
- Text drafts render only the selected object's resources, after a 120 ms debounce, through the same content patcher as Save. A draft image is limited to 8 MP. This is a screen preview, not rasterized PDF output. At unusually high zoom/large text blocks a draft preview may be downsampled; normal page reading remains tiled.
- Synthetic bold uses a modest 0.018-em stroke and synthetic slant uses a 0.22 shear. Styles and unchanged glyphs retain font resources; added characters first try reusable embedded coverage, then a visible local-font substitute. A substitute is not guaranteed to match a proprietary/missing original face. Paragraph reflow, complex shaping, clipping text and ambiguous mappings remain restricted.
- Color edits support current/all/specified pages in one undo transaction. Existing selection defaults to region scope. Region edits isolate original/outgoing content with complementary vector clips: no full-page rasterization. Text crossing a clip can appear twice to extractors that ignore clipping, and the resulting page content becomes Form groups for object selection. This limitation is shown before applying the operation. Patterns/gradients/ICC/spot paints, annotations and animation frames retain their existing colors.
- Annotation time is stored in PDF CreationDate/M fields. Older annotations with no time are labelled accordingly. Sorting uses creation time (modification time as fallback), then page/position; positions sort by page, Y then X. The visibility switch does not alter export, print or save.


## 0.7 additions and precise boundaries

- PDF figure insertion copies the selected page content as a vector Form XObject; text/fonts and raster assets retain their original nature. Source links, annotations, forms and scripts are not imported. EPS/PS conversion is optional and requires an already-installed Ghostscript; no converter is bundled. PDF insertion is the dependency-free vector path.
- Shape tools draw native rectangle, ellipse, line, block arrow, triangle, diamond and star paths. Fill, outline color and width apply to painted paths; arbitrary Bézier control-point editing and recursive Form editing remain unsupported.
- Object clipboard uses a PDF payload and pastes at the original visual size and coordinates, including between open documents. Pasted content is a Form group; move/scale it as a group. Internal text-editor clipboard also carries character styling and usable embedded input fonts; arbitrary external application clipboard formats may only supply plain text/raster data.
- Page mirrors preserve native content, but currently refuse pages containing annotations, links or media because their interaction geometry would also need transformation. Rotation remains available for those pages. Page deletion has no second confirmation; it is undoable and keeps at least one page.
- Whole-document scrollbar in noncontinuous views is enabled by default and can be disabled in View. The track maps document spreads and scrolling within a tall spread. Ctrl+wheel preserves the mouse location unless a page edge/scroll boundary prevents it.
- Toolbar drag is restricted to pointer/hand, the four module buttons, and the optional-tool group respectively. Fixed page/zoom controls stay together. Overflow arrows and edge scrolling expose hidden tools; drag previews clear on release/cancel.
- 100% uses physical monitor metadata and rendering uses native device pixels. Incorrect EDID/remote-desktop DPI can still require manually changing the zoom; no physical-ruler calibration is claimed.

## 0.8 superseding page-tool behavior

The whole-document single-page scrollbar option is removed; Quick overview handles document-wide navigation and follows the reader's columns. Automatic preview scale is 10% for <=20 pages and 5% above 20.

Destructive crop removes outside content using page-local redaction and cleaned resource transplantation, preserving the main PDF catalog and unrelated pages. Crossing text/path objects are removed entirely; outside image pixels are cleared. Outside/crossing annotations and links are removed. Interactive pages with Widget/RichMedia/Movie/Screen/3D are refused before committing; use keep-outside mode. This is not a global confidential-data scrub: other pages, attachments and local undo/recovery copies remain. See [0.8 usage](USABILITY-0.8.md).


## 0.9 authored text boxes / 新建文本框

New AsterPDF text boxes use native PDF text and embedded fonts, with explicit coordinate isolation. They support mixed Latin/CJK input, wrapping by width and rotation, with editable box metadata kept in marked content. Existing arbitrary text blocks retain the conservative local-edit path; this does not enable Word-like paragraph layout. Complex shaping and vertical writing remain unsupported.

新建文本框支持自动扩展、边框调宽换行、旋转及保存后再次编辑；不会转换成图片。PDF 中文本框可读取性不依赖本软件的私有状态。框的二次编辑参数使用标记内容元数据；第三方软件若移除该元数据，仍可显示文字，但不保证继续作为同一个可重排文本框识别。


## 1.0 recoloring and search

Solid gray/RGB/CMYK operators and common decodable raster XObjects can be recolored. Multiple pairs match original values once; raster pixels use an RGB tolerance. Raster dimensions and alpha masks are retained, but changed images are stored as lossless RGB rather than retaining original JPEG compression or CMYK space. Matching paper white also paints the new background. Sampling provides at most 64 representative colors sorted by estimated visible coverage for the selected scope; it does not enumerate every internal color. The exact rendered-color picker remains available. Vector shadings/patterns, annotations and animation frames are not recolored. Stencil/color-key images and unsupported content streams produce errors. Region clipping preserves vector content but can duplicate boundary text in some extractors.

Applied native text is searchable immediately and after reopening. Search refreshes after edits and supports previous/next results plus overview markers. A font/application failure retains the draft instead of presenting it as saved searchable PDF content.


## 1.0.1 palette and shape interaction

The source palette now clusters by the selected tolerance and displays at most 32 swatches (default 8%). Shape selection tests native paths/filled interiors rather than the entire bounding rectangle. New shapes return to direct selection and support a mouse rotation handle. Each newly opened overview fits its own document, regardless of a previous tab’s manually resized height.
