"""Visible-coordinate object transforms preserve untouched content after saving."""
import math
import pytest
import pymupdf as fitz
from asterpdf import objects
from asterpdf.core import Document,Unsupported


def make_pdf(path,stream,rotation=0,crop=True):
    with fitz.open() as pdf:
        page=pdf.new_page(width=600,height=500)
        xref=pdf.get_new_xref();pdf.update_object(xref,'<<>>');pdf.update_stream(xref,stream);page.set_contents(xref)
        if crop:page.set_cropbox((40,60,550,450))
        page.set_rotation(rotation);pdf.save(path)


def visible_points(obj):
    return [point for _,points in obj.details['hit_path'] for point in points]


def expected_points(points,bounds,dx=0,dy=0,sx=1,sy=1,rotate=0):
    x0,y0,x1,y1=bounds;cx=x0+(x1-x0)*sx/2+dx;cy=y0+(y1-y0)*sy/2+dy
    angle=math.radians(rotate);cos=math.cos(angle);sin=math.sin(angle)
    out=[]
    for x,y in points:
        x=x0+(x-x0)*sx+dx-cx;y=y0+(y-y0)*sy+dy-cy
        out.append((cx+x*cos-y*sin,cy+x*sin+y*cos))
    return out


def bounds(points):
    return min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)


def drawing_records(path):
    with fitz.open(path) as pdf:
        return [{key:value for key,value in record.items() if key!='seqno'} for record in pdf[0].get_drawings()]


@pytest.mark.parametrize('rotation',[0,90,180,270])
@pytest.mark.parametrize('operation',[
    dict(dx=25,dy=15),dict(sx=1.5,sy=.75),dict(rotate=90),dict(dx=15,dy=-12,sx=1.25,sy=.8,rotate=37)
],ids=['move','scale','clockwise-rotation','combined'])
def test_cropped_rotated_nested_path_roundtrip(tmp_path,rotation,operation):
    source=tmp_path/'source.pdf';saved=tmp_path/'saved.pdf'
    make_pdf(source,b'q 1 0 .2 1 10 5 cm q .8 0 0 1.1 10 15 cm 1 0 0 rg 100 270 80 40 re f Q Q '
                    b'q 0 0 1 rg 400 150 30 40 re f Q',rotation)
    doc=Document(source,tmp_path/'recovery')
    try:
        original=objects.discover(doc,0);chosen=original[0]
        expected=expected_points(visible_points(chosen),chosen.bbox,**operation)
        cached=objects.transform(doc,0,[chosen],all_objects=original,**operation)
        fresh=objects.discover(doc,0)
        assert fresh[0].bbox==pytest.approx(bounds(expected),abs=.001)
        assert cached[0].bbox==pytest.approx(fresh[0].bbox,abs=.001)
        assert len(visible_points(fresh[0]))==len(expected)
        for actual,want in zip(visible_points(fresh[0]),expected):assert actual==pytest.approx(want,abs=.001)
        assert fresh[1].bbox==pytest.approx(original[1].bbox,abs=.001)
        doc.save(saved)
        reopened=Document(saved,tmp_path/'recovery')
        try:assert objects.discover(reopened,0)[0].bbox==pytest.approx(bounds(expected),abs=.001)
        finally:reopened.close()
        doc.undo()
        with fitz.open(doc.path) as restored,fitz.open(source) as before:
            assert restored[0].get_pixmap().samples==before[0].get_pixmap().samples
    finally:doc.close()


@pytest.mark.parametrize('operation',[dict(dx=20),dict(sx=1.5),dict(rotate=90),dict(delete=True)],ids=['move','scale','rotate','delete'])
@pytest.mark.parametrize('paint',['stroke','fill'])
def test_path_state_changes_do_not_modify_unselected_neighbors(tmp_path,operation,paint):
    source=tmp_path/'source.pdf';saved=tmp_path/'saved.pdf'
    raw=(b'0 0 0 RG 1 w 50 200 m 1 0 0 RG 6 w [3 2] 1 d 2 J 1 j 150 200 l S 300 200 m 400 200 l S'
         if paint=='stroke' else b'0 0 0 rg 50 200 100 30 re 1 0 0 rg f 300 200 100 30 re f')
    make_pdf(source,raw,crop=False);before=drawing_records(source)
    doc=Document(source,tmp_path/'recovery')
    try:
        selected=objects.discover(doc,0)[0];objects.transform(doc,0,[selected],**operation);doc.save(saved)
    finally:doc.close()
    assert drawing_records(saved)[-1]==before[-1]


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_vertex_move_uses_visible_cropped_coordinates(tmp_path,rotation):
    source=tmp_path/'source.pdf';saved=tmp_path/'saved.pdf'
    make_pdf(source,b'q 2 0 0 1 0 0 cm 50 300 m 100 300 l S Q 350 200 m 400 200 l S',rotation)
    doc=Document(source,tmp_path/'recovery')
    try:
        obj=objects.discover(doc,0)[0];first,last=obj.details['vertices'];target=(last[1]+15,last[2]+7)
        objects.move_vertex(doc,0,obj,last[0],target);doc.save(saved)
        reopened=Document(saved,tmp_path/'recovery')
        try:
            result=objects.discover(reopened,0)[0].details['vertices']
            assert result[0][1:]==pytest.approx(first[1:],abs=.001)
            assert result[-1][1:]==pytest.approx(target,abs=.001)
        finally:reopened.close()
    finally:doc.close()


def test_rotation_cache_can_be_moved_and_scaled_again(tmp_path):
    source=tmp_path/'source.pdf';saved=tmp_path/'saved.pdf'
    make_pdf(source,b'q 1 0 0 rg 100 300 80 40 re f Q q 0 0 1 rg 400 150 30 40 re f Q',90)
    doc=Document(source,tmp_path/'recovery')
    try:
        inventory=objects.discover(doc,0)
        rotated=objects.transform(doc,0,[inventory[0]],rotate=37,all_objects=inventory)
        expected=expected_points(visible_points(rotated[0]),rotated[0].bbox,dx=13,dy=7,sx=1.2,sy=.9)
        cached=objects.transform(doc,0,[rotated[0]],dx=13,dy=7,sx=1.2,sy=.9,all_objects=rotated)
        fresh=objects.discover(doc,0)
        assert fresh[0].bbox==pytest.approx(bounds(expected),abs=.001)
        assert cached[0].bbox==pytest.approx(fresh[0].bbox,abs=.001)
        doc.save(saved)
        reopened=Document(saved,tmp_path/'recovery')
        try:assert objects.discover(reopened,0)[0].bbox==pytest.approx(fresh[0].bbox,abs=.001)
        finally:reopened.close()
    finally:doc.close()


@pytest.mark.parametrize('stream',[
    b'q 50 250 m 2 0 0 1 0 0 cm 100 250 l S Q',
    b'50 250 m q 100 250 l S Q'
])
def test_path_with_internal_graphics_state_is_refused_without_mutation(tmp_path,stream):
    source=tmp_path/'source.pdf';make_pdf(source,stream,crop=False)
    doc=Document(source,tmp_path/'recovery')
    try:
        obj=objects.discover(doc,0)[0];before=doc.path.read_bytes()
        assert obj.reason and not obj.details['vertices'] and not obj.details['hit_path']
        for operation in (dict(dx=10),dict(rotate=90),dict(delete=True)):
            with pytest.raises(Unsupported):objects.transform(doc,0,[obj],**operation)
        with pytest.raises(Unsupported):objects.move_vertex(doc,0,obj,0,(20,20))
        assert doc.revision==0 and doc.path.read_bytes()==before
    finally:doc.close()


@pytest.mark.parametrize('angle',[0,37,90])
@pytest.mark.parametrize('path',[b'50 180 m 150 180 l S',b'50 180 100 40 re S'],ids=['square-cap-line','stroked-rectangle'])
def test_scaled_stroke_cache_matches_remeasurement_and_next_move(tmp_path,angle,path):
    source=tmp_path/'source.pdf';saved=tmp_path/'saved.pdf'
    make_pdf(source,b'12 w 2 J '+path,crop=False)
    doc=Document(source,tmp_path/'recovery')
    try:
        models=objects.discover(doc,0)
        if angle:models=objects.transform(doc,0,[models[0]],rotate=angle,all_objects=models)
        scaled=objects.transform(doc,0,[models[0]],sx=1.7,sy=.6,dx=5,dy=8,all_objects=models)
        measured=objects.discover(doc,0)
        assert scaled[0].bbox==pytest.approx(measured[0].bbox,abs=.001)
        moved=objects.transform(doc,0,[scaled[0]],dx=9,dy=11,all_objects=scaled)
        measured=objects.discover(doc,0)
        assert moved[0].bbox==pytest.approx(measured[0].bbox,abs=.001)
        doc.save(saved)
        reopened=Document(saved,tmp_path/'recovery')
        try:assert objects.discover(reopened,0)[0].bbox==pytest.approx(moved[0].bbox,abs=.001)
        finally:reopened.close()
    finally:doc.close()


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_clipped_path_translation_cache_matches_remeasurement(tmp_path,rotation):
    source=tmp_path/'source.pdf'
    make_pdf(source,b'q 90 250 60 60 re W n 12 w 2 J 60 280 m 180 280 l S Q',rotation)
    doc=Document(source,tmp_path/'recovery')
    try:
        models=objects.discover(doc,0)
        moved=objects.transform(doc,0,[models[0]],dx=23,dy=-17,all_objects=models)
        fresh=objects.discover(doc,0)
        assert moved[0].bbox==pytest.approx(fresh[0].bbox,abs=.001)
    finally:doc.close()
