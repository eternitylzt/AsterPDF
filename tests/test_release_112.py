"""1.1.2 workflows: scoped ink, sequential pairs, menus and retained page previews."""
import io
from pathlib import Path
import pymupdf as fitz
from PIL import Image
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtGui import QColor,QCloseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu,QFileDialog,QMessageBox
from asterpdf.core import Document
from asterpdf import colors,objects
from test_practical_ui import ui


def choose_next_popup(app,seen,index=0):
    def choose():
        menu=app.activePopupWidget()
        if not isinstance(menu,QMenu):QTimer.singleShot(20,choose);return
        seen.append([action.text() for action in menu.actions()]);action=menu.actions()[index]
        menu.close();action.trigger()
    QTimer.singleShot(20,choose)


def test_region_black_text_image_and_sequential_pairs(tmp_path):
    path=tmp_path/'ink.pdf';buf=io.BytesIO();Image.new('RGB',(20,20),'black').save(buf,format='PNG')
    with fitz.open() as pdf:
        page=pdf.new_page(width=300,height=200)
        page.insert_text((20,35),'Small black ink',fontsize=8)
        page.insert_text((160,35),'Outside unchanged',fontsize=8)
        page.insert_image((20,60,60,100),stream=buf.getvalue())
        page.draw_rect((80,70,130,110),color=None,fill=(0,0,0));pdf.save(path)
    doc=Document(path,tmp_path/'recovery');region=(10,10,140,120)
    try:
        assert (0,0,0) in colors.inventory(doc,0,region)['colors']
        with fitz.open(doc.path) as pdf:before=pdf[0].get_pixmap(matrix=fitz.Matrix(2,2))
        colors.replace(doc,0,pairs=[((0,0,0),(1,0,0))],images=True,region=region)
        saved=tmp_path/'saved.pdf';doc.save(saved)
        with fitz.open(saved) as pdf:
            pix=pdf[0].get_pixmap(matrix=fitz.Matrix(2,2));im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            ink=im.crop((40,48,270,72))
            assert sum(1 for r,g,b in ink.getdata() if r>180 and g<100 and b<100)>30
            assert pix.pixel(60,150)==(255,0,0) and pix.pixel(200,160)==(255,0,0)
            original=Image.frombytes('RGB',(before.width,before.height),before.samples)
            assert im.crop((300,0,600,400)).tobytes()==original.crop((300,0,600,400)).tobytes()
            assert pdf[0].search_for('Small black ink')
        doc.undo()
        colors.replace(doc,0,pairs=[((0,0,0),(1,0,0)),((1,0,0),(0,0,0))],images=True,region=region)
        with fitz.open(doc.path) as pdf:assert pdf[0].get_pixmap(matrix=fitz.Matrix(2,2)).samples==before.samples
    finally:doc.close()


def test_selected_pairs_keep_list_order(ui,monkeypatch):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs)
    t.replace_colors();pane=t.color_properties;pump(lambda:pane.inputs['source'].count()>0)
    pairs=[((1,0,0),(0,0,1)),((0,1,0),(1,0,0)),((0,0,1),(1,0,0))]
    for source,target in pairs:
        t.set_color_source(source);t.color_target.color=QColor.fromRgbF(*target);pane.add_pair()
    calls=[];monkeypatch.setattr(colors,'replace',lambda *args,**kwargs:calls.append(kwargs['pairs']))
    pane.apply_selected_pairs.setChecked(True)
    pane.pair_list.item(2).setSelected(True);pane.pair_list.item(0).setSelected(True)
    pane.apply_colors();pump(lambda:not t.busy and not w.queue.jobs)
    assert calls[-1]==[list(pairs[0]),list(pairs[2])]
    pane.apply_all_pairs.setChecked(True);pane.apply_colors();pump(lambda:not t.busy and not w.queue.jobs)
    assert calls[-1]==[list(p) for p in pairs]


def test_text_and_vector_stacking_preserves_content(tmp_path):
    path=tmp_path/'layers.pdf'
    with fitz.open() as pdf:
        p=pdf.new_page(width=250,height=150);p.insert_text((40,65),'Layered text',fontsize=18,color=(0,0,.8))
        p.draw_rect((30,35,190,85),color=None,fill=(1,.5,0));pdf.save(path)
    doc=Document(path,tmp_path/'recovery')
    try:
        with fitz.open(doc.path) as pdf:words=pdf[0].get_text('words');before=pdf[0].get_pixmap().samples
        text=next(o for o in objects.discover(doc,0) if o.kind=='text');objects.set_stacking(doc,0,[text],True)
        with fitz.open(doc.path) as pdf:
            assert pdf[0].get_text('words')==words and pdf[0].get_pixmap().samples!=before
            assert pdf[0].get_bboxlog()[-1][0]=='fill-text'
        shape=next(o for o in objects.discover(doc,0) if o.kind=='vector');objects.set_stacking(doc,0,[shape],True)
        with fitz.open(doc.path) as pdf:assert pdf[0].get_pixmap().samples==before and pdf[0].get_text('words')==words
        doc.undo();doc.undo()
        with fitz.open(doc.path) as pdf:assert pdf[0].get_pixmap().samples==before
    finally:doc.close()


def test_text_layer_after_inline_change(ui):
    from PySide6.QtGui import QTextCursor
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs)
    obj=next(o for o in t.canvas.objects if o.kind=='text' and not o.reason)
    t.canvas.selected=[obj.id];t.start_inline(obj)
    t.inline_editor.moveCursor(QTextCursor.End);t.inline_editor.insertPlainText(' layer')
    t.stack_images(True);pump(lambda:t.document.revision==2 and not t.busy and not w.queue.jobs)
    assert t.inline_editor is None
    with fitz.open(t.document.path) as pdf:
        assert 'layer' in pdf[0].get_text() and pdf[0].get_bboxlog()[-1][0]=='fill-text'


def test_animation_right_click_saves_and_opens_controls(ui,monkeypatch,tmp_path):
    app,w,t,pump=ui;assert t.animations
    a=t.animations[0];t.goto(a.page);pump(lambda:not w.queue.jobs)
    pos=t.canvas.page_rect(a.page,a.rect).center().toPoint();out=tmp_path/'animation.zip';menus=[]
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(out),'ZIP (*.zip)'))
    choose_next_popup(app,menus)
    QTest.mouseClick(t.canvas,Qt.RightButton,Qt.NoModifier,pos);pump(lambda:not t.busy and not w.queue.jobs)
    assert out.exists() and len(menus)==1 and len(menus[0])==2
    choose_next_popup(app,menus,1);QTest.mouseClick(t.canvas,Qt.RightButton,Qt.NoModifier,pos);pump()
    assert t.playback_panel.isVisible()


def test_image_sidebar_copy_menu(ui,monkeypatch):
    app,w,t,pump=ui;t.open_panel('extract');t.extract_embedded();pump(lambda:not t.busy and not w.queue.jobs)
    assert t.image_list.count();seen=[]
    choose_next_popup(app,seen);app.clipboard().clear()
    t.image_list_menu(t.image_list.visualItemRect(t.image_list.item(0)).center());pump(lambda:not t.busy and not w.queue.jobs)
    assert seen and not app.clipboard().image().isNull()


def test_video_surface_right_click_extracts_original(ui,monkeypatch,tmp_path):
    from asterpdf.tab import DocumentTab
    from asterpdf.media import extract_media
    app,w,t,pump=ui;source=Path(__file__).parents[1]/'examples'/'AsterPDF-media.pdf'
    doc=Document(source,tmp_path/'video-recovery');video_tab=DocumentTab(w,doc,doc.info())
    w.tabs.addTab(video_tab,'Video');w.tabs.setCurrentWidget(video_tab)
    try:
        pump(lambda:bool(video_tab.assets) and not w.queue.jobs)
        asset=video_tab.assets[0];video_tab.goto(asset.page);video_tab.open_media(asset)
        pump(lambda:bool(video_tab.video_players) and video_tab.video_players[0].actual_video_frames>=2)
        player=video_tab.video_players[0];out=tmp_path/'saved.mp4';menus=[]
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(out),'Media (*.mp4)'))
        choose_next_popup(app,menus)
        QTest.mouseClick(player.video,Qt.RightButton,Qt.NoModifier,player.video.rect().center());pump(lambda:not video_tab.busy and not w.queue.jobs)
        assert out.read_bytes()==Path(extract_media(doc,asset)).read_bytes() and len(menus)==1
        choose_next_popup(app,menus,1);QTest.mouseClick(player.video,Qt.RightButton,Qt.NoModifier,player.video.rect().center());pump()
        assert video_tab.playback_panel.isVisible() and len(menus)==2
    finally:
        video_tab.closed=True;video_tab.pause_media()
        for player in video_tab.video_players:player.shutdown()
        w.tabs.removeTab(w.tabs.indexOf(video_tab));video_tab.deleteLater();pump(lambda:not w.queue.jobs);doc.close()


def test_page_operations_retain_other_previews(ui,monkeypatch):
    app,w,t,pump=ui;t.open_panel('pages');pump(lambda:not t.busy and not w.queue.jobs)
    before=[t.organizer.item(i) for i in range(t.organizer.count())]
    icons=[it.icon().cacheKey() for it in before]
    monkeypatch.setattr(t,'refresh',lambda:(_ for _ in ()).throw(AssertionError('Full refresh')))
    monkeypatch.setattr(t.canvas,'invalidate',lambda:(_ for _ in ()).throw(AssertionError('All tiles invalidated')))
    t.organizer.clearSelection();before[0].setSelected(True);t.page_selection_operation('rotate',t.organizer)
    pump(lambda:not t.busy and not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:assert pdf[0].rotation==90
    assert t.organizer.item(1) is before[1] and t.organizer.item(1).icon().cacheKey()==icons[1]
    order=[2,0,1];t.reorder(order);pump(lambda:not t.busy and not w.queue.jobs)
    assert all(t.organizer.item(n) is before[old] for n,old in enumerate(order))
    with fitz.open(t.document.path) as pdf:assert pdf[1].rotation==90 and pdf[0].rotation==0
    t.organizer.clearSelection();t.organizer.item(1).setSelected(True);t.page_selection_operation('delete',t.organizer)
    pump(lambda:not t.busy and not w.queue.jobs)
    assert t.organizer.count()==2 and t.organizer.item(0) is before[2] and t.organizer.item(1) is before[1]


def test_markdown_html_table_and_linked_images(ui,tmp_path,monkeypatch):
    from PySide6 import QtPrintSupport
    def no_system_printer(*args,**kwargs):raise AssertionError("Markdown must not initialize a system printer")
    monkeypatch.setattr(QtPrintSupport,"QPrinter",no_system_printer)
    from asterpdf.markdown_import import prepare,render
    Image.new('RGB',(60,40),'red').save(tmp_path/'figure.png')
    (tmp_path/'logo.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40"><rect width="100" height="40" fill="blue"/></svg>')
    source=tmp_path/'README.md';source.write_text('# Complete README\n\nBefore table\n\n<table><tr><td><img src="figure.png" width="100"></td><td><img src="logo.svg" width="100"></td></tr></table>\n\n## After table\n\nBody survives HTML and `code`.\n\n|Feature|Status|\n|---|---|\n|Images|Working|\n\n![Missing](missing.png)\n',encoding='utf8')
    data=prepare(source);assert len(data[1])==2 and data[2]==['missing.png']
    result=tmp_path/'README.pdf';render(source,result,data)
    with fitz.open(result) as pdf:
        text=''.join(p.get_text() for p in pdf)
        assert all(word in text for word in ('Complete README','Before table','After table','survives','Working','Image unavailable'))
        assert sum(len(p.get_images()) for p in pdf)>=2


def test_single_document_close_skips_choice_keeps_unsaved_prompt(ui,monkeypatch):
    app,w,t,pump=ui;t.document.page_operation('rotate',[0]);called=[]
    monkeypatch.setattr(QMessageBox,'exec',lambda *_:(_ for _ in ()).throw(AssertionError('Unexpected current/all choice')))
    monkeypatch.setattr(QMessageBox,'question',lambda *args:(called.append(args),QMessageBox.Cancel)[1])
    event=QCloseEvent();w.closeEvent(event);pump()
    assert called and not event.isAccepted() and t in w.document_tabs() and not w._closing_all
