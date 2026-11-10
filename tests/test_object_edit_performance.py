"""Measure only changed objects, retaining authoritative stroke/clip geometry."""
import pymupdf as fitz
import pytest
from asterpdf.core import Document
from asterpdf import objects


@pytest.mark.parametrize('rotation',[0,90])
def test_scaled_selection_measures_only_changed_objects_and_matches_reopen(tmp_path,monkeypatch,rotation):
    source=tmp_path/'many-paths.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page(width=500,height=600)
        for y in range(8):
            for x in range(8):page.draw_rect((30+x*40,30+y*40,50+x*40,50+y*40),width=4,color=(0,.3,.7))
        page.insert_text((40,450),'Keep neighboring text')
        page.set_rotation(rotation);pdf.save(source)
    doc=Document(source,tmp_path/'history')
    try:
        models=objects.discover(doc,0);selected=[o for o in models if o.kind=='vector'][:2]
        calls=[];original=fitz.Page.get_bboxlog
        def counted(page,*args,**kwargs):calls.append(1);return original(page,*args,**kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(fitz.Page,'get_bboxlog',counted)
            result=objects.transform(doc,0,selected,sx=1.6,sy=.8,rotate=27,all_objects=models)
        assert len(calls)==len(selected)
        full=objects.discover(doc,0)
        assert len(result)==len(full)==len(models)
        for cached,actual in zip(result,full):
            assert (cached.id,cached.start,cached.end,cached.kind)==(actual.id,actual.start,actual.end,actual.kind)
            assert cached.bbox==pytest.approx(actual.bbox,abs=.001)
            assert cached.ctm==pytest.approx(actual.ctm,abs=.001)
        saved=tmp_path/'saved.pdf';doc.save(saved)
        with fitz.open(saved) as pdf:assert 'Keep neighboring text' in pdf[0].get_text()
        # Deletion retains IDs in the live selection cache, while a fresh scan
        # numbers objects again. A later resize must still measure that object.
        result=objects.transform(doc,0,[result[0]],delete=True,all_objects=result)
        target=result[0];assert target.id==1
        for _ in range(2):
            result=objects.transform(doc,0,[target],sx=.8,sy=1.4,rotate=19,all_objects=result)
            target=next(o for o in result if o.id==1)
            full=objects.discover(doc,0)
            assert len(full)==len(result)
            for cached,actual in zip(result,full):
                assert (cached.start,cached.end,cached.kind)==(actual.start,actual.end,actual.kind)
                assert cached.bbox==pytest.approx(actual.bbox,abs=.001)
    finally:doc.close()
