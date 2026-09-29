<p align="center"><img src="assets/wordmark.svg" width="500" alt="AsterPDF"></p>

# AsterPDF

**Read · Edit · Animate · Annotate · Extract**

An offline desktop PDF workspace for research and technical documents.

**[中文](README.zh-CN.md) | English** · [Compatibility](docs/COMPATIBILITY.md) · [Build](docs/BUILDING.md) · [Verification](docs/VALIDATION.md)

<table><tr>
<td><a href="docs/evidence/overview-1.0.png"><img src="docs/evidence/overview-1.0.png" width="290" alt="Search and Quick overview"></a><br>Search & Quick overview</td>
<td><a href="docs/evidence/extract-1.0.png"><img src="docs/evidence/extract-1.0.png" width="290" alt="Extract vector figures"></a><br>Vector figure extraction</td>
<td><a href="docs/evidence/tools-1.0.png"><img src="docs/evidence/tools-1.0.png" width="290" alt="Customizable tools"></a><br>Your tools, your layout</td>
</tr></table>

## What makes it useful

- **Read animated papers.** Play recognized LaTeX `animate` icon/widget sequences and embedded video/audio inside the document, including presentation mode.
- **Markdown and video.** Read mathematical Markdown, preview HTML in your browser and export PDF/HTML; insert videos, save embedded media and arrange media layers.
- **Extract research figures.** Export high-resolution regions, extract embedded raster images at their original resolution, or save a cropped PDF that retains text and vectors.
- **Edit real PDF content.** Modify identifiable text, images and vector groups. Preserve untouched glyphs; move, resize, delete and paste objects in place across documents. Insert vector PDF figures.
- **Annotate and organize.** Standard PDF comments, character-range markup, reflowing text annotations, page drag/reorder, merge queues, extraction, rotation and adjustable cropping.
- **Fill PDF forms in place.** Standard AcroForm text, checkboxes, radio groups, choices, multi-select lists and common dates, with field highlighting, Tab navigation, saving and recovery drafts.
- **Navigate comfortably.** Tabs, search, outlines, named favorites and a floating Quick overview. Native-DPI rendering, light/dark UI, Chinese/English, customizable tools and local crash recovery.

No account. No cloud dependency. PDF processing stays on your computer.

### Reading controls

- **F11:** document-only fullscreen defaults to fit width; move to the top edge for fit/zoom/layout/exit controls. Existing media controls and Quick overview remain available. Press F11 or Esc to restore the interface. F5 remains presentation mode.
- **Markdown:** opens inside AsterPDF first, then asks whether to open a local HTML preview in the default browser. Remember Yes or No with “Do not ask again”; Preferences → Markdown offers Ask each time / Always open / Stay in AsterPDF. Save As offers HTML or PDF (A4 by default, or one long page). HTML embeds loaded images and formulas for sharing and reflects the opened Markdown snapshot; save subsequent PDF edits/annotations as PDF. In-app reading defaults to a long page with heading outlines, and edited PDFs retain their current layout.
- **Page gaps:** double-click between pages to remove the spacing, and double-click the faint divider to restore it. Hover cursors indicate collapse/expand. Also available in View → Hide / show page gaps. This changes display spacing only, not the page's own white margins or PDF content.

## 1.3.2 · Changes since 1.3.0

- **Markdown preview and export:** opens inside AsterPDF first, then offers a local HTML preview in the default browser. Remember Yes/No or change the choice in preferences. Outlines, formulas, images, tables and code copying are supported; Save As now offers HTML. No browser engine is bundled.
- **Fullscreen reading:** fit width by default, with auto-hiding fit, zoom, layout and exit controls; restores the previous zoom on exit.
- **Recent files on Home:** space for five complete entries, with scrolling in smaller windows.
- **macOS video interaction:** revised click handling and playback-state synchronization address the double-click-to-pause report; confirmation on affected users’ Macs is still needed.

[Release notes](docs/RELEASE_NOTES.md) · [Math example](examples/Markdown-math.md) · [Screenshot](docs/evidence/markdown-1.2.1.png)

## Run

[Linux installation: deb / rpm / portable](docs/LINUX.md)

**Windows x64:** extract the complete `AsterPDF-1.3.2-windows-amd64.zip`, then run `AsterPDF/AsterPDF.exe`. Keep the accompanying `_internal` folder. No Python installation is required; the executable is unsigned.

**macOS / Linux:** download the native archive from the GitHub Release. The automated build verifies packaging on each target; see the validation and compatibility documents for the features tested on real desktops.

From source (Python 3.12 recommended):

```sh
python -m venv .venv
# Activate .venv: Windows .venv\Scripts\activate; macOS/Linux source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m asterpdf examples/AsterPDF-demo.pdf
```

Dependency installation requires internet access. Optional font lookup, update checks and externally linked Markdown images also use the network.

## Start here

Open a PDF; use the pointer for text/image selection or the hand to pan. The four modules expose annotation, object editing, page organization and extraction tools only when needed. Open **Settings → Preferences** (`Ctrl+,`) for defaults. Right-click the toolbar to customize it.

Double-click an editable text block to edit selected characters. Apply with `Ctrl+Enter`; cancel with `Esc`. Choose **Insert text box** to create independent text. Drag its border to wrap or its circular handle to rotate; precise width and angle are available in the text pane. Files marked `*` contain unsaved changes.

Try the two original sample PDFs in `examples/`. [Usage](docs/USABILITY-1.0.md) · [Shortcuts and help](asterpdf/resources/HELP.en.md)

## Honest boundaries

AsterPDF is a local scientific-document editor, not a full Acrobat replacement. Text editing depends on identifiable content and reliable glyph mappings; complex shaping, arbitrary paragraph reflow and recursive editing inside every Form XObject are not supported. Unsupported edits retain the draft and explain the limitation. Original font resources remain untouched for unchanged text; new input may use an identified local substitute.

Animation support is based on tested icon/widget samples, not general Acrobat JavaScript compatibility. OCG animation, Flash and PDF 3D are unsupported; codecs vary by platform. Page imports do not transfer document-level script/form trees. Mirroring pages with annotations, links or media is refused. See the [compatibility matrix](docs/COMPATIBILITY.md).

No OCR, PDF-to-Word, AI services, certificate signing or mobile client.

## Build and release

The project includes PyInstaller configurations, platform icons, GitHub Actions, third-party licenses and public test fixtures. [Build and packaging instructions](docs/BUILDING.md).

Source and native Windows/macOS/Linux builds are published in [GitHub Releases](https://github.com/eternitylzt/AsterPDF/releases). **Help → Check GitHub updates** compares the installed version with the latest stable Release and opens its download page.

**GitHub About:** Offline scientific PDF editor with LaTeX animation, embedded video, Markdown reading and vector figure extraction.

**Author:** Zhentong Li · eternitylzt@gmail.com

**License:** [AGPL-3.0-only](LICENSE). Dependencies retain their licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Release binaries must be accompanied by matching source.

### Format and media notes

Markdown uses a lightweight parser to produce searchable PDF, including mathematics, common tables and images; it is not a full browser layout engine and adds no WebEngine. EPS/PS requires a separate Ghostscript installation. Media layer controls reorder same-page media annotations; interactive players remain above ordinary page content. Animation export contains a vector-frame PDF and timing information, not a transcoded MP4. Media support varies by reader, system and codec.
