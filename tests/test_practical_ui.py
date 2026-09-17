"""Common user workflows exercised through real Qt mouse/keyboard events."""
import time
from pathlib import Path
import pytest
import pymupdf as fitz
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from asterpdf.app import Window
from asterpdf.tab import DocumentTab
from asterpdf.dialogs import MergeDialog
from asterpdf.core import Document

@pytest.fixture
def ui(document,tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    errors=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:errors.append(str(args[-1])))
    window=Window(tmp_path/'ui');window.show()
    tab=DocumentTab(window,document,document.info());window.tabs.addTab(tab,'sample');window.tabs.setCurrentWidget(tab)
    def pump(predicate=lambda:True,timeout=20):
        start=time.monotonic()
        while True:
            app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete);time.sleep(.01)
            assert not errors,errors
            if predicate():return
            assert time.monotonic()-start<timeout,('UI workflow timed out',tab.busy,tab.document.revision,tab.inline_editor,[o.text for o in tab.canvas.objects],tab.canvas.mode,tab.editing_objects)
    pump(lambda:bool(tab.canvas.words.get(0)) and not tab.queue.jobs)
    tab.set_view(1,False);tab.goto(0)
    settle=time.monotonic()+.2;pump(lambda:time.monotonic()>settle and not tab.queue.jobs)
    tab.fit(False);pump(lambda:not tab.queue.jobs)
    yield app,window,tab,pump
    for i in reversed(range(window.tabs.count())):
        widget=window.tabs.widget(i)
        if isinstance(widget,DocumentTab):widget.closed=True;widget.pause_media();window.tabs.removeTab(i)
    pump(lambda:not window.queue.jobs)
    window.close();window.deleteLater();app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete)


def drag(tab,start,end):
    canvas=tab.canvas
    QTest.mousePress(canvas,Qt.LeftButton,Qt.NoModifier,start)
    QTest.mouseMove(canvas,end,20)
    QTest.mouseRelease(canvas,Qt.LeftButton,Qt.NoModifier,end)


def point(tab,rect):return tab.canvas.page_rect(tab.canvas.page,rect).center().toPoint()


def test_reading_wheel_keys_four_views_and_presentation(ui):
    app,window,tab,pump=ui
    tab.canvas.setFocus()
    QTest.keyClick(tab.canvas,Qt.Key_Right);pump();assert tab.canvas.page==1
    QTest.keyClick(tab.canvas,Qt.Key_Left);pump();assert tab.canvas.page==0
    bar=tab.scroll.verticalScrollBar();bar.setValue(bar.maximum())
    pos=QPointF(200,200)
    event=QWheelEvent(pos,pos,QPoint(),QPoint(0,-120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
    QApplication.sendEvent(tab.scroll.viewport(),event);pump();assert tab.canvas.page==1
    assert tab.thumbnails.currentItem().data(Qt.UserRole)==1
    tab.set_zoom(1.5);bar.setValue(0)
    QTest.keyClick(tab.canvas,Qt.Key_Down);assert bar.value()>0
    QTest.keyClick(tab.canvas,Qt.Key_Up);assert bar.value()==0
    tab.set_view(2,False);tab.goto(0);pump()
    assert sum(not r.isEmpty() for r in tab.canvas.rects)==2
    QTest.keyClick(tab.canvas,Qt.Key_Right);pump();assert tab.canvas.page==2
    tab.set_view(2,True);pump();assert all(not r.isEmpty() for r in tab.canvas.rects)
    tab.set_view(1,True);tab.goto(0);tab.scroll.verticalScrollBar().setValue(int(tab.canvas.rects[1].y()));pump()
    assert tab.canvas.page==1 and tab.thumbnails.currentItem().data(Qt.UserRole)==1
    window.toggle_presentation();pump();assert window.presentation and not tab.navbar_host.isVisible()
    QTest.keyClick(tab.canvas,Qt.Key_Right);pump();assert tab.canvas.page==2
    QTest.keyClick(tab.canvas,Qt.Key_Left);pump();assert tab.canvas.page==1
    QTest.keyClick(tab.canvas,Qt.Key_Escape);pump();assert not window.presentation and window.menuBar().isVisible()
    tab.set_zoom(1.5);bar.setValue(150);tab.set_mode('hand')
    drag(tab,QPoint(300,300),QPoint(300,350));pump();assert bar.value()<150


def test_partial_text_highlight_author_sidebar_and_no_click_shape(ui,tmp_path):
    app,window,tab,pump=ui
    chars=tab.canvas.words[0]
    text=''.join(c[1] for c in chars);start=text.index('Select this text')+2
    chosen=chars[start:start+4]
    a=tab.canvas.page_rect(0,chosen[0][0]);b=tab.canvas.page_rect(0,chosen[-1][0])
    first=QPoint(int(a.left()+.1),int(a.center().y()));last=QPoint(int(b.right()-.1),int(b.center().y()))
    tab.pointer();drag(tab,first,last);tab.copy_text();assert app.clipboard().text()=='lect',(first,last,tab.canvas.scale,chosen,tab.canvas.word_selection)
    tab.set_panel('annotate');pump();tab.annot_author='Test Researcher';tab.set_mode('highlight')
    revision=tab.document.revision;drag(tab,first,last)
    pump(lambda:tab.document.revision>revision and not tab.busy and tab.annotation_list.count()==1)
    ann=tab.document.annotations(0)[0];assert ann['author']=='Test Researcher' and ann['own']
    assert ann['rect'][2]-ann['rect'][0]<40
    tab.set_mode('arrow');revision=tab.document.revision
    QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,point(tab,(100,300,100,300)));pump();assert tab.document.revision==revision
    drag(tab,point(tab,(100,300,100,300)),point(tab,(190,360,190,360)));pump(lambda:tab.document.revision>revision and not tab.busy)
    tab.document.add_annotation(0,'note',[(80,220),(80,220)],text='Check this result',author_name='Test Researcher')
    tab.load_annotations();pump(lambda:tab.annotation_list.count()==3)
    tab.select_annotation(next(a for a in tab.annotations_data if a['text']=='Check this result'));assert tab.annotation_text.toPlainText()=='Check this result'
    dest=tmp_path/'annotations.pdf';tab.document.save(dest)
    with fitz.open(dest) as pdf:assert len(list(pdf[0].annots()))==3
    tab.delete_annotation();pump(lambda:not tab.busy);assert len(tab.document.annotations(0))==2


def test_direct_object_edit_move_resize_delete_undo_save_reopen(ui,tmp_path):
    app,window,tab,pump=ui
    tab.set_panel('objects');pump(lambda:not tab.busy and tab.canvas.object_page==0)
    obj=next(o for o in tab.canvas.objects if o.text=='Signal amplitude')
    center=point(tab,obj.bbox)
    QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,center)
    QTest.mouseDClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,center);pump()
    assert tab.inline_editor is not None
    QTest.keyClicks(tab.inline_editor,'New signal label')
    QTest.keyClick(tab.inline_editor,Qt.Key_Return,Qt.ControlModifier)
    pump(lambda:not tab.busy and any(o.text=='New signal label' for o in tab.canvas.objects))
    assert '*' in window.tabs.tabText(window.tabs.currentIndex())
    new=next(o for o in tab.canvas.objects if o.text=='New signal label')
    center=point(tab,new.bbox);drag(tab,center,center+QPoint(22,15))
    pump(lambda:not tab.busy and any(o.text=='New signal label' and o.bbox[0]>new.bbox[0]+10 for o in tab.canvas.objects))
    image=next(o for o in tab.canvas.objects if o.kind=='image')
    QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,point(tab,image.bbox))
    handle=tab.canvas.resize_handle().center().toPoint();drag(tab,handle,handle+QPoint(30,10))
    pump(lambda:not tab.busy and any(o.kind=='image' and o.bbox[2]-o.bbox[0]>image.bbox[2]-image.bbox[0]+10 for o in tab.canvas.objects))
    new=next(o for o in tab.canvas.objects if o.text=='New signal label')
    QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,point(tab,new.bbox));QTest.keyClick(tab.canvas,Qt.Key_Delete)
    pump(lambda:not tab.busy and not any(o.text=='New signal label' for o in tab.canvas.objects))
    QTest.keyClick(tab.canvas,Qt.Key_Z,Qt.ControlModifier)
    pump(lambda:not tab.busy and any(o.text=='New signal label' for o in tab.canvas.objects))
    tab.turn_page(1);pump(lambda:not tab.busy and tab.canvas.object_page==1)
    assert not tab.canvas.selected
    tab.turn_page(-1);pump(lambda:not tab.busy and tab.canvas.object_page==0)
    dest=tmp_path/'edited.pdf';tab.document.save(dest);window.update_title()
    assert '*' not in window.tabs.tabText(window.tabs.currentIndex())
    reopened=Document(dest,tmp_path/'reopened')
    with fitz.open(reopened.path) as pdf:
        assert 'New signal label' in pdf[0].get_text() and 'Signal amplitude' not in pdf[0].get_text()
        assert len(pdf[0].get_images())>=1 and len(pdf[0].get_drawings())>=3
    reopened.close()


def test_crop_first_image_hit_and_merge_queue(ui,tmp_path,monkeypatch):
    app,window,tab,pump=ui
    picked=[];monkeypatch.setattr(tab,'save_image_xref',lambda page,xref:picked.append((page,xref)))
    tab.extract_embedded();pump(lambda:not tab.busy and tab.canvas.objects)
    image=tab.canvas.objects[0];QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,point(tab,image.bbox));assert not picked
    assert tab.image_list.selectedItems()
    tab.extract_selected_images();assert picked==[(0,image.xref)]
    monkeypatch.setattr(tab,'approve_limit',lambda *args:True)
    tab.page_tools('crop');tab.page_properties.inputs['keep'].setChecked(True);revision=tab.document.revision
    r=tab.canvas.rects[0];drag(tab,(r.topLeft()+QPointF(20,20)).toPoint(),(r.bottomRight()-QPointF(20,20)).toPoint())
    assert tab.document.revision==revision;tab.page_properties.apply_button.click()
    pump(lambda:not tab.busy and tab.document.revision>revision);assert tab.info['sizes'][0][0]<595
    dialog=MergeDialog(tab);dialog.show()
    dialog.add_files([tab.document.original,tab.document.original]);pump(lambda:not tab.queue.jobs)
    assert len(dialog.files())==2 and ('3 页' in dialog.list.item(0).text() or '3 pages' in dialog.list.item(0).text())
    item=dialog.list.takeItem(0);dialog.list.insertItem(1,item);dialog.list.setCurrentRow(0);dialog.remove();assert len(dialog.files())==1
    dialog.reject()


def test_unicode_paste_multiline_and_commit_on_page_change(ui,tmp_path,monkeypatch):
    import os
    from PySide6.QtGui import QFont,QFontDatabase
    app,window,tab,pump=ui
    families=QFontDatabase.families()
    family=next((f for f in ('Microsoft YaHei','Noto Sans CJK SC','PingFang SC') if f in families),None)
    if family is None:pytest.skip('No tested CJK system font installed on this host')
    tab.set_panel('objects');pump(lambda:not tab.busy and tab.canvas.object_page==0)
    obj=next(o for o in tab.canvas.objects if o.text=='Signal amplitude')
    center=point(tab,obj.bbox);QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,center);QTest.mouseDClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,center)
    tab.object_font.setCurrentFont(QFont(family));app.clipboard().setText('测量结果\nNew caption')
    QTest.keyClick(tab.inline_editor,Qt.Key_V,Qt.ControlModifier)
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.Cancel)
    assert not window.close_tab(window.tabs.currentIndex())
    assert tab.inline_editor and '测量结果' in tab.inline_editor.toPlainText()
    tab.goto(1)
    pump(lambda:tab.canvas.page==1 and not tab.busy and tab.canvas.object_page==1)
    tab.goto(0);pump(lambda:not tab.busy and tab.canvas.object_page==0)
    obj=next(o for o in tab.canvas.objects if '测量结果' in o.text)
    assert 'New caption' in obj.text
    center=point(tab,obj.bbox);QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,center);QTest.mouseDClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,center)
    app.clipboard().setText('Second caption');QTest.keyClick(tab.inline_editor,Qt.Key_V,Qt.ControlModifier)
    # Saving commits the active editor before writing the PDF.
    window.save_tab()
    pump(lambda:not tab.busy and not tab.document.dirty and tab.inline_editor is None)
    with fitz.open(tab.document.original) as pdf:
        assert 'Second caption' in pdf[0].get_text() and '测量结果' not in pdf[0].get_text()


def test_text_annotation_style_roundtrip(document,tmp_path):
    document.add_annotation(0,'freetext',[(40,300),(420,345)],text='科研批注 / Research note',fontname='china-s',fontsize=17,color=(.1,.2,.4),author_name='Researcher')
    ann=document.annotations(0)[0]
    document.change_annotation(0,ann['xref'],text='已修改 / Revised',fontsize=15,fontname='china-s',color=(.7,.1,.1))
    document.add_annotation(0,'arrow',[(90,350),(220,370)],width=3,opacity=.9,line_end=5,dashed=True,author_name='Researcher')
    target=tmp_path/'styled.pdf';document.save(target)
    with fitz.open(target) as pdf:
        page=pdf[0];items=list(page.annots())
        assert items[0].info['content']=='已修改 / Revised'
        assert items[1].line_ends==(0,5) and items[1].border['width']==3
        assert page.get_pixmap().width==595
