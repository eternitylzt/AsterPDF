"""Real desktop process observed by the CLI integration tests; not shipped code."""
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from asterpdf import cli
from asterpdf.app import Window
from asterpdf.launch import main

cli.application_command = lambda: [sys.executable, str(Path(__file__).resolve())]
original_init = Window.__init__


def observed_init(self, data_dir=None):
    original_init(self, data_dir)
    self.settings.setValue('window/confirm_close', False)
    self.settings.setValue('markdown/browser_mode', 'never')
    profile = Path(data_dir)
    report = profile / f'probe-{os.getpid()}.json'
    seeded = False

    def tick():
        nonlocal seeded
        if self.opening or self.queue.jobs:
            return
        tabs = self.document_tabs()
        if tabs and not seeded:
            tabs[0].document.add_annotation(0, 'note', [(40, 50), (40, 50)], text='Unsaved CLI check')
            seeded = True
        state = {'pid': os.getpid(), 'tabs': [t.document.original for t in tabs],
                 'dirty': [t.document.dirty for t in tabs], 'minimized': self.isMinimized()}
        temporary = report.with_suffix('.tmp')
        temporary.write_text(json.dumps(state), encoding='utf-8')
        temporary.replace(report)
        if (profile / 'minimize').exists():
            (profile / 'minimize').unlink();self.showMinimized()
        if (profile / 'stop').exists():
            timer.stop()
            for tab in tabs:
                self.finish_close_tab(tab)
            self.close()

    timer = QTimer(self)
    timer.timeout.connect(tick)
    timer.start(50)
    # A failed parent test cannot leave a test GUI running indefinitely.
    QTimer.singleShot(60000, lambda: (profile / 'stop').touch())


Window.__init__ = observed_init
raise SystemExit(main())
