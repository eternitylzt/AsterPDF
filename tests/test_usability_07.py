"""Practical 0.7 workflows: mouse navigation, edits, clipboard, recovery."""
import json,time,subprocess,sys,os
from pathlib import Path
import pytest
import pymupdf as fitz
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtGui import QWheelEvent,QTextCursor,QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton,QMessageBox,QFileDialog
from asterpdf.core import Document
from asterpdf import objects,figures
from asterpdf.object_clipboard import copy_pdf,paste_pdf
from test_practical_ui import ui,drag,point

def test_pointer_zoom_whole_document_track_and_overflow(ui):
    app,w,t,pump=ui;t.set_view(1,True);t.set_zoom(2);t.goto(0)
    global_point=QPointF(t.scroll.viewport().mapToGlobal(QPoint(330,280)))
    before=t.canvas.locate(QPointF(t.canvas.mapFromGlobal(global_point.toPoint())))
    t.zoom_by(1.2,global_point);pump()
    after=t.canvas.locate(QPointF(t.canvas.mapFromGlobal(global_point.toPoint())))
    assert before[0]==after[0] and (before[1]-after[1]).manhattanLength()<1.5
    t.set_view(1,False);t.fit(False);pump();assert not hasattr(t.scroll,'document_bar')
    t.minimap.sync();t.minimap.seek(t.minimap.rects[-1].center());pump();assert t.canvas.page==t.info['count']-1
    w.settings.setValue('toolbar/tools',list(t.quick_actions)+list(t.module_actions));t.configure_chrome();w.resize(850,700);pump(lambda:t.navbar_host.right.isVisible())
    assert t.navbar_host.right.isVisible() and t.navbar_host.right.isEnabled()
    QTest.mouseClick(t.navbar_host.right,Qt.LeftButton);pump();assert t.navbar_host.scroller.horizontalScrollBar().value()>0
    assert t.navbar_host.left.isEnabled()

def test_notes_marquee_delete_move_hover_and_deselect(ui):
    app,w,t,pump=ui;t.open_panel('annotate');pump(lambda:not w.queue.jobs)
    t.add_annotation(0,'note',[(300,400),(300,400)],text='Preview this note');pump(lambda:not t.busy and len(t.annotations_data)==1)
    note=t.annotations_data[0];t.select_annotation(note);start=point(t,note['rect']);drag(t,start,start+QPoint(30,20));pump(lambda:not t.busy and not w.queue.jobs)
    moved=t.annotations_data[0];assert moved['rect'][0]>note['rect'][0]+10
    QTest.mouseMove(t.canvas,point(t,moved['rect']));pump();assert t.canvas.toolTip()=='Preview this note'
    t.add_annotation(0,'rectangle',[(300,450),(400,500)],text='Shape');pump(lambda:not t.busy and len(t.annotations_data)==2)
    assert not t.annotation_list.selectedItems()
    t.set_mode('select_annot');drag(t,point(t,(280,380,280,380)),point(t,(450,520,450,520)));assert len(t.annotation_list.selectedItems())==2
    QTest.keyClick(t.canvas,Qt.Key_Delete);pump(lambda:not t.busy and not t.annotations_data)
    assert not t.document.annotations()

def test_docked_shapes_pdf_insertion_color_region_and_paste(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy)
    t.begin_vector_edit();pump(lambda:not t.busy);assert t.shape_properties.isVisible() and not t.shape_properties.isWindow()
    t.shape_properties.inputs['kind'].setCurrentIndex(3);t.shape_properties.inputs['fill'].setChecked(True)
    t.set_mode('draw_shape');drag(t,point(t,(300,470,300,470)),point(t,(470,530,470,530)));pump(lambda:not t.busy and not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:assert any(d['fill'] for d in pdf[0].get_drawings())
    t.set_mode('objects');t.inspect_objects();pump(lambda:not t.busy)
    selected=[o for o in t.canvas.objects if o.kind=='text' and o.text=='Signal amplitude'];t.canvas.selected=[o.id for o in selected];t.copy_objects();pump(lambda:app.clipboard().mimeData().hasFormat('application/x-asterpdf-objects'))
    t.goto(1);pump(lambda:not t.busy);t.canvas.setFocus();t.paste();pump(lambda:not t.busy and not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:
        assert 'Signal amplitude' in pdf[1].get_text();assert not pdf[1].get_images()
        pasted=next(s for b in pdf[1].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['text']=='Signal amplitude')
        assert pasted['size']==pytest.approx(selected[0].size,abs=.02)
        assert pasted['origin']==pytest.approx(selected[0].details['origin'],abs=.02)
    source=tmp_path/'figure.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page(width=200,height=100);page.insert_text((20,50),'Vector figure');page.draw_line((20,60),(180,60));pdf.save(source)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(source),'PDF'))
    t.choose_insert_image();assert t.image_properties.isVisible();w.toggle_presentation();pump();assert not t.property_container.isVisible();w.toggle_presentation();pump(lambda:not t.busy);assert t.property_container.isVisible();t.browse_image();assert t.canvas.mode=='add_image'
    t.place_image(1,(100,350,300,450));pump(lambda:not t.busy and not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:assert 'Vector figure' in pdf[1].get_text() and not pdf[1].get_images()
    t.replace_colors();pump(lambda:t.color_properties.inputs['source'].count()>0);assert not t.color_properties.isWindow()
    t.canvas.region=(1,(100,350,300,450));t.color_properties.inputs['scope'].setCurrentIndex(3);t.color_properties.inputs['invert'].setChecked(True)
    revision=t.document.revision
    button=next(b for b in t.property_container.findChildren(QPushButton) if b.text() in ('应用','Apply'));button.click();pump(lambda:not t.busy and t.document.revision>revision)
    target=tmp_path/'all-edits.pdf';t.document.save(target)
    with fitz.open(target) as pdf:assert 'Vector figure' in pdf[1].get_text()

def test_page_rotation_selection_flip_revert_and_browser(ui,monkeypatch):
    app,w,t,pump=ui;t.open_panel('pages');pump();t.organizer.item(1).setSelected(True)
    chosen=t.selected_pages();t.page_selection_operation('rotate');pump(lambda:not t.busy);assert t.selected_pages()==chosen
    t.page_selection_operation('rotate');pump(lambda:not t.busy);assert t.selected_pages()==chosen
    urls=[];monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:urls.append(url.toString()) or True)
    assert t.activate_link({'uri':'www.science.org/doi/10.1126/science.ads9412'})
    assert urls==['https://www.science.org/doi/10.1126/science.ads9412']
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.Yes)
    t.reset_document();pump(lambda:not t.busy);assert not t.document.dirty
    t.document.undo();assert t.document.dirty

def test_real_crash_recovery_and_draft(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui;root=w.recovery_root
    script="from asterpdf.core import Document;import os;d=Document(os.environ['ASTER_SOURCE'],os.environ['ASTER_RECOVERY']);d.add_annotation(0,'note',[(50,50),(50,50)],text='Before process termination');os._exit(7)"
    env=dict(os.environ,ASTER_SOURCE=t.document.original,ASTER_RECOVERY=str(root))
    child=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,timeout=20);assert child.returncode==7,child.stderr
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.Yes)
    w.offer_recovery();pump(lambda:len(w.document_tabs())==2 and not w.queue.jobs)
    recovered=w.current();assert recovered.document.dirty and any(a['text']=='Before process termination' for a in recovered.document.annotations())
    check=Document(t.document.original,tmp_path/'verify');assert not check.annotations();check.close()
    w.tabs.setCurrentWidget(t);t.open_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    t.start_inline(next(o for o in t.canvas.objects if o.text=='Signal amplitude'));editor=t.inline_editor;cursor=editor.textCursor();cursor.movePosition(QTextCursor.End);editor.setTextCursor(cursor);QTest.keyClicks(editor,' draft')
    t.persist_recovery_draft();draft=json.loads((t.document.folder/'draft.json').read_text(encoding='utf-8'));assert 'draft' in ''.join(run['text'] for line in draft['runs'] for run in line)
    t.cancel_inline();assert not (t.document.folder/'draft.json').exists()



def test_close_all_activates_and_saves_each_dirty_tab(ui,tmp_path,monkeypatch):
    from asterpdf.tab import DocumentTab
    app,w,t,pump=ui
    t.document.add_annotation(0,'note',[(50,50),(50,50)],text='First changed')
    second_source=tmp_path/'second.pdf';second_source.write_bytes(Path(t.document.original).read_bytes())
    second=Document(second_source,tmp_path/'second-recovery');other=DocumentTab(w,second,second.info());w.tabs.addTab(other,'second');w.tabs.setCurrentWidget(t)
    second.add_annotation(0,'note',[(70,70),(70,70)],text='Second changed');pump(lambda:not w.queue.jobs)
    prompted=[]
    def choose(*args,**kwargs):prompted.append(w.current().document.original);return QMessageBox.Save
    monkeypatch.setattr(QMessageBox,'question',choose);w.close();pump(lambda:not w.isVisible() and not w.document_tabs(),30)
    assert prompted==[str(second_source.resolve()),t.document.original]
    with fitz.open(second_source) as pdf:assert next(pdf[0].annots()).info['content']=='Second changed'


def test_rich_clipboard_keeps_text_size_color_and_font(ui):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    source=next(o for o in t.canvas.objects if o.text=='Signal amplitude');t.start_inline(source);editor=t.inline_editor;editor.selectAll()
    expected=t.text_runs()[0][0].copy();QTest.keyClick(editor,Qt.Key_C,Qt.ControlModifier);assert app.clipboard().mimeData().hasFormat('application/x-asterpdf-text')
    t.cancel_inline();target=next(o for o in t.canvas.objects if o.text.startswith('Select this text'));t.start_inline(target);editor=t.inline_editor;cursor=editor.textCursor();cursor.movePosition(QTextCursor.End);editor.setTextCursor(cursor)
    QTest.keyClick(editor,Qt.Key_V,Qt.ControlModifier);runs=t.text_runs();last=runs[-1][-1]
    assert last['text'].endswith(expected['text']) and last['family']==expected['family'] and last['size']==expected['size'] and last['color']==expected['color']
    t.cancel_inline()


def test_page_flip_retains_text_vectors_and_is_undoable(tmp_path):
    source=tmp_path/'flip.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page(width=300,height=400);page.insert_text((25,50),'Mirror');page.draw_rect((20,200,80,250),fill=(1,0,0));pdf.save(source)
    doc=Document(source,tmp_path/'recovery')
    try:
        doc.page_operation('flip_h',[0])
        with fitz.open(doc.path) as pdf:
            pix=pdf[0].get_pixmap();assert pix.pixel(240,220)==(255,0,0) and pix.pixel(40,220)==(255,255,255)
            assert 'Mirror' in pdf[0].get_text() and not pdf[0].get_images()
        doc.page_operation('flip_v',[0]);doc.save(tmp_path/'flipped.pdf')
        with fitz.open(tmp_path/'flipped.pdf') as pdf:assert pdf[0].get_pixmap().pixel(240,170)==(255,0,0)
        doc.undo();doc.undo();assert doc.dirty  # Saved mirrored revision differs from the original.
    finally:doc.close()
