"""Font identity, mixed-script fallback and saved PDF regressions."""
import copy
import time
from types import SimpleNamespace

import pymupdf as fitz
import pytest
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QMimeData,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox

from asterpdf import objects, text_editing, text_patch
from asterpdf.core import Document, Unsupported
from asterpdf.font_library import normalized, suggestions
from asterpdf.fonts import font_bytes, font_name_key, matched_family


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('name', ['宋体', '黑体', '微软雅黑', 'ABCDEF+微软雅黑', 'ＭＳ ゴシック'])
def test_non_latin_font_identity(app, monkeypatch, name):
    monkeypatch.setattr(QFontDatabase, 'families', lambda: ['Arial', '宋体', '黑体', '微软雅黑', 'MS ゴシック'])
    expected='微软雅黑' if '+' in name else 'MS ゴシック' if name=='ＭＳ ゴシック' else name
    assert matched_family(name)==(expected, True)
    assert font_name_key('宋体') != font_name_key('黑体')
    assert normalized('ABCDEF+微软雅黑-Regular') == normalized('微软雅黑')


def test_font_catalog_does_not_label_other_chinese_family_exact():
    catalog={'song':['ofl/song/宋体-Regular.ttf'], 'hei':['ofl/hei/黑体-Regular.ttf']}
    result=suggestions('黑体',catalog)
    assert result[0][2]=='hei' and result[0][-1]
    assert not next(row for row in result if row[2]=='song')[-1]


def source_document(tmp_path):
    path=tmp_path/'source.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page()
        page.insert_text((60,90),'Anchor',fontname='helv',fontsize=18,color=(.2,.35,.6))
        page.insert_text((60,160),'Untouched neighbour',fontname='tiro',fontsize=12)
        pdf.save(path)
    return Document(path,tmp_path/'recovery')


def runs_for(obj):
    return [[dict(text=obj.text,family=obj.details['family'],size=obj.size,bold=False,italic=False,color=(.2,.35,.6))]]


def test_mixed_chinese_math_fonts_save_reopen_and_reedit(app,tmp_path,monkeypatch):
    # The local machine has both glyph sets, but no single candidate face
    # covers Chinese and mathematical italic alpha together.
    try:
        text_editing.resolve_font('Helvetica','中')
        text_editing.resolve_font('Helvetica','𝛼')
    except Unsupported:
        pytest.skip('Needs installed embeddable Chinese and mathematical fonts')
    calls=[];original_font_bytes=text_editing.font_bytes
    def counted(*args):
        calls.append(args)
        return original_font_bytes(*args)
    monkeypatch.setattr(text_editing,'font_bytes',counted)
    doc=source_document(tmp_path)
    try:
        obj=next(o for o in objects.discover(doc,0) if o.text=='Anchor')
        old=runs_for(obj);new=copy.deepcopy(old);new[0][0]['text']='Anchor 中文𝛼'
        owner=SimpleNamespace(document=doc,inline_page=0,inline_object=obj,inline_original_runs=old)
        text_editing.TextEditingMixin.resolve_inline_fonts(owner,new)
        assert len(calls)==len(set(calls)), 'Each fallback face is read only once per resolution'
        text_patch.apply(doc,0,obj,old,new)
        target=tmp_path/'mixed-saved.pdf';doc.save(target)
    finally:doc.close()
    reopened=Document(target,tmp_path/'reopened')
    try:
        with fitz.open(reopened.path) as pdf:
            assert 'Anchor 中文𝛼' in pdf[0].get_text()
            assert 'Untouched neighbour' in pdf[0].get_text()
            fonts=pdf[0].get_fonts();assert len(fonts)>=4
            spans=[s for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['origin'][1]<120]
            assert all(s['size']==pytest.approx(18,abs=.02) for s in spans)
            assert all(s['color']==0x335999 for s in spans)
            assert all(g[1]!=0 for trace in pdf[0].get_texttrace() for g in trace['chars'])
        obj=next(o for o in objects.discover(reopened,0) if o.text.startswith('Anchor'))
        old=copy.deepcopy(new);changed=copy.deepcopy(new);changed[0][-1]['text']+=' Z'
        owner=SimpleNamespace(document=reopened,inline_page=0,inline_object=obj,inline_original_runs=old)
        text_editing.TextEditingMixin.resolve_inline_fonts(owner,changed)
        text_patch.apply(reopened,0,obj,old,changed)
        again=tmp_path/'mixed-resaved.pdf';reopened.save(again)
        with fitz.open(again) as pdf:
            assert 'Anchor 中文𝛼 Z' in pdf[0].get_text()
            assert 'Untouched neighbour' in pdf[0].get_text()
    finally:reopened.close()


@pytest.mark.parametrize('space',[' ','\u00a0'])
def test_missing_space_in_embedded_subset_uses_valid_font(app,tmp_path,space):
    if 'Arial' not in QFontDatabase.families():pytest.skip('Needs Arial')
    path=tmp_path/'no-space.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page();xref=page.insert_font(fontname='OldSubset',fontbuffer=font_bytes('Arial'))
        page.insert_text((60,90),'AB',fontname='OldSubset',fontsize=18)
        pdf.subset_fonts()
        assert not fitz.Font(fontbuffer=pdf.extract_font(xref)[3]).has_glyph(ord(space))
        pdf.save(path)
    doc=Document(path,tmp_path/'space-recovery')
    try:
        obj=objects.discover(doc,0)[0];old=runs_for(obj);new=copy.deepcopy(old)
        new[0][0]['text']='A'+space+'B'
        owner=SimpleNamespace(document=doc,inline_page=0,inline_object=obj,inline_original_runs=old)
        text_editing.TextEditingMixin.resolve_inline_fonts(owner,new)
        assert fitz.Font(fontbuffer=new[0][0]['fontbuffer']).has_glyph(ord(space))
        text_patch.apply(doc,0,obj,old,new)
        target=tmp_path/'space-saved.pdf';doc.save(target)
        with fitz.open(target) as pdf:
            assert pdf[0].get_text().strip()=='A'+space+'B'
            assert '\0' not in pdf[0].get_text()
    finally:doc.close()


def test_regular_paste_does_not_reuse_cached_bold_face(app,tmp_path):
    if 'Arial' not in QFontDatabase.families():pytest.skip('Needs Arial regular/bold')
    doc=source_document(tmp_path)
    try:
        obj=next(o for o in objects.discover(doc,0) if o.text=='Anchor')
        old=runs_for(obj);new=[[dict(old[0][0],text='Plain',family='Arial')]]
        owner=SimpleNamespace(document=doc,inline_page=0,inline_object=obj,inline_original_runs=old,
                              clipboard_fonts={'Arial':font_bytes('Arial',bold=True)})
        text_editing.TextEditingMixin.resolve_inline_fonts(owner,new)
        assert not fitz.Font(fontbuffer=new[0][0]['fontbuffer']).is_bold
        text_patch.apply(doc,0,obj,old,new)
        target=tmp_path/'regular-paste.pdf';doc.save(target)
        with fitz.open(target) as pdf:
            spans=[s for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['text']=='Plain']
            assert len(spans)==1 and not spans[0]['flags']&16
    finally:doc.close()


@pytest.mark.parametrize('styled',[False,True])
@pytest.mark.parametrize('input_method',['plain_mime','keyboard'])
def test_replace_whole_inline_word_keeps_pdf_format(app,tmp_path,monkeypatch,styled,input_method):
    """Use a real, hidden DocumentTab: application QSS triggers the Qt MIME bug."""
    from asterpdf.app import Window
    from asterpdf.tab import DocumentTab
    if 'Arial' not in QFontDatabase.families():pytest.skip('Needs Arial')
    source=tmp_path/'inline-source.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page();page.insert_font(fontname='Original',fontbuffer=font_bytes('Arial',styled,styled))
        page.insert_text((60,90),'ABXDE',fontname='Original',fontsize=20,color=(.2,.35,.6),
                         morph=(fitz.Point(60,90),fitz.Matrix(1.5,0,0,1,0,0)))
        pdf.save(source)
    errors=[];monkeypatch.setattr(QMessageBox,'warning',lambda *a:errors.append(str(a[-1])))
    window=Window(tmp_path/'hidden-ui');doc=Document(source,tmp_path/'inline-recovery')
    tab=DocumentTab(window,doc,doc.info());window.tabs.addTab(tab,'inline');window.tabs.setCurrentWidget(tab)
    def pump(done):
        end=time.monotonic()+20
        while True:
            app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete)
            assert not errors,errors
            if done():return
            assert time.monotonic()<end,'Hidden inline operation timed out'
            time.sleep(.01)
    try:
        pump(lambda:not window.queue.jobs)
        obj=objects.discover(doc,0)[0];tab.start_inline(obj);editor=tab.inline_editor
        original=copy.deepcopy(tab.text_runs()[0][0]);editor.selectAll()
        if input_method=='plain_mime':
            mime=QMimeData();mime.setText('ABYDE');editor.insertFromMimeData(mime)
        else:QTest.keyClicks(editor,'ABYDE')
        runs=tab.text_runs()[0]
        assert ''.join(r['text'] for r in runs)=='ABYDE'
        for run in runs:
            for key in ('family','size','bold','italic','color'):assert run[key]==original[key]
        tab.commit_inline();pump(lambda:tab.inline_editor is None and not window.queue.jobs)
        target=tmp_path/'inline-saved.pdf';doc.save(target)
        with fitz.open(target) as pdf:
            assert pdf[0].get_text().strip()=='ABYDE'
            spans=[s for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
            assert all('Arial' in s['font'] for s in spans)
            assert all(s['size']==pytest.approx(original['size'],abs=.02) for s in spans)
            assert all(s['color']==0x335999 for s in spans)
            assert all(bool(s['flags']&16)==styled and bool(s['flags']&2)==styled for s in spans)
    finally:
        if tab.inline_editor:tab.cancel_inline()
        tab.closed=True;tab.pause_media();window.tabs.removeTab(window.tabs.indexOf(tab))
        pump(lambda:not window.queue.jobs);doc.close();window.close();window.deleteLater()
        app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete)
