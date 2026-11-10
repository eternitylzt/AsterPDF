"""Image occurrences, transformed placement and alpha survive PDF roundtrips."""
import io
import math

import pikepdf as pp
import pymupdf as fitz
from PIL import Image,ImageDraw
import pytest

from asterpdf import objects
from asterpdf.core import Document


def image_file(path, color, alpha=False, size=(60,40)):
    image=Image.new('RGBA' if alpha else 'RGB',size,color)
    if alpha:
        ImageDraw.Draw(image).rectangle((0,0,size[0]//2-1,size[1]-1),fill=(30,180,70,0))
    else:ImageDraw.Draw(image).rectangle((0,0,size[0]//3-1,size[1]-1),fill=(10,90,220))
    image.save(path)
    return path


def shared_images(tmp_path, *, collision=False, rotation=0, skew=False, crop=False):
    source=tmp_path/'source.pdf';old=image_file(tmp_path/'old.png',(230,30,40))
    with fitz.open() as pdf:
        p=pdf.new_page(width=420,height=320)
        p.draw_rect((0,0,420,320),color=None,fill=(.9,.8,.4))
        xref=p.insert_image((40,40,160,120),filename=str(old),keep_proportion=False)
        p.insert_image((240,40,360,120),xref=xref,keep_proportion=False)
        p.insert_text((240,180),'UNCHANGED',fontsize=14)
        if crop:p.set_cropbox((20,10,400,300))
        p.set_rotation(rotation)
        pdf.save(source)
    if collision or skew:
        with pp.open(source) as pdf:
            page=pdf.pages[0];raw=objects.content_bytes(page)
            if collision:
                names=list(page.Resources.XObject.keys())
                name='/CollisionOriginal'
                resource=page.Resources.XObject[names[0]]
                # A legitimate pre-existing resource may have any name. Both
                # occurrences deliberately use the prospective generated name.
                page.Resources.XObject=pp.Dictionary({name:resource})
                for oldname in names:raw=raw.replace(oldname.encode()+b' Do',name.encode()+b' Do')
            if skew:raw=raw.replace(b'120 0 0 80 40 200 cm',b'100 30 20 70 40 180 cm')
            page.Contents=pdf.make_stream(raw)
            staged=tmp_path/'staged.pdf';pdf.save(staged)
        source=staged
    if collision:
        # Determine the import allocator's next image number without saving
        # that copy. Renaming an existing resource/stream adds no objects.
        with fitz.open() as temp:
            page=temp.new_page();xref=page.insert_image((0,0,100,100),filename=str(old));data=temp.tobytes()
        with pp.open(source) as pdf,pp.open(io.BytesIO(data)) as temp:
            next_image=pdf.copy_foreign(temp.get_object((xref,0))).objgen[0]
        with pp.open(source) as pdf:
            page=pdf.pages[0];name=f'/AsterImage{next_image}'
            page.Resources.XObject=pp.Dictionary({name:page.Resources.XObject['/CollisionOriginal']})
            page.Contents.write(objects.content_bytes(page).replace(b'/CollisionOriginal Do',name.encode()+b' Do'))
            final=tmp_path/'collision.pdf';pdf.save(final)
        source=final
    return source


def image_info(path):
    with fitz.open(path) as pdf:
        return pdf[0].get_image_info(xrefs=True)


@pytest.mark.parametrize('collision',[False,True])
def test_replace_one_shared_image_preserves_other_occurrence(tmp_path,collision):
    source=shared_images(tmp_path,collision=collision)
    replacement=image_file(tmp_path/'replacement.png',(30,210,50))
    doc=Document(source,tmp_path/'recovery')
    try:
        images=[o for o in objects.discover(doc,0) if o.kind=='image']
        assert len(images)==2 and images[0].xref==images[1].xref
        with fitz.open(doc.path) as pdf:before=pdf[0].get_pixmap(clip=(230,30,370,190)).samples
        objects.replace_image(doc,0,images[0],str(replacement),keep_proportion=False)
        saved=tmp_path/'replaced.pdf';doc.save(saved)
        with fitz.open(saved) as pdf:
            assert pdf[0].get_pixmap(clip=(230,30,370,190)).samples==before
            assert 'UNCHANGED' in pdf[0].get_text()
            actual=pdf[0].get_image_info(xrefs=True)
            assert actual[0]['xref']!=actual[1]['xref']
            assert pdf[0].get_pixmap().pixel(120,80)==(30,210,50)
    finally:doc.close()


@pytest.mark.parametrize('rotation',[0,90,180,270])
@pytest.mark.parametrize('replacement_size',[(90,90),(35,80)])
def test_transformed_alpha_replacement_preserves_matrix_and_other_pixels(tmp_path,rotation,replacement_size):
    source=shared_images(tmp_path,rotation=rotation,skew=True)
    replacement=image_file(tmp_path/'transparent.png',(30,210,50,180),alpha=True,size=replacement_size)
    original=image_info(source)
    assert original[0]['transform'][1] and original[0]['transform'][2], 'Fixture must exercise actual shear'
    doc=Document(source,tmp_path/'recovery')
    try:
        images=[o for o in objects.discover(doc,0) if o.kind=='image']
        objects.replace_image(doc,0,images[0],str(replacement),keep_proportion=False)
        saved=tmp_path/'alpha-saved.pdf';doc.save(saved)
        result=image_info(saved)
        assert len(result)==2
        assert (result[0]['width'],result[0]['height'])==replacement_size
        assert result[0]['transform']==pytest.approx(original[0]['transform'],abs=.001)
        assert result[1]['transform']==pytest.approx(original[1]['transform'],abs=.001)
        with fitz.open(saved) as pdf,fitz.open(source) as before:
            assert pdf[0].get_image_info(hashes=True)[1]['digest']==before[0].get_image_info(hashes=True)[1]['digest']
            assert pdf.extract_image(result[0]['xref'])['smask']>0
            # Turn off page rotation solely for deterministic pixel comparison.
            pdf[0].set_rotation(0);before[0].set_rotation(0)
            assert pdf[0].get_pixmap(clip=(230,30,370,190)).samples==before[0].get_pixmap(clip=(230,30,370,190)).samples
            pix=pdf[0].get_pixmap();matrix=fitz.Matrix(result[0]['transform'])
            transparent=fitz.Point(.25,.5)*matrix;translucent=fitz.Point(.75,.5)*matrix
            assert pix.pixel(round(transparent.x),round(transparent.y))==(229,204,102)
            expected=tuple(round(bg*(1-180/255)+fg*180/255) for bg,fg in zip((229,204,102),(30,210,50)))
            assert pix.pixel(round(translucent.x),round(translucent.y))==pytest.approx(expected,abs=2)
    finally:doc.close()


def test_repeated_reopen_image_replacement_keeps_prior_instances(tmp_path):
    source=shared_images(tmp_path)
    replacements=[image_file(tmp_path/f'replace-{i}.png',c) for i,c in enumerate([(60,160,200),(220,140,20),(120,60,200)])]
    for n,replacement in enumerate(replacements):
        doc=Document(source,tmp_path/'repeated-recovery')
        try:
            images=[o for o in objects.discover(doc,0) if o.kind=='image']
            target=n%2;other=1-target
            with fitz.open(doc.path) as pdf:
                rect=images[other].bbox
                previous=pdf[0].get_pixmap(clip=rect).samples
            objects.replace_image(doc,0,images[target],str(replacement))
            saved=tmp_path/f'round-{n}.pdf';doc.save(saved)
            with fitz.open(saved) as pdf:assert pdf[0].get_pixmap(clip=rect).samples==previous
            source=saved
        finally:doc.close()


@pytest.mark.parametrize('page_rotation,instance_rotation,skew',[(0,0,False),(90,37,False),(270,90,False),(180,37,True)])
@pytest.mark.parametrize('replacement_size',[(90,90),(35,80)])
def test_default_replacement_fits_instance_axes_and_center_after_reopen(tmp_path,page_rotation,instance_rotation,skew,replacement_size):
    source=shared_images(tmp_path,rotation=page_rotation,skew=skew,crop=True)
    replacement=image_file(tmp_path/'fit-image.png',(30,210,50,180),alpha=True,size=replacement_size)
    doc=Document(source,tmp_path/'fit-recovery')
    try:
        images=[o for o in objects.discover(doc,0) if o.kind=='image']
        if instance_rotation:
            objects.transform(doc,0,[images[0]],rotate=instance_rotation)
            images=[o for o in objects.discover(doc,0) if o.kind=='image']
        with fitz.open(doc.path) as pdf:
            previous=pdf[0].get_image_info(hashes=True,xrefs=True)
            matrix=fitz.Matrix(previous[0]['transform'])
            pdf[0].set_rotation(0)
            neighbor=pdf[0].get_pixmap(clip=previous[1]['bbox']).samples
        width=math.hypot(matrix.a,matrix.b);height=math.hypot(matrix.c,matrix.d)
        ratio=replacement_size[0]/replacement_size[1]
        fx,fy=(height*ratio/width,1.) if width/height>ratio else (1.,width/ratio/height)
        expected=fitz.Matrix(fx,0,0,fy,(1-fx)/2,(1-fy)/2)*matrix
        objects.replace_image(doc,0,images[0],str(replacement))
        saved=tmp_path/'fit-saved.pdf';doc.save(saved)
        with fitz.open(saved) as pdf:
            result=pdf[0].get_image_info(hashes=True,xrefs=True)
            actual=fitz.Matrix(result[0]['transform'])
            assert tuple(actual)==pytest.approx(tuple(expected),abs=.001)
            assert math.hypot(actual.a,actual.b)/math.hypot(actual.c,actual.d)==pytest.approx(ratio,abs=.00001)
            assert tuple(fitz.Point(.5,.5)*actual)==pytest.approx(tuple(fitz.Point(.5,.5)*matrix),abs=.001)
            assert result[1]['transform']==pytest.approx(previous[1]['transform'],abs=.001)
            assert result[1]['digest']==previous[1]['digest']
            assert pdf.extract_image(result[0]['xref'])['smask']>0
            assert pdf[0].rotation==page_rotation
            assert 'UNCHANGED' in pdf[0].get_text()
            pdf[0].set_rotation(0)
            assert pdf[0].get_pixmap(clip=result[1]['bbox']).samples==neighbor
    finally:doc.close()
