# Changelog

## 1.0.1 — 2026-09-17

- Fit each newly opened document overview independently; manual resize stays local to its tab.
- Align recent files, sizes and opening times in a three-column Home table.
- Use a 4 × 8 source-color grid, cluster similar colors with the tolerance, and default to 8%.
- Return to direct selection after drawing; select real paths, marquee, move, resize and rotate shapes with a mouse handle.

## 1.0.0 — 2026-09-17

- Faster dense-page object discovery without repeated scratch-stream compression.
- Scope-aware palettes, raster/region recoloring, simultaneous replacement pairs and reusable schemes.
- Search applied text, cycle matches and locate them in Quick overview.
- Sequential per-document close/save prompts and synchronized animation/tool preferences.
- Dark defaults, discoverable bilingual language entry, recent-file details and overview reading progress.
- Compact real-product screenshots in both README versions.

## 0.9.0 — 2026-09-17

- Immediate rotation/mirroring of the selected organizer page; Cancel reverses the tool session.
- Reliable text properties layout; native, reflowable Chinese text boxes with border resize and rotation controls.
- Arrow-key object nudging; three interface font sizes; recent files on Home.
- Central categorized preferences, synchronized controls, release toolbar defaults, resize repaint and tab alignment fixes.
- Auto-sized translucent Quick overview with gentle Ctrl+wheel scaling.
- Filled bookmark indicators, rename and page/document-position metadata.
- Concise switchable Chinese/English GitHub introductions and practical Windows verification.

## 0.8.0 — 2026-09-17

- Fix rejected organizer drops with explicit insertion targets, indicators and multi-page moves.
- Dock page operation settings, adjustable crop handles and transactional destructive/retained-content crop.
- Rename Quick overview, follow two-page layout, automatically choose 5% above 20 pages and 10% otherwise.
- Remove whole-document scrollbar override in noncontinuous views.

## 0.7.0 — 2026-09-17

- Fix long journal text caret/selection, whitespace/small-caps/ligature mapping; preserve original bytes on append.
- Docked image/vector/color panes, vector PDF figure insertion, native basic shapes and in-place PDF object clipboard.
- Mouse-anchored zoom, compact sidebar, grouped drag previews and toolbar overflow arrows.
- Floating document map with viewport dragging, page-position jumps, preview panning/resizing and lazy thumbnails; spacious outlines and higher-contrast scrollbars.
- Annotation metadata styling, sticky-note movement, hover, marquee/batch deletion and FreeText resize cursors.
- Whole-document single-page scrollbar, persistent rotation selection, content-page mirrors and document revert.
- Sequential unsaved-tab closing, configurable crash snapshots and debounced text-draft recovery.

## 0.6.0 — 2026-09-16

- Drag live toolbar icons; reserve the initial reading area below translucent chrome.
- Preserve source font/glyph resources for style changes; fix excessive synthetic bold, glyph/caret alignment and repeated editing. Isolated PDF draft previews and explicit clipboard controls.
- Physical monitor-size zoom from 1.5625% to 6400%; centered single/two-page non-scrolling layouts.
- Current/all/range/region color editing; named single-page/region image export.
- Double-click FreeText creation, auto-growth, drag resizing/reflow, annotation timestamps/document-wide sorting and view-only visibility.

## 0.5.0 — 2026-09-16

- Character-range editing retains original glyph resources and styling; no-op copy/cancel, partial deletion, inline text boxes and input-only fallback.
- Independent image placement, clipboard copy/paste, aspect/free resize preview and localized page refresh.
- Toggleable modules, active tool feedback, editable annotation styles, independent arrowhead size and optional text borders.
- Transparent toolbar/subbar overlays, customization drag ordering, clearer light icons, navigation context menu and link cursor.
- Preserve monitor on minimize/restore; expanded practical editing/reopen and real-PDF preservation checks.


## 0.4.0 — 2026-09-16

- Native-DPI tiled reading, cross-monitor invalidation and byte-bounded display caches.
- Compact configurable modules/tools, tab overflow menu, sidebar collapse, in-place language switching, unified Home.
- Selected-text font/size/bold/italic/color panel, local font fallback and safe draft undo/cancel/suspension.
- Faster repeated image transforms, straight vector endpoint editing and page-local solid color replacement/inversion.
- Page organization grid with multi-page reorder/delete and PDF insertion.
- Persistent raw-frame animation rendering, wall-clock speed/reverse pacing, playback quality options and resource cleanup.
- Local file information, native printing, expanded practical save/reopen and playback validation.


## 0.3.0 — 2026-09-16

- Preserve original glyphs and PDF bytes when entering and leaving text editing without changes; keep deletion/movement independent of fonts.
- Match local substitutes; add opt-in open-font search, OFL downloads, private persistent cache and local font import.
- Make Home permanent; merge into a new PDF using an ordered queue of files or current open-document snapshots.
- Add linked image thumbnails/page highlights, multi-selection extraction and explicit empty states.
- Remember image export DPI/width/quality/format and clear region selection when clicking elsewhere.
- Fill closed arrow heads; label line width/opacity; enlarge vector quick-tool icons and restore text navigation labels.
- Separate Chinese/English UI strings, standard Qt dialog translations and in-app help.
- Add practical tests for unchanged missing-font editors, no-font deletion/movement, merge snapshots, layered image extraction, export defaults and language switching.

## 0.2.0 — 2026-09-15

- Repair single-page wheel/arrow navigation, presentation navigation and Escape; add four page layouts and current-page thumbnail tracking.
- Introduce pointer/hand tools, undo/redo buttons, customizable quick tools and connected module/panel styling.
- Select and copy individual characters; annotate partial text ranges. Add annotation sidebar, author, font/size, visible color and arrow/dash style controls. Ignore zero-length shape clicks.
- Automatically inspect objects on entering Edit and visiting pages. Double-click text to edit in place with installed fonts; drag to move/resize, press Delete, and automatically inspect the updated page.
- Embed replacement fonts with explicit ToUnicode mappings; support local multiline horizontal text blocks and preserve other content. Keep typed drafts on failed edits; commit before page changes and Save.
- Fix scientific-notation numbers in content transforms; retain rendered pages while new revisions render.
- Crop after choosing the tool; highlight original raster image locations for click extraction. Add a reorderable merge file queue and one-PDF-per-page extraction; remove Split from the UI.
- Show `*` on modified filenames. Add author information and configured GitHub version comparison/download flow.
- Add six practical workflow tests alongside the original twelve, including native Windows input, Unicode paste, repeated object edits, save/reopen and annotation style checks.


## 0.1.0 — 2026-09-15

Initial usable desktop release: Qt reading workspace, standard annotations, page tools, native image and vector-region extraction, conservative true PDF content editing, static animate icon/widget playback and embedded media controls. Added disk revisions/recovery, Chinese/English UI, release checking, platform packaging configurations and validation fixtures.

Windows is the first verified desktop environment. macOS/Linux, OCG animation, universal CID text editing and complete Acrobat scripting/media compatibility are not claimed as tested or supported.
