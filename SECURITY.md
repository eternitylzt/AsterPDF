# Security boundary

- PDFs are processed locally. Reading does not require a network service.
- PDF JavaScript is not evaluated. Animation adapters inspect known field names and bounded literal numbers, then use native timers.
- Embedded files are not launched with the operating system. Recognized media assets are extracted using generated filenames inside the session directory, checked for expected container signatures, and passed to Qt Multimedia.
- External media URLs, script launches, shell commands, 3D/Flash runtimes and playlist masquerading are not supported. Ordinary HTTP(S) document links open only after an explicit click.
- Font search/download occurs only after explicit use of Find fonts. Downloads use the official google/fonts OFL tree; the app keeps licenses, source URLs and hashes, applies per-request size limits and registers fonts privately. No PDF bytes are uploaded. Local font import does not install system fonts.
- User-selected files are accessed for open/save/export. Update checking contacts GitHub only on explicit user action; it never downloads/executes an installer.
- Save uses a new revision and an atomic replacement; recovery never silently overwrites the source.
- A crop is **not** redaction: content outside the crop can remain in the file.
- MuPDF, qpdf, image decoders and Qt/FFmpeg are native libraries in the desktop process. This release does not provide an OS-level sandbox or claim that arbitrary malicious PDFs/codecs cannot exploit native-library vulnerabilities. Keep dependencies updated and report reproducible parser/decoder failures privately to the relevant upstream project and the maintainer of your AsterPDF distribution.

For a local bug report, remove private document content and supply the minimum reproducer. This project has no telemetry endpoint or embedded support account.
