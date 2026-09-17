"""Standard line annotations with an independently sized appearance arrowhead."""
import math
import re


def text_style(annot):
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
