# Changelog

## 1.3.9

Changes since 1.3.8.

- Prioritize the visible page when opening a document and limit scroll-time drawing to visible rows.
- Reuse unchanged object measurements during local edits and splice common deletions into the original text runs.
- Update individual page streams for object transforms, retaining undo and recovery. Saving writes a compact current PDF.
