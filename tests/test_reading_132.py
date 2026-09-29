"""Markdown prompts, portable HTML export, and five-row recent-file reading."""
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog,QMessageBox,QComboBox
from asterpdf.markdown_reading import MarkdownSaveDialog,export_markdown_html
from asterpdf.preferences import Preferences
from test_practical_ui import ui


def open_note(w,pump,path):
    path.write_text('# Example\n\n## Section\n\nFormula $x^2$\n\n```python\nprint(123)\n```',encoding='utf-8')
    w.open_file(path);pump(lambda:not w.opening and not w.queue.jobs)
    return w.current()


@pytest.mark.parametrize('answer',[QMessageBox.Yes,QMessageBox.No])
def test_browser_prompt_after_in_app_preview_and_remember(ui,tmp_path,monkeypatch,answer):
    app,w,t,pump=ui;launched=[]
    monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:(launched.append(url),True)[1])
    w.settings.setValue('markdown/browser_mode','ask')
    tab=open_note(w,pump,tmp_path/'first.md')
    pump(lambda:getattr(w,'_markdown_prompt',None) is not None)
    prompt=w._markdown_prompt
    assert w.current()==tab and tab.canvas.cache and len(tab.info['toc'])==2 and not launched
    # A plain No is only for this opening; it must not change the preference.
    QTest.mouseClick(prompt.button(QMessageBox.No),Qt.LeftButton);pump(lambda:w._markdown_prompt is None)
    assert w.settings.value('markdown/browser_mode')=='ask'
    w.close_tab(w.tabs.indexOf(tab));pump()
    tab=open_note(w,pump,tmp_path/'second.md');pump(lambda:w._markdown_prompt is not None)
    prompt=w._markdown_prompt;prompt.checkBox().setChecked(True)
    QTest.mouseClick(prompt.button(answer),Qt.LeftButton);pump(lambda:w._markdown_prompt is None and not w.queue.jobs)
    expected='always' if answer==QMessageBox.Yes else 'never'
    assert w.settings.value('markdown/browser_mode')==expected
    assert len(launched)==int(answer==QMessageBox.Yes)
    assert not tab.document.dirty
    open_note(w,pump,tmp_path/'third.md')
    if answer==QMessageBox.Yes:pump(lambda:len(launched)==2)
    else:QTest.qWait(350)
    assert w._markdown_prompt is None and len(launched)==2*int(answer==QMessageBox.Yes)
    prefs=Preferences(w);field=next(f.inputs['markdown/browser_mode'] for f in prefs.forms if 'markdown/browser_mode' in f.inputs)
    assert field.currentData()==expected
    field.setCurrentIndex(field.findData('ask'));prefs.apply();pump();prefs.deleteLater()
    assert w.settings.value('markdown/browser_mode')=='ask'


def test_html_save_action_format_switch_and_pdf_edits_remain_dirty(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui;tab=open_note(w,pump,tmp_path/'note.md')
    tab.document.add_annotation(0,'note',[(40,50),(40,50)],text='PDF-only note')
    revision=tab.document.revision
    dialog=MarkdownSaveDialog(w,tab);dialog.show();pump()
    combo=dialog.findChild(QComboBox,'fileTypeCombo');assert combo
    QTest.keyClick(combo,Qt.Key_Down);pump()
    assert dialog.html_selected and dialog.html_note.isVisible() and not dialog.pdf_options.isVisible()
    assert Path(dialog.selectedFiles()[0]).suffix=='.html'
    QTest.keyClick(combo,Qt.Key_Up);pump()
    assert not dialog.html_selected and dialog.pdf_options.isVisible() and not dialog.layout_choice.isEnabled()
    assert Path(dialog.selectedFiles()[0]).suffix=='.pdf'
    dialog.reject();dialog.deleteLater()
    closing=MarkdownSaveDialog(w,tab,allow_html=False);assert closing.nameFilters()==['PDF (*.pdf)'];closing.deleteLater()
    destination=tmp_path/'portable.html'
    def accept_html(dialog):
        dialog.selectNameFilter('HTML (*.html *.htm)');dialog.format_changed();return QDialog.Accepted
    monkeypatch.setattr(MarkdownSaveDialog,'exec',accept_html)
    monkeypatch.setattr(MarkdownSaveDialog,'selectedFiles',lambda _:[str(destination)])
    w.save_tab(True);pump(lambda:not tab.busy and not w.queue.jobs)
    html=destination.read_text(encoding='utf8')
    assert '<nav' in html and 'data:image/svg+xml;base64,' in html and 'print(123)' in html
    assert 'PDF-only note' not in html and 'file://' not in html
    assert tab.document.dirty and tab.document.revision==revision
    source=Path(tab.markdown_source);before=source.read_bytes()
    with pytest.raises(ValueError):export_markdown_html(tab,source)
    assert source.read_bytes()==before


def test_home_recent_shows_five_complete_rows(ui,tmp_path):
    app,w,t,pump=ui
    w.settings.setValue('recent',[str(tmp_path/f'History {i}.pdf') for i in range(9)]);w.refresh_recent()
    w.tabs.setCurrentWidget(w.welcome);w.resize(1250,900);QTest.qWait(250);pump();w.welcome.layout().activate();pump()
    tree=w.home_recent;fifth=tree.visualItemRect(tree.topLevelItem(4))
    assert tree.sizeHint().height()>=5*fifth.height()+tree.header().height()
    # macOS limits top-level windows to the runner's small desktop. Five rows
    # are preferred; a shorter actual window must still scroll to every row.
    if w.height()>=850:assert fifth.bottom()<tree.viewport().height()
    else:
        assert tree.viewport().height()>=120
        tree.scrollToItem(tree.topLevelItem(8));pump()
        assert tree.viewport().rect().contains(tree.visualItemRect(tree.topLevelItem(8)).center())
    assert tree.topLevelItem(0).text(0).startswith('History 0.pdf') and tree.topLevelItemCount()==9
    assert tree.verticalScrollBar().maximum()>0
