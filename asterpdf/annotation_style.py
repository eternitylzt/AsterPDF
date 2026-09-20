"""Standard line annotations with an independently sized appearance arrowhead."""
import math
import re

def rgb(color):
    if not color:return None
    if len(color)==1:return [color[0]]*3
    if len(color)==4:return [(1-color[i])*(1-color[3]) for i in range(3)]
    return color[:3]

def note_style(page,annot,size,fontname,color):
    import html
    import pymupdf as fitz
    family={'helv':'Helvetica','tiro':'Times New Roman','cour':'Courier','china-s':'sans-serif'}.get(fontname,'sans-serif')
    rgbcolor=rgb(color) or (0,0,0);hexcolor='#'+''.join(f'{round(c*255):02x}' for c in rgbcolor)
    style=f'font-family:{family};font-size:{size:g}pt;color:{hexcolor};'
    body=html.escape(annot.info.get('content','')).replace('\n','<br/>')
    rich=f'<body xmlns="http://www.w3.org/1999/xhtml"><p style="{style}">{body}</p></body>'
    page.parent.xref_set_key(annot.xref,'RC',fitz.get_pdf_str(rich));page.parent.xref_set_key(annot.xref,'DS',fitz.get_pdf_str(style))
    page.parent.xref_set_key(annot.xref,'AsterFontSize',str(size));page.parent.xref_set_key(annot.xref,'AsterFont',fitz.get_pdf_str(fontname))

def markup_appearance(page,annot,width,dash='solid'):
    """Use standard quad geometry with a customized, self-contained appearance."""
    if annot.type[1] not in ('Underline','StrikeOut','Squiggly'):return
    pdf=page.parent
    quads=[float(v) for v in re.findall(r'[-+]?(?:\d*\.\d+|\d+)',pdf.xref_get_key(annot.xref,'QuadPoints')[1])]
    if len(quads)%8:return
    color=annot.colors.get('stroke') or (0,0,0);rgb=' '.join(f'{v:g}' for v in color);op={1:'G',3:'RG',4:'K'}.get(len(color),'RG');segments=[]
    dashed={'dash':'[4 3]','dot':'[1 2]','dashdot':'[4 2 1 2]'}.get(dash,'[]')
    for n in range(0,len(quads),8):
        x0,y0,x1,y1,x2,y2,x3,y3=quads[n:n+8]
        factor=.5 if annot.type[1]=='StrikeOut' else .08
        left=(x2+(x0-x2)*factor,y2+(y0-y2)*factor);right=(x3+(x1-x3)*factor,y3+(y1-y3)*factor)
        segments.append(f'{left[0]:g} {left[1]:g} m')
        if dash=='wave' or annot.type[1]=='Squiggly':
            distance=math.hypot(right[0]-left[0],right[1]-left[1]);steps=max(2,round(distance/2));ux=(right[0]-left[0])/max(distance,.01);uy=(right[1]-left[1])/max(distance,.01)
            for k in range(1,steps+1):
                d=distance*k/steps;offset=(1 if k%2 else -1)*max(.6,width*.55)
                segments.append(f'{left[0]+ux*d-uy*offset:g} {left[1]+uy*d+ux*offset:g} l')
        else:segments.append(f'{right[0]:g} {right[1]:g} l')
        segments.append('S')
    xs=quads[::2];ys=quads[1::2];margin=max(2,width*2);bounds=[min(xs)-margin,min(ys)-margin,max(xs)+margin,max(ys)+margin];bbox='['+' '.join(map(str,bounds))+']'
    opacity=annot.opacity if annot.opacity>=0 else 1
    ap=pdf.get_new_xref();pdf.update_object(ap,f'<< /Type /XObject /Subtype /Form /BBox {bbox} /Resources << /ExtGState << /GS << /CA {opacity:g} /ca {opacity:g} >> >> >> >>')
    pdf.update_stream(ap,(f'q /GS gs {rgb} {op} {max(.1,width):g} w {dashed} 0 d '+' '.join(segments)+' Q').encode())
    pdf.xref_set_key(annot.xref,'AP',f'<< /N {ap} 0 R >>');pdf.xref_set_key(annot.xref,'Rect',bbox)
    pdf.xref_set_key(annot.xref,'AsterDash','/'+dash);pdf.xref_set_key(annot.xref,'BS',f'<< /W {width:g} /S /S >>')


def text_style(annot):
    if annot.type[1]=='Text':
        pdf=annot.parent.parent;kind,size=pdf.xref_get_key(annot.xref,'AsterFontSize')
        if kind in ('int','float'):return {'fontsize':float(size),'fontname':pdf.xref_get_key(annot.xref,'AsterFont')[1]}
    if annot.type[1]!='FreeText':return {}
    spans=[s for b in annot.get_text('dict').get('blocks',[]) for line in b.get('lines',[]) for s in line['spans']]
    if not spans:return {}
    span=spans[0];c=span['color']
    return {'color':[(c>>16&255)/255,(c>>8&255)/255,(c&255)/255],'fontsize':span['size']}


def freetext_border(page,annot,width,color,dashed=False):
    pdf=page.parent;ap=int(pdf.xref_get_key(annot.xref,'AP/N')[1].split()[0])
    values=[float(v) for v in re.findall(r'[-+]?(?:\d*\.\d+|\d+)',pdf.xref_get_key(ap,'BBox')[1])]
    if len(values)!=4:return
    dash='[4 3]' if dashed else '[]';rgb=' '.join(str(v) for v in color)
    if width>0:
        x,y,x1,y1=values;x+=width/2;y+=width/2
        drawing=f'\nq {rgb} RG {width:g} w {dash} 0 d {x:g} {y:g} {x1-x-width/2:g} {y1-y-width/2:g} re S Q\n'
        pdf.update_stream(ap,pdf.xref_stream(ap)+drawing.encode())
    pdf.xref_set_key(annot.xref,'BS',f'<< /W {width:g} /S /'+('D' if dashed else 'S')+f' /D {dash} >>')
    pdf.xref_set_key(annot.xref,'AsterBorderColor','['+rgb+']')


def line_appearance(page,annot,size):
    pdf=page.parent
    values=[float(v) for v in re.findall(r'[-+]?(?:\d*\.\d+|\d+)',pdf.xref_get_key(annot.xref,'L')[1])]
    if len(values)!=4:return
    x,y,tx,ty=values;length=math.hypot(tx-x,ty-y)
    if length<.01:return
    size=min(float(size),length*.8);ux,uy=(tx-x)/length,(ty-y)/length
    bx,by=tx-ux*size,ty-uy*size;half=size*.42
    left=(bx-uy*half,by+ux*half);right=(bx+uy*half,by-ux*half)
    color=annot.colors.get('stroke') or (0,0,0);width=annot.border.get('width',2);ends=annot.line_ends
    if ends[1] not in (4,5):return
    rgb=' '.join(f'{c:.6f}' for c in color);operator='G' if len(color)==1 else 'K' if len(color)==4 else 'RG'
    margin=max(size,width)+2;bounds=(min(x,tx)-margin,min(y,ty)-margin,max(x,tx)+margin,max(y,ty)+margin)
    bbox='['+' '.join(f'{v:.6f}' for v in bounds)+']'
    dashes=annot.border.get('dashes') or [];dash='['+' '.join(str(v) for v in dashes)+'] 0 d'
    tip=(bx,by) if ends[1]==5 else (tx,ty)
    stream=f'q /GS gs {rgb} {operator} {rgb} {operator.lower()} {width:g} w {dash} {x:g} {y:g} m {tip[0]:g} {tip[1]:g} l S [] 0 d {left[0]:g} {left[1]:g} m {tx:g} {ty:g} l {right[0]:g} {right[1]:g} l '+('h f' if ends[1]==5 else 'S')+' Q'
    opacity=max(0,annot.opacity) if annot.opacity>=0 else 1
    ap=pdf.get_new_xref();pdf.update_object(ap,f'<< /Type /XObject /Subtype /Form /BBox {bbox} /Resources << /ExtGState << /GS << /CA {opacity:g} /ca {opacity:g} >> >> >> >>');pdf.update_stream(ap,stream.encode())
    pdf.xref_set_key(annot.xref,'AP',f'<< /N {ap} 0 R >>');pdf.xref_set_key(annot.xref,'Rect',bbox)
    pdf.xref_set_key(annot.xref,'AsterHeadSize',str(size))
