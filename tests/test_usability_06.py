"""Daily-use regressions reported for 0.5: real input, saved PDFs and layout."""
import copy
from pathlib import Path
import pytest
import pymupdf as fitz
import pikepdf as pp
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QTextCursor,QTextCharFormat,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QInputDialog,QFileDialog
from asterpdf import objects,text_patch,colors
from asterpdf.core import Document
from asterpdf.fonts import font_bytes
from test_practical_ui import ui,drag
from test_usability_05 import select


def test_exact_text_preview_copy_paste_style_and_reedit(ui,tmp_path):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text.startswith('Select this text'));t.start_inline(obj);editor=t.inline_editor
    boxes,_=editor.glyph_rects();first=boxes[0];expected=t.canvas.page_rect(0,obj.details['glyphs'][0][3]);actual=editor.mapTo(t.canvas,(first.topLeft()+editor.viewport().pos()).toPoint())
    assert abs(actual.x()-expected.left())<=1 and abs(actual.y()-expected.top())<=1
    select(editor,0,6);QTest.keyClick(editor,Qt.Key_C,Qt.ControlModifier);assert app.clipboard().text()=='Select'
    cursor=editor.textCursor();cursor.movePosition(QTextCursor.End);editor.setTextCursor(cursor);app.clipboard().setText(' appended')
    QTest.keyClick(editor,Qt.Key_V,Qt.ControlModifier);assert editor.toPlainText().endswith(' appended')
    editor.selectAll();t.text_bold.setChecked(True);t.text_italic.setChecked(True)
    fmt=QTextCharFormat();fmt.setForeground(QColor('#216ea8'));editor.mergeCurrentCharFormat(fmt)
    pump(lambda:getattr(editor,'preview_text','').endswith(' appended') and getattr(editor,'preview_image',None) is not None)
    assert t.document.revision==0 and not t.progress.isVisible()
    glyphs=editor.preview_glyphs;assert max(g[2][1] for g in glyphs)-min(g[2][1] for g in glyphs)<.02
    t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None and not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:
        assert obj.text+' appended' in pdf[0].get_text()
        source=next(s for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['text'].startswith('Select'))
        assert source['font']==obj.details['family'] and source['color']==0x216ea8
    t.inspect_objects();pump(lambda:not t.busy and any(o.text.endswith(' appended') for o in t.canvas.objects))
    edited=next(o for o in t.canvas.objects if o.text.endswith(' appended'));t.start_inline(edited)
    assert t.text_bold.isChecked() and t.text_italic.isChecked()
    t.inline_editor.selectAll();t.text_bold.setChecked(False);t.text_italic.setChecked(False)
    t.commit_inline();pump(lambda:not t.busy and t.inline_editor is None and not w.queue.jobs)
    target=tmp_path/'reedited.pdf';t.document.save(target)
    with fitz.open(target) as pdf:assert obj.text+' appended' in pdf[0].get_text()


@pytest.mark.parametrize('face',['cff','truetype'])
def test_font_resources_survive_repeated_styles_and_partial_delete(tmp_path,face):
    app=QApplication.instance() or QApplication([])
    data=fitz.Font('tiro').buffer if face=='cff' else font_bytes('Arial')
    filename=tmp_path/(face+'.pdf')
    with fitz.open() as pdf:
        p=pdf.new_page();p.insert_font(fontname='Original',fontbuffer=data);p.insert_text((70,120),'Research label',fontname='Original',fontsize=18,color=(.2,.35,.6))
        # TeX-like TJ advances, independent of the chosen font technology.
        raw=pdf.xref_stream(p.get_contents()[0]);raw=raw.replace(b']TJ',b' -20 ]TJ');pdf.update_stream(p.get_contents()[0],raw);pdf.save(filename)
    with fitz.open(filename) as pdf:original_font_name=pdf[0].get_fonts()[0][3]
    doc=Document(filename,tmp_path/'recovery')
    try:
        obj=objects.discover(doc,0)[0];span=obj.details['spans'][0]
        old=[[dict(text=obj.text,family=span['font'],size=span['size'],color=(.2,.35,.6),bold=False,italic=False)]]
        new=copy.deepcopy(old);new[0][0].update(bold=True,italic=True,color=(.7,.2,.1))
        text_patch.apply(doc,0,obj,old,new)
        result=objects.discover(doc,0)[0];assert result.text==obj.text and len(result.details['glyphs'])==len(obj.text)
        with fitz.open(doc.path) as pdf:
            assert pdf[0].get_fonts()[0][3]==original_font_name
            assert max(g[2][1] for g in result.details['glyphs'])-min(g[2][1] for g in result.details['glyphs'])<.02
        shorter=copy.deepcopy(new);shorter[0][0]['text']=new[0][0]['text'][:-2];text_patch.apply(doc,0,result,new,shorter)
        with fitz.open(doc.path) as pdf:assert pdf[0].get_text().strip().replace('\xa0',' ')=='Research lab'
        target=tmp_path/'saved.pdf';doc.save(target)
        with fitz.open(target) as pdf:assert pdf[0].get_text().strip().replace('\xa0',' ')=='Research lab'
    finally:doc.close()


def test_live_toolbar_drag_opacity_centering_and_physical_zoom(ui):
    app,w,t,pump=ui
    source=t.navbar.widgetForAction(t.module_actions['annotate']);target=t.navbar.widgetForAction(t.module_actions['extract'])
    end=source.mapFromGlobal(target.mapToGlobal(target.rect().center()))
    QTest.mousePress(source,Qt.LeftButton,Qt.NoModifier,source.rect().center());QTest.mouseMove(source,end,30);QTest.mouseRelease(source,Qt.LeftButton,Qt.NoModifier,end);pump()
    actions=t.navbar.actions();assert actions.index(t.module_actions['annotate'])>actions.index(t.module_actions['extract'])
    assert QApplication.overrideCursor() is None and t.active_panel=='read'
    button=t.navbar.widgetForAction(t.module_actions['pages']);QTest.mouseClick(button,Qt.LeftButton);assert t.active_panel=='pages'
    QTest.mouseClick(button,Qt.LeftButton);assert t.active_panel=='read'
    t.set_chrome_option('opacity',65);pump();t.set_view(1,False);t.fit(False);pump(lambda:not w.queue.jobs)
    r=t.canvas.rects[0];inset=t.reading_inset;viewport=t.scroll.viewport().height()
    assert r.top()>=inset+15 and abs((r.top()-inset)-(viewport-r.bottom()))<2
    t.set_view(2,False);t.fit(False);pump();assert abs((t.canvas.rects[0].top()-inset)-(viewport-t.canvas.rects[0].bottom()))<2
    t.zoom.setCurrentText('100%');t.zoom_changed();assert t.canvas.scale==pytest.approx(w.screen().physicalDotsPerInch()/72)
    t.zoom.setCurrentText('6400%');t.zoom_changed();assert t.zoom_factor==64
    t.zoom.setCurrentText('1.5625%');t.zoom_changed();assert t.zoom_factor==1/64
    t.fit(False)


def test_text_annotation_doubleclick_resize_visibility_time_and_export(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui;t.open_panel('annotate');t.set_mode('freetext')
    text='A text annotation that automatically wraps. '*4
    monkeypatch.setattr(QInputDialog,'getMultiLineText',lambda *a,**kw:(text,True))
    point=t.canvas.page_rect(0,(300,600,300,600)).topLeft().toPoint();QTest.mouseDClick(t.canvas,Qt.LeftButton,Qt.NoModifier,point)
    pump(lambda:not t.busy and any(a['type']=='FreeText' for a in t.annotations_data))
    ann=next(a for a in t.annotations_data if a['type']=='FreeText');assert ann['rect'][3]-ann['rect'][1]>40 and ann['created'].startswith('D:')
    t.select_annotation(ann);pump();box=t.canvas.page_rect(0,ann['rect']);start=QPoint(round(box.right()),round(box.center().y()))
    drag(t,start,start+QPoint(-50,0));pump(lambda:not t.busy and not w.queue.jobs)
    ann=next(a for a in t.annotations_data if a['type']=='FreeText');assert ann['rect'][2]<505
    t.annot_width_widget.setValue(2);pump(lambda:not t.annotation_style_timer.isActive() and not t.busy and not w.queue.jobs)
    assert next(a for a in t.annotations_data if a['type']=='FreeText')['width']==2 and t.annot_width_widget.value()==2
    path=t.document.path;visible=t.document.render_tile(0,1,(280,570,570,820),show_annotations=True)[0]
    t.show_annotations.setChecked(False);pump(lambda:not w.queue.jobs)
    hidden=t.document.render_tile(0,1,(280,570,570,820),show_annotations=False)[0]
    assert visible!=hidden and t.annotation_list.count()==1 and t.document.path==path
    t.show_annotations.setChecked(True);pump(lambda:not w.queue.jobs);t.document.add_annotation(1,'note',[(40,40),(40,40)],text='Second page')
    t.load_annotations();pump(lambda:t.annotation_list.count()==2);t.annotation_sort.setCurrentIndex(1);pump(lambda:not w.queue.jobs)
    assert 'D:' not in t.annotation_list.item(0).text() and '20' in t.annotation_list.item(0).text()
    t.open_panel('extract');t.canvas.region=(0,(50,100,250,200));calls=[]
    def save_dialog(*args):calls.append(args);return str(tmp_path/'chosen-region.png'),'PNG (*.png)'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',save_dialog);t.export_images(True);pump(lambda:not t.busy)
    assert (tmp_path/'chosen-region.png').exists() and '_p0001_region.png' in calls[0][2]


def test_color_scopes_region_and_one_step_undo(tmp_path):
    filename=tmp_path/'colors.pdf'
    with fitz.open() as pdf:
        for _ in range(3):
            page=pdf.new_page(width=300,height=300);page.draw_rect((40,40,260,260),color=None,fill=(1,0,0));page.insert_text((70,100),'Vector text')
        pdf.save(filename)
    doc=Document(filename,tmp_path/'recovery')
    try:
        colors.replace(doc,[0,2],(1,0,0),(0,0,1));assert doc.revision==1
        with fitz.open(doc.path) as pdf:
            assert pdf[0].get_pixmap().pixel(50,50)==(0,0,255) and pdf[1].get_pixmap().pixel(50,50)==(255,0,0)
        doc.undo();colors.replace(doc,1,(1,0,0),(0,1,0),region=(130,130,280,280))
        with fitz.open(doc.path) as pdf:
            pix=pdf[1].get_pixmap();assert pix.pixel(160,160)==(0,255,0) and pix.pixel(70,160)==(255,0,0)
            assert not pdf[1].get_images() and 'Vector text' in pdf[1].get_text()
        colors.replace(doc,[0,1,2],invert=True);doc.save(tmp_path/'all.pdf')
        with fitz.open(tmp_path/'all.pdf') as pdf:assert len(pdf)==3
    finally:doc.close()


def test_reopen_then_insert_another_font_preserves_prior_resources(tmp_path):
    app=QApplication.instance() or QApplication([]);filename=tmp_path/'labels.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page();page.insert_text((40,50),'one');page.insert_text((40,90),'two');pdf.save(filename)
    def append(doc,label,font):
        obj=next(o for o in objects.discover(doc,0) if o.text==label)
        old=[[dict(text=label,family=obj.details['family'],size=obj.size,color=(0,0,0),bold=False,italic=False)]]
        new=copy.deepcopy(old);new[0][0].update(text=label+' A',fontbuffer=font_bytes(font))
        text_patch.apply(doc,0,obj,old,new)
    doc=Document(filename,tmp_path/'recovery');append(doc,'one','Arial');saved=tmp_path/'saved.pdf';doc.save(saved);doc.close()
    reopened=Document(saved,tmp_path/'recovery')
    try:
        with fitz.open(reopened.path) as pdf:before={font[4]:pdf.extract_font(font[0])[3] for font in pdf[0].get_fonts()}
        append(reopened,'two','Times New Roman')
        with fitz.open(reopened.path) as pdf:
            after={font[4]:pdf.extract_font(font[0])[3] for font in pdf[0].get_fonts()}
            assert all(after[key]==value for key,value in before.items())
            assert 'one A' in pdf[0].get_text() and 'two A' in pdf[0].get_text()
    finally:reopened.close()
