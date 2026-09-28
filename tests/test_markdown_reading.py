"""Single-layer Markdown code rendering and source-snapshot PDF export."""
import pymupdf as fitz
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog
from asterpdf.markdown_reading import MarkdownSaveDialog,export_markdown
from asterpdf.preferences import Preferences
from test_practical_ui import ui


def open_markdown(w,pump,tmp_path):
    source=tmp_path/'codes.md'
    code='print("'+('long token '*45)+'")\nend_of_code_marker'
    source.write_text('# Heading\n\n```python\n'+code+'\n```\n\n'+('Normal paragraph.\n\n'*100)+'## Last heading\n\nEnd of document.',encoding='utf8')
    w.open_file(source);pump(lambda:not w.opening and not w.queue.jobs)
    tab=w.current();tab.fit(True);pump()
    return source,tab,code


def test_code_uses_document_layout_and_export_snapshot(ui,tmp_path):
    app,w,t,pump=ui
    # Existing preferences from the withdrawn overlay must not enable it again.
    w.settings.setValue('markdown/code_scroll',True);w.settings.setValue('markdown/code_wrap',True)
    source,tab,code=open_markdown(w,pump,tmp_path)
    assert tab.info['count']==1 and not hasattr(tab,'markdown_codes')
    with fitz.open(tab.document.path) as pdf:
        assert pdf[0].get_text().count('end_of_code_marker')==1
        words=pdf[0].get_text('words');last=next(x for x in words if x[4]=='end_of_code_marker')
        assert last[3]<next(x[1] for x in words if x[4]=='Normal')
        original=pdf[0].get_text('dict')
    tab.set_mode('region');tab.pointer();tab.set_zoom(1.3);pump()
    with fitz.open(tab.document.path) as pdf:assert pdf[0].get_text('dict')==original
    source.write_text('# Changed on disk\nThis is not the opened document.',encoding='utf8')
    with pytest.raises(ValueError):export_markdown(tab,source,True)
    assert 'Changed on disk' in source.read_text(encoding='utf8')
    for paginate in (True,False):
        destination=tmp_path/('paged.pdf' if paginate else 'long.pdf');export_markdown(tab,destination,paginate)
        with fitz.open(destination) as pdf:
            assert len(pdf)>1 if paginate else len(pdf)==1
            text=''.join(p.get_text() for p in pdf)
            assert 'end_of_code_marker' in text and 'End of document.' in text and 'Changed on disk' not in text
            assert len(pdf.get_toc())==2
            if paginate:assert all(abs(p.rect.height-842)<2 for p in pdf)
    assert tab.document.original==str(source.resolve()) and not tab.document.dirty


def test_markdown_save_dialog_defaults_and_save_action(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui
    source,tab,code=open_markdown(w,pump,tmp_path)
    dialog=MarkdownSaveDialog(w,tab);assert dialog.layout_choice.currentData() is True;dialog.deleteLater()
    destination=tmp_path/'saved.pdf'
    monkeypatch.setattr(MarkdownSaveDialog,'exec',lambda _:QDialog.Accepted)
    monkeypatch.setattr(MarkdownSaveDialog,'selectedFiles',lambda _:[str(destination)])
    w.save_tab(True)
    with fitz.open(destination) as pdf:assert len(pdf)>1 and 'end_of_code_marker' in ''.join(p.get_text() for p in pdf)
    tab.document.add_annotation(0,'note',[(50,70),(50,70)],text='Keep this note')
    dialog=MarkdownSaveDialog(w,tab);assert not dialog.layout_choice.isEnabled() and dialog.layout_choice.currentData() is None;dialog.deleteLater()
    w.save_tab(True);pump(lambda:not tab.busy)
    with fitz.open(destination) as pdf:assert any(a.info.get('content')=='Keep this note' for a in pdf[0].annots())
    preferences=Preferences(w)
    index=next(i for i in range(preferences.tabs.count()) if preferences.tabs.tabText(i)=='Markdown')
    assert {'markdown/paginate','markdown/export_paginate'}<=preferences.forms[index].inputs.keys()
    assert not {'markdown/code_scroll','markdown/code_wrap'}&preferences.forms[index].inputs.keys()
    preferences.deleteLater()
