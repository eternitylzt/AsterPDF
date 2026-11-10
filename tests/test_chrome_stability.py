"""Keep the document-tab menu stationary during editing and routine relayout."""
from PySide6.QtCore import QObject,QEvent,Qt
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QApplication
from test_practical_ui import ui


class GeometryEvents(QObject):
    def __init__(self,widget):
        super().__init__(widget);self.events=[];widget.installEventFilter(self)

    def eventFilter(self,obj,event):
        if event.type() in (QEvent.Move,QEvent.Resize):self.events.append((event.type(),obj.geometry().getRect()))
        return False


def test_tab_menu_does_not_jump_when_editing_relayouts(ui):
    app,w,t,pump=ui;QTest.qWait(150);pump()
    button=w.document_switcher;events=GeometryEvents(button);before=button.geometry()
    t.open_panel('objects');pump(lambda:not w.queue.jobs);QTest.qWait(100)
    assert button.geometry()==before and not events.events
    spy=QSignalSpy(w.corner_timer.timeout)
    # Normal document/property changes send LayoutRequest to the tab widget.
    # Its own corner layout must not fight a second manual move/resize pass.
    for _ in range(20):QApplication.sendEvent(w.tabs,QEvent(QEvent.LayoutRequest))
    pump();QTest.qWait(100)
    assert button.geometry()==before and not events.events
    assert spy.count()<=3
    t.open_panel('read');pump();QTest.qWait(100)
    assert button.geometry()==before and not events.events


def test_corner_alignment_and_overflow_survive_resize_theme_and_language(ui):
    app,w,t,pump=ui
    w.settings.setValue('toolbar/tools',list(t.quick_actions)+list(t.module_actions));t.configure_chrome()
    for dark,language,width in [(False,'en',900),(True,'zh',1200)]:
        w.set_dark(dark);w.change_language(language);w.resize(width,800);QTest.qWait(200);pump()
        button=w.document_switcher
        assert button.width()==button.sizeHint().width()
        # The native tab-frame style may reserve a one-pixel border per side.
        assert abs(button.height()-button.sizeHint().height())<=2
        assert abs(button.geometry().right()-w.tabs.rect().right())<=2
        assert abs(button.y()-w.tabs.tabBar().y())<=2
        events=GeometryEvents(button)
        for _ in range(3):w.sync_tab_corner()
        QTest.qWait(100);pump();assert not events.events
    # Overflow arrows still expose tools and an unchanged reflow causes no
    # resize requests (checked/enabled changes need only normal Qt painting).
    w.resize(850,700);pump(lambda:t.navbar_host.right.isVisible())
    strip=t.navbar_host;toolbar_events=GeometryEvents(t.navbar)
    QTest.qWait(100);toolbar_events.events.clear()
    for _ in range(10):strip.reflow()
    assert not toolbar_events.events
    bar=strip.scroller.horizontalScrollBar();start=bar.value()
    QTest.mouseClick(strip.right,Qt.LeftButton);pump();assert bar.value()>start
