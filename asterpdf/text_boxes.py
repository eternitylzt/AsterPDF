"""Reflowable authored text boxes, kept as native PDF text with explicit graphics state."""
import io,json,hashlib
import pymupdf as fitz
import pikepdf as pp
from .objects import content_bytes,commands,operands
from .fonts import set_unicode_map
from .text_patch import characters

def final_ctm(data):
    matrix=fitz.Matrix(1,0,0,1,0,0);stack=[]
    for c in commands(data):
        if c.op=='q':stack.append(fitz.Matrix(matrix))
        elif c.op=='Q' and stack:matrix=stack.pop()
        elif c.op=='cm':matrix=fitz.Matrix(*map(float,operands(c)))*matrix
    return tuple(matrix)

def apply(document,page_index,obj,lines):
    box=dict(obj.details['box']);x,y,width,height=box['rect'];auto=box.get('auto',True)
    with fitz.open(document.path) as source,fitz.open() as draft:
        src=source[page_index];p=draft.new_page(width=src.rect.width,height=src.rect.height);fonts={};reserved={entry[4] for entry in src.get_fonts()};px=x;py=y;lineheight=obj.size*1.3;maxwidth=2.
        for n,line in enumerate(lines):
            if n:px=x;py+=lineheight;lineheight=obj.size*1.3
            for run in line:
                if not run['text']:continue
                data=run['fontbuffer'];key=hashlib.sha256(data).hexdigest()
                if key not in fonts:
                    font=fitz.Font(fontbuffer=data);name=f'AsterBox{getattr(document,"serial",0)}_{len(fonts)}'
                    while name in reserved:name+='x'
                    reserved.add(name);fonts[key]=[name,p.insert_font(fontname=name,fontbuffer=data),font,'']
                name,xref,font,used=fonts[key];size=run['size'];lineheight=max(lineheight,size*1.3)
                for ch in run['text']:
                    advance=font.text_length(ch,fontsize=size)*box.get('xscale',1)
                    if not auto and px>x and px+advance>x+max(2,width):px=x;py+=lineheight
                    baseline=fitz.Point(px,py+size)
                    skew=.22 if run['italic'] and not font.is_italic else 0
                    morph=(baseline,fitz.Matrix(box.get('xscale',1),0,skew,1,0,0))
                    p.insert_text(baseline,ch,fontname=name,fontsize=size,color=run['color'],morph=morph,render_mode=2 if run['bold'] and not font.is_bold else 0,border_width=.018)
                    px+=advance;maxwidth=max(maxwidth,px-x);fonts[key][3]+=ch
        for name,xref,font,used in fonts.values():set_unicode_map(draft,xref,font,used)
        draft.subset_fonts();authored=draft.tobytes()
        box['rect']=[x,y,maxwidth if auto else width,max(height,py-y+lineheight)]
        # Convert visual PDF coordinates to the source's PDF coordinates, including
        # page rotation/crop. Cancel inherited CTM before inserting this local block.
        center=fitz.Point(x,y);angle=box.get('angle',0)
        turn=fitz.Matrix(1,0,0,1,-center.x,-center.y)*fitz.Matrix(angle)*fitz.Matrix(1,0,0,1,center.x,center.y)
        matrix=p.transformation_matrix*turn*src.derotation_matrix*~src.transformation_matrix
    def mutate(pdf):
        dst=pdf.pages[page_index];data=content_bytes(dst)
        with pp.open(io.BytesIO(authored)) as incoming:
            resource=pp.Dictionary(dst.Resources);fd=pp.Dictionary(resource.get('/Font',pp.Dictionary()))
            for key,value in incoming.pages[0].Resources.get('/Font',{}).items():fd[key]=pdf.copy_foreign(value)
            resource.Font=fd;dst.Resources=resource;stream=content_bytes(incoming.pages[0])
        ctm=final_ctm(data[:obj.start]);inverse=~fitz.Matrix(ctm)
        fmt=lambda m:' '.join(f'{v:.9f}' for v in m).encode()
        meta=pp.String(json.dumps(characters(lines),ensure_ascii=True,separators=(',',':'))).unparse();frame=pp.String(json.dumps(box,separators=(',',':'))).unparse()
        block=b'\n/AsterText << /Styles '+meta+b' /Box '+frame+b' >> BDC\nq '+fmt(inverse)+b' cm\n'+fmt(matrix)+b' cm\n'+stream+b'\nQ\nEMC\n'
        dst.Contents=pdf.make_stream(data[:obj.start]+block+data[obj.end:])
    document.edit('text box',mutate)
