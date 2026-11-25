"""Reading and editing gestures through the Windows/Qt event dispatch path."""
import pymupdf as fitz
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from test_practical_ui import ui, point


def gesture(widget, start, end, modifiers=Qt.NoModifier):
    QTest.mousePress(widget,Qt.LeftButton,modifiers,start)
    QTest.mouseMove(widget,end,20)
    QTest.mouseRelease(widget,Qt.LeftButton,modifiers,end)


@pytest.mark.parametrize('panel',['read','objects','pages'])
def test_drag_scroll_thumb_from_above_toolbar(ui,panel):
    app,w,t,pump=ui
    t.set_chrome_option('opacity',65)
    t.set_view(1,True);t.set_zoom(2)
    if panel!='read':t.open_panel(panel)
    if panel=='pages':
        t.organizer_zoom.setValue(50)
    bar=t.document_views.currentWidget().verticalScrollBar()
    pump(lambda:bar.isVisible() and bar.maximum()>0 and not t.busy)
    bar.setValue(0);pump()
    start=QPoint(bar.width()//2,7)
    global_pos=bar.mapToGlobal(start)
    assert t.mapFromGlobal(global_pos).y()<t.reading_inset
    assert t.childAt(t.mapFromGlobal(global_pos)) is bar
    gesture(bar,start,start+QPoint(0,75))
    assert bar.value()>0


def test_move_overview_across_sidebar_and_keep_navigation(ui):
    app,w,t,pump=ui
    t.set_chrome_option('opacity',65);m=t.minimap;m.sync()
    header=QPoint(25,m.HEADER//2)
    target=QPoint(28,9)
    page=t.canvas.page
    QTest.mousePress(m,Qt.LeftButton,Qt.NoModifier,header)
    QTest.mouseMove(m,m.mapFrom(t,target+header))
    QTest.mouseRelease(m,Qt.LeftButton,Qt.NoModifier,header)
    for _ in range(3):m.sync()
    assert m.pos()==target and t.canvas.page==page
    assert t.childAt(target+header) is m
    w.resize(w.width()-90,w.height()-60);pump();m.sync()
    assert t.rect().contains(m.geometry())
    assert m.x()<t.scroll.viewport().mapTo(t,QPoint()).x()
    last=m.rects[-1].center();m.offset=last.y()-m.body().height()/2;m.clamp_offset()
    QTest.mouseClick(m,Qt.LeftButton,Qt.NoModifier,QPoint(round(last.x()),round(last.y()-m.offset+m.HEADER)))
    pump(lambda:t.canvas.page==t.info['count']-1)
    m.set_corner('bottom-right')
    assert m.free_position is None and m.y()>t.reading_inset


def test_mixed_marquee_toggle_move_copy_paste_and_reopen(ui,tmp_path):
    app,w,t,pump=ui
    t.open_panel('objects');c=t.canvas
    pump(lambda:not t.busy and c.object_page==0)
    image=next(o for o in c.objects if o.kind=='image')
    label=next(o for o in c.objects if o.text=='Signal amplitude')
    axis=next(o for o in c.objects if o.kind=='vector')
    # A narrow right-to-left marquee touches the heatmap without enclosing it.
    gesture(c,point(t,(555,585,555,585)),point(t,(520,575,520,575)))
    assert c.selected==[image.id]
    pos=point(t,label.bbox)
    QTest.mouseClick(c,Qt.LeftButton,Qt.ControlModifier,pos)
    assert set(c.selected)=={label.id,image.id}
    QTest.mouseClick(c,Qt.LeftButton,Qt.ControlModifier,pos)
    assert c.selected==[image.id]
    # Extend the selection with an enclosed label, then add a vector by click.
    region=c.page_rect(0,label.bbox).toAlignedRect().adjusted(-6,-6,6,6)
    gesture(c,region.topLeft(),region.bottomRight(),Qt.ControlModifier)
    QTest.mouseClick(c,Qt.LeftButton,Qt.ControlModifier,point(t,axis.bbox))
    ids={label.id,axis.id,image.id}
    assert set(c.selected)==ids
    original={o.id:o.bbox for o in t.selected_objects()}
    with fitz.open(t.document.path) as before:
        source_text=before[0].search_for(label.text)[0]
    delta=QPoint(12,9)
    dx,dy=delta.x()/c.scale,delta.y()/c.scale
    gesture(c,pos,pos+delta)
    pump(lambda:not t.busy and bool(c.objects) and t.document.dirty)
    assert set(c.selected)==ids
    for obj in t.selected_objects():
        assert obj.bbox[0]-original[obj.id][0]==pytest.approx(dx,abs=.1)
        assert obj.bbox[1]-original[obj.id][1]==pytest.approx(dy,abs=.1)
    mime='application/x-asterpdf-objects'
    app.clipboard().clear()
    QTest.keyClick(c,Qt.Key_C,Qt.ControlModifier)
    pump(lambda:app.clipboard().mimeData() and app.clipboard().mimeData().hasFormat(mime))
    with fitz.open(stream=bytes(app.clipboard().mimeData().data(mime)),filetype='pdf') as copied:
        assert copied[0].get_text().strip()==label.text
        assert len(copied[0].get_drawings())==1 and len(copied[0].get_image_info())==1
    t.goto(2);pump(lambda:not t.busy and c.object_page==2)
    QTest.keyClick(c,Qt.Key_V,Qt.ControlModifier)
    pump(lambda:not t.busy and not t.queue.jobs)
    filename=tmp_path/'group.pdf';t.document.save(filename)
    with fitz.open(filename) as reopened:
        dest=reopened[2]
        for page in [reopened[0],dest]:
            assert tuple(page.search_for(label.text)[0])==pytest.approx(tuple(source_text+(dx,dy,dx,dy)),abs=.1)
        assert len(dest.get_drawings())==1 and len(dest.get_image_info())==1
    QTest.keyClick(c,Qt.Key_Z,Qt.ControlModifier)
    pump(lambda:not t.busy and not t.queue.jobs)
    with fitz.open(t.document.path) as undone:assert not undone[2].search_for(label.text)


def test_first_marquee_on_adjacent_visible_page(ui):
    app,w,t,pump=ui
    t.open_panel('objects');t.set_view(2,True);t.fit(False)
    c=t.canvas;pump(lambda:not t.busy and c.object_page==0 and not t.queue.jobs)
    box=c.page_rect(1,(32,30,570,82)).toAlignedRect()
    assert c.locate(box.topLeft())[0]==1
    gesture(c,box.topLeft(),box.bottomRight())
    pump(lambda:c.object_page==1 and not t.busy)
    assert [o.text for o in t.selected_objects()]==['Motion belongs in the document']
