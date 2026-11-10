"""Rotated cross-line selection and editable highlight save/reopen regressions."""
import pytest
import pymupdf as fitz
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from asterpdf.canvas import Canvas
from asterpdf.core import Document


@pytest.mark.parametrize('rotation',[0,90,180,270])
@pytest.mark.parametrize('reverse',[False,True])
def test_cross_line_highlight_rotated_save_reopen(tmp_path,rotation,reverse):
    source=tmp_path/'source.pdf'
    with fitz.open() as pdf:
        p=pdf.new_page(width=400,height=400)
        p.insert_text((60,100),'Alpha first line.\nBeta second line.',fontsize=16)
        p.set_cropbox(fitz.Rect(20,20,380,380))
        p.set_rotation(rotation);pdf.save(source)
    app=QApplication.instance() or QApplication([])
    doc=Document(source,tmp_path/'recovery');canvas=Canvas(None)
    try:
        chars=doc.characters(0);canvas.words[0]=chars
        with fitz.open(doc.path) as pdf:
            p=pdf[0];first=fitz.Rect(chars[0][0])*p.derotation_matrix
            last=fitz.Rect(chars[-1][0])*p.derotation_matrix
            a=fitz.Point(first.x0+.1,(first.y0+first.y1)/2)*p.rotation_matrix
            b=fitz.Point(last.x1-.1,(last.y0+last.y1)/2)*p.rotation_matrix
        start,end=(b,a) if reverse else (a,b)
        chosen=canvas.select_characters(0,QPointF(*start),QPointF(*end))
        assert ''.join(c[1] for c in chosen)=='Alpha first line.Beta second line.'
        rows={}
        for c in chosen:
            key=c[2:4];rows[key]=rows[key]|fitz.Rect(c[0]) if key in rows else fitz.Rect(c[0])
        assert len(rows)==2
        doc.add_annotation(0,'highlight',[tuple(start),tuple(end)],word_rects=list(rows.values()),
                           color=(.2,.6,.9),opacity=.45,text='Cross-line note\n中文备注')
        target=tmp_path/'saved.pdf';doc.save(target)
        reopened=Document(target,tmp_path/'reopened')
        try:
            ann=reopened.annotations(0)[0]
            assert ann['text']=='Cross-line note\n中文备注'
            assert ann['color']==pytest.approx((.2,.6,.9),abs=1e-5)
            assert ann['opacity']==pytest.approx(.45)
            with fitz.open(reopened.path) as pdf:
                p=pdf[0];saved=next(p.annots())
                assert p.rotation==rotation and len(saved.vertices)==8
                for n,rect in enumerate(rows.values()):
                    actual=fitz.Quad(saved.vertices[n*4:n*4+4]).rect*p.rotation_matrix
                    assert tuple(actual)==pytest.approx(tuple(rect),abs=.001)
        finally:reopened.close()
    finally:
        canvas.close();canvas.deleteLater();app.processEvents();doc.close()
