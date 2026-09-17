# Contributing

Use Python 3.12 and install `.[dev]`. Run `python -m pytest -q` for backend workflows. For UI changes, open both original example PDFs in a real desktop session and verify reading, selection, editing/save/reopen and media controls.

Keep preservation changes narrow: never replace real object editing with rasterization or masking; never advertise a multimedia format based only on an engine API. Add a small reproducer for a new document structure and record the platform/codec actually tested. Avoid committing personal PDFs, document paths, settings or recovery snapshots.

Please retain AGPL-3.0-only licensing and third-party notices. No contributor license agreement is required by this project.
