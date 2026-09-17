# Validation record / 实测记录

Date: **2026-09-15**. Environment: **Windows 11 x64, build 26200; Python 3.12.10; PySide6 6.10.2; PyMuPDF 1.27.1; pikepdf 10.3.0**. This record separates implementation, executed checks and unverified claims.

## Automated workflows

`python -m pytest -q`: **12 passed** in approximately 8–10 seconds on this machine.

- Page-range validation, overlapping-range deduplication and invalid-range refusal.
- Existing text changed from `Signal amplitude` to `Photon flux`; old text disappears from extraction, new text is searchable, surrounding text remains. Undo restores prior bytes; redo, save and reopen succeed.
- Original image extraction at **720 × 300 pixels**, replacement with an **88 × 44** image, extraction of the replacement and deletion of that image occurrence.
- Vector object translation with measured geometry, retaining text. A clipped Form group keeps its original internal stream while its invocation moves/scales.
- Creation of all ten annotation tool types, applicable property updates, deletion, standard appearance streams and reopening. Existing animation widgets survive annotation writes.
- Rotate, crop, blank insertion, reorder, delete, page-range extraction, image export and recovery manifest state.
- Distinct animation frame renders and unchanged frame streams after editing/save.
- RichMedia embedded stream hashes unchanged after content insertion, annotations, rotation and saving.
- Unknown catalog dictionary and opaque vendor payload retained through content/annotation changes.
- Missing-glyph edit rejected transactionally; supported added text is searchable.
- Qt UI search, animation timer progression, theme switch, reading bookmark and language rebuild with an open document.

Tests are limited workflow checks, not a broad PDF conformance suite. Native decoder and real-document evidence below is separate from these tests.

## User-supplied real PDF

Input: the user-provided `testpage.pdf`, **89,588,667 bytes**, 3 pages. The file itself and its rendered research content are not included in this repository.

SHA-256: `add246f1c7b278c3cbe499c3e4ec5d4009dbf2275f239ab7c95a7d29796c159d`.

Verified:

- Page 2: animate **icon** mechanism; inherited field names; **180 frames**, declared **18 fps**; original animation rectangle and 13 button widgets detected.
- Frames **0, 30, 90, 179** independently rendered; all four rendered frame hashes differ. Opening a PDF is not used as evidence of animation success.
- Real Windows GUI playback advanced through **25 frames in a 2.4-second observed interval** in one driven run. The final packaged executable separately displayed **54 frames during a 4.06-second diagnostic including setup**, while video was also decoding.
- Frame preparation alone took approximately **0.153 seconds** in one backend run. This is not a formal benchmark or a startup guarantee.
- Added a standard rectangle annotation to page 1 and rotated page 3; saved a separate PDF. **All 180 animation appearance-stream hashes remained unchanged** and the animation sequence was rediscovered after save.
- SHA-256 of the original user file remained unchanged.

Actual frame throughput is resolution/load dependent and did not always reach the document's requested 18 fps. The current implementation waits for each render rather than presenting a frozen first frame or claiming fixed-rate playback.

## Additional real animate sample

Used the [official animate package manual](https://tug.ctan.org/macros/latex/contrib/animate/animate.pdf), retrieved from CTAN. Seven icon sequences were detected; the first and last frame of each were rendered and were visually/data-wise distinct:

| PDF page | Frames | Declared fps |
| --- | ---: | ---: |
| 1 | 4 | 8 |
| 4 | 2 | 1 |
| 18 | 9 | 4 |
| 19 | 101 | 12 |
| 21 | 29 | 12 |
| 22 | 191 | 10 |
| 24 | 26 | 25 |

The manual's `click.mp3` RichMedia asset was detected. It was not separately subjected to a complete audible listening test. The manual is not redistributed in this project.

The original `examples/AsterPDF-demo.pdf` supplies a 24-frame widget-structure fixture for repeatable automated playback checks. A fixture verifies the implemented mechanism; it does not establish compatibility with every possible `animate` producer option.

## Video and audio

Original `examples/AsterPDF-media.pdf` contains:

- H.264 High-profile MP4 video, **480 × 270**, **24 fps**, with AAC audio.
- Mono **44.1 kHz PCM WAV**.

On Windows, the Qt video sink emitted **11 valid decoded frames**, with position **333 ms**, in a dedicated media check. The WAV player's position advanced to **557 ms** with no media error. The final packaged diagnostic separately decoded **74 video frames** with position **3041 ms** and no decoder error, and exited with code **0**.

This is decoder/position evidence, not a human listening assessment or a claim covering HEVC, every H.264 profile, every container listed in the adapter, or every operating system. Unrecognized signatures, unsupported structures and Qt codec failures produce visible messages.

## Visual and desktop review

- Inspected Windows Qt reading, object-selection and animation screenshots. The user sample renders at its document location with its original button artwork.
- Independently rendered the annotated original demo through **Poppler** at 96 DPI and visually inspected highlight and arrow appearances. Poppler reported unavailable fallback fonts for unrelated Symbol/ArialUnicode names; the inspected page's text and annotations rendered correctly.
- Added `太阳耀斑 HXR 图注` using a local Microsoft YaHei font, saved and reopened; Chinese text remained searchable. That system font is not bundled with the app or example PDFs.
- Standalone Windows application was built with PyInstaller. A discovered build-environment ICU collision was fixed in the spec: Qt's OS ICU dependency is not replaced with a Poppler-distributed ICU. Qt MSVC runtime versions are aligned in the bundle.
- `--smoke-test` checks startup only. The opt-in `--verify-desktop OUTPUT_DIRECTORY` diagnostic exercises actual frame/decoder progression and writes JSON plus screenshots; it is never enabled during ordinary use.

## Not verified here

- macOS and Linux execution, packaging, clipboard, multimedia codecs and display servers.
- Windows installer compilation, code signing, Apple notarization, clean-machine install on systems without this development environment.
- Acrobat application interoperability as a separately launched reader; standards/appearance checks used MuPDF, pikepdf and Poppler.
- Every PDF font/encoding, nested graphics state, malicious file, extreme-size document, accessible tagged-PDF structure, form calculation, signature or historical multimedia mode.
- Full manual UI coverage of every export dialog/keyboard sequence, OCG playback (unsupported), all variable-rate timelines or all update-service error conditions.

## Release review checklist

For each additional platform, record the OS, architecture, Python/Qt/codec versions and actual outcome:

1. Launch the packaged app on a clean target and open both original example PDFs.
2. Read/search/select/copy; verify clipboard PNG resolution independently of zoom.
3. Play widget and real icon examples, step frames, pause, loop, and use original buttons in reading and presentation mode.
4. Confirm decoded video frame progression and audio output, then exercise an unsupported codec/structure error.
5. Modify text/image/vector content and annotations; save as, close and reopen; inspect with a second reader.
6. Apply representative page operations to a copy of a dynamic document; compare frames/assets and heed preservation warnings.
7. Test undo/redo, unsaved cancel/save/discard, forced-close recovery to a different filename, English/Chinese and night-mode export isolation.
8. Publish only the platforms actually verified, with matching source, notices and checksums.
