"""Conservative, byte-preserving content-stream object edits.

Only identifiable top-level text blocks, image/Form invocations and paths are
editable. Original bytes outside selected ranges are never reserialized. A
MuPDF scratch page measures each isolated object, so selection bounds are not
guessed from text extraction order. No redaction, white rectangles or rasterizing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .i18n import L
import re
import json
import pikepdf as pp
import pymupdf as fitz
from .core import Unsupported

WS = b'\x00\t\n\x0c\r '
DELIM = b'()<>[]{}/%'
NUMBER = re.compile(rb'^[+-]?(?:\d*\.\d+|\d+\.?\d*)$')
PAINT = {'S', 's', 'f', 'F', 'f*', 'B', 'B*', 'b', 'b*'}
PATH = {'m', 'l', 'c', 'v', 'y', 'h', 're'}


@dataclass
class Command:
    start: int
    end: int
    op: str
    raw: bytes


def commands(data: bytes) -> list[Command]:
    """Lex balanced PDF literals/arrays/dictionaries; retain exact byte offsets."""
    out, depth, i, start = [], 0, 0, 0
    while i < len(data):
        c = data[i]
        if c in WS:
            i += 1
            continue
        if c == 37:
            while i < len(data) and data[i] not in b'\r\n':
                i += 1
            continue
        if c == 40:
            nesting, i = 1, i + 1
            while i < len(data) and nesting:
                if data[i] == 92:
                    i += 2
                    continue
                if data[i] == 40:
                    nesting += 1
                if data[i] == 41:
                    nesting -= 1
                i += 1
            if nesting:
                raise Unsupported(L('PDF 字符串不完整。','Unbalanced PDF string'))
            continue
        if data[i:i+2] in (b'<<', b'>>'):
            depth += 1 if data[i:i+2] == b'<<' else -1
            i += 2
            continue
        if c == 60:
            end = data.find(b'>', i+1)
            if end < 0:
                raise Unsupported('Invalid hex string')
            i = end + 1
            continue
        if c in b'[]':
            depth += 1 if c == 91 else -1
            i += 1
            continue
        if c == 47:
            i += 1
            while i < len(data) and data[i] not in WS + DELIM:
                i += 1
            continue
        begin = i
        while i < len(data) and data[i] not in WS + DELIM:
            i += 1
        if i == begin:
            raise Unsupported(L('无法可靠解析该内容流。','Unsupported content delimiter'))
        token = data[begin:i]
        if depth == 0 and not NUMBER.match(token) and token not in (b'true', b'false', b'null'):
            op = token.decode('ascii')
            if op in ('BI', 'ID', 'EI'):
                raise Unsupported(L('含内联图片的页面暂不支持对象编辑，可使用页面导出与批注。','Inline images on this page are not editable. Page export and annotations remain available.'))
            out.append(Command(start, i, op, data[start:i]))
            start = i
    if depth:
        raise Unsupported('Unbalanced content stream')
    return out


def operands(command):
    # Parsing is used only for inspection, never for rewriting original bytes.
    numeric = re.sub(rb'%[^\r\n]*', b'', command.raw).split()[:-1]
    if command.op in {'cm','Tm','Td','TD','Tc','Tw','Tz','TL','Tr','Ts','g','G','rg','RG','k','K','w','J','j','M','m','l','c','v','y','re'} and all(NUMBER.fullmatch(token) for token in numeric):
        return [float(token) for token in numeric]
    probe = pp.Pdf.new()
    try:
        return list(pp.parse_content_stream(probe.make_stream(command.raw))[0].operands)
    finally:
        probe.close()


@dataclass
class PdfObject:
    id: int
    kind: str
    start: int
    end: int
    ctm: tuple
    bbox: tuple = (0, 0, 0, 0)
    text: str = ''
    font: str = ''
    size: float = 12
    resource: str = ''
    xref: int = 0
    reason: str = ''
    details: dict = field(default_factory=dict)


def content_bytes(page):
    c = page.obj.get('/Contents')
    if c is None:
        return b''
    return b'\n'.join(x.read_bytes() for x in c) if isinstance(c, pp.Array) else c.read_bytes()


def discover(document, page_index, progress=None, cancel=None):
    with pp.open(document.path) as pdf:
        p = pdf.pages[page_index]
        data = content_bytes(p)
        cmds = commands(data)
        resources = p.obj.get('/Resources', pp.Dictionary())
        objects, stack, ctm = [], [], fitz.Matrix(1, 0, 0, 1, 0, 0)
        text_start = path_start = None
        text_matrix = path_matrix = None
        fontname, fontsize, text_render = '', 12.0, 0
        edit_groups=[]
        for c in cmds:
            if c.op in ('BMC','BDC'):
                args=operands(c)
                box=json.loads(str(args[1]['/Box'])) if c.op=='BDC' and str(args[0])=='/AsterText' and '/Box' in args[1] else None
                metadata=json.loads(str(args[1].get('/Styles','[]'))) if c.op=='BDC' and str(args[0])=='/AsterText' else None
                edit_groups.append((c.start,len(objects),tuple(ctm),str(args[0])=='/AsterText',metadata,box))
            elif c.op=='EMC' and edit_groups:
                start,index,group_ctm,is_edit,metadata,box=edit_groups.pop()
                members=objects[index:]
                if is_edit and members and all(o.kind=='text' for o in members):
                    first=members[0];objects[index:]=[PdfObject(index,'text',start,c.end,group_ctm,font=first.font,size=first.size,reason=first.reason,details={'edit_styles':metadata,**({'box':box} if box else {})})]
            if c.op == 'q':
                stack.append((fitz.Matrix(ctm), fontname, fontsize, text_render))
            elif c.op == 'Q':
                if not stack:
                    raise Unsupported('Unbalanced graphics state')
                ctm, fontname, fontsize, text_render = stack.pop()
            elif c.op == 'cm':
                ctm = fitz.Matrix(*map(float, operands(c))) * ctm
            elif c.op == 'Tf':
                args = operands(c)
                fontname, fontsize = str(args[0]), float(args[1])
            elif c.op == 'Tr':
                text_render = int(operands(c)[0])
            elif c.op == 'BT':
                text_start, text_matrix = c.start, tuple(ctm)
            elif c.op == 'ET' and text_start is not None:
                obj = PdfObject(len(objects), 'text', text_start, c.end, text_matrix,
                                font=fontname, size=fontsize)
                if text_render >= 4:
                    obj.reason = L('暂不编辑参与裁剪的文字。','Text clipping mode cannot be edited')
                objects.append(obj)
                text_start = None
            elif c.op in PATH and text_start is None:
                if path_start is None:
                    path_start, path_matrix = c.start, tuple(ctm)
            elif c.op in PAINT and path_start is not None:
                objects.append(PdfObject(len(objects), 'vector', path_start, c.end, path_matrix))
                path_start = None
            elif c.op == 'n':
                path_start = None
            elif c.op in ('W', 'W*'):
                # Clipping paths remain part of graphics state; don't select them as painted objects.
                path_start = None
            elif c.op == 'Do' and text_start is None:
                name = str(operands(c)[0])
                xo = resources.get('/XObject', {}).get(name)
                if xo is not None:
                    kind = 'image' if xo.get('/Subtype') == pp.Name('/Image') else 'group'
                    objects.append(PdfObject(len(objects), kind, c.start, c.end, tuple(ctm),
                                             resource=name, xref=xo.objgen[0]))
        if stack or text_start is not None:
            raise Unsupported(L('页面图形状态不完整。','Unbalanced page graphics state'))
    # Isolate only painting operators. Keep state, paths and clips, and do not
    # alter the authoritative document. Each candidate is measured by the renderer.
    with fitz.open(document.path) as scratch:
        sp = scratch[page_index]
        xref = scratch.get_new_xref()
        scratch.update_object(xref, '<<>>')
        scratch.update_stream(xref, b'')
        sp.set_contents(xref)
        scratch.xref_set_key(sp.xref, 'Annots', '[]')
        # Build the inert background once. Preserve byte offsets and graphics state.
        masked = bytearray(data)
        for c in cmds:
            if c.op in PAINT or c.op in ('Do', 'sh', 'Tj', 'TJ', "'", '"'):
                replacement = b'n' if c.op in PAINT else b''
                masked[c.start:c.end] = replacement.rjust(c.end-c.start, b' ')
        background = bytes(masked)
        accepted = []
        for k, obj in enumerate(objects):
            if cancel and cancel():
                break
            isolated = background[:obj.start] + data[obj.start:obj.end] + background[obj.end:]
            # Scratch streams are never saved: compressing each one wastes most
            # of the discovery time on dense scientific plots.
            scratch.update_stream(xref, isolated, compress=False)
            sp = scratch.reload_page(sp)
            bounds = [fitz.Rect(b[1]) for b in sp.get_bboxlog() if b[0] != 'ignore-text']
            if bounds:
                rect = fitz.Rect(bounds[0])
                for r in bounds[1:]:
                    rect |= r
                rect = rect * sp.rotation_matrix
                if not rect.is_empty and not rect.is_infinite:
                    obj.bbox = tuple(rect)
                    if obj.kind == 'text':
                        obj.text = sp.get_text().strip()
                        lines=[line for b in sp.get_text('dict',flags=fitz.TEXTFLAGS_TEXT)['blocks'] for line in b.get('lines',[])]
                        spans=[span for line in lines for span in line['spans']]
                        if spans:
                            first=spans[0]
                            metadata=obj.details.get('edit_styles');box=obj.details.get('box')
                            obj.details={'family':first['font'],'origin':first['origin'],'color':first['color'],
                                'direction':lines[0]['dir'], 'flags':first['flags'],'page_rotation_matrix':tuple(sp.rotation_matrix),
                                'spans':[dict(span,line=n) for n,line in enumerate(lines) for span in line['spans']]}
                            traces=[]
                            for trace in sp.get_texttrace():
                                if trace['type']==1 and traces and traces[-1]['type']==0 and trace['chars']==traces[-1]['chars']:continue
                                traces.append(trace)
                            obj.details['glyphs']=[char for span in traces for char in span['chars']]
                            obj.details['glyph_styles']=[{'size':span['size'],'color':span['color'],'type':span['type']} for span in traces for char in span['chars']]
                            if box:obj.details['box']=box
                            if metadata:
                                obj.details['edit_styles']=metadata
                                obj.text=''.join(c for c,_ in metadata)
                            obj.size=first['size']
                    if obj.kind=='vector':
                        points=[];hit_path=[];filled=False;coord=fitz.Matrix(obj.ctm)*sp.transformation_matrix*sp.rotation_matrix
                        for index,c in enumerate(commands(data[obj.start:obj.end])):
                            if c.op in ('m','l'):
                                args=operands(c);pt=fitz.Point(float(args[0]),float(args[1]))*coord
                                points.append((index,pt.x,pt.y))
                            if c.op in ('m','l','c','v','y'):
                                args=list(map(float,operands(c)));hit_path.append((c.op,[tuple(fitz.Point(args[n],args[n+1])*coord) for n in range(0,len(args),2)]))
                            elif c.op=='re':
                                x,y,w,h=map(float,operands(c));hit_path.append(('poly',[tuple(fitz.Point(a,b)*coord) for a,b in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]]))
                            elif c.op=='h':hit_path.append(('h',[]))
                            elif c.op in PAINT:filled=c.op in ('f','F','f*','B','B*','b','b*')
                        obj.details['vertices']=points;obj.details['hit_path']=hit_path;obj.details['filled']=filled
                    accepted.append(obj)
            if progress:
                progress(k+1, len(objects))
        return accepted


def _transform_bytes(data, obj, matrix):
    ctm = fitz.Matrix(obj.ctm)
    if abs(ctm.a * ctm.d - ctm.b * ctm.c) < 1e-9:
        raise Unsupported('Singular object transform')
    local = ctm * matrix * ~ctm
    prefix = ('\nq ' + ' '.join(f'{v:.9f}' for v in local) + ' cm\n').encode()
    block = data[obj.start:obj.end]
    # q/Q restores text style as well as CTM. Replay style changes made inside
    # a text block so later blocks that inherit its font/spacing stay unchanged.
    replay = b''
    if obj.kind == 'text':
        state_ops = {'Tf', 'Tc', 'Tw', 'Tz', 'TL', 'Tr', 'Ts', 'g', 'G', 'rg', 'RG', 'k', 'K'}
        state = [c.raw for c in commands(block) if c.op in state_ops]
        if state:
            replay = b'\nBT\n' + b'\n'.join(state) + b'\nET\n'
    return prefix + block + b'\nQ\n' + replay


def transform(document, page_index, selected, dx=0, dy=0, sx=1, sy=1, delete=False, all_objects=None):
    if sx <= 0 or sy <= 0:
        raise ValueError('Scale must be positive')
    for obj in selected:
        if obj.reason:
            raise Unsupported(obj.reason)
    with fitz.open(document.path) as view:
        p = view[page_index]
        coord = p.transformation_matrix * p.rotation_matrix
        union = fitz.Rect(selected[0].bbox)
        for o in selected[1:]:
            union |= fitz.Rect(o.bbox)
        # Screen-space affine transform, conjugated into PDF coordinates.
        screen = fitz.Matrix(sx, 0, 0, sy, union.x0 * (1-sx) + dx, union.y0 * (1-sy) + dy)
        matrix = coord * screen * ~coord
    changes={}
    def mutate(pdf):
        page = pdf.pages[page_index]
        data = content_bytes(page)
        for obj in sorted(selected, key=lambda o: o.start, reverse=True):
            replacement = b'\n' if delete else _transform_bytes(data, obj, matrix)
            if not delete and obj.details.get('box'):
                # Keep authored-box metadata in sync with the native transform so
                # reopening its editor does not jump back to the insertion point.
                import copy
                box=copy.deepcopy(obj.details['box']);x,y,w,h=box['rect'];rect=fitz.Rect(x,y,x+w,y+h)*screen;box['rect']=[rect.x0,rect.y0,rect.width,rect.height];box['xscale']=box.get('xscale',1)*sx/sy
                styles=copy.deepcopy(obj.details.get('edit_styles',[]))
                for char,style in styles:
                    if style:style[1]*=sy
                for command in commands(replacement):
                    if command.op!='BDC':continue
                    args=operands(command)
                    if str(args[0])!='/AsterText':continue
                    args[1]['/Box']=pp.String(json.dumps(box));args[1]['/Styles']=pp.String(json.dumps(styles))
                    replacement=replacement[:command.start]+b'\n/AsterText '+args[1].unparse()+b' BDC'+replacement[command.end:];break
            # Text state can persist across BT blocks. Deletion removes show operators
            # only; preserving font and spacing state protects subsequent content.
            if delete and obj.kind == 'text':
                replacement = b'\n'.join(c.raw for c in commands(data[obj.start:obj.end])
                                           if c.op not in ('Tj', 'TJ', "'", '"'))
            changes[obj.id]=(obj.start,obj.end,len(replacement),replacement)
            data = data[:obj.start] + replacement + data[obj.end:]
        page.Contents = pdf.make_stream(data)
    document.edit('objects', mutate)
    if all_objects is not None and all(o.kind!='text' for o in selected):
        import copy
        updated=[]
        for old in all_objects:
            shift=sum(length-(end-start) for start,end,length,_ in changes.values() if end<=old.start)
            if old.id in changes:
                if delete:continue
                obj=copy.deepcopy(old);replacement=changes[old.id][3]
                prefix_end=next(c.end for c in commands(replacement) if c.op=='cm')
                obj.start=old.start+shift+prefix_end;obj.end=obj.start+(old.end-old.start)+1
                obj.ctm=tuple(fitz.Matrix(old.ctm)*matrix);obj.bbox=tuple(fitz.Rect(old.bbox)*screen)
                if 'hit_path' in obj.details:
                    obj.details['hit_path']=[(op,[tuple(fitz.Point(x,y)*screen) for x,y in points]) for op,points in obj.details['hit_path']]
                if 'vertices' in obj.details:
                    obj.details['vertices']=[(index,*(fitz.Point(x,y)*screen)) for index,x,y in obj.details['vertices']]
            else:
                obj=copy.deepcopy(old);obj.start+=shift;obj.end+=shift
            updated.append(obj)
        with pp.open(document.path) as pdf:
            resources=pdf.pages[page_index].Resources.get('/XObject',{})
            for obj in updated:
                if obj.resource and obj.resource in resources:obj.xref=resources[obj.resource].objgen[0]
        return updated


def replace_text(document, page_index, obj, text, fontsize=None, color=None, font='inherit'):
    if obj.reason:
        raise Unsupported(obj.reason)
    if '\n' in text:
        raise Unsupported(L('局部替换仅支持单行。','Local text replacement is a single line'))
    def mutate(pdf):
        page = pdf.pages[page_index]
        data = content_bytes(page)
        block = data[obj.start:obj.end]
        cs = commands(block)
        shows = [c for c in cs if c.op in ('Tj', 'TJ', "'", '"')]
        if len(shows) != 1 or shows[0].op not in ('Tj', 'TJ'):
            raise Unsupported(L('此文字块含多个定位片段，暂仅支持整体移动或缩放。','This block contains multiple positioned text runs. Move it as a group, or select a simpler label.'))
        resources = pp.Dictionary(page.Resources)
        fonts = pp.Dictionary(resources.get('/Font', pp.Dictionary()))
        name = obj.font
        if font != 'inherit':
            name = '/AsterEditFont'
            fonts[name] = pdf.make_indirect(pp.Dictionary(Type=pp.Name('/Font'), Subtype=pp.Name('/Type1'),
                BaseFont=pp.Name('/'+font), Encoding=pp.Name('/WinAnsiEncoding')))
            resources.Font = fonts
            page.Resources = resources
            encoding = 'cp1252'
        else:
            f = fonts.get(name)
            if f is None or str(f.get('/Subtype')) not in ('/Type1', '/TrueType'):
                raise Unsupported(L('子集或 CID 字体无法可靠编码新文字；可明确选择 Helvetica、Times-Roman 或 Courier 替代。','Subset/CID font cannot safely encode new text. Choose Helvetica, Times-Roman or Courier explicitly.'))
            enc = f.get('/Encoding')
            if str(enc) == '/WinAnsiEncoding':
                encoding = 'cp1252'
            elif not enc and str(f.get('/BaseFont', '')).lstrip('/') in ('Helvetica', 'Times-Roman', 'Courier'):
                encoding = 'ascii'
            else:
                raise Unsupported(L('自定义字体编码：请选择替代字体。','Custom font encoding: choose an explicit replacement font'))
            if '+' in str(f.get('/BaseFont', '')):
                raise Unsupported(L('子集字体：请选择替代字体。','Subset font: choose an explicit replacement font'))
        try:
            encoded = text.encode(encoding)
        except UnicodeEncodeError:
            raise Unsupported(L('该字体不支持这些字形；可选择 Unicode 字体添加独立文字对象。','This font cannot encode the text. Add a separate text object with a Unicode font.'))
        show = shows[0]
        setup = f' {name} {fontsize or obj.size:g} Tf '
        if color:
            setup += ' '.join(f'{c:.5f}' for c in color) + ' rg '
        replacement = setup.encode() + pp.String(encoded).unparse() + b' Tj '
        block = block[:show.start] + replacement + block[show.end:]
        page.Contents = pdf.make_stream(data[:obj.start] + block + data[obj.end:])
    document.edit('text', mutate)


def replace_image(document, page_index, obj, filename):
    if obj.kind != 'image':
        raise Unsupported(L('请选择图片对象。','Select an image'))
    # MuPDF authors a fresh image stream; pikepdf imports just that XObject.
    with fitz.open() as temp:
        p = temp.new_page()
        xref = p.insert_image(fitz.Rect(0, 0, 100, 100), filename=filename)
        data = temp.tobytes()
    import io
    def mutate(pdf):
        with pp.open(io.BytesIO(data)) as src:
            image = pdf.copy_foreign(src.get_object((xref, 0)))
            page = pdf.pages[page_index]
            resources = pp.Dictionary(page.Resources)
            xobjects = pp.Dictionary(resources.get('/XObject', pp.Dictionary()))
            name = '/AsterImage' + str(image.objgen[0])
            xobjects[name] = image
            resources.XObject = xobjects
            page.Resources = resources
            raw = content_bytes(page)
            page.Contents = pdf.make_stream(raw[:obj.start] + f'\n{name} Do\n'.encode() + raw[obj.end:])
    document.edit('replace image', mutate)


def replace_text_font(document,page_index,obj,text,fontbuffer,fontsize=None,color=None):
    """Remove original show operators and insert genuine searchable font-backed text.

    Other original operators and bytes remain. A fresh font resource is scoped
    by a unique name; no redaction, covering rectangle or page rasterization.
    """
    import io
    if obj.reason: raise Unsupported(obj.reason)
    if tuple(obj.details.get('direction',(1,0))) != (1.0,0.0):
        raise Unsupported(L('旋转或倾斜文字可移动/删除；内容输入暂限水平文字','Input editing currently requires horizontal text'))
    if not text:
        transform(document,page_index,[obj],delete=True);return
    font=fitz.Font(fontbuffer=fontbuffer)
    if any(not font.has_glyph(ord(c)) for c in text if not c.isspace()):
        raise Unsupported(L('所选字体缺少字形；请选择包含输入字符的系统字体','Selected font lacks requested glyphs'))
    with fitz.open(document.path) as original, fitz.open() as temp:
        source=original[page_index]
        p=temp.new_page(width=source.mediabox.width,height=source.mediabox.height)
        # Content coordinates are original PDF user space, independent of visible crop/rotation.
        point=fitz.Point(obj.details.get('origin',(obj.bbox[0],obj.bbox[1]+obj.size)))
        point=point * ~source.transformation_matrix * p.transformation_matrix
        name='AsterText'+str(document.serial+1)
        fontxref=p.insert_font(fontname=name,fontbuffer=fontbuffer)
        c=obj.details.get('color',0)
        rgb=color if color is not None else ((c>>16&255)/255,(c>>8&255)/255,(c&255)/255)
        p.insert_text(point,text,fontname=name,fontsize=fontsize or obj.size,color=rgb)
        from .fonts import set_unicode_map
        set_unicode_map(temp,fontxref,font,text)
        temp.subset_fonts()
        authored=temp.tobytes()
    def mutate(pdf):
        page=pdf.pages[page_index];data=content_bytes(page)
        with pp.open(io.BytesIO(authored)) as src:
            resources=pp.Dictionary(page.Resources)
            fonts=pp.Dictionary(resources.get('/Font',pp.Dictionary()))
            for key,value in src.pages[0].Resources.Font.items(): fonts[key]=pdf.copy_foreign(value)
            resources.Font=fonts;page.Resources=resources
            clean=b'\n'.join(c.raw for c in commands(data[obj.start:obj.end]) if c.op not in ('Tj','TJ',"'",'"'))
            inv=~fitz.Matrix(obj.ctm)
            prefix=('\nq '+' '.join(f'{v:.9f}' for v in inv)+' cm\n').encode()
            new=prefix+content_bytes(src.pages[0])+b'\nQ\n'+clean
            page.Contents=pdf.make_stream(data[:obj.start]+new+data[obj.end:])
    document.edit('text',mutate)


def replace_text_runs(document,page_index,obj,lines):
    """Regenerate an editable local block, preserving per-selection font styles."""
    import io,hashlib
    from .fonts import set_unicode_map
    if not any(run['text'] for line in lines for run in line):
        transform(document,page_index,[obj],delete=True);return
    if obj.reason:raise Unsupported(obj.reason)
    if tuple(obj.details.get('direction',(1,0)))!=(1.0,0.0):
        raise Unsupported(L('当前仅支持水平文字内容输入；此对象仍可移动、缩放或删除。','Input editing requires horizontal text; move, resize or delete remains available.'))
    with fitz.open(document.path) as original,fitz.open() as temp:
        source=original[page_index];p=temp.new_page(width=source.mediabox.width,height=source.mediabox.height)
        point=fitz.Point(obj.details.get('origin',(obj.bbox[0],obj.bbox[1]+obj.size))) * ~source.transformation_matrix * p.transformation_matrix
        fonts={};y=point.y;origins={}
        for span in obj.details.get('spans',[]):origins.setdefault(span['line'],span['origin'])
        for line_index,line in enumerate(lines):
            x=point.x
            if line_index in origins:
                baseline=fitz.Point(origins[line_index])*~source.transformation_matrix*p.transformation_matrix;x,y=baseline.x,baseline.y
            for run in line:
                text=run['text'];data=run['fontbuffer'];key=hashlib.sha256(data).hexdigest()
                if key not in fonts:
                    font=fitz.Font(fontbuffer=data);name=f'AsterR{document.serial+1}_{len(fonts)}'
                    fonts[key]=[name,p.insert_font(fontname=name,fontbuffer=data),font,'']
                name,xref,font,used=fonts[key]
                if any(not font.has_glyph(ord(c)) for c in text if not c.isspace()):raise Unsupported('Font lacks requested glyphs')
                p.insert_text((x,y),text,fontname=name,fontsize=run['size'],color=run['color'])
                x+=font.text_length(text,fontsize=run['size']);fonts[key][3]+=text
            y+=max([r['size'] for r in line] or [obj.size])*1.25
        for name,xref,font,used in fonts.values():set_unicode_map(temp,xref,font,used)
        temp.subset_fonts();authored=temp.tobytes()
    def mutate(pdf):
        page=pdf.pages[page_index];data=content_bytes(page)
        with pp.open(io.BytesIO(authored)) as src:
            resources=pp.Dictionary(page.Resources);fonts=pp.Dictionary(resources.get('/Font',pp.Dictionary()))
            for key,value in src.pages[0].Resources.Font.items():fonts[key]=pdf.copy_foreign(value)
            resources.Font=fonts;page.Resources=resources
            clean=b'\n'.join(c.raw for c in commands(data[obj.start:obj.end]) if c.op not in ('Tj','TJ',"'",'"'))
            # Keep all runs in one BT/ET so it remains one locally editable block.
            authored_ops=b'\n'.join(c.raw for c in commands(content_bytes(src.pages[0])) if c.op not in ('q','Q','BT','ET'))
            inv=~fitz.Matrix(obj.ctm);prefix=('\nq '+' '.join(f'{v:.9f}' for v in inv)+' cm\nBT\n0 Tc 0 Tw 100 Tz 0 Ts 0 Tr\n').encode()
            new=prefix+authored_ops+b'\nET\nQ\n'+clean
            page.Contents=pdf.make_stream(data[:obj.start]+new+data[obj.end:])
    document.edit('text',mutate)


def move_vertex(document,page_index,obj,index,point):
    """Change one straight path endpoint in original vector coordinates."""
    if obj.kind!='vector':raise Unsupported('Select a vector path')
    with fitz.open(document.path) as view:
        page=view[page_index];coord=fitz.Matrix(obj.ctm)*page.transformation_matrix*page.rotation_matrix
        if abs(coord.a*coord.d-coord.b*coord.c)<1e-9:raise Unsupported('Singular transform')
        local=fitz.Point(point)*~coord
    def mutate(pdf):
        page=pdf.pages[page_index];data=content_bytes(page);block=data[obj.start:obj.end];cmd=commands(block)[index]
        if cmd.op not in ('m','l'):raise Unsupported('Only straight path endpoints can be changed')
        old=list(map(float,operands(cmd)))
        for part in reversed(commands(block)):
            if part.op not in ('m','l'):continue
            xy=list(map(float,operands(part)))
            if max(abs(a-b) for a,b in zip(xy,old))<.0001:
                replacement=f' {local.x:.8f} {local.y:.8f} {part.op} '.encode()
                block=block[:part.start]+replacement+block[part.end:]
        page.Contents=pdf.make_stream(data[:obj.start]+block+data[obj.end:])
    document.edit('vector endpoint',mutate)


def set_stacking(document,page_index,selected,front=True):
    """Arrange chosen text/path/image/Form occurrences, retaining state and clips."""
    if not selected or any(o.kind not in ('image','group','text','vector') or o.end<=o.start or o.reason for o in selected):
        raise Unsupported(L('请选择可编辑的文字、图形或图片。','Select editable text, shapes or images.'))
    def mutate(pdf):
        page=pdf.pages[page_index];data=content_bytes(page);base=[];isolated=[]
        for c in commands(data):
            chosen=any(o.start<=c.start and c.end<=o.end for o in selected)
            if chosen and c.op in PAINT:base.append(b'n')
            elif chosen and c.op in ('Do','sh','Tj','TJ',"'",'"'):base.append(b' ')
            else:base.append(c.raw)
            if not chosen and c.op in PAINT:isolated.append(b'n')
            elif not chosen and c.op in ('Do','sh','Tj','TJ',"'",'"'):isolated.append(b' ')
            else:isolated.append(c.raw)
        original=b'\n'.join(base);layer=b'\n'.join(isolated)
        first,last=(original,layer) if front else (layer,original)
        page.Contents=pdf.make_stream(b'q\n'+first+b'\nQ\nq\n'+last+b'\nQ\n')
    document.edit('bring to front' if front else 'send to back',mutate)
