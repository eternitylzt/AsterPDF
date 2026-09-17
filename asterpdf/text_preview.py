"""Isolated PDF text drafts. No document revision or full-page reload per key."""
import copy
import io
import tempfile
from pathlib import Path
import pymupdf as fitz
import pikepdf as pp
from . import objects,text_patch
from .rendering import image_from_pixmap


def render(document,page_index,obj,old,new,scale):
    # Only the selected text's resources and state are copied. Images, media,
    # annotations and other page paint never enter the preview document.
    with pp.open(document.path) as source,pp.Pdf.new() as pdf:
        src=source.pages[page_index];page=pdf.add_blank_page(page_size=(612,792))
        for key in ('/MediaBox','/CropBox','/Rotate'):
            if key in src.obj:page.obj[key]=pp.Array(src.obj[key]) if key!='/Rotate' else src.obj[key]
        resources=pp.Dictionary()
        for key in ('/Font','/ExtGState','/ColorSpace','/Pattern'):
            if key in src.Resources:resources[key]=pdf.copy_foreign(source.make_indirect(src.Resources[key]))
        page.Resources=resources;data=objects.content_bytes(src);isolated=bytearray(data)
        for cmd in objects.commands(data):
            if not (obj.start<=cmd.start and cmd.end<=obj.end) and cmd.op in objects.PAINT|{'Do','sh','Tj','TJ',"'",'"'}:
                isolated[cmd.start:cmd.end]=b' '*(cmd.end-cmd.start)
        page.Contents=pdf.make_stream(bytes(isolated))
        out=io.BytesIO();pdf.save(out);base=out.getvalue()
    # The patcher deliberately uses the same path as a real commit. The tiny
    # private scratch file is removed even if a font/encoding rejects the draft.
    with tempfile.TemporaryDirectory(prefix='aster-text-') as folder:
        class Draft:
            serial=0
            path=Path(folder)/'text.pdf'
            result=base
            def edit(self,label,callback):
                with pp.open(self.path) as pdf:
                    callback(pdf);out=io.BytesIO();pdf.save(out);self.result=out.getvalue()
        draft=Draft();draft.path.write_bytes(base)
        text_patch.apply(draft,0,copy.deepcopy(obj),old,new)
        with fitz.open(stream=draft.result,filetype='pdf') as pdf:
            p=pdf[0];traces=[]
            for trace in p.get_texttrace():
                if trace['type']==1 and traces and traces[-1]['type']==0 and trace['chars']==traces[-1]['chars']:continue
                traces.append(trace)
            glyphs=[c for t in traces for c in t['chars']]
            box=fitz.Rect(obj.bbox)
            for kind,bounds,*_ in p.get_bboxlog():
                if 'text' in kind:box|=fitz.Rect(bounds)*p.rotation_matrix
            box=(box+(-3,-3,3,3))&p.rect
            scale=min(scale,(8_000_000/max(1,box.width*box.height))**.5)
            pix=p.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=box,alpha=bool(obj.details.get('new')))
            return image_from_pixmap(pix),(pix.x/scale,pix.y/scale,pix.width/scale,pix.height/scale),glyphs
