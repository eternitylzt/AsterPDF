# AsterPDF 1.3.7 verification / 验证

2026-11-18. Focused Windows run: **24 passed, 1 skipped in 50.05 seconds**. The skipped test requires a POSIX shell and is included in macOS/Linux CI.

- Qt native pinch and high-resolution wheel events preserve the document point under the gesture; zero-delta start/end events do not change zoom; ordinary pixel-based scrolling stays scrolling.
- Real externally rewritten PDFs refresh in the same tab, preserving position and zoom. Tests cover unsaved-edit cancellation/discard, shortened documents, invalid-source preservation and exiting fullscreen/presentation after reload.
- Command registration preserves relative paths, spaces, Chinese application/file names and the caller's working directory. Tests cover idempotence, conflicting commands and rollback on a failed profile write.
- Existing toolbar stability, fullscreen and Markdown reading/export workflows are included in the focused run.

The release workflow runs the broader existing PDF editing/preservation, forms and reading suites on Windows/macOS and the Linux glibc 2.28 build before publishing. Workflow logs are the record of those platform results. Physical trackpad feel and physical macOS/Linux desktop interaction are **not** claimed as tested. No browser engine or additional runtime dependency was added.

The frozen Windows 1.3.7 executable passed its desktop diagnostic in 16.33 seconds: page navigation, presentation exit, 36 animation frames, PDF printing and local text edit/save/reopen. The captured native window was inspected, including the new Reload button. This fixture contains no video, so this run makes no new video-playback claim. [Packaged report](evidence/desktop-1.3.7.json).
