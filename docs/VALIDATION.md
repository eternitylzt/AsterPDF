# AsterPDF 1.3.8 verification / 验证

Focused Windows regression: **27 passed, 2 skipped in 53.70 seconds**. The skipped checks execute POSIX shell scripts and are included in macOS/Linux CI.

- Real subprocess tests launch the desktop through a registered-style command. The caller exits while the GUI remains open; relative paths, Chinese names and spaces are preserved.
- A second command adds a tab in the same process, restores a minimized window and preserves the first tab's unsaved annotation. Reopening the same file does not duplicate its tab.
- Simultaneous cold starts produce one window with both files. Per-profile test sessions remain isolated from a user's running application.
- Installer checks cover sudo refusal before configuration writes, same-path legacy launcher migration, custom-command preservation and existing idempotence/conflict/rollback behavior.
- Previous PDF refresh, fullscreen/presentation, toolbar stability and Markdown reading/export checks remain passing. The theme no longer specifies missing Windows font families.

The release CI repeats these workflows on macOS and Linux alongside the existing PDF editing/preservation suite. Local IPC and shell behavior are tested on those OS runners; macOS privacy dialogs, real Terminal permissions and physical desktop activation still need end-user verification. macOS can reject a script before it executes; the application cannot override that system permission. The in-app installer avoids depending on Terminal access to the downloaded installer folder.

No new runtime dependency or browser engine was added.

The frozen Windows bundle also passed the real command workflow: command invocations returned in 0.610 / 0.297 / 0.328 seconds while one GUI process retained two tabs. Duplicate-file reuse and a clean normal window close were checked. [Packaged report](evidence/cli-1.3.8.json). Release CI runs an additional frozen-bundle command check on all three platforms before packaging.
