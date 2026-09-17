"""Small real Qt workflow test; use QT_QPA_PLATFORM=offscreen on headless CI."""
import os
if os.name!='nt' and not os.environ.get('DISPLAY'):os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
from PySide6.QtWidgets import QApplication, QMessageBox
from asterpdf.app import Window
from asterpdf.tab import DocumentTab


def test_desktop_search_language_theme_and_animation(document,tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    window=Window(tmp_path/'ui');window.show()
    # Use a private registry/INI scope so tests don't inspect or change user settings.
    from PySide6.QtCore import QSettings
    window.settings=QSettings(str(tmp_path/'settings.ini'),QSettings.IniFormat)
    errors=[];monkeypatch.setattr(QMessageBox,'warning',lambda *a:errors.append(str(a[-1])))
    tab=DocumentTab(window,document,document.info());window.tabs.addTab(tab,'test');window.tabs.setCurrentWidget(tab)
    def until(predicate,timeout=15):
        started=time.monotonic()
        while not predicate():
            app.processEvents();time.sleep(.01)
            if time.monotonic()-started>timeout:raise AssertionError('Qt workflow timeout')
    until(lambda:len(tab.players)==1)
    tab.search_input.setText('Signal amplitude');tab.search();until(lambda:not tab.busy)
    assert tab.results.count()==1
    tab.goto(1);tab.set_panel('media');p=next(iter(tab.players.values()));p.start()
    until(lambda:p.rendered_frames>=5)
    p.stop();assert p.index>=3
    window.set_dark(True);tab.night=True;tab.canvas.invalidate(False)
    tab.toggle_bookmark();assert 1 in tab.bookmark_pages
    window.change_language('en');until(lambda:window.current() is not None)
    assert window.current().info['count']==3
    assert not errors
    # The fixture owns document cleanup; detach sessions without deleting its files.
    for i in reversed(range(window.tabs.count())):
        widget=window.tabs.widget(i)
        if isinstance(widget,DocumentTab):widget.closed=True;widget.pause_media();window.tabs.removeTab(i)
    window.queue.pool.waitForDone(15000);window.close();app.processEvents()
