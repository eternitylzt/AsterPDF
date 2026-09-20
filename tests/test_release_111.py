"""1.1.1 practical regressions: list selection, overlays, transforms and media UI."""
import json,zipfile
from pathlib import Path
import pymupdf as fitz
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtGui import QColor,QCloseEvent
from PySide6.QtWidgets import QLabel,QMessageBox,QColorDialog,QApplication
from PySide6.QtTest import QTest
from asterpdf import figures,objects
from test_practical_ui import ui,point,drag


def test_recent_select_double_click_and_columns(ui,monkeypatch,tmp_path):
    app,w,t,pump=ui
    paths=[str(tmp_path/('Recent document '+str(n)+'.pdf')) for n in range(6)]
    w.settings.setValue('recent',paths);w.refresh_recent();w.tabs.setCurrentWidget(w.welcome);pump()
    tree=w.home_recent;opened=[];monkeypatch.setattr(w,'open_file',opened.append)
    for n in range(3):
        item=tree.topLevelItem(n);tree.scrollToItem(item);pump();rect=tree.visualItemRect(item)
        assert tree.itemWidget(item,0) is None and rect.height()>=55
        pos=QPoint(30,rect.center().y());QTest.mouseClick(tree.viewport(),Qt.LeftButton,Qt.NoModifier,pos)
        assert tree.currentItem() is item and not opened
    QTest.mouseDClick(tree.viewport(),Qt.LeftButton,Qt.NoModifier,pos);pump();assert opened==[paths[2]]
    assert tree.columnWidth(1)==90 and tree.columnWidth(2)==175


def test_recolor_overlay_scope_exit_and_color_pairs(ui):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not w.queue.jobs);t.replace_colors();pane=t.color_properties
    pump(lambda:pane.inputs['source'].count()>0 and not w.queue.jobs)
    border=pane.inputs['boundary'];assert border.isHidden()
    assert pane.form.getWidgetPosition(border)[0]==pane.form.getWidgetPosition(pane.inputs['scope'])[0]+1
    pane.inputs['scope'].setCurrentIndex(3);assert border.isVisible()
    t.selection_finished(0,[(50,70),(240,140)],'region');pump(lambda:not w.queue.jobs)
    pane.add_pair();assert pane.pairs
    from PySide6.QtWidgets import QListWidget
    listing=pane.findChild(QListWidget);label=listing.itemWidget(listing.item(0));assert 'color:' in label.text() and '→' in label.text()
    assert pane.inputs['images'].toolTip()
    pane.apply_colors();pump(lambda:not t.busy and not w.queue.jobs)
    assert t.canvas.color_boundary
    revision=t.document.revision;t.text_tools();assert not t.canvas.color_boundary and not t.canvas.region
    for leave in (t.close_properties,t.begin_vector_edit,lambda:t.open_panel('read')):
        t.replace_colors();p=t.color_properties;p.inputs['scope'].setCurrentIndex(3)
        t.selection_finished(0,[(50,70),(240,140)],'region');t.canvas.color_boundary=t.canvas.region
        leave();assert t.canvas.color_boundary is None and t.canvas.region is None
    assert t.document.revision==revision


def test_shape_free_resize_preserves_background(ui,tmp_path):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not w.queue.jobs);t.begin_vector_edit()
    with fitz.open(t.document.path) as pdf:before=pdf[0].get_text('words')
    figures.draw_shape(t.document,0,(80,95,220,155),'ellipse',(1,0,0),None,2)
    t.refresh();pump(lambda:not t.busy and not w.queue.jobs);t.inspect_objects();pump(lambda:not t.busy and not w.queue.jobs)
    obj=[o for o in t.canvas.objects if o.kind=='vector'][-1];t.canvas.selected=[obj.id]
    box=t.canvas.selection_box();start=t.canvas.resize_handle().center().toPoint();end=start+QPoint(50,15)
    QTest.mousePress(t.canvas,Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(t.canvas,end,20)
    assert t.canvas.drag_preview is None
    QTest.mouseRelease(t.canvas,Qt.LeftButton,Qt.NoModifier,end);pump(lambda:not t.busy and not w.queue.jobs)
    new=next(o for o in t.canvas.objects if o.id==obj.id)
    assert abs((new.bbox[2]-new.bbox[0])/(obj.bbox[2]-obj.bbox[0])-(new.bbox[3]-new.bbox[1])/(obj.bbox[3]-obj.bbox[1]))>.02
    with fitz.open(t.document.path) as pdf:assert pdf[0].get_text('words')==before
    t.document.save(tmp_path/'shapes.pdf')
    with fitz.open(tmp_path/'shapes.pdf') as pdf:assert pdf[0].get_text('words')==before


def test_image_stacking_retains_text_and_can_undo(document):
    found=objects.discover(document,0);image=next(o for o in found if o.kind=='image')
    with fitz.open(document.path) as pdf:before=pdf[0].get_text('words');original=pdf[0].get_pixmap().samples
    objects.set_stacking(document,0,[image],False)
    with fitz.open(document.path) as pdf:
        assert pdf[0].get_text('words')==before
        log=pdf[0].get_bboxlog();assert log[0][0]=='fill-image'
    image=next(o for o in objects.discover(document,0) if o.kind=='image');objects.set_stacking(document,0,[image],True)
    with fitz.open(document.path) as pdf:
        assert pdf[0].get_text('words')==before
        assert pdf[0].get_bboxlog()[-1][0]=='fill-image'
    document.undo();document.undo()
    with fitz.open(document.path) as pdf:assert pdf[0].get_pixmap().samples==original


def test_controls_bounded_grip_presentation(ui):
    from asterpdf.playback_controls import WidthGrip
    app,w,t,pump=ui;t.show_playback_controls();panel=t.playback_panel;pump()
    assert panel.parentWidget() is w and panel.isVisible()
    if t.animations:
        panel.fps.setFocus();panel.fps.lineEdit().setText('18.0 fps');panel.sync();assert panel.fps.lineEdit().text()=='18.0 fps'
        panel.handle.setFocus()
    panel.move(-800,-800);panel.reposition();assert panel.bounds().contains(panel.geometry())
    panel.move(10000,10000);panel.reposition();assert panel.bounds().contains(panel.geometry())
    old_window=w.size();old_width=panel.width();grip=panel.findChild(WidthGrip)
    QTest.mousePress(grip,Qt.LeftButton,Qt.NoModifier,QPoint(5,10));QTest.mouseMove(grip,QPoint(-75,10),20);QTest.mouseRelease(grip,Qt.LeftButton,Qt.NoModifier,QPoint(-75,10))
    assert w.size()==old_window and panel.width()<old_width
    w.toggle_presentation();pump();assert panel.isHidden()
    w.toggle_presentation();pump();assert not panel.requested


def test_preferences_colors_overview_organizer_and_close(ui,monkeypatch,tmp_path):
    from asterpdf.preferences import Preferences
    from asterpdf.tool_widgets import ColorButton
    app,w,t,pump=ui;settings=Preferences(w)
    form=next(f for f in settings.forms if 'annotation/annot_color' in f.inputs)
    button=form.inputs['annotation/annot_color'];assert isinstance(button,ColorButton)
    monkeypatch.setattr(QColorDialog,'getColor',lambda *args:QColor('#35aa66'));button.click();assert form.values()['annotation/annot_color']=='#35aa66'
    assert t.organizer_zoom.maximum()==50
    t.minimap.auto_size=True;t.minimap.percent=20;t.minimap.auto_scale=False;t.minimap.sync()
    maximum=(t.scroll.viewport().height()-getattr(t,'reading_inset',0))*.8
    assert t.minimap.height()<=round(maximum)+1
    from asterpdf.core import Document
    from asterpdf.tab import DocumentTab
    other=Document(t.document.original,tmp_path/'second');w.tabs.addTab(DocumentTab(w,other,other.info()),'second');pump(lambda:not w.queue.jobs)
    closed=[];monkeypatch.setattr(w,'close_tab',lambda n:closed.append(n))
    def choose_current():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,QMessageBox)
        assert dialog.checkBox() is not None
        next(b for b in dialog.buttons() if b.text() in ('当前标签页','Current tab')).click()
    QTimer.singleShot(0,choose_current)
    event=QCloseEvent();w.closeEvent(event)
    assert closed==[w.tabs.indexOf(t)] and not getattr(w,'_closing_all',False) and not event.isAccepted()


def test_animation_source_export_all_frames(document,tmp_path):
    from asterpdf.media import scan,export_animation
    animations,_,_=scan(document);assert animations
    out=tmp_path/'animation.zip';a=animations[0];export_animation(document,a,out)
    with zipfile.ZipFile(out) as z:
        timing=json.loads(z.read('timing.json'));assert timing['frame_count']==len(a.frames) and timing['fps']==a.fps
        with fitz.open(stream=z.read('frames.pdf'),filetype='pdf') as frames:
            assert len(frames)==len(a.frames)
            assert frames[0].get_pixmap().samples!=frames[-1].get_pixmap().samples
