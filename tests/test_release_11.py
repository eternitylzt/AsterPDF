"""1.1 workflows: real document mutations, inline controls and import/open events."""
import json
from pathlib import Path
import pymupdf as fitz
import pikepdf as pp
from PySide6.QtCore import Qt,QTimer,QPoint,QEvent
from PySide6.QtGui import QColor,QFileOpenEvent
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from asterpdf.core import Document
from asterpdf import figures,objects
from test_practical_ui import ui,drag,point

def test_home_customize_and_preferences_customize(ui,monkeypatch):
    app,w,t,pump=ui;w.tabs.setCurrentWidget(w.welcome)
    from asterpdf.dialogs import FormDialog
    shown=[]
    def accept(form):shown.append(form);return QDialog.Accepted
    monkeypatch.setattr(FormDialog,'exec',accept)
    w.customize_toolbar();assert len(shown)==1 and w.settings.contains('toolbar/tools')
    from asterpdf.preferences import Preferences
    from PySide6.QtWidgets import QPushButton
    settings=Preferences(w)
    next(b for b in settings.findChildren(QPushButton) if '自定义工具栏' in b.text() or 'Customize toolbar' in b.text()).click()
    assert len(shown)==2

def test_annotation_profiles_batch_and_replacement(ui,tmp_path):
    app,w,t,pump=ui;t.open_panel('annotate');pump(lambda:not t.busy and not w.queue.jobs)
    t.set_mode('arrow');pane=t.annotation_properties;pane.inputs['width'].setValue(4)
    t.set_mode('underline');assert t.annot_width==2
    t.set_mode('arrow');assert t.annot_width==4
    t.document.add_annotation(0,'arrow',[(80,180),(140,215)],author_name='AsterPDF',head_size=12)
    t.document.add_annotation(0,'rectangle',[(160,180),(220,230)])
    t.document.add_annotation(0,'ellipse',[(270,180),(320,230)])
    t.load_annotations();pump(lambda:len(t.annotations_data)==3)
    t.set_mode('select_annot');pump(lambda:not w.queue.jobs)
    for n in (0,1):t.annotation_list.item(n).setSelected(True)
    selected=[it.data(Qt.UserRole) for it in t.annotation_list.selectedItems()]
    t.show_annotation_properties('select_annot',selected);pane=t.annotation_properties;pane.inputs['width'].setValue(5);pane.inputs['opacity'].setValue(45)
    revision=t.document.revision;pane.apply_annotations();pump(lambda:not t.busy and not w.queue.jobs)
    assert t.document.revision==revision+1
    result=t.document.annotations(0);assert sum(abs(a['opacity']-.45)<.01 for a in result)==2
    t.document.add_annotation(0,'replace_text',[(70,90),(140,110)],word_rects=[(70,90,140,110)],text='replacement')
    anns=t.document.annotations(0);replacement=next(a for a in anns if a['type']=='ReplaceText');assert replacement['text']=='replacement' and replacement['related']
    target=tmp_path/'comments.pdf';t.document.save(target)
    with fitz.open(target) as pdf:assert any(a.type[1]=='Caret' and a.info['content']=='replacement' for a in pdf[0].annots())
    t.document.delete_annotations([replacement]);assert all(a['type']!='ReplaceText' for a in t.document.annotations(0))

def test_shape_palette_toggle_style_reopen(ui,tmp_path):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs);t.begin_vector_edit();pump(lambda:not t.busy and not w.queue.jobs)
    button=t.shape_buttons['ellipse'];button.click();assert t.canvas.mode=='draw_shape' and button.isChecked()
    button.click();assert t.canvas.mode=='objects' and not button.isChecked()
    button.click();t.shape_properties.inputs['dash'].setCurrentIndex(2);t.shape_properties.inputs['fill'].setChecked(True)
    drag(t,point(t,(300,450,300,450)),point(t,(420,500,420,500)));pump(lambda:not t.busy and not w.queue.jobs)
    assert t.canvas.selected and t.canvas.mode=='objects'
    t.shape_stroke.color=QColor('#ff0000');t.apply_shape_style();pump(lambda:not t.busy and not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:assert any(path.get('color')==(1.,0.,0.) and path.get('fill') is not None for path in pdf[0].get_drawings())

def test_scope_palette_explicit_pair_and_region_persistence(ui):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs);t.replace_colors();pane=t.color_properties
    pump(lambda:pane.inputs['source'].count()>0 and not w.queue.jobs)
    revision=t.document.revision;pane.apply_colors();pump();assert t.document.revision==revision
    pane.inputs['scope'].setCurrentIndex(3);assert t.canvas.mode=='region'
    t.selection_finished(0,[(50,70),(240,140)],'region');before=t.canvas.region
    QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,point(t,(280,300,280,300)));assert t.canvas.region==before
    pump(lambda:not w.queue.jobs);pane.add_pair();assert len(pane.pairs)==1
    t.quick_actions['region'].trigger();assert t.canvas.mode=='select'

def test_string_destination_import_md_and_preview_scroll(ui,tmp_path):
    app,w,t,pump=ui;assert t.activate_link({'kind':4,'page':'2','view':'Fit'}) and t.canvas.page==1
    t.minimap.percent=20;t.minimap.auto_scale=False;t.minimap.auto_size=False;t.minimap.resize(130,150);t.minimap.sync();assert t.minimap.rail.maximum()>0
    t.minimap.rail.setValue(t.minimap.rail.maximum());assert t.minimap.offset>0
    t.organizer_zoom.setValue(8);assert t.organizer.iconSize().width()<120
    md=tmp_path/'sample.md';md.write_text('# Research\n\n**Bold** text and 中文.\n\n- Item one\n- Item two',encoding='utf8')
    w.open_file(md);assert w.tabs.currentWidget() is not w.welcome
    pump(lambda:not w.opening and not w.queue.jobs)
    imported=w.current();assert imported.document.original==str(md.resolve())
    with fitz.open(imported.document.path) as pdf:
        if app.platformName()=='offscreen':assert pdf[0].get_drawings() or 'Research' in pdf[0].get_text()  # Offscreen Qt may use outline-only fonts.
        else:assert 'Research' in pdf[0].get_text()
    saved=tmp_path/'markdown.pdf';imported.document.save(saved);assert saved.is_file() and md.read_text(encoding='utf8').startswith('# Research')

def test_copy_paste_preserves_visual_position(document,tmp_path):
    from asterpdf.object_clipboard import copy_pdf,paste_pdf
    found=objects.discover(document,0);chosen=[o for o in found if o.kind=='text' and 'AsterPDF' in o.text][:1];assert chosen
    
    with fitz.open(document.path) as pdf:source=tuple(pdf[0].search_for('AsterPDF')[0])
    payload=copy_pdf(document,0,chosen);paste_pdf(document,1,payload)
    with fitz.open(document.path) as pdf:
        hits=pdf[1].search_for('AsterPDF');assert hits
        assert min(abs(r.x0-source[0])+abs(r.y0-source[1]) for r in hits)<3

def test_video_embedding_and_reopen(document,tmp_path):
    from asterpdf.video_insert import insert
    from asterpdf.media import scan,extract_media
    # Container payload integrity only; actual decoding is separately tested with a valid clip.
    clip=tmp_path/'video.mp4';clip.write_bytes(b'\x00\x00\x00\x18ftypisomfixture-container')
    insert(document,0,(70,200,260,310),clip)
    _,assets,_=scan(document);asset=next(a for a in assets if a.name=='video.mp4')
    assert max(abs(a-b) for a,b in zip(asset.rect,(70,200,260,310)))<.1
    assert Path(extract_media(document,asset)).read_bytes()==clip.read_bytes()

def test_tex_metadata_display_preserves_real_title():
    from asterpdf.metadata_display import readable
    assert readable('Research title [5pt] ` `%%%garbled')=='Research title'
    assert readable('陈俊[5pt]Institute')=='陈俊\nInstitute'
    assert readable('An ordinary [title]')=='An ordinary [title]'

def test_unrelated_preferences_preserve_active_annotation_style(ui):
    from asterpdf.preferences import apply_preferences
    app,w,t,pump=ui;t.open_panel('annotate');t.set_mode('arrow');pump(lambda:not w.queue.jobs)
    t.annotation_properties.inputs['width'].setValue(4.5);color=t.annot_color.name();revision=t.document.revision
    apply_preferences(w,{'home/recent'});pump(lambda:not w.queue.jobs)
    assert t.annot_width==4.5 and t.annot_color.name()==color and t.document.revision==revision

def test_note_popup_and_replacement_links_survive_style_edit(document):
    document.add_annotation(0,'note',[(40,220),(40,220)],text='before')
    note=next(a for a in document.annotations(0) if a['type']=='Text')
    document.change_annotations([(note,dict(text='after',fontsize=14,color=(0,0,1)))])
    with pp.open(document.path) as pdf:
        items=list(pdf.pages[0].obj.Annots);note=next(a for a in items if a.Subtype==pp.Name('/Text'))
        assert str(note.Contents)=='after' and note.Popup.Parent.objgen==note.objgen
        assert note.Popup.objgen in [a.objgen for a in items]
    document.add_annotation(0,'replace_text',[(80,90),(140,110)],word_rects=[(80,90,140,110)],text='new text')
    group=next(a for a in document.annotations() if a['type']=='ReplaceText')
    document.change_annotations([(group,dict(text='edited replacement',color=(1,0,0)))])
    assert next(a for a in document.annotations() if a['type']=='ReplaceText')['text']=='edited replacement'

def test_pointer_image_copy_paste_preserves_bounds_and_panel(ui):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not w.queue.jobs);t.choose_insert_image();pump(lambda:not w.queue.jobs)
    obj=next(o for o in objects.discover(t.document,0) if o.kind=='image');t.copy_image(obj);pump(lambda:not w.queue.jobs)
    pane=t.image_properties;revision=t.document.revision;t.paste(True);pump(lambda:not t.busy and not w.queue.jobs)
    assert t.document.revision>revision and t.image_properties is pane and t.edit_tool=='image'
    with fitz.open(t.document.path) as pdf:
        bounds=pdf[0].get_image_info()[-1]['bbox']
        assert max(abs(a-b) for a,b in zip(bounds,obj.bbox))<.1
    app.clipboard().clear()
