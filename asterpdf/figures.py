"""Insert native PDF vector figures and basic shapes without rasterization."""
import io,math,shutil,subprocess,tempfile
from pathlib import Path
import pikepdf as pp
import pymupdf as fitz
from .core import Unsupported
from .i18n import L
from .objects import content_bytes,commands,operands

DASHES={'solid':'[] 0','dash':'[6 3] 0','dot':'[1 3] 0','dashdot':'[6 3 1 3] 0'}

def ghostscript():
    for name in ('gswin64c','gswin32c','gs'):
        found=shutil.which(name)
        if found:return found
    for base in (Path('C:/Program Files/gs'),Path('C:/Program Files (x86)/gs')):
        found=sorted(base.glob('*/bin/gswin*c.exe'),reverse=True)
        if found:return str(found[0])
    return None

def prepare(filename,directory):
    path=Path(filename)
    if path.suffix.lower() not in ('.eps','.ps'):return str(path)
    executable=ghostscript()
    if not executable:raise Unsupported(L('EPS/PS 需要本机安装 Ghostscript；本软件不附带该依赖。也可先转换为 PDF 后插入。','EPS/PS requires a local Ghostscript installation (not bundled). Alternatively convert it to PDF first.'))
    target=Path(directory)/('figure-'+__import__('uuid').uuid4().hex+'.pdf')
    subprocess.run([executable,'-dSAFER','-dBATCH','-dNOPAUSE','-dEPSCrop','-sDEVICE=pdfwrite','-sOutputFile='+str(target),str(path)],check=True,timeout=60,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return str(target)

def insert_pdf(document,page,rect,filename,source_page=0,keep_ratio=True):
    with fitz.open(document.path) as original,fitz.open(filename) as source,fitz.open() as scratch:
        src=original[page];p=scratch.new_page(width=src.mediabox.width,height=src.mediabox.height)
        p.set_mediabox(src.mediabox);p.set_cropbox(src.cropbox);p.set_rotation(src.rotation)
        p.show_pdf_page(fitz.Rect(rect)*p.derotation_matrix,source,source_page,keep_proportion=keep_ratio)
        data=scratch.tobytes()
    def mutate(pdf):
        with pp.open(io.BytesIO(data)) as authored:
            dst=pdf.pages[page];src=authored.pages[0];resources=pp.Dictionary(dst.Resources)
            xobjects=pp.Dictionary(resources.get('/XObject',pp.Dictionary()));names={}
            for key,value in src.Resources.XObject.items():
                name=f'/AsterFigure{document.serial}_{len(names)}'
                while name in xobjects:name+='x'
                names[key]=name;xobjects[name]=pdf.copy_foreign(value)
            resources.XObject=xobjects;dst.Resources=resources
            drawing=b'\n'.join((names[str(operands(c)[0])]+' Do').encode() if c.op=='Do' else c.raw for c in commands(content_bytes(src)))
            from .text_boxes import final_ctm
            original=content_bytes(dst);inverse=~fitz.Matrix(final_ctm(original));prefix=('\nq '+' '.join(map(str,inverse))+' cm\n').encode()
            dst.Contents=pdf.make_stream(original+prefix+drawing+b'\nQ')
    document.edit('insert vector figure',mutate)

def draw_shape(document,page,rect,kind,color,fill,width,dash='solid'):
    with fitz.open(document.path) as original,fitz.open() as scratch:
        src=original[page];p=scratch.new_page(width=src.mediabox.width,height=src.mediabox.height)
        p.set_mediabox(src.mediabox);p.set_cropbox(src.cropbox);p.set_rotation(src.rotation)
        r=fitz.Rect(rect)*p.derotation_matrix;shape=p.new_shape();cx,cy=(r.x0+r.x1)/2,(r.y0+r.y1)/2
        if kind=='rectangle':shape.draw_rect(r)
        elif kind=='ellipse':shape.draw_oval(r)
        elif kind=='line':shape.draw_line(r.bl,r.tr)
        elif kind=='arrow':
            points=[(r.x0,cy-r.height*.15),(r.x0+r.width*.65,cy-r.height*.15),(r.x0+r.width*.65,r.y0),(r.x1,cy),(r.x0+r.width*.65,r.y1),(r.x0+r.width*.65,cy+r.height*.15),(r.x0,cy+r.height*.15)]
            shape.draw_polyline(points+[points[0]])
        else:
            if kind=='triangle':points=[(cx,r.y0),(r.x1,r.y1),(r.x0,r.y1)]
            elif kind=='diamond':points=[(cx,r.y0),(r.x1,cy),(cx,r.y1),(r.x0,cy)]
            else:points=[(cx+math.cos(-math.pi/2+n*math.pi/5)*r.width/2*(1 if n%2==0 else .42),cy+math.sin(-math.pi/2+n*math.pi/5)*r.height/2*(1 if n%2==0 else .42)) for n in range(10)]
            shape.draw_polyline(points+[points[0]])
        shape.finish(color=color,fill=fill if kind!='line' else None,width=width,dashes=DASHES.get(dash,'[] 0'),closePath=kind!='line');shape.commit()
        data=p.read_contents()
    def mutate(pdf):
        from .text_boxes import final_ctm
        target=pdf.pages[page];original=content_bytes(target);inverse=~fitz.Matrix(final_ctm(original))
        prefix=('\nq '+' '.join(f'{v:.9f}' for v in inverse)+' cm\n').encode()
        target.Contents=pdf.make_stream(original+prefix+data+b'\nQ\n')
    document.edit('draw vector shape',mutate)

def style_vectors(document,page,selected,color,fill,width,dash='solid'):
    if any(o.kind!='vector' for o in selected):raise Unsupported(L('样式修改适用于直接绘制的路径；组合图可整体移动、缩放。','Style changes apply to painted paths; Form groups support moving and scaling.'))
    stroke=(' '.join(map(str,color))+' RG '+str(width)+' w '+DASHES.get(dash,'[] 0')+' d\n').encode();paint=(' '.join(map(str,fill))+' rg\n').encode() if fill is not None else b''
    def mutate(pdf):
        p=pdf.pages[page];data=content_bytes(p)
        for o in sorted(selected,key=lambda o:o.start,reverse=True):
            parts=[]
            for c in commands(data[o.start:o.end]):
                if c.op in ('RG','G','K','w','rg','g','k','d'):continue
                if c.op in ('f','F','f*','B','B*','b','b*','S','s'):parts.append(b'B' if fill is not None else b'S')
                else:parts.append(c.raw)
            data=data[:o.start]+b' q '+stroke+paint+b'\n'.join(parts)+b' Q '+data[o.end:]
        p.Contents=pdf.make_stream(data)
    document.edit('style vectors',mutate)


def rotate(document,page,selected,angle):
    from .objects import _transform_bytes
    bounds=fitz.Rect(selected[0].bbox)
    for obj in selected[1:]:bounds |= fitz.Rect(obj.bbox)
    cx,cy=(bounds.x0+bounds.x1)/2,(bounds.y0+bounds.y1)/2
    screen=fitz.Matrix(1,0,0,1,-cx,-cy)*fitz.Matrix(angle)*fitz.Matrix(1,0,0,1,cx,cy)
    with fitz.open(document.path) as view:
        p=view[page];coord=p.transformation_matrix*p.rotation_matrix;matrix=coord*screen*~coord
    def mutate(pdf):
        p=pdf.pages[page];data=content_bytes(p)
        for obj in sorted(selected,key=lambda o:o.start,reverse=True):
            data=data[:obj.start]+_transform_bytes(data,obj,matrix)+data[obj.end:]
        p.Contents=pdf.make_stream(data)
    document.edit('rotate shapes',mutate)
