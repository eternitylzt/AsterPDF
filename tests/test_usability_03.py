"""0.3 everyday workflows: no-op editing, home merging, images and defaults."""
import hashlib
import re
import time
from pathlib import Path
import pymupdf as fitz
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTabBar,QLabel,QDialog,QFileDialog,QInputDialog
from asterpdf import i18n,objects
from asterpdf.core import Document,merge_files
from asterpdf.dialogs import MergeDialog,FormDialog
from test_practical_ui import ui,point,drag

def test_missing_font_noop_click_away_delete_move(ui,monkeypatch,tmp_path):
    app,w,t,pump=ui
    import asterpdf.tab as module
    t.set_panel('objects');pump(lambda:not t.busy and bool(t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text=='Signal amplitude');obj.details['family']='AbsentFontABC'
    before=t.document.path.read_bytes();revision=t.document.revision
    def forbidden(*args):raise AssertionError('Font must not be consulted without text changes')
    monkeypatch.setattr(module,'font_bytes',forbidden)
    t.start_inline(obj);assert not t.inline_dirty()
    QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,point(t,(20,400,20,400)));pump()
    assert t.inline_editor is None and t.document.revision==revision and t.document.path.read_bytes()==before
    t.canvas.selected=[obj.id];t.move_objects(5,8);pump(lambda:not t.busy and t.document.revision>revision and any(o.text=='Signal amplitude' for o in t.canvas.objects))
    obj=next(o for o in t.canvas.objects if o.text=='Signal amplitude')
    t.start_inline(obj);QTest.keyClick(t.inline_editor,Qt.Key_Backspace)
    QTest.keyClick(t.inline_editor,Qt.Key_Return,Qt.ControlModifier)
    pump(lambda:not t.busy and not any(o.text=='Signal amplitude' for o in t.canvas.objects))
    target=tmp_path/'deleted.pdf';t.document.save(target)
    with fitz.open(target) as pdf:assert 'Signal amplitude' not in pdf[0].get_text()

def test_home_merge_open_snapshot_reorder_and_sources_unchanged(ui,tmp_path):
    app,w,t,pump=ui
    home=w.tabs.indexOf(w.welcome)
    assert all(w.tabs.tabBar().tabButton(home,side) is None for side in (QTabBar.LeftSide,QTabBar.RightSide))
    original=Path(t.document.original);original_hash=hashlib.sha256(original.read_bytes()).digest()
    t.document.add_annotation(0,'note',[(50,100),(50,100)],text='Unsaved merge note')
    dialog=MergeDialog(w,include_open=True);dialog.show();dialog.add_files([str(original)])
    pump(lambda:not w.queue.jobs)
    assert dialog.files()[0]==str(t.document.path) and '*' in dialog.list.item(0).text()
    first=dialog.list.takeItem(0);dialog.list.insertItem(1,first)
    target=tmp_path/'merged.pdf';merge_files(dialog.files(),target)
    with fitz.open(target) as pdf:
        assert len(pdf)==6
        assert any(a.info['content']=='Unsaved merge note' for a in pdf[3].annots())
    assert hashlib.sha256(original.read_bytes()).digest()==original_hash
    dialog.reject()

def test_region_click_clears_and_persistent_export_settings(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui
    t.set_mode('region');drag(t,point(t,(40,60,40,60)),point(t,(190,140,190,140)))
    assert t.canvas.region
    QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,point(t,(250,300,250,300)));assert t.canvas.region is None
    def choose():
        dialog=app.activeModalWidget();assert isinstance(dialog,FormDialog)
        dialog.inputs['dpi'].setValue(144);dialog.inputs['width'].setValue(0);dialog.inputs['quality'].setValue(88);dialog.accept()
    QTimer.singleShot(50,choose);w.export_settings();assert w.export_options()['dpi']==144
    w.settings.sync();assert w.settings.value('export/quality',type=int)==88
    t.canvas.region=(0,(40,60,190,140));t.copy_region();pump(lambda:not t.busy)
    assert app.clipboard().image().width()==300
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(tmp_path/'region.png'),'PNG (*.png)'))
    def no_prompt(*a,**kw):raise AssertionError('DPI should not be requested during export')
    monkeypatch.setattr(QInputDialog,'getInt',no_prompt)
    t.export_images(True);pump(lambda:not t.busy)
    assert any(p.suffix=='.png' for p in tmp_path.iterdir())

def test_image_sidebar_overlap_multiselect_empty_page(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui
    # Add a second image at the same position: the sidebar must reach both layers.
    with fitz.open(t.document.path) as pdf:
        img=pdf.extract_image(pdf[0].get_images()[0][0]);rect=pdf[0].get_image_rects(pdf[0].get_images()[0][0])[0]
    source=tmp_path/'raster.png';pix=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,24,24),False);pix.clear_with(120);pix.save(source)
    t.document.insert_image(0,tuple(rect),source)
    t.extract_embedded();pump(lambda:not t.busy and t.image_list.count()>=2)
    t.image_list.setCurrentRow(0);assert t.canvas.selected==[t.image_list.item(0).data(Qt.UserRole)[1]]
    t.image_list.item(1).setSelected(True);assert len(t.canvas.selected)==2
    picked=[];monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
    t.extract_selected_images();pump(lambda:not t.busy)
    assert len(list(tmp_path.glob('page-001-image-*')))>=2
    obj=t.canvas.objects[0];QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,point(t,obj.bbox))
    assert t.image_list.selectedItems()
    t.goto(1);pump(lambda:not t.busy and t.image_revision==(1,t.document.revision))
    assert t.image_list.count()==0 and ('没有' in t.image_hint.text() or 'No extractable' in t.image_hint.text())

def test_closed_arrow_has_solid_fill_and_labels(ui,tmp_path):
    app,w,t,pump=ui
    t.annot_color.setRgbF(.8,.15,.1);t.annot_width=4;t.set_mode('arrow')
    t.add_annotation(0,'arrow',[(80,330),(230,370)]);pump(lambda:not t.busy)
    target=tmp_path/'arrow.pdf';t.document.save(target)
    with fitz.open(target) as pdf:
        page=pdf[0];arrow=list(page.annots())[-1]
        assert arrow.line_ends==(0,5) and arrow.colors['fill']==arrow.colors['stroke']
    labels=[x.text() for x in t.tool_panels.findChildren(QLabel)]
    assert i18n.tr('width') in labels and i18n.tr('opacity') in labels

def test_ui_english_language_is_not_bilingual(ui):
    app,w,t,pump=ui
    w.change_language('en');pump(lambda:not w.queue.jobs)
    tab=w.current();tab.set_panel('objects');pump(lambda:not tab.busy)
    assert tab.sidebar.tabText(0)=='Pages'
    for action in w.menuBar().actions():assert not re.search('[\u4e00-\u9fff]',action.text())
    for label in w.findChildren(QLabel):
        if label.isVisible():assert not re.search('[\u4e00-\u9fff]',label.text()),label.text()
    assert all(not re.search('[\u4e00-\u9fff]',a.text()) for a in tab.tools.actions())
    w.change_language('zh');pump(lambda:not w.queue.jobs)
    assert w.current().sidebar.tabText(0)=='页面'
