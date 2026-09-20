# Architecture

## Choices

- **PySide6 / Qt Widgets:** desktop UI and Qt Multimedia on all targets. No bundled Chromium or web UI server. Its shared-library directory deployment allows replacement of Qt libraries.
- **PyMuPDF / MuPDF:** render, search, text geometry, isolated object measurement and standard annotation authoring. Used under AGPL, so AsterPDF is AGPL-3.0-only.
- **pikepdf / qpdf:** authoritative PDF document graph, page-tree manipulation, foreign resource import, native image extraction and save. Existing catalog data remains under pikepdf ownership.
- **Python:** low build-system overhead for an initial maintainable desktop implementation. This favors a reliable functional first version over the minimum possible executable size. Runtime bundles include Qt and PDF engines; “lightweight” does not mean a tiny download.

## Modules

| Module | Responsibility |
| --- | --- |
| `app.py` | Window, tabs, menus, settings, recent files, recovery, explicit GitHub check |
| `tab.py` | Document tools, dialogs, navigation, workflow coordination |
| `canvas.py` | Virtual page canvas, visible-page rendering cache, selection and media placement |
| `jobs.py` | Background work with a serialized engine lock, progress/cancellation |
| `core.py` | Disk revisions, transaction commit, saving, PDF pages, annotations and exports |
| `text_editing.py` / `text_patch.py` | Rich drafts, canonical per-character change detection, original-glyph-preserving local commits |
| `annotation_style.py` | Standard annotation appearance details: independent arrowhead size and FreeText borders |
| `objects.py` | Balanced lexical byte ranges, isolated bounds, direct content mutation |
| `media.py` | Static animate adapter, filespec discovery, asset validation/extraction |
| `player.py` | Frame timer/cache and native Qt video/audio controls |
| `fonts.py` | Installed font table reconstruction through Qt; embedding restrictions and explicit Unicode maps |
| `release.py` | Repository configuration and stable version comparison |
| `i18n.py` | Explicit English/Chinese label catalog |

## Mutation flow

1. Open source into a session snapshot; opening does not rewrite the source.
2. Read current snapshot into pikepdf. Apply one command to that private graph.
3. Write a new revision, reopen with MuPDF to confirm nonempty PDF structure.
4. Commit the revision pointer and recovery manifest. An exception before commit leaves the old pointer unchanged.
5. Invalidate revision-sensitive geometry and render caches; retain the prior page pixels until replacement rendering arrives. Automatically inspect editable objects again; media widget references are refreshed without discarding prepared animation data for ordinary content/annotation edits.
6. On Save, copy to a temporary sibling file, flush/fsync, parse-check and replace destination atomically.

MuPDF annotation operations are performed on a separate scratch document. Only explicitly edited annotation objects (including a selected replacement group) are imported back; unselected annotations retain their original objects. Batch styling creates one recovery/undo revision. Added text/images import the changed page resources/content, while the original document catalog and page annotations stay authoritative. Unknown vendor dictionary preservation and embedded stream checks are covered by tests.

Object editing uses a small balanced PDF lexer to record raw byte ranges. pikepdf parsing only inspects operands. The editor keeps untouched source bytes; it does not round-trip the whole page through a lossy serializer. A scratch MuPDF page suppresses other painting operators to measure each candidate. Content/state patterns outside this conservative model are refused or documented as unsupported.

## Concurrency and limits

All MuPDF work runs through one background queue and lock because the library must not execute concurrently in threads. Reading and animation rendering return owned QImage buffers without PNG encode/decode; QPixmap creation remains on the GUI thread. Page tiles have a 64 MiB budget and animation frames a 32 MiB budget. Persistent renderers reuse page display lists or the animation PDF. Inactive/closed tabs cancel jobs and release caches; retired jobs disconnect callbacks. Engine store resources are periodically trimmed. Batch cancellation is checked between pages, object inspection between candidates.

The queue is designed for a desktop first release, not a distributed job system. PDF parsers and decoders run in-process; there is no operating-system sandbox around native libraries. PDFs do not receive a JavaScript interpreter or filesystem API.

## Upstream technical references

- [PyMuPDF page and annotation API](https://pymupdf.readthedocs.io/en/latest/page.html)
- [PyMuPDF object geometry](https://pymupdf.readthedocs.io/en/latest/functions.html)
- [pikepdf content stream guidance](https://pikepdf.readthedocs.io/en/latest/topics/content_streams.html)
- [animate package and source](https://ctan.org/pkg/animate)
- [Qt Multimedia](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/index.html)

These references informed architecture. Compatibility claims are based on tests documented in VALIDATION.md, not on capability descriptions alone.

## Direct manipulation and text

Canvas view state separates column count, continuous scrolling and the current page. Layout suppresses scroll-driven current-page updates; single-page updates never infer a page from empty rectangles. Window key routing excludes text input controls. Character selection uses raw text character boxes and caret boundaries rather than line/word rectangle intersection.

The inline editor commits through the same transaction path. Failed font/glyph operations retain the draft. Text input embeds tables from an installed QRawFont, checks embedding flags and glyph presence, and builds a ToUnicode map for the typed characters (including space aliases). New PDF text replaces the selected show operators. Other byte ranges remain intact; style state from the original block is retained for subsequent content. Numeric transforms use fixed decimals because PDF numeric syntax does not permit exponent notation.

The new UI retains conservative selection granularity: top-level BT/ET blocks, painted paths and image/Form invocations. Lazy inspection across pages is a responsiveness choice, not a claim to understand every object in every PDF.


## 0.4 interaction modules

`chrome.py` manages compact optional tools, transparency/auto-hide, sidebar collapse and in-place translation. `text_editing.py` owns rich text drafts, selected-character styles and safe suspension; `text_patch.apply` retains original glyph codes and generates only new input ranges. Pure image/vector transforms return updated byte offsets and bounds so subsequent drags do not rescan the page. `colors.py` clones shared resources before page-local color changes. `printing.py` queues one raster print page at a time through Qt PrintSupport. Native page rendering and animation quality are separate controls.


## 0.6 text drafts and view coordinates

The diff aligns text plus font-family identity, independently of color/weight/slant/size. Retained glyphs reuse original PDF resources and positioning, with explicit per-glyph style changes; new input is authored separately. AsterText marked content records editable style metadata, while ordinary PDF text/paint operators provide compatibility to other readers. Fill/stroke text traces are deduplicated for subsequent editing.

`text_preview.py` isolates the object's resources and graphics state in a short-lived private scratch PDF and uses the commit patcher to render its draft. The main PDF and recovery revisions do not change while typing. Preview results carry glyph positions, so caret hit testing and highlighting use the displayed PDF geometry, even when the original font is absent from Qt. The same single engine queue runs preview jobs; stale results are ignored.

Toolbar drag uses mouse events on actual QToolButtons, without native QDrag pixmaps or override cursors. The canvas has an initial top inset for overlay bars, while scrolling remains free to pass beneath them. Zoom percentages are separated from logical rendering scale. Annotation visibility affects the private renderer only; the authoritative annotation dictionaries are unchanged.


## 0.7 editing and desktop additions

`text_mapping.py` caches and bounds Unicode-to-glyph alignment, accounting for extraction whitespace, small caps and soft hyphens. `text_patch.py` retains a common ligature as one PDF code and uses an exact-byte append path for large unchanged text blocks. `text_editing.py` persists cancellable rich text drafts and carries local styling/font data on the clipboard.

`properties.py` owns docked image/vector/color panels. `figures.py` authors paths and imports vector PDF figures; optional EPS/PS conversion invokes a separately installed Ghostscript. `object_clipboard.py` emits local PDF selection payloads with no action/annotation catalog, pasted as native Form content at original visual coordinates.

`ui_details.py` provides the compact splitter, annotation delegate and horizontally scrollable toolbar host. `chrome.py` implements group-restricted button dragging. The 0.7 separate whole-document track was removed in 0.8; `ReaderScroll` now retains ordinary local/spread scrolling.

Recovery manifests and text drafts are written atomically with file synchronization. Per-session lock files exclude running instances. App close resumes after each asynchronous Save, activating each remaining dirty tab.

`minimap.py` provides a floating document overview using independent page coordinates, visible-only background thumbnails, an 8 MB LRU budget and monitor-DPR-aware rendering. It never runs animation or scripts in thumbnail previews.

## 0.8 page tools

`page_tools.py` implements docked scopes and Apply/Cancel operations; all property panes can scroll on short displays. `cropping.py` derives proportional rectangles in visual coordinates, authors only modified page content with MuPDF, cleans resources, then transplants into the authoritative pikepdf document in one undo transaction. Explicit page-order MIME acceptance and insertion indicators bypass Qt item-drop rejection. The minimap stores row geometry separately from page geometry for paired layouts.
