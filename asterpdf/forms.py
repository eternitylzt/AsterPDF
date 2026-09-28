"""Standard AcroForm values and appearances; never execute document JavaScript."""
import io
import re
import pymupdf as fitz
import pikepdf as pp
from .core import Unsupported
from .i18n import L

DATE_FORMATS={'dd.mm.yyyy':'dd.MM.yyyy','dd/mm/yyyy':'dd/MM/yyyy','mm/dd/yyyy':'MM/dd/yyyy',
              'yyyy-mm-dd':'yyyy-MM-dd','yyyy/mm/dd':'yyyy/MM/dd','m/d/yyyy':'M/d/yyyy',
              'd/m/yyyy':'d/M/yyyy','mm/dd/yy':'MM/dd/yy','dd/mm/yy':'dd/MM/yy'}


def inherited(node,key,default=None):
    seen=set()
    while node is not None:
        if key in node:return node[key]
        identity=node.objgen
        if identity in seen:return default
        seen.add(identity);node=node.get('/Parent')
    return default


def widgets(pdf):
    for page,p in enumerate(pdf.pages):
        number=0
        for node in p.obj.get('/Annots',[]):
            if node.get('/Subtype')==pp.Name.Widget:
                yield f'{page}:{number}',page,node
                number+=1


def scan(path):
    fields=[]
    with fitz.open(path) as doc,pp.open(path) as pdf:
        acro=pdf.Root.get('/AcroForm',{});xfa='/XFA' in acro
        signed=any(w.field_type==fitz.PDF_WIDGET_TYPE_SIGNATURE and w.is_signed for p in doc for w in p.widgets() or [])
        nodes={key:node for key,_,node in widgets(pdf)}
        for page,p in enumerate(doc):
            for ordinal,w in enumerate(p.widgets() or []):
                key=f'{page}:{ordinal}';node=nodes[key];flags=w.field_flags
                scripts=[getattr(w,k,None) for k in ('script','script_format','script_stroke','script_change','script_calc','script_blur','script_focus')]
                match=re.fullmatch(r'\s*AFDate_FormatEx\([\"\']([^\"\']+)[\"\']\);?\s*',w.script_format or '')
                date=DATE_FORMATS.get(match[1]) if match else None
                scripts_unknown=any(s and not (date and re.fullmatch(r'\s*AFDate_(?:FormatEx|KeystrokeEx)\([\"\'][^\"\']+[\"\']\);?\s*',s)) for s in scripts)
                options=[]
                for option in inherited(node,'/Opt',[]):
                    options.append((str(option[0]),str(option[1])) if isinstance(option,pp.Array) else (str(option),str(option)))
                value=inherited(node,'/V','')
                value=[str(v) for v in value] if isinstance(value,pp.Array) else str(value)
                kind={fitz.PDF_WIDGET_TYPE_TEXT:'text',fitz.PDF_WIDGET_TYPE_CHECKBOX:'check',fitz.PDF_WIDGET_TYPE_RADIOBUTTON:'radio',fitz.PDF_WIDGET_TYPE_COMBOBOX:'combo',fitz.PDF_WIDGET_TYPE_LISTBOX:'list',fitz.PDF_WIDGET_TYPE_SIGNATURE:'signature'}.get(w.field_type,'unsupported')
                ap=node.get('/AP',{}).get('/N',{})
                states=[str(k)[1:] for k in ap.keys() if str(k)!='/Off'] if kind in ('check','radio') and isinstance(ap,pp.Dictionary) else []
                font_xref=0
                fonts=acro.get('/DR',{}).get('/Font',{})
                for name,font in fonts.items():
                    if str(name)[1:]==w.text_font:font_xref=font.objgen[0];break
                fields.append(dict(key=key,page=page,xref=w.xref,name=w.field_name or '',label=w.field_label or w.field_name or L('表单字段','Form field'),
                    rect=tuple(w.rect*p.rotation_matrix),raw_rect=tuple(w.rect),kind=kind,value=value,
                    checked=str(node.get('/AS','/Off'))!='/Off',on=states[0] if states else '',
                    readonly=bool(flags&1) or xfa or signed,required=bool(flags&2),multiline=bool(flags&4096),password=bool(flags&8192),
                    editable=bool(flags&(1<<18)),multiple=bool(flags&(1<<21)),comb=bool(flags&(1<<24)),
                    maxlen=w.text_maxlen or 0,options=options,date=date,scripts=scripts_unknown,rich=bool(flags&(1<<25)) or '/RV' in node,
                    visible=not bool(int(node.get('/F',0))&(1|2|32)),align=int(inherited(node,'/Q',0)),
                    font=w.text_font,size=w.text_fontsize,color=w.text_color or [0],font_xref=font_xref,
                    fill=w.fill_color,border=w.border_color,border_width=w.border_width or 0))
    return {'fields':fields,'xfa':xfa,'signed':signed}


def rgb(color):
    if not color:return (0,0,0)
    if len(color)==1:return tuple(color)*3
    if len(color)==4:return tuple(1-min(1,color[i]+color[3]) for i in range(3))
    return tuple(color[:3])


def appearance(source,field,value):
    """Author a clipped, searchable appearance with embedded fonts when needed."""
    r=fitz.Rect(field['raw_rect']);width,height=r.width,r.height
    text='\n'.join(value) if isinstance(value,list) else value
    if field['kind'] in ('list','combo'):
        display=dict(field['options']);text='\n'.join(display.get(v,v) for v in value) if isinstance(value,list) else display.get(value,value)
    if field['password']:text='*'*len(text)
    font=None
    if field['font_xref']:
        try:
            data=source.extract_font(field['font_xref'])[3]
            if data:font=fitz.Font(fontbuffer=data)
        except (ValueError,RuntimeError):pass
    if font is None:
        name=field['font'] or 'helv';italic='italic' in name.lower() or 'ob' in name.lower();bold='bold' in name.lower() or name.lower() in ('hebo','hebi')
        try:font=fitz.Font(name)
        except Exception:font=fitz.Font('hebi' if italic and bold else 'heit' if italic else 'hebo' if bold else 'helv')
    if any(not font.has_glyph(ord(c)) for c in text if not c.isspace()):font=fitz.Font('china-s')
    if any(not font.has_glyph(ord(c)) for c in text if not c.isspace()):raise Unsupported(L('该输入包含无法显示的字形，请更换字符。','The input contains unsupported glyphs. Please use different characters.'))
    with fitz.open() as scratch:
        p=scratch.new_page(width=width,height=height);box=p.rect
        if field['fill']:p.draw_rect(box,color=None,fill=rgb(field['fill']))
        if field['border'] and field['border_width']:
            bw=min(field['border_width'],min(width,height)/2);p.draw_rect(box+fitz.Rect(bw/2,bw/2,-bw/2,-bw/2),color=rgb(field['border']),width=bw)
        pad=max(1.5,field['border_width']+1);inner=box+fitz.Rect(pad,pad,-pad,-pad)
        size=field['size'] or min(12,inner.height/max(1,font.ascender-font.descender))
        if not field['multiline'] and field['kind']!='list':
            text=text.replace('\r',' ').replace('\n',' ')
            if not field['size'] and not field['comb']:size=min(size,inner.width/max(.01,font.text_length(text,fontsize=1)))
        size=max(2,size)
        writer=fitz.TextWriter(box)
        if field['kind']=='list':
            selected=set(value if isinstance(value,list) else [value]);rowheight=size*1.3
            options=field['options'];first=next((i for i,(v,_) in enumerate(options) if v in selected),0);y=pad
            for export,label in options[first:]:
                if y+rowheight>height-pad:break
                if export in selected:p.draw_rect(fitz.Rect(pad,y,width-pad,y+rowheight),color=None,fill=(.75,.85,1))
                writer.append(fitz.Point(pad,y+size*font.ascender),label,font=font,fontsize=size);y+=rowheight
        elif field['comb'] and field['maxlen']:
            cell=inner.width/field['maxlen'];baseline=inner.y0+(inner.height+size*(font.ascender+font.descender))/2
            for i,char in enumerate(text[:field['maxlen']]):writer.append(fitz.Point(inner.x0+cell*(i+.5)-font.text_length(char,fontsize=size)/2,baseline),char,font=font,fontsize=size)
        elif field['multiline']:
            if not field['size']:
                while size>4:
                    probe=fitz.TextWriter(box)
                    if not probe.fill_textbox(inner,text,font=font,fontsize=size,align=min(2,field['align']),warn=False):break
                    size-=.5
            writer.fill_textbox(inner,text,font=font,fontsize=size,align=min(2,field['align']),warn=False)
        else:
            x=inner.x0+max(0,inner.width-font.text_length(text,fontsize=size))*(min(2,field['align'])/2)
            baseline=inner.y0+(inner.height+size*(font.ascender+font.descender))/2
            writer.append(fitz.Point(x,baseline),text,font=font,fontsize=size)
        writer.write_text(p,color=rgb(field['color']))
        scratch.subset_fonts()
        # Form XObject BBox clips overflow; input itself remains complete in /V.
        return scratch.tobytes(garbage=3,deflate=True)


def fill(document,changes):
    data=scan(document.path);bykey={f['key']:f for f in data['fields']}
    updates={};appearances={};pages=set()
    with fitz.open(document.path) as source:
        for key,value in changes.items():
            field=bykey.get(key)
            if not field or field['readonly'] or field['kind'] in ('unsupported','signature'):raise Unsupported(L('该表单字段不可填写。','This form field cannot be filled.'))
            kind=field['kind']
            if kind in ('text','combo'):
                value=str(value)
                if field['maxlen'] and len(value)>field['maxlen']:raise ValueError(L('输入超过字段长度限制。','Input exceeds the field length limit.'))
            if kind in ('combo','list'):
                values=value if isinstance(value,list) else [value]
                if (kind=='list' or not field['editable']) and any(v and v not in dict(field['options']) for v in values):raise ValueError(L('请选择字段中提供的选项。','Choose one of the field options.'))
            if field['date'] and value:
                from PySide6.QtCore import QDate
                if not QDate.fromString(value,field['date']).isValid():raise ValueError(L('日期格式应为：','Required date format: ')+field['date'])
            if kind in ('check','radio') and value and not field['on']:raise Unsupported(L('该按钮缺少选中外观。','The button has no selected appearance.'))
            updates[field['name']]=(field,value)
        for field in data['fields']:
            if field['name'] not in updates:continue
            value=updates[field['name']][1];pages.add(field['page'])
            if field['kind'] in ('text','combo','list'):appearances[field['key']]=appearance(source,field,value)
    def mutate(pdf):
        for key,page,node in widgets(pdf):
            field=bykey[key]
            if field['name'] not in updates:continue
            selected,value=updates[field['name']];kind=field['kind'];owner=node
            while '/T' not in owner and owner.get('/Parent') is not None:owner=owner.Parent
            if kind in ('check','radio'):
                state=selected['on'] if value else 'Off';stored=pp.Name('/'+state)
                active=bool(value) and (kind=='check' or key==selected['key'])
                node.AS=pp.Name('/'+(field['on'] if active else 'Off'))
            else:stored=pp.Array([pp.String(v) for v in value]) if isinstance(value,list) else pp.String(value)
            owner.V=stored
            if '/V' in node:node.V=stored
            if kind in ('text','combo','list'):
                if '/RV' in owner:del owner['/RV']
                if '/RV' in node:del node['/RV']
                if kind=='list':
                    values=value if isinstance(value,list) else [value]
                    owner.I=pp.Array([i for i,(v,_) in enumerate(field['options']) if v in values])
                elif '/I' in owner:del owner['/I']
                with pp.open(io.BytesIO(appearances[key])) as authored:
                    page=authored.pages[0];stream=pdf.make_stream(b'\n'.join(s.read_bytes() for s in page.Contents) if isinstance(page.Contents,pp.Array) else page.Contents.read_bytes())
                    stream.Type=pp.Name.XObject;stream.Subtype=pp.Name.Form;stream.BBox=pp.Array(page.MediaBox)
                    stream.Resources=pdf.copy_foreign(authored.make_indirect(page.Resources));node.AP=pp.Dictionary(N=stream)
        if '/AcroForm' in pdf.Root:pdf.Root.AcroForm.NeedAppearances=False
    document.edit('form',mutate)
    return sorted(pages)
