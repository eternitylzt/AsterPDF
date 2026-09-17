"""Edit character ranges without substituting untouched PDF font resources.

Original font resources, glyph codes, transforms and colors survive. Local
spacing closes or opens as ranges change; added/restyled ranges use embedded
fonts. Content is emitted in reading order. No redaction or covering.
"""
from .text_mapping import opcodes, glyph_mapping
import io
import hashlib
import json
import pikepdf as pp
import pymupdf as fitz
from .core import Unsupported
from .i18n import L


def characters(lines):
    out=[]
    for n,line in enumerate(lines):
        if n:out.append(('\n',None))
        for run in line:
            style=(run['family'],round(run['size'],4),run['bold'],run['italic'],tuple(round(v,4) for v in run['color']))
            out.extend((c,style) for c in run['text'])
    return out


def changes(old,new):
    # A color/weight/slant/size change must never trigger font substitution.
    def keys(lines):return [(ch,style[0] if style else None) for ch,style in characters(lines)]
    return opcodes(keys(old),keys(new))


def changed_runs(old,new):
    """Resolve fonts only for genuinely new or explicitly reformatted characters."""
    changed=set()
    for tag,a,b,c,d in changes(old,new):
        if tag!='equal':changed.update(range(c,d))
    offset=0
    for n,line in enumerate(new):
        if n:offset+=1
        for run in line:
            delta=''.join(c for i,c in enumerate(run['text'],offset) if i in changed)
            if delta:run['delta_text']=delta;yield run
            offset+=len(run['text'])


def _width(font,code):
    if str(font.get('/Subtype'))=='/Type0':
        child=font.DescendantFonts[0];arr=child.get('/W',[]);i=0
        while i<len(arr):
            first=int(arr[i]);value=arr[i+1];i+=2
            if isinstance(value,pp.Array):
                if first<=code<first+len(value):return float(value[code-first])
            else:
                end=int(value);width=float(arr[i]);i+=1
                if first<=code<=end:return width
        return float(child.get('/DW',1000))
    widths=font.get('/Widths',[]);index=code-int(font.get('/FirstChar',0))
    if 0<=index<len(widths):return float(widths[index])
    base=str(font.get('/BaseFont','/Helvetica')).lstrip('/')
    try:return fitz.Font(base).glyph_advance(code)*1000
    except Exception:raise Unsupported(L('此字体的字宽无法可靠读取；仍可移动或删除整个文字块。','Cannot safely read glyph advances; the entire block can still be moved or deleted.'))


def apply(document,page_index,obj,old,new):
    from .objects import commands,operands,content_bytes
    from .fonts import set_unicode_map
    if obj.details.get('box'):
        from .text_boxes import apply as apply_box
        return apply_box(document,page_index,obj,new)
    ops=changes(old,new)
    if characters(old)==characters(new):return
    if obj.reason:raise Unsupported(obj.reason)
    if tuple(obj.details.get('direction',(1,0)))!=(1.,0.):
        raise Unsupported(L('此旋转文字可整体移动或删除；逐字编辑暂仅支持水平文字。','Character edits require horizontal text; move or delete the entire block instead.'))
    trace=obj.details.get('glyphs',[])
    oldchars=characters(old);newchars=characters(new)
    original=''.join(c for c,_ in oldchars);painted=''.join(chr(c[0]) for c in trace)
    mapping=glyph_mapping(original,painted)
    if mapping is None:
        raise Unsupported(L('该文字块包含无法一一映射的字形。可取消后移动或删除整个对象，或插入独立文本框。','This block has ambiguous glyph mapping. Cancel and move/delete the object, or insert a separate text box.'))
    reverse_mapping={v:k for k,v in mapping.items()}
    keep={};authored_parts={};newruns=[]
    for n,line in enumerate(new):
        if n:newruns.append(None)
        for run in line:newruns.extend([run]*len(run['text']))
    # Removing/inserting an explicit newline changes the target baseline. A
    # common character on the former second line must not stay on that line.
    target_positions={}
    if original.count('\n')!=''.join(ch for ch,_ in newchars).count('\n') and trace:
        reused={}
        for tag,a,b,c,d in ops:
            if tag=='equal':reused.update((c+i-a,mapping[i]) for i in range(a,b) if i in mapping)
        x0,y0=trace[0][2];x=x0;y=y0;measure={}
        for index,(char,style) in enumerate(newchars):
            if char=='\n':x=x0;y+=obj.size*1.25;continue
            target_positions[index]=(x,y)
            if index in reused:
                g=reused[index];before=oldchars[reverse_mapping[g]][1]
                end=trace[g+1][2][0] if g+1<len(trace) and abs(trace[g+1][2][1]-trace[g][2][1])<.01 else trace[g][3][2]
                advance=(end-trace[g][2][0])*style[1]/before[1]
            else:
                data=newruns[index].get('fontbuffer')
                if data:
                    key=hashlib.sha256(data).digest()
                    if key not in measure:measure[key]=fitz.Font(fontbuffer=data)
                    advance=measure[key].text_length(char,fontsize=style[1])
                else:advance=style[1]*.25
            x+=advance
    # Local editing preserves the original baseline and inter-glyph spacing.
    # New ranges shift the following original codes on that baseline only.
    shifts={};shift_by_y={}
    with fitz.open(document.path) as original_pdf,fitz.open() as temp:
        source=original_pdf[page_index];p=temp.new_page(width=source.mediabox.width,height=source.mediabox.height)
        fonts={};reserved={entry[4] for entry in source.get_fonts()}
        for tag,a,b,c,d in ops:
            if tag=='equal':
                for index in range(a,b):
                    if index in mapping:
                        g=mapping[index];y=round(trace[g][2][1],3);keep[g]=c+index-a;shifts[g]=shift_by_y.get(y,0)
                        before=oldchars[index][1];after=newchars[c+index-a][1]
                        if before and after and before[1]!=after[1]:
                            end=trace[g+1][2][0] if g+1<len(trace) and round(trace[g+1][2][1],3)==y else trace[g][3][2]
                            shift_by_y[y]=shift_by_y.get(y,0)+(end-trace[g][2][0])*(after[1]/before[1]-1)
                continue
            at=next((mapping[i] for i in range(a,len(oldchars)) if i in mapping),None)
            if at is not None:anchor=fitz.Point(trace[at][2])
            elif trace:
                last=trace[-1];anchor=fitz.Point(last[3][2],last[2][1])
            else:anchor=fitz.Point(obj.details.get('origin',(obj.bbox[0],obj.bbox[1]+obj.size)))
            ykey=round(anchor.y,3);anchor.x+=shift_by_y.get(ykey,0);start_x=anchor.x
            removed=[trace[mapping[i]] for i in range(a,b) if i in mapping and round(trace[mapping[i]][2][1],3)==ykey]
            removed_width=(removed[-1][3][2]-removed[0][2][0]) if removed else 0
            following=next((mapping[i] for i in range(b,len(oldchars)) if i in mapping),None)
            if removed and following is not None and round(trace[following][2][1],3)==ykey:
                removed_width=trace[following][2][0]-removed[0][2][0]
            elif not removed and b>a and original[a:b].isspace() and at is not None:
                previous=next((mapping[i] for i in range(a-1,-1,-1) if i in mapping),None)
                if previous is not None and round(trace[previous][2][1],3)==ykey:
                    removed_width=max(0,trace[at][2][0]-trace[previous][3][2])
            pos=c
            while pos<d:
                run=newruns[pos]
                if run is None:anchor.x=start_x;anchor.y+=obj.size*1.25;pos+=1;continue
                end=pos+1
                while end<d and newruns[end] is run:end+=1
                text=''.join(ch for ch,_ in newchars[pos:end]);data=run['fontbuffer'];key=hashlib.sha256(data).hexdigest()
                if pos in target_positions:anchor=fitz.Point(target_positions[pos])
                if key not in fonts:
                    font=fitz.Font(fontbuffer=data);name=f'AsterDelta{document.serial+1}_{len(fonts)}'
                    while name in reserved:name+='x'
                    reserved.add(name);fonts[key]=[name,p.insert_font(fontname=name,fontbuffer=data),font,'']
                name,xref,font,used=fonts[key];point=anchor*~source.transformation_matrix*p.transformation_matrix
                # Qt may synthesize italic/bold when a family has no physical face.
                morph=(point,fitz.Matrix(1,0,.22,1,0,0)) if run['italic'] and not font.is_italic else None
                p.insert_text(point,text,fontname=name,fontsize=run['size'],color=run['color'],morph=morph,
                              render_mode=2 if run['bold'] and not font.is_bold else 0,border_width=.018)
                authored_parts[pos]=temp.xref_stream(p.get_contents()[-1])
                anchor.x+=font.text_length(text,fontsize=run['size']);fonts[key][3]+=text;pos=end
            shift_by_y[ykey]=shift_by_y.get(ykey,0)+(anchor.x-start_x)-removed_width
        for name,xref,font,used in fonts.values():set_unicode_map(temp,xref,font,used)
        temp.subset_fonts();authored=temp.tobytes()

    def mutate(pdf):
        page=pdf.pages[page_index];data=content_bytes(page);fonts=page.Resources.get('/Font',{});parts=dict(authored_parts);glyph=0
        font=None;name='';size=12.;tc=tw=0.;stack=[];fill=b'0 g';stroke=b'0 G';render=0;horizontal=100.;graphics=b''
        ctm=fitz.Matrix(1,0,0,1,0,0);axes=fitz.Matrix(1,0,0,1,0,0)
        # Appending to a large journal BT block need not regenerate its thousands
        # of untouched glyphs. Retain its exact bytes and append only new runs.
        block=data[obj.start:obj.end]
        append_only=newchars[:len(oldchars)]==oldchars and len(newchars)>len(oldchars) and all(c.op!='cm' for c in commands(block))
        if append_only:
            with pp.open(io.BytesIO(authored)) as authored_pdf:
                resource=pp.Dictionary(page.Resources);fontdict=pp.Dictionary(resource.get('/Font',pp.Dictionary()))
                for key,value in authored_pdf.pages[0].Resources.get('/Font',{}).items():fontdict[key]=pdf.copy_foreign(value)
                resource.Font=fontdict;page.Resources=resource
            inv=~fitz.Matrix(obj.ctm);prefix=('\nq '+' '.join(f'{v:.9f}' for v in inv)+' cm\n').encode()
            metadata=pp.String(json.dumps(newchars,ensure_ascii=True,separators=(',',':'))).unparse()
            replacement=b'\n/AsterText << /Styles '+metadata+b' >> BDC\n'+block+prefix+b'\n'.join(authored_parts[key] for key in sorted(authored_parts))+b'\nQ\nEMC\n'
            page.Contents=pdf.make_stream(data[:obj.start]+replacement+data[obj.end:]);return
        with fitz.open(document.path) as original_pdf:to_pdf=~original_pdf[page_index].transformation_matrix
        for cmd in commands(data):
            args=None
            if cmd.op in ('Tf','Tc','Tw','Tr','Tz','Tm','cm'):args=operands(cmd)
            if cmd.op=='q':stack.append((font,name,size,tc,tw,fill,stroke,render,horizontal,fitz.Matrix(ctm),graphics))
            elif cmd.op=='Q' and stack:font,name,size,tc,tw,fill,stroke,render,horizontal,ctm,graphics=stack.pop()
            elif cmd.op=='cm':ctm=fitz.Matrix(*map(float,args))*ctm
            elif cmd.op=='BT':axes=fitz.Matrix(1,0,0,1,0,0)
            elif cmd.op=='Tm':axes=fitz.Matrix(*map(float,args[:4]),0,0)
            elif cmd.op=='Tz':horizontal=float(args[0])
            elif cmd.op=='Tf':name=str(args[0]);font=fonts.get(name);size=float(args[1])
            elif cmd.op=='Tc':tc=float(args[0])
            elif cmd.op=='Tw':tw=float(args[0])
            elif cmd.op in ('g','rg','k'):fill=cmd.raw
            elif cmd.op in ('G','RG','K'):stroke=cmd.raw
            elif cmd.op=='cs':fill=cmd.raw
            elif cmd.op in ('sc','scn'):fill+=cmd.raw
            elif cmd.op=='CS':stroke=cmd.raw
            elif cmd.op in ('SC','SCN'):stroke+=cmd.raw
            elif cmd.op in ('gs','ri'):graphics+=cmd.raw
            elif cmd.op=='Tr':render=int(args[0])
            within=obj.start<=cmd.start and cmd.end<=obj.end
            if not within:continue
            if cmd.op not in ('Tj','TJ',"'",'"'):continue
            if font is None or not size:raise Unsupported('Missing PDF font/size')
            composite=str(font.get('/Subtype'))=='/Type0'
            if composite and str(font.get('/Encoding'))!='/Identity-H':raise Unsupported(L('此 CID 字体编码暂不支持逐字修改，可移动或删除整个对象。','This CID encoding cannot be safely edited character by character. Move/delete remains available.'))
            args=operands(cmd)
            array=args[0] if cmd.op=='TJ' else [args[-1]]
            for item in array:
                if not isinstance(item,pp.String):continue
                raw=bytes(item);step=2 if composite else 1
                if len(raw)%step:raise Unsupported('Invalid character code length')
                for offset in range(0,len(raw),step):
                    codebytes=raw[offset:offset+step];code=int.from_bytes(codebytes,'big')
                    if glyph>=len(trace):raise Unsupported('Glyph mapping does not match PDF codes')
                    record=trace[glyph];glyph_step=1
                    # MuPDF expands a single ligature code into several Unicode
                    # characters; continuation records carry glyph id -1. Keep
                    # that PDF code once, never emit one code per Unicode letter.
                    while glyph+glyph_step<len(trace) and trace[glyph+glyph_step][1]<0:glyph_step+=1
                    members=list(range(glyph,glyph+glyph_step));retained=[g for g in members if g in keep]
                    if retained and (len(retained)!=len(members) or any(newchars[keep[g]][1]!=newchars[keep[glyph]][1] for g in retained)):
                        raise Unsupported(L('选区只修改了合字的一部分（如 ffi）。请选择整个合字后修改；其它文字保持原样。','This selection changes only part of a ligature (for example ffi). Select the whole ligature; other text remains unchanged.'))
                    if glyph in keep:
                        if render>=4:raise Unsupported(L('裁剪文字暂不支持逐字修改，可整体移动或删除。','Clipping text can be moved/deleted, but cannot yet be edited by character.'))
                        position=fitz.Point(target_positions.get(keep[glyph],(record[2][0]+shifts[glyph],record[2][1])))*to_pdf
                        old_index=reverse_mapping[glyph]
                        before=oldchars[old_index][1];after=newchars[keep[glyph]][1]
                        ratio=after[1]/before[1];matrix=axes*ctm
                        if after[3]!=before[3]:matrix=fitz.Matrix(1,0,.22 if after[3] else -.22,1,0,0)*matrix
                        matrix=fitz.Matrix(ratio,ratio)*matrix
                        coeff=' '.join(f'{v:.9f}' for v in (matrix.a,matrix.b,matrix.c,matrix.d,position.x,position.y))
                        paint=fill;edge=stroke;mode=render;weight=b''
                        if after[4]!=before[4]:paint=(' '.join(map(str,after[4]))+' rg').encode()
                        if after[2]!=before[2]:
                            if after[2]:mode=2;weight=f'{after[1]*.018:.7f} w 1 J 1 j '.encode()
                            elif render==2:mode=0
                            else:raise Unsupported(L('原字体本身为粗体，无法无损取消加粗；请选择明确的常规字体。','This face is intrinsically bold. Choose a regular font explicitly to remove its weight.'))
                        if mode==2:edge=(' '.join(map(str,after[4]))+' RG').encode();weight=f'{after[1]*.018:.7f} w 1 J 1 j '.encode()
                        setup=f'\nq\nBT\n0 Tc 0 Tw 0 Ts {mode} Tr {horizontal:.7f} Tz {name} {size:.7f} Tf {coeff} Tm\n'.encode()
                        parts[keep[glyph]]=setup+graphics+b'\n'+weight+paint+b'\n'+edge+b'\n<'+codebytes.hex().encode()+b'> Tj\nET Q\n'
                    glyph+=glyph_step
        if glyph!=len(trace):raise Unsupported('Glyph mapping does not match PDF codes')
        with pp.open(io.BytesIO(authored)) as authored_pdf:
            resource=pp.Dictionary(page.Resources);fontdict=pp.Dictionary(resource.get('/Font',pp.Dictionary()))
            for key,value in authored_pdf.pages[0].Resources.get('/Font',{}).items():fontdict[key]=pdf.copy_foreign(value)
            resource.Font=fontdict;page.Resources=resource
            inv=~fitz.Matrix(obj.ctm);prefix=('\nq '+' '.join(f'{v:.9f}' for v in inv)+' cm\n').encode()
            clean=b'\n'.join(c.raw for c in commands(data[obj.start:obj.end]) if c.op not in ('Tj','TJ',"'",'"','BMC','BDC','EMC'))
            metadata=pp.String(json.dumps(newchars,ensure_ascii=True,separators=(',',':'))).unparse()
            replacement=b'\n/AsterText << /Styles '+metadata+b' >> BDC\n'+prefix+b'\n'.join(parts[key] for key in sorted(parts))+b'\nQ\n'+clean+b'\nEMC\n'
            page.Contents=pdf.make_stream(data[:obj.start]+replacement+data[obj.end:])
    document.edit('text ranges',mutate)
