# AsterPDF 0.4.0 validation / 实测记录

Date: **2026-09-16**. Host: **Windows 11 x64 build 26200**, native Qt, Python 3.12.10, PySide6 6.10.2, PyMuPDF 1.27.1, pikepdf 10.3.0.

## Practical workflow tests

The full suite passed **32 tests in 208.75 seconds**. After the final text/resource/control refinements, **10 affected tests passed in 50.88 seconds**, including a new overlapping animate-control/replay/quality test. The final vector endpoint test passed in 2.32 seconds; reading/presentation and animation-control tests passed again in 5.61 seconds after presentation layout restoration was fixed. There are **33 distinct tests** in the delivered suite.

Coverage emphasizes everyday use:

- Four reading views, wheel/keyboard navigation, presentation and Escape; character-range selection and standard annotations.
- Native-pixel tiles, physical image dimensions, device-ratio invalidation and bounded caches.
- Language changes preserve the actual tab/editor objects, draft text and scroll position; 22 tabs remain reachable through the dropdown without reorder.
- No-op missing-font editing preserves bytes; selected-character size/italic changes save/reopen correctly; local fallback input, Unicode and multi-line text work.
- Failed-font drafts can undo, cancel and switch modules. Saving commits active edits before writing.
- Repeated mouse image drags retain selection; repeated move/resize/delete preserves true PDF objects and saves correct geometry.
- Vector endpoint edits remain vector commands; multi-page preview drop reorder and PDF insertion persist in the correct order.
- Page color inversion changes the selected page while preserving another page and searchable text.
- Qt PrintSupport outputs a valid three-page PDF; physical printers remain untested.
- Existing original-image list/multi-select extraction, merge queue, author/solid-arrow styling, persistent export DPI, save/reopen and media preservation continue to pass.

## Actual Windows bundle

The final GUI executable is tested directly with the private research PDF and the MP4 fixture. The diagnostic requires actual base-page tiles plus animation/decoder output, verifies keyboard navigation and presentation exit, performs genuine font-backed text replacement and save/reopen, and prints/reopens a three-page PDF. The executable exited successfully in **18.14 seconds**, including startup, both playback checks and printing. The research sample presented **45 animation frames** with **6 cached base-page tiles**; MP4 produced **65 decoded video frames**, reaching 2647 ms. Navigation, text save/reopen and three-page print/reopen passed with no player errors. See [the frozen report](evidence/windows-0.4.json).

The Windows bundle test launches with a hidden-start flag, which can suppress native paint events. The diagnostic now explicitly asks Qt to paint the real viewport and requires completed base-page tiles, preventing animation decoding alone from counting as reading success. Visible page tiles also have priority over animation jobs. Normal visible rendering was separately tested on three displays. The report field `rendered_pages` is a historical name for the maximum **cached tile count**, not a unique-page count in 0.4.

## High DPI and actual multiple displays

Moved the native application between **three attached displays** and verified canvas/tile device pixel ratios:

| Display | Available logical size | Screen DPR | Canvas and cache DPR |
| --- | --- | --- | --- |
| Laptop 4K | 1536 × 816 | 2.5 | 2.5 |
| External landscape | 2560 × 1392 | 1.0 | 1.0 |
| External portrait | 1440 × 2512 | 1.0 | 1.0 |

The old renderer capped DPR at 1.5. The new reader renders native-pixel tiles; a 100 × 80 point region at scale 2.5 produced **250 × 200 pixels**, with sampled pixels matching a direct MuPDF render. This verifies resolution handling, not identical antialiasing to Acrobat or every GPU/monitor combination.

[Cross-screen and playback evidence](evidence/screens-playback-0.4.json).

## Animation source and timing

Used the private `E:\tempdata\testpage.pdf`: **89,588,667 bytes**, 3 pages, 180 icon animation frames on page 2, **18 declared FPS**. All 180 frames rendered to distinct hashes at the inspection resolution; no adjacent pair was identical. The file itself therefore does not explain the prior stalls as repeated identical frames.

Measured in Auto playback quality (1280-pixel animation width, ordinary reading still native DPI):

| Direction / speed | Duration | Frame presentations | Timeline advancement | Expected advancement |
| --- | --- | --- | --- | --- |
| Forward 0.5× | 4.000 s | 36 | 35 | 36 |
| Forward 1× | 4.000 s | 72 | 71 | 72 |
| Forward 2× | 4.031 s | 45 | 141 | 145 |
| Reverse 1× | 10.000 s | 180 | 179 | 180 |

Presentations can include the initial/quality-change frame. Timeline advancement measures sequence positions, and differs when late frames are skipped. **2× was not rendered at 36 distinct frames per second**: time progression stayed near the requested speed, with dropped frames. Native-pixel playback can also be slower on complex pages.

The real PDF stacks Pause, Play and PlayPause widgets at the same location. Hit testing now prefers the combined recognized control, rather than hitting a hidden Pause widget first. Its original button was clicked with Qt mouse input in presentation; frames advanced, leaving the page paused playback, and Escape exited. A separate final run repeated reading and presentation advancement with original controls.

Also clicked the original PDF Plus, Minus, Reset, forward and reverse/pause controls: speed changed to 1.25×, returned to 1×, reset, reversed for seven observed frames and paused. [Original button record](evidence/original-buttons-0.4.json).

[Timing and screen record](evidence/screens-playback-0.4.json) · [Final original-button presentation run](evidence/presentation-0.4.json).

## Memory and old-version comparison

Same Windows host, native Qt event processing including deferred deletion, same ten documents (private sample plus nine copies of the public demo), five seconds forward and reverse, then close all. Values are process working set, not Python-only allocations. These are individual runs, not statistically controlled universal performance claims.

| Measurement | 0.3.0 | 0.4.0 |
| --- | ---: | ---: |
| Startup | 188 MB | 190 MB |
| Ten documents open | 332 MB | 332 MB |
| After playback | 551 MB | 477 MB |
| After all documents closed | **534 MB** | **240 MB** |
| Five-second forward presentations | 60 | 90 |
| Five-second reverse presentations | 67 | 89 |

The 0.4 default animation Auto quality uses a different resolution policy from the old player; this is a comparison of delivered defaults, not equal-resolution engine benchmarking. Reading quality is higher on DPR 2.5. Both versions had zero live native document widgets after close, but retained Python wrapper references; the new version clears their heavy resources. Qt/fonts/native allocators can retain memory beyond startup.

A separate three-cycle open/play/image-edit/undo/redo/close exercise ended at **242, 259 and 273 MB** after each close. This remains above startup and shows residual growth; this release does **not** claim all memory retention is eliminated or a fixed process-memory limit. Reading cache is budgeted at 64 MiB, animation cache at 32 MiB, while parser/font/decoder memory is separate.

[Baseline](evidence/benchmark-baseline-0.3.json) · [0.4 comparison](evidence/benchmark-0.4.json) · [Repeated lifecycle run](evidence/memory-repeat-0.4.json).

## Save and dynamic-content preservation

Added an annotation, rotated another page and saved a separate PDF. Compared **all 180 frame-stream hashes**, unchanged; original input hash unchanged. Four sampled frames remained distinct. Seven sequences from the official animate manual had distinct rendered endpoints; this does not validate all animate options.

[Preservation record](evidence/real-pdf-0.4.json). Input SHA-256: `add246f1c7b278c3cbe499c3e4ec5d4009dbf2275f239ab7c95a7d29796c159d`.

Private PDFs, private page screenshots and the upstream manual are not redistributed.

## Visual review

Inspected native screenshots of compact reading chrome, original-glyph edit entry, Home, page organization, image list, solid arrows, English UI, dark UI and toolbar customization. Explicit checkbox styling corrected the dark unchecked boxes found in the initial light-theme review. Distributed screenshots show only public project fixtures.

[Reader](evidence/reader-zh-0.4.png) · [Text properties](evidence/inline-unchanged-0.4.png) · [Home](evidence/home-zh-0.4.png) · [Page organization](evidence/organizer-zh-0.4.png) · [Customization](evidence/customize-zh-0.4.png) · [English](evidence/objects-en-0.4.png).

## Unverified and known limits

- macOS/Linux runtime, native packaging startup and codecs: configurations supplied, **not actually verified**.
- Physical printers, duplex behavior and printer drivers: not verified. Print-to-PDF is raster output; PDF extraction preserves vectors.
- Acrobat itself was not launched. Native/multiple-engine and save/reopen evidence is not an Acrobat application test.
- Unpublished repository/update endpoint remains unset. Font availability, exact version matches, all codecs, complex shaping and arbitrary PDF structures are not promised.
- Straight vector endpoints are supported; general Bézier handles and semantic compound-arrow reconstruction are not.
- Color edits exclude gradients/patterns/special color paint, annotations and animation frames. Raster stencil/color-key masks are rejected when image recoloring is requested.
- OCG animation, arbitrary JavaScript/3D, nested Form text editing and paragraph reflow remain unsupported.

[Compatibility](COMPATIBILITY.md) · [Feedback mapping](USABILITY-0.4.md) · [Historical 0.3 validation](VALIDATION-0.3.md).
