"""Reload a real externally replaced PDF, keeping the old snapshot on failure."""
from pathlib import Path

import pymupdf as fitz
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from test_practical_ui import ui


def replace_source(tab, count=None):
    with fitz.open(tab.document.original) as pdf:
        if count:
            pdf.select(list(range(count)))
        pdf[0].insert_text((40, 80), 'Externally updated PDF')
        data = pdf.tobytes()
    Path(tab.document.original).write_bytes(data)


def test_reload_shortcut_keeps_position_zoom_and_tab_order(ui):
    app, window, tab, pump = ui
    tab.set_view(1, True)
    tab.set_zoom(2)
    tab.goto(1)
    tab.scroll.verticalScrollBar().setValue(tab.scroll.verticalScrollBar().value() + 100)
    pump(lambda: not window.queue.jobs)
    before_y = tab.scroll.verticalScrollBar().value()
    zoom, count, index = tab.zoom_factor, window.tabs.count(), window.tabs.currentIndex()
    assert tab.quick_actions['reload'].isVisible()
    replace_source(tab)
    tab.canvas.setFocus()
    QTest.keyClick(tab.canvas, Qt.Key_R, Qt.ControlModifier)
    pump(lambda: window.current() is not tab and not window.queue.jobs)
    current = window.current()
    assert current.info['count'] == 3 and current.canvas.page == 1
    assert current.zoom_factor == pytest.approx(zoom)
    assert abs(current.scroll.verticalScrollBar().value() - before_y) <= 2
    assert current.canvas.continuous and not current.document.dirty
    assert window.tabs.count() == count and window.tabs.currentIndex() == index
    with fitz.open(current.document.path) as pdf:
        assert 'Externally updated PDF' in pdf[0].get_text()


def test_reload_dirty_cancel_then_discard_and_clamp_page(ui, monkeypatch):
    app, window, tab, pump = ui
    tab.document.add_annotation(0, 'note', [(40, 50), (40, 50)], text='Unsaved note')
    tab.goto(2)
    replace_source(tab, 1)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Cancel)
    window.reload_file()
    assert window.current() is tab and tab.document.dirty and not tab.busy
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Discard)
    tab.quick_actions['reload'].trigger()
    pump(lambda: window.current() is not tab and not window.queue.jobs)
    current = window.current()
    assert current.info['count'] == 1 and current.canvas.page == 0
    assert not current.canvas.continuous and not current.document.dirty
    with fitz.open(current.document.path) as pdf:
        assert all(a.info['content'] != 'Unsaved note' for a in pdf[0].annots())


def test_reload_invalid_source_preserves_document_and_edits(ui, monkeypatch):
    app, window, tab, pump = ui
    tab.document.add_annotation(0, 'note', [(40, 50), (40, 50)], text='Keep this')
    snapshot = tab.document.path.read_bytes()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Discard)
    failures = []
    monkeypatch.setattr(tab, 'error', failures.append)
    Path(tab.document.original).write_bytes(b'not a PDF')
    window.reload_file()
    pump(lambda: not tab.busy and not window.queue.jobs)
    assert failures and window.current() is tab and tab.isEnabled()
    assert tab.document.dirty and tab.document.path.read_bytes() == snapshot
    assert window.reload_action.isEnabled()


@pytest.mark.parametrize('mode', ['fullscreen', 'presentation'])
def test_reload_document_view_can_still_exit(ui, mode):
    app, window, tab, pump = ui
    (window.fullscreen if mode == 'fullscreen' else window.toggle_presentation)()
    QTest.qWait(180)
    replace_source(tab)
    window.reload_file()
    pump(lambda: window.current() is not tab and not window.queue.jobs)
    QTest.qWait(180)
    assert window.document_fullscreen if mode == 'fullscreen' else window.presentation
    window.escape()
    pump()
    assert not window.presentation and not window.document_fullscreen
    # macOS keeps the native menu outside the window; the document tab strip
    # is the cross-platform indication that ordinary window chrome returned.
    assert window.tabs.tabBar().isVisible()
