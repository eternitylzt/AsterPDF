"""Document overview: actual mouse jumps, viewport drag and preview-only pan."""
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtTest import QTest
from test_practical_ui import ui


def test_map_jump_drag_pan_resize_and_hide(ui):
    app,w,t,pump=ui;m=t.minimap
    t.set_view(1,True);t.set_zoom(2);m.percent=20;m.resize(160,200);m.sync()
    pump(lambda:bool(m.cache));assert m.isVisible() and len(m.rects)==t.info['count']
    target=m.rects[-1].center();m.offset=target.y()-m.body().height()/2;m.clamp_offset()
    pos=QPoint(round(target.x()),round(target.y()-m.offset+m.HEADER))
    QTest.mouseClick(m,Qt.LeftButton,Qt.NoModifier,pos);pump();assert t.canvas.page==t.info['count']-1
    m.sync();marker=m.markers[-1];pos=QPoint(round(marker.center().x()),round(marker.center().y()-m.offset+m.HEADER))
    old=t.scroll.verticalScrollBar().value()
    QTest.mousePress(m,Qt.LeftButton,Qt.NoModifier,pos);QTest.mouseMove(m,pos-QPoint(0,12),20);QTest.mouseRelease(m,Qt.LeftButton,Qt.NoModifier,pos-QPoint(0,12))
    assert t.scroll.verticalScrollBar().value()<old
    before=t.scroll.verticalScrollBar().value();offset=m.offset
    QTest.mousePress(m,Qt.RightButton,Qt.NoModifier,QPoint(30,85));QTest.mouseMove(m,QPoint(30,125),20);QTest.mouseRelease(m,Qt.RightButton,Qt.NoModifier,QPoint(30,125))
    assert m.offset<offset and t.scroll.verticalScrollBar().value()==before
    m.set_corner('top-left');m.sync();assert m.x()==8 and m.y()>=getattr(t,'reading_inset',0)
    old=m.size();pos=QPoint(m.width()-2,m.height()-2)
    QTest.mousePress(m,Qt.LeftButton,Qt.NoModifier,pos);QTest.mouseMove(m,pos+QPoint(24,30),20);QTest.mouseRelease(m,Qt.LeftButton,Qt.NoModifier,pos+QPoint(24,30))
    assert m.width()>old.width() and m.height()>old.height()
    m.toggle();assert not m.isVisible();m.toggle();assert m.isVisible()
    w.toggle_presentation();pump();assert not m.isVisible();w.toggle_presentation();pump();m.sync();assert m.isVisible()
    assert m.cache_bytes<=8*1024*1024


def test_map_noncontinuous_zoom_and_revised_preview(ui):
    app,w,t,pump=ui;m=t.minimap
    for columns in (1,2):
        t.set_view(columns,False);t.set_zoom(2);m.sync();m.seek(m.rects[-1].center());pump()
        assert not t.canvas.rects[-1].isEmpty()
        assert t.scroll.verticalScrollBar().value()>0
    t.document.add_annotation(0,'note',[(30,30),(30,30)],text='Map revision')
    old=m.generation;m.sync();assert m.generation>old
    m.percent=.5;m.sync();pump(lambda:not m.pending);assert len(m.rects)==t.info['count']
    assert all(not r.isEmpty() for r in m.rects)
