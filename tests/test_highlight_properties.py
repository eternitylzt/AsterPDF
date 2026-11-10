import pytest
from test_practical_ui import ui


@pytest.mark.parametrize('opacity',[.7,.65])
def test_comment_edit_preserves_highlight_color_and_opacity(ui,tmp_path,opacity):
    app,window,tab,pump=ui
    tab.document.add_annotation(0,'highlight',[(70,90),(180,110)],word_rects=[(70,90,180,110)],
                                color=(.1,.8,.25),opacity=opacity,text='Original')
    original=tab.document.annotations(0)[0]
    tab.set_panel('annotate')
    for text in ['Updated note','中文备注']:
        tab.load_annotations();pump(lambda:not tab.queue.jobs and not tab.busy)
        item=tab.annotation_list.item(0);tab.annotation_list.setCurrentItem(item);item.setSelected(True)
        tab.show_annotation_properties('select_annot',[tab.document.annotations(0)[0]])
        assert tab.annotation_properties.inputs['opacity'].value()==round(opacity*100)
        tab.annotation_text_input.setPlainText(text);tab.annotation_properties.apply_annotations()
        pump(lambda:not tab.busy and not tab.queue.jobs)
        saved=tab.document.annotations(0)[0]
        assert saved['text']==text
        assert saved['opacity']==pytest.approx(original['opacity'],abs=1e-7)
        assert saved['color']==pytest.approx(original['color'],abs=1e-7)
    target=tmp_path/'saved.pdf';tab.document.save(target)
    from asterpdf.core import Document
    reopened=Document(target,tmp_path/'reopened')
    try:
        saved=reopened.annotations(0)[0]
        assert saved['text']=='中文备注' and saved['opacity']==pytest.approx(original['opacity'],abs=1e-7)
        assert saved['color']==pytest.approx(original['color'],abs=1e-7)
    finally:reopened.close()


def test_mouse_switch_refreshes_comment_and_style_before_apply(ui):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    app,window,tab,pump=ui
    for y,color,opacity,text in [(90,(1,0,0),.7,'First'),(140,(.2,.4,1),.65,'Second')]:
        tab.document.add_annotation(0,'highlight',[(70,y),(180,y+20)],word_rects=[(70,y,180,y+20)],color=color,opacity=opacity,text=text)
    tab.set_panel('annotate');tab.load_annotations();pump(lambda:not tab.queue.jobs and not tab.busy)
    for n,text,percent in [(0,'First',70),(1,'Second',65)]:
        item=tab.annotation_list.item(n);tab.annotation_list.scrollToItem(item);pump()
        QTest.mouseClick(tab.annotation_list.viewport(),Qt.LeftButton,Qt.NoModifier,tab.annotation_list.visualItemRect(item).center());pump()
        assert tab.annotation_text_input.toPlainText()==text
        assert tab.annotation_properties.inputs['opacity'].value()==percent
    original=next(a for a in tab.document.annotations(0) if a['text']=='Second')
    tab.annotation_text_input.setPlainText('Edited second');tab.annotation_properties.apply_annotations()
    pump(lambda:not tab.busy and not tab.queue.jobs)
    result=next(a for a in tab.document.annotations(0) if a['text']=='Edited second')
    assert result['color']==pytest.approx(original['color'],abs=1e-7)
    assert result['opacity']==pytest.approx(original['opacity'],abs=1e-7)
    assert any(a['text']=='First' for a in tab.document.annotations(0))
