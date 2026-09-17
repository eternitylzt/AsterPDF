"""Read the selected installed font through Qt; never require a font file picker."""
from .i18n import L
import re
import struct
from PySide6.QtGui import QFont, QFontDatabase, QRawFont
from .core import Unsupported

TAGS = ('head','hhea','maxp','OS/2','hmtx','cmap','loca','glyf','name','post','cvt ','fpgm','prep','gasp','kern','GPOS','GSUB','GDEF','CFF ','CFF2','VORG','vhea','vmtx','BASE','JSTF','DSIG','fvar','gvar','avar','HVAR','MVAR','STAT')

def matched_family(name):
    name = name.split('+')[-1]
    norm = lambda n: re.sub('[^a-z0-9]','',n.lower())
    families = QFontDatabase.families()
    wanted = norm(name)
    for family in families:
        if norm(family)==wanted: return family,True
    # Style suffixes and PDF subset prefixes are not family names.
    base=re.sub(r'(regular|bolditalic|bold|italic|oblique|roman|psmt|mt)$','',wanted)
    for family in families:
        if norm(family)==base:return family,True
    aliases={'helvetica':['Arial','Liberation Sans','Noto Sans'], 'times':['Times New Roman','Liberation Serif','Noto Serif'],
             'courier':['Courier New','Liberation Mono','Noto Sans Mono'], 'cmr':['Latin Modern Roman','CMU Serif','Times New Roman','Noto Serif'],
             'cmb':['Latin Modern Roman','CMU Serif','Times New Roman','Noto Serif'], 'cmss':['Latin Modern Sans','Arial','Noto Sans'],
             'cmtt':['Latin Modern Mono','Courier New','Noto Sans Mono'], 'nimbus':['Arial','Liberation Sans'],
             'simsun':['SimSun','Noto Serif CJK SC','Songti SC'], 'song':['SimSun','Noto Serif CJK SC','Songti SC']}
    for prefix,options in aliases.items():
        if wanted.startswith(prefix):
            for family in options:
                if family in families:return family,False
    for family in sorted(families,key=len,reverse=True):
        if wanted.startswith(norm(family)) and len(norm(family))>3:return family,True
    serif=any(x in wanted for x in ('serif','roman','times','cmr','cmb','song'))
    for family in (['Times New Roman','Noto Serif','Liberation Serif'] if serif else ['Arial','Noto Sans','Liberation Sans']):
        if family in families:return family,False
    return QFont().defaultFamily(),False


def font_bytes(family, bold=False, italic=False):
    font=QFont(family);font.setBold(bold);font.setItalic(italic)
    raw=QRawFont.fromFont(font)
    if not raw.isValid(): raise Unsupported(L('无法读取系统字体','Cannot read system font'))
    tables={tag:bytes(raw.fontTable(tag)) for tag in TAGS}
    tables={k:v for k,v in tables.items() if v}
    os2=tables.get('OS/2',b'')
    if len(os2)>=10 and int.from_bytes(os2[8:10],'big') & 0x302:
        raise Unsupported(L('该字体限制嵌入，请选择其它字体','Font restricts embedding/subsetting; choose another font'))
    if 'head' not in tables or not ('glyf' in tables or 'CFF ' in tables):
        raise Unsupported(L('该系统字体格式暂不支持嵌入','This font format cannot be embedded'))
    head=bytearray(tables['head']);head[8:12]=b'\0'*4;tables['head']=bytes(head)
    count=len(tables);power=2**(count.bit_length()-1)
    header=struct.pack('>4sHHHH',b'OTTO' if 'CFF ' in tables else b'\0\1\0\0',count,power*16,power.bit_length()-1,count*16-power*16)
    directory=bytearray();body=bytearray();offset=12+16*count;head_offset=0
    for tag,data in sorted(tables.items()):
        padded=data+b'\0'*((-len(data))%4)
        checksum=sum(struct.unpack('>'+str(len(padded)//4)+'I',padded))&0xffffffff
        directory.extend(struct.pack('>4sIII',tag.encode(),checksum,offset,len(data)))
        if tag=='head': head_offset=offset
        body.extend(padded);offset+=len(padded)
    result=bytearray(header+directory+body)
    checksum=sum(struct.unpack('>'+str(len(result)//4)+'I',result))&0xffffffff
    result[head_offset+8:head_offset+12]=struct.pack('>I',(0xB1B0AFBA-checksum)&0xffffffff)
    return bytes(result)


def set_unicode_map(pdf,xref,font,text):
    """Resolve shared glyph IDs (e.g. space/NBSP) to the characters actually typed."""
    mapping={}
    for ch in text:
        if ch in '\r\n':continue
        gid=font.has_glyph(ord(ch))
        if gid and (gid not in mapping or ch==' '):mapping[gid]=ch
    entries=[f'<{gid:04x}> <{ch.encode("utf-16-be").hex()}>' for gid,ch in sorted(mapping.items())]
    chunks=[]
    for start in range(0,len(entries),100):
        rows=entries[start:start+100];chunks.append(f'{len(rows)} beginbfchar\n'+'\n'.join(rows)+'\nendbfchar')
    cmap='/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def /CMapName /AsterUnicode def /CMapType 2 def 1 begincodespacerange <0000> <ffff> endcodespacerange\n'+'\n'.join(chunks)+'\nendcmap CMapName currentdict /CMap defineresource pop end end'
    cm=pdf.get_new_xref();pdf.update_object(cm,'<<>>');pdf.update_stream(cm,cmap.encode('ascii'));pdf.xref_set_key(xref,'ToUnicode',f'{cm} 0 R')
