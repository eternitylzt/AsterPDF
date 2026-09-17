"""Page cropping with an explicit content-removal mode and transactional history."""
import io
import pikepdf as pp
import pymupdf as fitz
from .core import Unsupported
from .i18n import L


def crop_document(document, indices, source_page, rect, keep_outside=False):
    boxes={}
    with fitz.open(document.path) as original:
        reference=original[source_page].rect
        fractions=[rect[0]/reference.width,rect[1]/reference.height,rect[2]/reference.width,rect[3]/reference.height]
        if not (0<=fractions[0]<fractions[2]<=1 and 0<=fractions[1]<fractions[3]<=1):
            raise ValueError(L('裁剪框必须位于页面内。','The crop rectangle must be inside the page.'))
        for index in indices:
            page=original[index];w,h=page.rect.width,page.rect.height
            visual=fitz.Rect(fractions[0]*w,fractions[1]*h,fractions[2]*w,fractions[3]*h)
            boxes[index]=tuple((visual*page.derotation_matrix)*~page.transformation_matrix)

    def mutate(pdf):
        for index,box in boxes.items():
            target=pdf.pages[index]
            if not keep_outside:
                annots=list(target.obj.get('/Annots',[]))
                if any(str(a.get('/Subtype')) in ('/Widget','/RichMedia','/Movie','/Screen','/3D') for a in annots):
                    raise Unsupported(L('目标页含表单或动画/媒体。请勾选“保留框外内容”；删除式裁剪暂不处理此类页面。',
                        'This page has forms or animation/media. Enable “Keep outside content”; destructive cropping is unavailable for this page.'))
                # Author only this page, then transplant its content/resources. The
                # authoritative catalog, other pages and inside annotations stay intact.
                with pp.new() as scratch:
                    scratch.pages.append(target)
                    if '/Annots' in scratch.pages[0].obj:del scratch.pages[0].obj['/Annots']
                    buffer=io.BytesIO();scratch.save(buffer)
                with fitz.open(stream=buffer.getvalue(),filetype='pdf') as authored:
                    page=authored[0];page.set_rotation(0)
                    media=page.mediabox
                    page.set_cropbox(fitz.Rect(media.x0,0,media.x1,media.height))
                    keep=fitz.Rect(box)*page.transformation_matrix
                    bound=page.rect|keep
                    # Include content beyond old page boxes as well as visible margins.
                    for _,bbox in page.get_bboxlog():bound|=fitz.Rect(bbox)
                    bound=bound+(-20,-20,20,20)
                    for outside in (fitz.Rect(bound.x0,bound.y0,bound.x1,keep.y0),
                                    fitz.Rect(bound.x0,keep.y1,bound.x1,bound.y1),
                                    fitz.Rect(bound.x0,keep.y0,keep.x0,keep.y1),
                                    fitz.Rect(keep.x1,keep.y0,bound.x1,keep.y1)):
                        if not outside.is_empty:page.add_redact_annot(outside,fill=False,cross_out=False)
                    # Crossing text/path objects are removed; image pixels outside
                    # are erased in a new image, never hidden behind a white overlay.
                    page.apply_redactions(images=2,graphics=2,text=0)
                    page.clean_contents(sanitize=True)
                    data=authored.tobytes(garbage=4,deflate=True)
                with pp.open(io.BytesIO(data)) as cleaned:
                    cleaned.pages[0].remove_unreferenced_resources()
                    for key in ('/Contents','/Resources'):
                        target.obj[key]=pdf.copy_foreign(cleaned.make_indirect(cleaned.pages[0].obj[key]))
                allowed=[];keep_pdf=fitz.Rect(box)
                for a in annots:
                    if str(a.get('/Subtype'))=='/Popup':continue
                    if a.get('/Rect') and keep_pdf.contains(fitz.Rect(list(a.Rect))):
                        allowed.append(a)
                        if a.get('/Popup'):allowed.append(a.Popup)
                target.obj.Annots=pp.Array(allowed)
            target.obj.CropBox=pp.Array(box)
            if not keep_outside:
                target.obj.MediaBox=pp.Array(box)
                for key in ('/BleedBox','/TrimBox','/ArtBox'):
                    if key in target.obj:del target.obj[key]
    return document.edit('crop',mutate)
