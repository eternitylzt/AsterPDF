"""Standard embedded Screen/Rendition video annotations (no JavaScript)."""
from pathlib import Path
import uuid
import pikepdf as pp
from .objects import content_bytes,commands


def set_stacking(document,asset,front=True):
    """Reorder the original media annotation; preserve its rendition and streams."""
    token=asset.annotation_name or 'AsterPDF-media-'+uuid.uuid4().hex
    def mutate(pdf):
        page=pdf.pages[asset.page];annotations=list(page.obj.get('/Annots',[]))
        chosen=next((a for a in annotations if a.objgen[0]==asset.annotation_xref),None)
        if chosen is None or str(chosen.get('/Subtype','')) not in ('/Screen','/RichMedia','/Movie','/Sound'):
            raise ValueError('Select the media again before arranging it.')
        chosen.NM=pp.String(token)
        remaining=[a for a in annotations if a.objgen!=chosen.objgen]
        page.obj.Annots=pp.Array(remaining+[chosen] if front else [chosen]+remaining)
    document.edit('bring media to front' if front else 'send media to back',mutate)
    return token


def refresh_selection(tab,rebuild=True):
    """Rebind selections and live players after pikepdf renumbers saved objects."""
    def match(old):
        if old is None:return None
        return next((a for a in tab.assets if a.page==old.page and a.annotation_name and a.annotation_name==old.annotation_name),None) or next((a for a in tab.assets if (a.page,a.name,a.rect)==(old.page,old.name,old.rect)),None)
    tab.selected_media=match(getattr(tab,'selected_media',None))
    for player in tab.video_players:
        replacement=match(player.asset)
        if replacement:player.asset=replacement
    listing=getattr(tab,'video_list',None)
    if listing is not None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem
        listing.blockSignals(True)
        if rebuild:
            listing.clear()
            for asset in reversed(tab.assets):
                item=QListWidgetItem(f'{asset.page+1} · {asset.name}');item.setData(Qt.UserRole,asset);listing.addItem(item)
        for n in range(listing.count()):
            if listing.item(n).data(Qt.UserRole)==tab.selected_media:listing.setCurrentItem(listing.item(n))
        listing.blockSignals(False)
    tab.position_video();tab.canvas.update()

def insert(document,page,rect,filename,replacing=None):
    box=document.to_pdf_rect(page,rect);name=Path(filename).name;data=Path(filename).read_bytes()
    def mutate(pdf):
        dst=pdf.pages[page]
        if replacing is not None:
            if replacing.start==replacing.end:raise ValueError('This image occurrence cannot be replaced safely.')
            dst.Contents=pdf.make_stream(b'\n'.join(c.raw for c in commands(content_bytes(dst)) if not (c.op=='Do' and replacing.start<=c.start and c.end<=replacing.end)))
        stream=pdf.make_stream(data);stream.Type=pp.Name('/EmbeddedFile')
        spec=pdf.make_indirect(pp.Dictionary(Type=pp.Name('/Filespec'),F=pp.String(name),UF=pp.String(name),EF=pp.Dictionary(F=stream,UF=stream)))
        mime={'.mp4':'video/mp4','.mov':'video/quicktime','.webm':'video/webm','.m4v':'video/mp4'}.get(Path(filename).suffix.lower(),'video/mp4')
        clip=pp.Dictionary(Type=pp.Name('/MediaClip'),S=pp.Name('/MCD'),CT=pp.String(mime),D=spec,P=pp.Dictionary(TF=pp.String('TEMPACCESS')))
        ann=pdf.make_indirect(pp.Dictionary(Type=pp.Name('/Annot'),Subtype=pp.Name('/Screen'),Rect=pp.Array(box),P=dst.obj,F=4,T=pp.String('AsterPDF'),NM=pp.String('AsterPDF-video-'+uuid.uuid4().hex),Contents=pp.String(name)))
        ann.A=pp.Dictionary(S=pp.Name('/Rendition'),OP=0,AN=ann,R=pp.Dictionary(S=pp.Name('/MR'),N=pp.String(name),C=clip))
        w=box[2]-box[0];h=box[3]-box[1]
        ap=pdf.make_stream(f'q .08 .12 .18 rg 0 0 {w:g} {h:g} re f .85 .9 1 rg {w*.42:g} {h*.3:g} m {w*.42:g} {h*.7:g} l {w*.68:g} {h*.5:g} l h f Q'.encode());ap.Type=pp.Name('/XObject');ap.Subtype=pp.Name('/Form');ap.BBox=pp.Array([0,0,w,h]);ap.Resources=pp.Dictionary();ann.AP=pp.Dictionary(N=ap)
        dst.obj.Annots=pp.Array(list(dst.obj.get('/Annots',[]))+[ann])
    document.edit('insert video',mutate)

def pane(tab):
    from PySide6.QtWidgets import QPushButton,QLabel,QFileDialog,QListWidget
    from PySide6.QtCore import Qt
    from .i18n import L,tr
    form=tab.property_pane(tr('add_video'));tab.edit_tool='video';tab.set_mode('objects')
    form.form.addRow(QLabel(L('文档中的媒体 · 顶层在前','Document media · front first')))
    listing=QListWidget();listing.setMaximumHeight(135);form.form.addRow(listing);tab.video_list=listing
    listing.currentItemChanged.connect(lambda item,old:tab.select_media(item.data(Qt.UserRole)) if item else None)
    for label,front in [(L('置于顶层','Bring to front'),True),(L('置于底层','Send to back'),False)]:
        button=QPushButton(label);button.clicked.connect(lambda checked=False,f=front:tab.stack_media(getattr(tab,'selected_media',None),f));form.form.addRow(button)
    form.note(L('可点选视频画面，也可在列表选择被遮挡的媒体。调整同页媒体批注的叠放顺序；交互播放层位于正文内容之上。','Click a video or select covered media in the list. Arrange media annotations on the page; interactive playback remains above page content.'))
    refresh_selection(tab)
    name=QLabel(L('选择本地视频','Choose a local video'));name.setWordWrap(True);form.form.addRow(name)
    state={'file':None}
    def choose():
        path,_=QFileDialog.getOpenFileName(tab,tr('add_video'),'','Video (*.mp4 *.m4v *.mov *.webm)')
        if path:state['file']=path;name.setText(Path(path).name);place.setEnabled(True);replace.setEnabled(True)
    pick=QPushButton(L('选择视频…','Choose video…'));pick.clicked.connect(choose);form.form.addRow(pick)
    def place_mode():tab.pending_video=state['file'];tab.set_mode('add_video')
    place=QPushButton(L('框选放置','Draw placement'));place.setEnabled(False);place.clicked.connect(place_mode);form.form.addRow(place)
    def replace_image():
        chosen=tab.selected_objects()
        if len(chosen)!=1 or chosen[0].kind!='image':name.setText(L('请在页面选择一张图片。','Select one image on the page.'));return
        obj=chosen[0];page=tab.canvas.object_page
        tab.run(tr('add_video'),lambda j:insert(tab.document,page,obj.bbox,state['file'],obj),lambda _:tab.queue.submit(lambda j:__import__('asterpdf.media',fromlist=['scan']).scan(tab.document),tab.media_scanned,tab.error),editing=True,local_edit=True)
    replace=QPushButton(L('替换所选图片','Replace selected image'));replace.setEnabled(False);replace.clicked.connect(replace_image);form.form.addRow(replace)
    form.note(L('视频嵌入 PDF，在支持多媒体的阅读器中播放。编码支持取决于平台；普通阅读器仅显示播放标记。','Video is embedded in the PDF for multimedia-capable readers. Codec support depends on the platform; ordinary readers show a play marker.'))
