"""0.4 practical editing, compact chrome and native-pixel regressions."""
import time
from pathlib import Path
import pytest
import pymupdf as fitz
from PySide6.QtCore import Qt,QRectF,QEvent
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMenu,QWidget
from asterpdf import objects,colors
from asterpdf.tab import ThumbnailList
from asterpdf.rendering import PageRenderer
from asterpdf.core import Document,Unsupported
from test_practical_ui import ui,point,drag


def test_native_pixels_and_cache_budget(ui):
    app,w,t,pump=ui
    pump(lambda:not w.queue.jobs)
    dpr=t.canvas.devicePixelRatioF()
    assert t.canvas.cache and all(k[3]==round(dpr,5) for k in t.canvas.cache)
    r=PageRenderer();image,x,y=r.tile(t.document.path,0,2.5,(40,50,140,130));r.close()
    assert (image.width(),image.height())==(250,200)
    with fitz.open(t.document.path) as pdf:
        expected=pdf[0].get_pixmap(matrix=fitz.Matrix(2.5,2.5),clip=fitz.Rect(40,50,140,130),alpha=False)
        assert image.pixelColor(60,80).getRgb()[:3]==expected.pixel(60,80)
    assert t.canvas.cache_bytes<=t.canvas.cache_limit+1024**2*4
    old=t.canvas.generation;app.sendEvent(t.canvas,QEvent(QEvent.DevicePixelRatioChange));assert t.canvas.generation>old


def test_language_preserves_editor_tabs_and_layout(ui):
    app,w,t,pump=ui
    t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text=='Signal amplitude');t.start_inline(obj);pump()
    editor=t.inline_editor;editor.insertPlainText('Draft label');scroll=t.scroll.verticalScrollBar().value();revision=t.document.revision
    w.change_language('en');pump()
    assert w.current() is t and t.inline_editor is editor and editor.toPlainText()=='Draft label'
    assert t.document.revision==revision and t.scroll.verticalScrollBar().value()==scroll
    assert not w.statusBar().isVisible() and t.navbar.height()<45
    assert ' *' in w.tabs.tabText(w.tabs.indexOf(t))
    # Dropdown exposes every tab without changing its order.
    for n in range(20):w.tabs.addTab(QWidget(),f'Long technical document {n}.pdf')
    before=[w.tabs.widget(n) for n in range(w.tabs.count())];menu=QMenu();w.populate_tab_menu(menu)
    assert len(menu.actions())==22
    menu.actions()[12].trigger();assert w.tabs.currentWidget() is before[12]
    assert [w.tabs.widget(n) for n in range(w.tabs.count())]==before
    w.tabs.setCurrentWidget(t);t.cancel_inline();w.change_language('zh')


def test_selected_text_style_missing_font_and_reopen(ui,tmp_path):
    app,w,t,pump=ui;t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text=='Signal amplitude')
    for span in obj.details['spans']:span['font']='AbsentResearchFont'
    obj.details['family']='AbsentResearchFont';before=t.document.path.read_bytes()
    t.start_inline(obj);pump();assert not t.inline_dirty() and t.object_font.currentText()=='AbsentResearchFont'
    box=t.canvas.page_rect(0,obj.bbox);assert abs(t.inline_editor.x()-box.x())<6
    t.cancel_inline();assert t.document.path.read_bytes()==before
    t.start_inline(obj);editor=t.inline_editor
    cursor=editor.textCursor();cursor.setPosition(0);cursor.setPosition(6,QTextCursor.KeepAnchor);editor.setTextCursor(cursor)
    t.object_size.setValue(22);t.text_italic.setChecked(True)
    t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None)
    target=tmp_path/'styles.pdf';t.document.save(target)
    with fitz.open(target) as pdf:
        spans=[s for b in pdf[0].get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans']]
        signal=next(s for s in spans if s['text']=='Signal');remaining=next(s for s in spans if 'amplitude' in s['text'])
        assert abs(signal['size']-22)<.1 and abs(remaining['size']-obj.size)<.1
        edited=next(o for o in objects.discover(t.document,0) if o.text=='Signal amplitude')
        assert all(style[3] for _,style in edited.details['edit_styles'][:6])


def test_failed_font_draft_can_undo_switch_cancel(ui,monkeypatch):
    import asterpdf.text_editing as module
    app,w,t,pump=ui;t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text=='Signal amplitude');t.start_inline(obj);t.inline_editor.insertPlainText('Draft')
    def nofont(*a):raise Unsupported('No glyph')
    monkeypatch.setattr(module,'resolve_font',nofont)
    monkeypatch.setattr(module,'embedded_font',lambda *a:None)
    t.set_panel('extract');pump();assert t.canvas.mode=='region' and t.suspended_inline
    w.history(False);assert t.inline_editor and t.inline_editor.toPlainText()==obj.text
    t.cancel_inline();assert t.inline_editor is None and t.document.revision==0


def test_image_repeated_move_resize_and_delete(document,tmp_path):
    models=objects.discover(document,0);image=next(o for o in models if o.kind=='image');initial=image.bbox
    for n in range(4):
        models=objects.transform(document,0,[image],dx=3,dy=2,all_objects=models)
        image=next(o for o in models if o.id==image.id)
    actual=next(o for o in objects.discover(document,0) if o.kind=='image')
    assert actual.bbox==pytest.approx(image.bbox,abs=.05)
    assert image.bbox[0]==pytest.approx(initial[0]+12,abs=.05)
    models=objects.transform(document,0,[image],sx=.8,sy=.8,all_objects=models);image=next(o for o in models if o.id==image.id)
    actual=next(o for o in objects.discover(document,0) if o.kind=='image');assert actual.bbox==pytest.approx(image.bbox,abs=.05)
    objects.transform(document,0,[image],delete=True,all_objects=models)
    assert not [o for o in objects.discover(document,0) if o.kind=='image']


def test_vector_endpoint_and_page_organize(document,tmp_path):
    models=objects.discover(document,0);obj=next(o for o in models if o.kind=='vector' and o.details.get('vertices'))
    index,x,y=obj.details['vertices'][0];objects.move_vertex(document,0,obj,index,(x+20,y+10))
    updated=next(o for o in objects.discover(document,0) if o.id==obj.id)
    assert updated.details['vertices'][0][1:]==pytest.approx((x+20,y+10),abs=.05)
    assert ThumbnailList.reordered_ids([0,1,2,3,4],[1,2],5)==[0,3,4,1,2]
    with fitz.open(document.path) as pdf:titles=[p.get_text() for p in pdf]
    document.page_operation('reorder',[],order=[2,0,1]);document.page_operation('insert',[],files=[document.original],position=1)
    target=tmp_path/'organized.pdf';document.save(target)
    with fitz.open(target) as pdf:
        assert len(pdf)==6 and pdf[0].get_text()==titles[2] and pdf[4].get_text()==titles[0]


def test_page_colors_and_native_print(ui,tmp_path):
    from asterpdf.printing import print_document
    from PySide6.QtPrintSupport import QPrinter
    app,w,t,pump=ui
    with fitz.open(t.document.path) as pdf:other=pdf[1].get_pixmap().samples
    original=colors.inventory(t.document,0);assert original['colors']
    colors.replace(t.document,0,invert=True)
    with fitz.open(t.document.path) as pdf:
        assert pdf[0].get_pixmap().pixel(1,1)==(0,0,0)
        assert pdf[1].get_pixmap().samples==other and 'Signal amplitude' in pdf[0].get_text()
    target=tmp_path/'printed.pdf';printer=QPrinter(QPrinter.HighResolution);printer.setResolution(144);printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(str(target))
    completed=[];print_document(t,printer,completed.append);pump(lambda:bool(completed),40)
    assert completed==[True]
    with fitz.open(target) as pdf:assert len(pdf)==3

def test_object_drag_repeat_and_organizer_drop(ui,monkeypatch):
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QMessageBox
    app,w,t,pump=ui;t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.kind=='image');initial=obj.bbox
    for _ in range(2):
        start=point(t,obj.bbox);drag(t,start,start+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(15,8));pump(lambda:not t.busy and bool(t.canvas.selected))
        obj=next(o for o in t.canvas.objects if o.id in t.canvas.selected)
    with fitz.open(t.document.path) as pdf:
        box=pdf[0].get_image_rects(obj.xref)[0]
        assert box.x0>initial[0]+20
    monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.Ok)
    t.set_panel('pages');pump();listing=t.organizer;listing.clearSelection();listing.item(0).setSelected(True);listing.item(1).setSelected(True)
    from test_page_tools_08 import drop_pages
    drop_pages(listing,[0,1],2,True);pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert 'Build your own reading workflow' in pdf[0].get_text()

def test_overlapping_animate_controls_replay_and_quality(ui):
    from PySide6.QtCore import QPointF
    from PySide6.QtTest import QTest
    from asterpdf import media
    app,w,t,pump=ui;t.goto(1);t.fit(False);t.set_mode('select')
    pump(lambda:bool(t.players) and all(p.filename for p in t.players.values()) and not w.queue.jobs)
    p=next(iter(t.players.values()));a=p.animation
    # Standard animate overlays visible/hidden controls on the same rectangle.
    rect=(a.rect[0],a.rect[3]+2,a.rect[0]+20,a.rect[3]+20)
    a.buttons=[(rect,'PauseRight'),(rect,'PlayRight'),(rect,'PlayPauseRight')]
    pt=QPointF((rect[0]+rect[2])/2,(rect[1]+rect[3])/2)
    assert media.control_at(a,pt)=='PlayPauseRight'
    t.canvas.scale=2; t.canvas.layout_pages();p.stop();p.show_frame(3);p.start()
    initial=p.rendered_frames;pump(lambda:p.rendered_frames>initial+4)
    p.stop();pos=t.canvas.page_rect(1,rect).center().toPoint();QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,pos)
    assert p.playing
    initial=p.rendered_frames;w.animation_quality('native');pump(lambda:p.rendered_frames>initial+3)
    QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,pos);assert not p.playing
    pump(lambda:not w.queue.jobs)
