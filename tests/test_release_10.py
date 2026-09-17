"""1.0 practical workflows: scoped recolor, search, settings and sequential close."""
import io,json
import pymupdf as fitz
from PIL import Image
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QMessageBox
from asterpdf.core import Document
from asterpdf import colors
from asterpdf.preferences import apply_preferences
from asterpdf.tab import DocumentTab
from test_practical_ui import ui


def test_raster_multiple_pairs_region_save_search(tmp_path):
    path=tmp_path/'source.pdf';image=Image.new('RGB',(400,200),'red');image.paste((0,0,255),(200,0,400,200));buf=io.BytesIO();image.save(buf,format='PNG')
    with fitz.open() as pdf:
        page=pdf.new_page(width=400,height=300);page.insert_image((0,0,400,200),stream=buf.getvalue());page.insert_text((20,260),'Searchable source');pdf.new_page();pdf.save(path)
    doc=Document(path,tmp_path/'recovery')
    try:
        palette=colors.inventory(doc,0,region=(0,0,200,200));assert palette['images']==1 and len(palette['colors'])<=64
        assert max(palette['colors'],key=palette['colors'].get)==(1,0,0)
        colors.replace(doc,1,pairs=[((1,1,1),(.25,.5,.75))])
        with fitz.open(doc.path) as pdf:assert pdf[1].get_pixmap().pixel(10,10)==(63,127,191)
        doc.undo()
        pairs=[((1,0,0),(0,0,1)),((0,0,1),(0,1,0))]
        colors.replace(doc,0,images=True,pairs=pairs)
        with fitz.open(doc.path) as pdf:
            pix=pdf[0].get_pixmap();assert pix.pixel(50,50)==(0,0,255) and pix.pixel(300,50)==(0,255,0)
        doc.undo();colors.replace(doc,0,images=True,pairs=pairs,region=(20,20,100,100))
        saved=tmp_path/'saved.pdf';doc.save(saved)
        with fitz.open(saved) as pdf:
            pix=pdf[0].get_pixmap();assert pix.pixel(50,50)==(0,0,255) and pix.pixel(150,50)==(255,0,0) and pix.pixel(300,50)==(0,0,255)
            assert pdf[0].search_for('Searchable source') and len(pdf)==2
    finally:doc.close()


def test_gradient_palette_bounded_and_proportional(tmp_path):
    path=tmp_path/'gradient.pdf'
    with fitz.open() as pdf:
        p=pdf.new_page(width=500,height=400)
        for x in range(500):p.draw_rect((x,0,x+1,400),color=None,fill=(x/499,0,1-x/499))
        pdf.save(path)
    doc=Document(path,tmp_path/'recovery')
    try:
        data=colors.inventory(doc,0);assert 1<len(data['colors'])<=64 and data['estimated']
        assert sum(data['colors'].values())<=data['total']*1.001
    finally:doc.close()


def test_recolor_presets_boundary_settings(ui):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs)
    t.replace_colors();pane=t.color_properties;pump(lambda:pane.inputs['source'].count()>0)
    t.set_color_source((1,0,0));pane.add_pair();t.set_color_source((0,0,1));pane.add_pair();assert len(pane.pairs)==2
    pane.inputs['scheme_name'].setText('Two colors');pane.save_scheme();assert len(json.loads(w.settings.value('color/schemes'))['Two colors']['pairs'])==2
    t.replace_colors();pane=t.color_properties;pane.load_scheme();assert len(pane.pairs)==2
    t.canvas.region=(0,(50,50,200,200));pane.inputs['scope'].setCurrentIndex(3);pane.apply_colors();pump(lambda:not t.busy and not w.queue.jobs)
    assert t.canvas.color_boundary==(0,(50,50,200,200))
    pane.inputs['boundary'].setChecked(False);assert not t.canvas.show_color_boundary
    w.settings.setValue('animation/quality','native');w.settings.setValue('color/invert',True);w.settings.setValue('color/images',False);apply_preferences(w)
    assert w.quality_actions['native'].isChecked() and not w.quality_actions['auto'].isChecked()
    assert pane.inputs['invert'].isChecked() and not pane.inputs['images'].isChecked()
    w.change_language('en');assert w.settings_menu.title()=='Settings' and w.language_menu.title()=='语言/Language'


def test_new_text_search_navigation_overview(ui):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs)
    t.add_text(0,(150,430,150,430));t.inline_editor.insertPlainText('AsterFind AsterFind')
    t.search_input.setText('AsterFind');t.search();pump(lambda:t.inline_editor is None and not t.busy and not w.queue.jobs,timeout=40)
    assert t.results.count()==2 and t.document.search('AsterFind')
    first=t.canvas.active_search;t.search_step(1);assert t.canvas.active_search!=first and t.results.currentRow()==1
    t.search_step(1);assert t.canvas.active_search==first and t.results.currentRow()==0
    t.minimap.sync();assert t.minimap.reading_progress()>0 and t.canvas.search_hits
    t.goto(0);t.toggle_bookmark();assert t.bookmarks.item(0).text()=='1'
    t.minimap.grab()  # Paint search markers in the actual Qt widget.


def test_close_multiple_dirty_tabs_save_discard_cancel(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui
    second=Document(t.document.original,tmp_path/'other-recovery');other=DocumentTab(w,second,second.info());w.tabs.addTab(other,'other')
    t.document.page_operation('rotate',[0],angle=90);second.page_operation('rotate',[1],angle=90);t.refresh();other.refresh();pump(lambda:not w.queue.jobs)
    w.tabs.setCurrentWidget(w.welcome)
    seen=[]
    def cancel(*args):seen.append(w.current());return QMessageBox.Cancel
    monkeypatch.setattr(QMessageBox,'question',cancel);w.close();pump()
    assert seen==[other] and w.isVisible() and len(w.document_tabs())==2
    def respond(*args):
        current=w.current();seen.append(current)
        # Emulate a queued close during a modal prompt: must not reenter it.
        w.close()
        return QMessageBox.Save if current is t else QMessageBox.Discard
    monkeypatch.setattr(QMessageBox,'question',respond);w.close();pump(lambda:not w.isVisible() and not w.queue.jobs,timeout=40)
    assert seen==[other,other,t] and not w.document_tabs()
    with fitz.open(t.document.original) as pdf:assert pdf[0].rotation==90 and pdf[1].rotation==0
