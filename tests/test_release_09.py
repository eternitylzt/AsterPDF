import time
import pytest
import pymupdf as fitz
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtGui import QWheelEvent,QTextCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from asterpdf import objects
from asterpdf.preferences import Preferences,apply_preferences
from test_practical_ui import ui

def test_live_selected_page_cancel_and_leave(ui):
    app,w,t,pump=ui;t.open_panel('pages');t.organizer.setCurrentRow(2);t.page_tools('rotate');pane=t.page_properties
    assert pane.current_page==2 and pane.apply_button.text()!='应用'
    pane.apply_button.click();pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert [p.rotation for p in pdf]==[0,0,90]
    assert t.organizer.currentRow()==2 and t.info['sizes'][2][0]>t.info['sizes'][2][1]
    pane.apply_button.click();t.cancel_page_tools();pump(lambda:not t.busy and not t.property_container.isVisible());pump(lambda:not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:assert [p.rotation for p in pdf]==[0,0,0]
    t.page_tools('rotate');t.page_properties.apply_button.click();pump(lambda:not t.busy);t.open_panel('read')
    with fitz.open(t.document.path) as pdf:assert pdf[2].rotation==90

def test_text_panel_new_box_wrap_rotation_and_reopen(ui,tmp_path):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs)
    t.choose_insert_image();t.text_tools();pump();assert t.text_properties.isVisible() and t.text_container.width()>=205
    for _ in range(3):
        t.begin_vector_edit();pump(lambda:not t.busy);t.text_tools();pump();assert t.text_container.width()>=205
    t.add_text(0,(200,450,200,450));pump();assert t.inline_editor.width()<40
    t.inline_editor.insertPlainText('中文测试输入自动换行');pump(lambda:hasattr(t.inline_editor,'preview_glyphs'),timeout=40)
    t.change_box(width=30,angle=0);pump(lambda:not w.queue.jobs);t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None,timeout=40)
    with fitz.open(t.document.path) as pdf:
        text=pdf[0].get_text();assert '中' in text and '文' in text
        lines=[l for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) if any('中' in s['text'] for s in l['spans'])]
        assert lines[0]['dir']==pytest.approx((1,0))
    t.inspect_objects();pump(lambda:not t.busy);box=next(o for o in t.canvas.objects if o.details.get('box'));assert box.details['box']['rect'][2]==30
    t.start_inline(box);t.change_box(angle=30);t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None,timeout=40)
    target=tmp_path/'box.pdf';t.document.save(target)
    with fitz.open(target) as pdf:
        dirs=[l['dir'] for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) if any('中' in s['text'] for s in l['spans'])]
        assert dirs[0][0]==pytest.approx(.866,abs=.01)
    t.inspect_objects();pump(lambda:not t.busy);box=next(o for o in t.canvas.objects if o.details.get('box'));t.start_inline(box);revision=t.document.revision;t.commit_inline();pump();assert t.document.revision==revision

def test_preferences_overview_bookmarks_and_nudge(ui):
    app,w,t,pump=ui;m=t.minimap;m.sync();assert m.height()<=w.screen().availableGeometry().height()/2 and m.opacity==80
    percent=m.percent;pos=QPointF(40,50);ev=QWheelEvent(pos,pos,QPoint(),QPoint(0,120),Qt.NoButton,Qt.ControlModifier,Qt.NoScrollPhase,False);app.sendEvent(m,ev);assert m.percent==percent+1
    dialog=Preferences(w);fields={k:v for f in dialog.forms for k,v in f.inputs.items()};fields['home/recent'].setChecked(False);fields['minimap/opacity'].setValue(65);fields['ui/font_size'].setCurrentIndex(2);dialog.apply();pump();assert not w.home_recent.isVisible() and m.opacity==65
    t.goto(0);t.toggle_bookmark();assert t.quick_actions['bookmark'].isChecked();t.goto(1);assert not t.quick_actions['bookmark'].isChecked();t.goto(0);assert t.quick_actions['bookmark'].isChecked();assert '%' in t.bookmarks.item(0).data(Qt.UserRole+1)
    t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs);obj=next(o for o in t.canvas.objects if o.kind=='vector');t.canvas.selected=[obj.id];before=obj.bbox;t.canvas.setFocus();QTest.keyClick(t.canvas,Qt.Key_Right);pump(lambda:not t.busy);assert t.canvas.page==0
    moved=next(o for o in t.canvas.objects if o.id==obj.id);assert moved.bbox[0]-before[0]==pytest.approx(1/t.canvas.scale,abs=.05)

def test_box_border_drag_cancel_and_settings_keep_draft(ui):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs);t.add_text(0,(210,450,210,450));t.inline_editor.insertPlainText('Original size and a long enough line');pump(lambda:hasattr(t.inline_editor,'preview_image'))
    handles=t.inline_editor.handles;start=handles.box.bottomRight().toPoint();QTest.mousePress(handles,Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(handles,start+QPoint(50,20),20);QTest.mouseRelease(handles,Qt.LeftButton,Qt.NoModifier,start+QPoint(50,20));assert not t.inline_object.details['box']['auto']
    start=handles.knob.toPoint();angle=t.inline_object.details['box']['angle'];QTest.mousePress(handles,Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(handles,start+QPoint(3,2),20);QTest.mouseRelease(handles,Qt.LeftButton,Qt.NoModifier,start+QPoint(3,2));assert abs(t.inline_object.details['box']['angle']-angle)<15
    revision=t.document.revision;draft=t.inline_editor.toPlainText();w.settings.setValue('ui/font_size','large');apply_preferences(w);pump();assert t.document.revision==revision and t.inline_editor.toPlainText()==draft
    t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None and not w.queue.jobs);box=next(o for o in t.canvas.objects if o.details.get('box'));angle=box.details['box']['angle'];t.start_inline(box);t.change_box(angle=20);t.cancel_inline();assert box.details['box']['angle']==angle
    t.canvas.selected=[box.id];t.move_objects(20,10);pump(lambda:not t.busy and not w.queue.jobs);moved=next(o for o in t.canvas.objects if o.details.get('box'));assert moved.details['box']['rect'][0]==pytest.approx(box.details['box']['rect'][0]+20)
    t.start_inline(moved);t.inline_editor.moveCursor(QTextCursor.End);t.inline_editor.insertPlainText(' added');t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None and not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:assert 'added' in pdf[0].get_text()

def test_flip_cancel_and_bookmark_rename(ui,monkeypatch):
    import json
    from PySide6.QtWidgets import QMenu,QInputDialog
    app,w,t,pump=ui;t.open_panel('pages');t.organizer.setCurrentRow(2)
    with fitz.open(t.document.path) as pdf:before=pdf[2].get_pixmap().samples
    t.page_tools('flip_h');t.page_properties.apply_button.click();pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert before!=pdf[2].get_pixmap().samples
    t.cancel_page_tools();pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert before==pdf[2].get_pixmap().samples
    assert not t.document.dirty
    from PySide6.QtCore import QTimer
    t.goto(1);t.toggle_bookmark();t.sidebar.setCurrentWidget(t.bookmarks);pump()
    timer=QTimer(w)
    def respond():
        popup=app.activePopupWidget();dialog=app.activeModalWidget()
        if isinstance(popup,QMenu):popup.setActiveAction(popup.actions()[0]);QTest.keyClick(popup,Qt.Key_Return)
        elif isinstance(dialog,QInputDialog):dialog.setTextValue('Methods');dialog.accept();timer.stop()
    timer.timeout.connect(respond);timer.start(100)
    t.bookmark_menu(t.bookmarks.visualItemRect(t.bookmarks.item(0)).center());timer.stop()
    assert t.bookmarks.item(0).text()=='Methods';t.save_state();assert json.loads(w.settings.value(t.state_key))['bookmark_names']['1']=='Methods'
