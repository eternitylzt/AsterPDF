"""Media-layer persistence and real overlap/selection/playback workflows."""
from pathlib import Path
import pytest
import pikepdf as pp
import pymupdf as fitz
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from asterpdf import media,video_insert,objects
from asterpdf.core import Document
from test_practical_ui import ui


@pytest.mark.parametrize('subtype',['Screen','Movie','RichMedia'])
def test_media_layers_preserve_streams_and_page_content(document,tmp_path,subtype):
    clip=tmp_path/'clip.mp4';clip.write_bytes(b'\x00\x00\x00\x18ftypisomfixture-container')
    video_insert.insert(document,0,(50,50,250,170),clip)
    first=media.scan(document)[1][0]
    def convert(pdf):
        ann=pdf.get_object((first.annotation_xref,0));fs=ann.A.R.C.D
        if subtype=='Movie':ann.Subtype=pp.Name('/Movie');ann.Movie=pp.Dictionary(F=fs);del ann.A
        elif subtype=='RichMedia':ann.Subtype=pp.Name('/RichMedia');ann.RichMediaContent=pp.Dictionary(Assets=pp.Dictionary(Names=pp.Array(['clip.mp4',fs])));del ann.A
    document.edit('existing media variant',convert)
    video_insert.insert(document,0,(80,80,280,200),clip)
    assets=media.scan(document)[1];selected=assets[0];name=selected.annotation_name
    with pp.open(document.path) as pdf:before=[objects.content_bytes(p) for p in pdf.pages]
    with fitz.open(document.path) as pdf:words=[p.get_text('words') for p in pdf]
    video_insert.set_stacking(document,selected,True)
    assets=media.scan(document)[1];assert assets[-1].annotation_name==name
    target=tmp_path/'saved.pdf';document.save(target)
    with pp.open(target) as pdf:
        assert [objects.content_bytes(p) for p in pdf.pages]==before
        ann=pdf.pages[0].Annots[-1];assert str(ann.Subtype)=='/'+subtype
    with fitz.open(target) as pdf:assert [p.get_text('words') for p in pdf]==words
    assert all(Path(media.extract_media(document,a)).read_bytes()==clip.read_bytes() for a in assets)
    video_insert.set_stacking(document,assets[-1],False)
    assert media.scan(document)[1][0].annotation_name==name
    document.undo();assert media.scan(document)[1][-1].annotation_name==name


def test_video_selection_layer_and_playback(ui,tmp_path):
    app,w,t,pump=ui
    source=Document(Path(__file__).parents[1]/'examples'/'AsterPDF-media.pdf',tmp_path/'source-recovery')
    try:
        asset=media.scan(source)[1][0];original=Path(media.extract_media(source,asset)).read_bytes()
    finally:source.close()
    for name,rect in [('back.mp4',(50,150,300,300)),('front.mp4',(150,170,400,320))]:
        path=tmp_path/name;path.write_bytes(original);video_insert.insert(t.document,0,rect,path)
    t.refresh();t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs)
    video_insert.pane(t);pump(lambda:not t.busy and not w.queue.jobs)
    assert t.video_list.count()==2
    pos=t.canvas.page_rect(0,(170,200,170,200)).center().toPoint()
    QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,pos)
    assert t.selected_media.name=='front.mp4'
    t.video_list.setCurrentRow(1);assert t.selected_media.name=='back.mp4'
    t.stack_media(t.selected_media,True);pump(lambda:not t.busy and not w.queue.jobs)
    assert t.assets[-1].name=='back.mp4' and t.video_list.currentRow()==0
    t.close_properties();t.open_panel('read')
    for asset in t.assets:t.open_media(asset)
    pump(lambda:len(t.video_players)==2 and all(p.actual_video_frames>=2 for p in t.video_players))
    front=next(p for p in t.video_players if p.asset.name=='back.mp4')
    back=next(p for p in t.video_players if p.asset.name=='front.mp4')
    overlap=t.canvas.page_rect(0,(180,220,180,220)).center().toPoint()
    assert not back.mask().contains(overlap-back.pos()) and front.mask().contains(overlap-front.pos())
    t.stack_media(front.asset,False);pump(lambda:not t.busy and not w.queue.jobs)
    assert t.assets[0].name=='back.mp4' and front.player.source().isLocalFile()
    assert front.mask().contains((t.canvas.page_rect(0,(80,180,80,180)).center().toPoint()-front.pos()))
    assert not front.mask().contains(overlap-front.pos())
    front.toggle();pump(lambda:front.actual_video_frames>2)
    for player in t.video_players:player.shutdown()
