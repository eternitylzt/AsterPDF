# AsterPDF guide

## Reading

Use the pointer to select text and images, or the hand to pan. Left/right turns pages; up/down scrolls. In single page mode the wheel turns pages at the edge. F5 enters presentation; Escape exits. The sidebar contains Pages, Outline, Bookmarks, Search, Annotations and Images.

## Object editing and fonts

Enter Object editing and select an object directly. Double-click text to type, drag to move, drag the lower-right handle to resize, or press Delete. Ctrl+Enter applies; Escape cancels. Leaving an unchanged editor does not rewrite text: the PDF's original glyphs remain visible. Deleting and moving never require the original font.

Input automatically matches installed fonts and identifies substitutions. Find fonts searches open fonts by name and also imports local font files. Downloads require internet access and are cached in the app data directory under fonts for later offline reuse. Source records and licenses are retained. Fonts are registered privately with the app, never installed system-wide. Similar fonts can change layout; even the same family name may identify a different version. Commercial and unusual fonts may be unavailable. Missing glyphs or embedding restrictions produce an error while retaining the draft.

## Annotations

Drag across partial text to highlight, underline or strike out. Notes appear in the annotation sidebar. Color, Line width and Opacity set appearance. Style controls the author, text font/size and arrow ending. Closed arrows have solid standard fill.

## Extraction and export

Entering Export selects the region tool; drag to select; clicking elsewhere clears the region. Export settings remembers DPI, pixel width, format and JPG quality, including high-resolution clipboard copies. Embedded image extraction opens a list linked to page highlights. Use the list for overlapping layers; Ctrl/Shift selects several images. Extraction preserves original channels without compositing soft masks; it does not use a screenshot. Empty pages show an explicit no-images message.

## Merge and save

Home creates a new merge queue or adds all open PDFs, including current unsaved edits. Add more files, reorder or remove entries, then save a new PDF. Page content is copied; document-level outlines, scripts and form trees are not imported. Relevant documents trigger a pre-merge notice.

Ctrl+S saves, Ctrl+Shift+S saves as, Ctrl+Z undoes and Ctrl+Shift+Z redoes. Modified tabs have an asterisk. Recovery copies never overwrite originals.

## Compatibility limits

Recognized LaTeX animate widget/icon frame sequences and suitable embedded MP4/audio are supported, subject to codecs and platforms. PDF JavaScript is never executed. OCG animation, Flash, 3D and external media are unsupported. Nested vector groups can be transformed as a whole; straight-path endpoints can be dragged, while Bézier handles and complex paragraph reflow are excluded. Page cropping changes visibility; content outside the crop can remain recoverable.

Windows is the tested platform. macOS and Linux have build configurations but have not been validated on real hosts. See the included docs directory for detailed scope, licenses and validation records.


## 0.4 controls

Right-click the toolbar to customize modules/tools, hiding, auto-hide and opacity. Collapse the sidebar with its edge arrow or configure auto-hide from its context menu. The tab dropdown lists every document. Language switching preserves the existing session. Ctrl+F opens sidebar search.

Edit → Text opens the left properties panel. Double-click a block, select characters, then change font, size, bold, italic or color. Failed drafts support undo, cancellation and suspension when switching tools. Return to Text to continue. If PDF contents change meanwhile, copy the draft and select the current text block again before applying.

Page organization provides multi-page drag/delete and PDF insertion. Color editing changes actual solid page colors; raster images are optional. Gradients, patterns, special color paints, annotations and animation frames are excluded.

Animation quality offers Auto, Native and Smooth. Auto limits playing frames to 1280 pixels wide; the pause button restores native pixels. Ordinary reading always uses display DPI. Wall-clock playback skips late frames when required.

File information and Ctrl+P printing are in File. Printing renders pages at 300 DPI with a 32 MP cap; physical printers remain untested. Use PDF extraction for vector-preserving output.


## New in 0.7

Ctrl+wheel zooms around the pointer. Toolbar overflow arrows expose hidden tools; drag buttons within their group. Image, shape and color tools use docked property panels. PDF figures retain vectors; EPS/PS requires a locally installed Ghostscript.

Copy selected PDF objects and paste in place at their original size/position; pasted content moves/scales as a group. Internal text-editor clipboard retains character styling. Marquee-select annotations from blank space and press Delete; sticky notes move and annotations preview their contents on hover.

Edit includes document revert and recovery-folder settings. Applied edits create recovery revisions; text drafts are recorded after 350 ms without input. Unsaved tabs are activated and handled sequentially when exiting. Recovery never overwrites originals automatically.

Page mirrors currently require pages without annotations, links or media. Common ligatures must be selected as a whole; complex encodings, nested Form labels and paragraph reflow remain limited.

## Quick overview

The floating top-right preview follows the visible PDF area. Click to jump or drag the blue viewport. Wheel/right-drag pans the preview; right-click changes corner/scale; drag edges to resize. Reopen from View → Quick overview. Default 10% up to 20 pages, 5% above 20; range 0.5%–20%; wide pages fit the panel.

## 0.8 page tools and Quick overview

Drag page thumbnails to the blue insertion marker. Crop/rotate and other page tools use docked scope and Apply/Cancel controls. Crop has eight handles and removes outside content by default; crossing text/path objects are removed whole. Keep-outside mode is available and required on pages with forms/animation/media. Quick overview follows one/two columns and defaults to 10% up to 20 pages, 5% above 20. The whole-document scrollbar override is removed.


## 0.9 preferences and text boxes

Ctrl+, opens categorized preferences, with three interface font sizes and optional Home history. Preferences synchronize open documents and retain text drafts.

Page transforms use the selected organizer item. Rotate/Flip acts immediately; Cancel reverses this tool session; leaving keeps changes. New text boxes start at caret width, expand while typing, wrap after border resizing and rotate with the circular handle or angle field. Ctrl+Enter applies; Esc cancels.

Quick overview uses automatic dimensions, a half-screen height cap and 80% opacity. Ctrl+wheel changes scale gently. Bookmark stars track the current page; right-click a bookmark to rename.


## 1.0 recoloring and search

Color sources follow the selected scope, sorted by estimated visible area and limited to 64 representatives. Use the picker, tolerance, multiple pairs and named schemes. Raster changes require the image checkbox; vector shadings, patterns, annotations and animation frames are unchanged. Region boundaries are display aids only.

Applied text is searchable. Use F3 / Shift+F3 or Previous/Next to cycle matches; overview bands locate results and its footer shows reading progress. The language entry remains Settings → 语言/Language.
