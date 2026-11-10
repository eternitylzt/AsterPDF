"""Saved text edits retain PDF text-space geometry and surrounding artwork."""
import copy
import io
import pytest
import pymupdf as fitz
from PIL import Image
from asterpdf import objects,text_patch
from asterpdf.core import Document,Unsupported


def fixture(path,text,*,state=b'',matrix=b'1 0 0 1',ctm=b'',rotation=0,outside=False):
    with fitz.open() as pdf:
        page=pdf.new_page(width=600,height=500)
        page.insert_text((50,100),text,fontsize=20,color=(.2,.3,.7))
        stream=page.get_contents()[0];raw=pdf.xref_stream(stream)
        raw=raw.replace(b'1 0 0 1 50 400 Tm',matrix+b' 50 400 Tm')
        raw=raw.replace(b'BT',ctm+b'\n'+(state+b'\nBT' if outside else b'BT\n'+state),1)
        pdf.update_stream(stream,raw)
        page.insert_text((50,160),'NEIGHBOR remains exact',fontsize=14,color=(.1,.6,.2))
        page.draw_rect((45,78,350,112),color=(1,0,0),width=2)
        image=io.BytesIO();Image.new('RGB',(15,15),(10,80,200)).save(image,format='PNG')
        page.insert_image((400,60,460,120),stream=image.getvalue())
        page.set_rotation(rotation);pdf.save(path)


def runs(obj,text=None):
    span=obj.details['spans'][0]
    return [[dict(text=obj.text if text is None else text,family=span['font'],size=span['size'],
                  color=(.2,.3,.7),bold=False,italic=False,fontbuffer=fitz.Font('helv').buffer)]]


def glyphs(path):
    with fitz.open(path) as pdf:
        return [c for s in pdf[0].get_texttrace() for c in s['chars'] if c[2][1]<130]


def assert_glyphs(actual,expected):
    assert [c[0] for c in actual]==[c[0] for c in expected]
    for a,b in zip(actual,expected):
        assert a[2]==pytest.approx(b[2],abs=.002)
        assert a[3]==pytest.approx(b[3],abs=.002)


@pytest.mark.parametrize('options',[
    {'state':b'150 Tz'},
    {'state':b'50 Tz'},
    {'state':b'2 Tc 4 Tw'},
    {'ctm':b'2 0 0 1 0 0 cm'},
    {'ctm':b'1.25 0 0 .8 0 80 cm'},
    {'matrix':b'2 0 0 1'},
    {'matrix':b'1 0 .25 1'},
    {'state':b'150 Tz 2 Tc 4 Tw 6 Ts','outside':True},
    {'state':b'150 Tz 2 Tc 4 Tw','rotation':90},
],ids=['wide','narrow','spacing','ctm-x','ctm-xy','text-matrix','slant','inherited-state','rotated-page'])
def test_replacement_preserves_geometry_and_neighbors_after_reopen(tmp_path,options):
    source=tmp_path/'source.pdf';expected=tmp_path/'expected.pdf';saved=tmp_path/'saved.pdf'
    fixture(source,'AB CDE',**options);fixture(expected,'AB X YE',**options)
    document=Document(source,tmp_path/'recovery')
    try:
        obj=next(o for o in objects.discover(document,0) if o.kind=='text' and 'NEIGHBOR' not in o.text)
        old=runs(obj);new=runs(obj,'AB X YE')
        text_patch.apply(document,0,obj,old,new);document.save(saved)
    finally:document.close()
    assert_glyphs(glyphs(saved),glyphs(expected))
    with fitz.open(source) as before,fitz.open(saved) as after:
        assert after[0].rotation==before[0].rotation
        shapes=lambda page:[{k:v for k,v in item.items() if k!='seqno'} for item in page.get_drawings()]
        assert shapes(after[0])==shapes(before[0])
        assert len(after[0].get_images())==len(before[0].get_images())==1
        before[0].set_rotation(0);after[0].set_rotation(0)
        for rect in [(20,130,580,220),(390,50,470,130)]:
            assert after[0].get_pixmap(clip=rect).samples==before[0].get_pixmap(clip=rect).samples
        assert all(s['color']==pytest.approx((.2,.3,.7),abs=.0001) for s in after[0].get_texttrace() if s['chars'][0][2][1]<130)


def test_append_and_reedit_preserve_spacing_after_save_reopen(tmp_path):
    source=tmp_path/'source.pdf';expected=tmp_path/'expected.pdf';saved=tmp_path/'saved.pdf'
    options={'state':b'150 Tz 2 Tc 4 Tw 6 Ts','outside':True}
    fixture(source,'AB CDE',**options);fixture(expected,'AB CDE X Y',**options)
    doc=Document(source,tmp_path/'recovery')
    try:
        obj=next(o for o in objects.discover(doc,0) if o.kind=='text' and 'NEIGHBOR' not in o.text)
        old=runs(obj);new=runs(obj,'AB CDE X Y');text_patch.apply(doc,0,obj,old,new);doc.save(saved)
    finally:doc.close()
    assert_glyphs(glyphs(saved),glyphs(expected))
    fixture(expected,'AB CDE X Z',**options)
    reopened=Document(saved,tmp_path/'recovery')
    try:
        obj=next(o for o in objects.discover(reopened,0) if o.kind=='text' and 'NEIGHBOR' not in o.text)
        old=runs(obj,'AB CDE X Y');new=runs(obj,'AB CDE X Z')
        text_patch.apply(reopened,0,obj,old,new);reopened.save(saved)
    finally:reopened.close()
    assert_glyphs(glyphs(saved),glyphs(expected))


def test_same_text_and_color_only_edits_leave_positions_unchanged(tmp_path):
    source=tmp_path/'source.pdf';saved=tmp_path/'saved.pdf';fixture(source,'AB CDE',state=b'150 Tz 2 Tc 4 Tw')
    doc=Document(source,tmp_path/'recovery')
    try:
        obj=next(o for o in objects.discover(doc,0) if o.kind=='text' and 'NEIGHBOR' not in o.text)
        old=runs(obj);text_patch.apply(doc,0,obj,old,copy.deepcopy(old));assert doc.revision==0
        changed=copy.deepcopy(old);changed[0][0]['color']=(.6,.2,.1)
        text_patch.apply(doc,0,obj,old,changed);doc.save(saved)
    finally:doc.close()
    assert_glyphs(glyphs(saved),glyphs(source))


def test_backwards_text_is_refused_without_mutation(tmp_path):
    source=tmp_path/'source.pdf';fixture(source,'AB CDE',state=b'-100 Tz',ctm=b'1 0 0 1 300 0 cm')
    doc=Document(source,tmp_path/'recovery')
    try:
        obj=next(o for o in objects.discover(doc,0) if o.kind=='text' and 'NEIGHBOR' not in o.text)
        before=doc.path.read_bytes()
        with pytest.raises(Unsupported,match='horizontal|水平'):
            text_patch.apply(doc,0,obj,runs(obj),runs(obj,'AB XDE'))
        assert doc.revision==0 and doc.path.read_bytes()==before
    finally:doc.close()


@pytest.mark.parametrize('mixed_matrix',[False,True],ids=['same-ui-run','mixed-text-matrix-and-size'])
def test_font_change_keeps_each_original_text_state(tmp_path,mixed_matrix):
    source=tmp_path/'source.pdf';saved=tmp_path/'saved.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page(width=600,height=500);page.insert_font(fontname='helv')
        stream=pdf.get_new_xref();pdf.update_object(stream,'<<>>')
        extra=b'1.5 0 0 1 180 400 Tm /helv 10 Tf (EF) Tj' if mixed_matrix else b''
        pdf.update_stream(stream,b'BT /helv 20 Tf 1 0 0 1 50 400 Tm 0 Tc (AB) Tj 2 Tc (CD) Tj '+extra+b' ET')
        page.set_contents(stream);pdf.save(source)
    doc=Document(source,tmp_path/'recovery')
    try:
        obj=objects.discover(doc,0)[0];old=[]
        for span in obj.details['spans']:
            while len(old)<=span['line']:old.append([])
            old[span['line']].append(dict(text=span['text'],family=span['font'],size=span['size'],color=(0,0,0),bold=False,italic=False))
        new=copy.deepcopy(old)
        for line in new:
            for run in line:run.update(family='Explicit alternate family',fontbuffer=fitz.Font('helv').buffer)
        text_patch.apply(doc,0,obj,old,new);doc.save(saved)
    finally:doc.close()
    assert_glyphs(glyphs(saved),glyphs(source))


@pytest.mark.parametrize('partial',[False,True],ids=['whole-ligature','partial-ligature-refused'])
def test_font_change_groups_ligature_continuation_glyphs(tmp_path,partial):
    source=tmp_path/'ligature.pdf';saved=tmp_path/'saved.pdf';font=fitz.Font('tiro')
    with fitz.open() as pdf:
        page=pdf.new_page(width=600,height=500);xref=page.insert_font(fontname='Original',fontbuffer=font.buffer)
        page.insert_text((50,100),'A\ufb03B',fontname='Original',fontsize=20)
        cmap='''/CIDInit /ProcSet findresource begin
12 dict begin begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /LigatureTest def /CMapType 2 def
1 begincodespacerange <0000> <ffff> endcodespacerange
3 beginbfchar
'''+''.join(f'<{font.has_glyph(code):04x}> <{value}>\n' for code,value in ((65,'0041'),(0xfb03,'006600660069'),(66,'0042')))+'''endbfchar
endcmap CMapName currentdict /CMap defineresource pop end end'''
        mapping=int(pdf.xref_get_key(xref,'ToUnicode')[1].split()[0]);pdf.update_stream(mapping,cmap.encode());pdf.save(source)
    doc=Document(source,tmp_path/'recovery')
    try:
        obj=objects.discover(doc,0)[0];old=runs(obj);old[0][0]['color']=(0,0,0)
        assert obj.text=='AffiB' and [c[1]<0 for c in obj.details['glyphs']]==[False,False,True,True,False]
        if partial:
            new=[[dict(old[0][0],text='Af'),dict(old[0][0],text='f',family='Alternate',fontbuffer=font.buffer),dict(old[0][0],text='iB')]]
            before=doc.path.read_bytes()
            with pytest.raises(Unsupported,match='ligature|合字'):text_patch.apply(doc,0,obj,old,new)
            assert doc.revision==0 and doc.path.read_bytes()==before
        else:
            new=[[dict(old[0][0],family='Alternate',fontbuffer=font.buffer)]]
            text_patch.apply(doc,0,obj,old,new);doc.save(saved)
            actual=glyphs(saved);original=obj.details['glyphs']
            assert ''.join(chr(c[0]) for c in actual)=='AffiB'
            assert all(a[2][0]<b[2][0] for a,b in zip(actual,actual[1:]))
            assert actual[1][2]==pytest.approx(original[1][2],abs=.005)
            delta=font.text_length('ffi',fontsize=20)-(original[1][3][2]-original[1][2][0])
            assert actual[-1][2][0]==pytest.approx(original[-1][2][0]+delta,abs=.005)
    finally:doc.close()
