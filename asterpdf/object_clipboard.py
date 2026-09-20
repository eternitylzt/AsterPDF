"""Clipboard payloads preserve PDF fonts, vector paths, size and page position."""
import io
import pikepdf as pp
import pymupdf as fitz
from .objects import content_bytes,commands,PAINT

def copy_pdf(document,page,selected):
    with pp.open(document.path) as source,pp.Pdf.new() as result:
        result.pages.append(source.pages[page]);p=result.pages[0];data=content_bytes(p);parts=[]
        for c in commands(data):
            inside=any(o.start<=c.start and c.end<=o.end for o in selected)
            if not inside and c.op in PAINT:parts.append(b'n')
            elif not inside and c.op in ('Do','sh','Tj','TJ',"'",'"'):parts.append(b' ')
            else:parts.append(c.raw)
        p.Contents=result.make_stream(b'\n'.join(parts));p.obj.Annots=pp.Array([])
        result.remove_unreferenced_resources();out=io.BytesIO();result.save(out);return out.getvalue()

def paste_pdf(document,page,data):
    from .objects import operands
    with fitz.open(document.path) as dst,fitz.open(stream=data,filetype='pdf') as source,fitz.open() as scratch:
        src=dst[page];p=scratch.new_page(width=src.mediabox.width,height=src.mediabox.height)
        p.set_mediabox(src.mediabox);p.set_cropbox(src.cropbox);p.set_rotation(src.rotation)
        # Same visual coordinates even when target page is a different size.
        target=fitz.Rect(0,0,source[0].rect.width,source[0].rect.height)*p.derotation_matrix
        p.show_pdf_page(target,source,0,keep_proportion=False);authored=scratch.tobytes()
    def mutate(pdf):
        with pp.open(io.BytesIO(authored)) as temp:
            target=pdf.pages[page];src=temp.pages[0];resources=pp.Dictionary(target.Resources);xo=pp.Dictionary(resources.get('/XObject',pp.Dictionary()));names={}
            for key,value in src.Resources.XObject.items():
                name=f'/AsterPaste{document.serial}_{len(names)}'
                while name in xo:name+='x'
                xo[name]=pdf.copy_foreign(value);names[key]=name
            resources.XObject=xo;target.Resources=resources
            content=b'\n'.join((names[str(operands(c)[0])]+' Do').encode() if c.op=='Do' else c.raw for c in commands(content_bytes(src)))
            from .text_boxes import final_ctm
            original=content_bytes(target);inverse=~fitz.Matrix(final_ctm(original))
            prefix=('\nq '+' '.join(f'{v:.9f}' for v in inverse)+' cm\n').encode()
            target.Contents=pdf.make_stream(original+prefix+content+b'\nQ\n')
    document.edit('paste in place',mutate)
