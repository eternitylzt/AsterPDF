"""Common editing flows: copy/no-op, partial edits, tool state, image and notes."""
import hashlib
import time
import pytest
import pymupdf as fitz
import pikepdf as pp
from PySide6.QtCore import Qt,QPoint,QEvent
from PySide6.QtGui import QTextCursor,QColor,QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog,QPushButton
from asterpdf import objects
from test_practical_ui import ui,point,drag


def select(editor,a,b):
    cursor=editor.textCursor();cursor.setPosition(a);cursor.setPosition(b,QTextCursor.KeepAnchor);editor.setTextCursor(cursor)


def spans(path):
    with fitz.open(path) as pdf:return [s for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]


def test_copy_cancel_and_partial_delete_preserve_fonts(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui;t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text=='Signal amplitude');before=t.document.path.read_bytes();original=next(s for s in spans(t.document.path) if s['text']==obj.text)
    # Missing local font must not make copying, cancelling or deleting depend on a substitute.
    for span in obj.details['spans']:span['font']='UnavailableResearchFace'
    t.start_inline(obj);select(t.inline_editor,0,6);t.inline_editor.setFocus();QTest.keyClick(t.inline_editor,Qt.Key_C,Qt.ControlModifier);pump()
    assert QApplication.clipboard().text()=='Signal' and not t.inline_dirty()
    t.leave_inline(lambda:None);pump();assert t.document.path.read_bytes()==before and t.document.revision==0
    t.start_inline(obj);select(t.inline_editor,7,9);t.inline_editor.textCursor().removeSelectedText()
    import asterpdf.text_editing as editing
    monkeypatch.setattr(editing,'resolve_font',lambda *args:(_ for _ in ()).throw(AssertionError('Deletion must not load any font')))
    t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None)
    target=tmp_path/'partial-delete.pdf';t.document.save(target)
    remaining=next(s for s in spans(target) if 'Signal' in s['text'])
    assert remaining['text']=='Signal plitude'
    assert (remaining['font'],remaining['size'],remaining['color'])==(original['font'],original['size'],original['color'])
    t.inspect_objects();pump(lambda:not t.busy and bool(t.canvas.objects));obj=next(o for o in t.canvas.objects if 'Signal' in o.text)
    t.start_inline(obj);t.inline_editor.insertPlainText('Discard me');t.exit_text_tools();pump()
    assert t.inline_editor is None and t.text_properties.isHidden() and 'Discard me' not in ''.join(s['text'] for s in spans(target))


def test_bold_italic_color_new_text_and_insertions(ui,tmp_path):
    app,w,t,pump=ui;t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text.startswith('Select this text'));source=next(s for s in spans(t.document.path) if s['text']==obj.text)
    t.start_inline(obj);select(t.inline_editor,0,6);t.text_bold.setChecked(True);t.text_italic.setChecked(True)
    assert t.text_runs()[0][0]['color']==pytest.approx(tuple(((source['color']>>n)&255)/255 for n in (16,8,0)),abs=.002)
    t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None)
    result=spans(t.document.path);rest=next(s for s in result if 'this text' in s['text']);assert rest['font']==source['font'] and rest['color']==source['color']
    # Styling now retains source glyphs and records synthetic style explicitly.
    edited=next(o for o in objects.discover(t.document,0) if o.text.startswith('Select this text'))
    assert all(style[2] and style[3] for _,style in edited.details['edit_styles'][:6])
    # A blank-page click creates an inline text box without a modal input form.
    t.text_tools();t.add_text_button.click();assert t.canvas.mode=='add_text' and t.add_text_button.isChecked()
    pos=t.canvas.page_rect(0,(70,740,70,740)).topLeft().toPoint();QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,pos);pump()
    assert t.inline_editor is not None;t.inline_editor.insertPlainText('A new text box')
    revision=t.document.revision;pump();assert t.document.revision==revision
    t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None)
    assert any(s['text']=='A new text box' for s in spans(t.document.path))


def test_image_button_paste_resize_and_module_toggle(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui;t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    image=QImage(150,100,QImage.Format_RGB32);image.fill(QColor('#e1563b'));filename=tmp_path/'image.png';image.save(str(filename))
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args:(str(filename),''))
    bar=t.tool_panels.widget(t.panel_keys['objects']);next(a for a in bar.actions() if a.property('aster_key')=='add_image').trigger();pump();assert t.image_properties.isVisible();t.browse_image()
    assert t.canvas.mode=='add_image' and next(a for a in bar.actions() if a.property('aster_key')=='add_image').isChecked()
    t.inspect_objects();pump(lambda:not t.busy);assert t.canvas.mode=='add_image'
    start=t.canvas.page_rect(0,(80,700,80,700)).topLeft().toPoint();QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,start)
    pump(lambda:not t.busy and t.canvas.mode=='objects' and len([o for o in t.canvas.objects if o.kind=='image'])==2)
    obj=max((o for o in t.canvas.objects if o.kind=='image'),key=lambda o:o.bbox[1]);t.canvas.selected=[obj.id];t.canvas.setFocus();t.copy_text();pump(lambda:QApplication.clipboard().mimeData().hasFormat('application/x-asterpdf-objects'))
    groups=sum(o.kind=='group' for o in t.canvas.objects);t.paste();pump(lambda:not t.busy and sum(o.kind=='group' for o in t.canvas.objects)>groups)
    obj=min((o for o in t.canvas.objects if o.kind=='image'),key=lambda o:o.bbox[1]);t.canvas.selected=[obj.id];box=obj.bbox
    t.keep_image_ratio.setChecked(False);t.resize_objects(30,10);pump(lambda:not t.busy)
    obj=next(o for o in t.canvas.objects if o.id==obj.id)
    assert obj.bbox[2]-obj.bbox[0]==pytest.approx(box[2]-box[0]+30,abs=.1)
    assert obj.bbox[3]-obj.bbox[1]==pytest.approx(box[3]-box[1]+10,abs=.1)
    t.set_panel('objects');assert t.active_panel=='read' and t.tool_panels.isHidden() and not any(a.isChecked() for a in t.module_actions.values())
    t.set_panel('extract');assert t.canvas.mode=='region';t.set_panel('extract');assert t.canvas.mode=='select'
    t.set_chrome_option('opacity',65);t.open_panel('annotate');pump()
    assert t.chrome_overlay and t.layout().indexOf(t.navbar)==-1 and t.navbar.geometry().bottom()<t.tool_panels.geometry().top()
    t.order_toolbar(['bookmark','extract','annotate','objects','pages'])
    assert t.navbar.actions().index(t.quick_actions['bookmark']) < t.navbar.actions().index(t.quick_actions['undo'])
    assert t.navbar.actions()[0] is t.quick_actions['select']
    assert t.quick_actions['bookmark'].text()=='' and t.page_spin.isEnabled()


def test_annotation_selection_styles_and_border(ui,tmp_path):
    app,w,t,pump=ui;t.set_panel('annotate');t.set_mode('arrow');t.annot_head_size=22
    bar=t.tool_panels.widget(t.panel_keys['annotate']);assert next(a for a in bar.actions() if a.property('aster_key')=='arrow').isChecked()
    t.add_annotation(0,'arrow',[(80,680),(220,730)]);assert not t.progress.isVisible()
    pump(lambda:not t.busy and bool(t.annotations_data));arrow=next(a for a in t.annotations_data if a['type']=='Line')
    assert arrow['head_size']==22 and arrow['line_end']==5
    t.select_annotation(arrow);t.annot_width_widget.setValue(4);pump(lambda:not t.annotation_style_timer.isActive() and not t.busy and any(a['width']==4 for a in t.annotations_data))
    t.annot_color=QColor('#a32d50');t.apply_annotation_style();pump(lambda:not t.busy and not w.queue.jobs)
    arrow=next(a for a in t.annotations_data if a['type']=='Line');assert arrow['color']==pytest.approx(QColor('#a32d50').getRgbF()[:3],abs=.001)
    t.set_mode('freetext');t.add_annotation(0,'freetext',[(310,650),(520,715)],text='A visible note');pump(lambda:not t.busy and not w.queue.jobs)
    note=next(a for a in t.annotations_data if a['type']=='FreeText');assert note['width']==0
    QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,point(t,note['rect']));assert t.annotation_text.toPlainText()=='A visible note'
    target=tmp_path/'annotations.pdf';t.document.save(target)
    with fitz.open(target) as pdf:
        assert len(list(pdf[0].annots()))==2 and len(pdf[0].get_pixmap().samples)>0
