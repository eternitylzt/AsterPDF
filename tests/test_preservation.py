import hashlib
import io
from pathlib import Path
import pytest
import pikepdf as pp
import pymupdf as fitz
from asterpdf import media,objects
from asterpdf.core import Document,Unsupported


def streams(doc):
    with pp.open(doc.path) as pdf:
        return sorted(hashlib.sha256(o.read_raw_bytes()).hexdigest() for o in pdf.objects
                      if isinstance(o,pp.Stream) and o.get('/Type')==pp.Name('/EmbeddedFile'))


def test_richmedia_assets_retained_after_content_and_annotation_edit(tmp_path):
    source=Path(__file__).parents[1]/'examples'/'AsterPDF-media.pdf'
    if not source.exists():pytest.skip('Media fixture not generated')
    doc=Document(source,tmp_path/'recovery')
    original=streams(doc)
    assets=media.scan(doc)[1];assert len(assets)==2
    doc.insert_text(0,(55,25,510,70),'Embedded media test',fontsize=18)
    doc.add_annotation(0,'rectangle',[(30,30),(560,760)])
    assert streams(doc)==original
    doc.page_operation('rotate',[0],angle=90)
    target=tmp_path/'media-edited.pdf';doc.save(target)
    assert streams(doc)==original
    assert len(media.scan(doc)[1])==2
    doc.close()


def test_unknown_catalog_data_is_not_dropped(document,tmp_path):
    def custom(pdf):
        pdf.Root['/AsterUnknown']=pp.Dictionary(Message=pp.String('retain'),Payload=pdf.make_stream(b'opaque vendor payload'))
    document.edit('fixture',custom)
    document.add_annotation(0,'note',[(10,10),(11,11)],text='note')
    obj=next(o for o in objects.discover(document,0) if o.text=='Signal amplitude')
    objects.replace_text(document,0,obj,'Changed label')
    document.save(tmp_path/'unknown.pdf')
    with pp.open(document.path) as pdf:
        assert str(pdf.Root.AsterUnknown.Message)=='retain'
        assert pdf.Root.AsterUnknown.Payload.read_bytes()==b'opaque vendor payload'


def test_group_transform_keeps_searchable_text_and_vector_clip(tmp_path):
    with pp.Pdf.new() as pdf:
        page=pdf.add_blank_page(page_size=(400,400))
        form=pdf.make_stream(b'q 0 0 100 100 re W n 1 0 0 rg 10 10 180 80 re f Q')
        form.Type=pp.Name('/XObject');form.Subtype=pp.Name('/Form');form.BBox=pp.Array([0,0,100,100]);form.Resources=pp.Dictionary()
        page.Resources=pp.Dictionary(XObject=pp.Dictionary(Figure=form))
        page.Contents=pdf.make_stream(b'q 1 0 0 1 50 100 cm /Figure Do Q')
        source=tmp_path/'clip.pdf';pdf.save(source)
    doc=Document(source,tmp_path/'recovery')
    obj=objects.discover(doc,0)[0];assert obj.kind=='group'
    objects.transform(doc,0,[obj],dx=25,dy=20,sx=1.2,sy=1.2)
    with pp.open(doc.path) as pdf:
        assert pdf.pages[0].Resources.XObject.Figure.read_bytes()==b'q 0 0 100 100 re W n 1 0 0 rg 10 10 180 80 re f Q'
    with fitz.open(doc.path) as pdf:
        pix=pdf[0].get_pixmap()
        assert pix.pixel(95,245)!=(255,255,255)
    doc.close()
