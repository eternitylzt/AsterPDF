import hashlib
from pathlib import Path
import pikepdf as pp
import pymupdf as fitz
import pytest
from PIL import Image
from asterpdf.core import pages_from_text, Unsupported
from asterpdf import objects, media


def text_of(document,page=0):
    with fitz.open(document.path) as pdf:return pdf[page].get_text()


def test_ranges():
    assert pages_from_text('1,3-5,3',5)==[0,2,3,4]
    for invalid in ('0','6','4-2','x','1,,2'):
        with pytest.raises(ValueError):pages_from_text(invalid,5)


def test_real_text_edit_undo_save_reopen(document,tmp_path):
    before=document.path.read_bytes()
    discovered=objects.discover(document,0)
    obj=next(o for o in discovered if o.kind=='text' and o.text=='Signal amplitude')
    objects.replace_text(document,0,obj,'Photon flux',fontsize=16)
    text=text_of(document)
    assert 'Photon flux' in text and 'Signal amplitude' not in text
    assert 'Select this text' in text
    assert document.dirty
    document.undo();assert document.path.read_bytes()==before
    document.redo();assert 'Photon flux' in text_of(document)
    target=tmp_path/'edited.pdf';document.save(target)
    assert not document.dirty
    with fitz.open(target) as pdf:assert 'Photon flux' in pdf[0].get_text()
    with pp.open(target) as pdf:
        assert '/AcroForm' in pdf.Root and '/Names' in pdf.Root
        assert len(pdf.pages[1].Annots)==24


def test_images_vectors_transform_without_rasterizing(document,tmp_path):
    initial=objects.discover(document,0)
    image=next(o for o in initial if o.kind=='image')
    path=document.extract_image(0,image.xref,tmp_path/'original')
    assert Image.open(path).size==(720,300)
    vector=next(o for o in initial if o.kind=='vector' and (o.bbox[2]-o.bbox[0])>300)
    objects.transform(document,0,[vector],dx=12,dy=8)
    after=objects.discover(document,0)
    shifted=next(o for o in after if o.id==vector.id)
    assert shifted.bbox[0]==pytest.approx(vector.bbox[0]+12,abs=.05)
    assert shifted.bbox[1]==pytest.approx(vector.bbox[1]+8,abs=.05)
    assert text_of(document).count('Signal amplitude')==1
    replacement=tmp_path/'new.png';Image.new('RGB',(88,44),'red').save(replacement)
    image=next(o for o in after if o.kind=='image')
    objects.replace_image(document,0,image,replacement)
    found=objects.discover(document,0);new=next(o for o in found if o.kind=='image')
    extracted=document.extract_image(0,new.xref,tmp_path/'replaced')
    assert Image.open(extracted).size==(88,44)
    objects.transform(document,0,[new],delete=True)
    assert not any(o.kind=='image' for o in objects.discover(document,0))


def test_standard_annotations_survive_reopening(document,tmp_path):
    words=document.words(0);rects=[w[0] for w in words if w[1]=='Select']
    for kind in ('highlight','underline','strikeout'):
        document.add_annotation(0,kind,[(40,80),(220,110)],word_rects=rects)
    for kind in ('note','freetext','ink','line','arrow','rectangle','ellipse'):
        document.add_annotation(0,kind,[(75,710),(115,740),(180,770)],text='Research note')
    annotations=document.annotations(0);assert len(annotations)==10
    document.change_annotation(0,annotations[0]['xref'],color=(1,0,0),width=3,opacity=.5)
    annotations=document.annotations(0)
    document.change_annotation(0,annotations[-1]['xref'],delete=True)
    target=tmp_path/'notes.pdf';document.save(target)
    with pp.open(target) as pdf:
        anns=[a for a in pdf.pages[0].Annots if a.Subtype!=pp.Name('/Popup')]
        assert len(anns)==9
        assert all('/AP' in a for a in anns)
        assert all(str(a.T)=='AsterPDF' for a in anns)
        popups=[a for a in pdf.pages[0].Annots if a.Subtype==pp.Name('/Popup')]
        assert len(popups)==1 and popups[0].Parent.Subtype==pp.Name('/Text')
    assert len(media.scan(document)[0])==1


def test_pages_crop_export_and_revision_recovery(document,tmp_path):
    document.page_operation('rotate',[0],angle=90)
    with fitz.open(document.path) as pdf:assert pdf[0].rotation==90
    pdf_rect=document.to_pdf_rect(0,(10,20,200,300))
    document.page_operation('crop',[0],pdf_rect=pdf_rect)
    document.page_operation('blank',[],position=1)
    assert document.info()['count']==4
    document.page_operation('reorder',[],order=[3,0,1,2])
    assert 'Build your own' in text_of(document,0)
    document.page_operation('delete',[2]);assert document.info()['count']==3
    target=tmp_path/'range.pdf';document.extract_pages([0,1],target)
    with fitz.open(target) as pdf:assert len(pdf)==2
    outputs=document.export_pages([0],tmp_path/'png',dpi=100)
    assert Image.open(outputs[0]).width>800
    assert '"dirty": true' in (document.folder/'recovery.json').read_text()


def test_animation_frames_are_different_and_preserved(document,tmp_path):
    animations,assets,warnings=media.scan(document)
    assert len(animations)==1 and len(animations[0].frames)==24
    a=animations[0];assert a.fps==12 and a.method=='widget'
    filename=media.prepare_animation(document,a)
    first=media.render_frame(filename,0,440);middle=media.render_frame(filename,12,440)
    assert hashlib.sha256(first).digest()!=hashlib.sha256(middle).digest()
    with pp.open(document.path) as pdf:
        hashes=[hashlib.sha256(pdf.get_object((xref,0)).read_bytes()).hexdigest() for xref in a.frames]
    document.add_annotation(0,'rectangle',[(10,10),(40,40)])
    document.save(tmp_path/'roundtrip.pdf')
    updated=media.scan(document)[0][0]
    with pp.open(document.path) as pdf:
        assert hashes==[hashlib.sha256(pdf.get_object((xref,0)).read_bytes()).hexdigest() for xref in updated.frames]


def test_text_glyph_validation_is_transactional(document):
    before=document.path.read_bytes()
    with pytest.raises(Unsupported):document.insert_text(0,(30,30,300,70),'中文',fontsize=12)
    assert document.path.read_bytes()==before
    document.insert_text(0,(30,30,300,70),'New scientific label',fontsize=12)
    assert 'New scientific label' in text_of(document)


def test_raw_lexer_handles_strings_arrays_comments():
    data=b'% untouched\nBT /F1 12 Tf [(a \\(b\\) % c) -20 <4445>] TJ ET\nq 1 0 0 1 3 4 cm /Im Do Q'
    ops=[x.op for x in objects.commands(data)]
    assert ops==['BT','Tf','TJ','ET','q','cm','Do','Q']
