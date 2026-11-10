"""Typing/cancel/commit remain responsive while a PDF worker holds the engine."""
import threading
import time
from contextlib import contextmanager

import pymupdf as fitz
from PySide6.QtGui import QTextCursor,QFontDatabase
from PySide6.QtTest import QTest

from asterpdf import objects,text_preview
from asterpdf.core import ENGINE_LOCK
from asterpdf.fonts import matched_family
from test_practical_ui import ui


@contextmanager
def busy_engine():
    entered=threading.Event();release=threading.Event()
    def hold():
        with ENGINE_LOCK:entered.set();release.wait(5)
    thread=threading.Thread(target=hold);thread.start();assert entered.wait(2)
    try:yield
    finally:release.set();thread.join(5)


def begin(t,pump):
    obj=next(o for o in objects.discover(t.document,0) if o.kind=='text' and o.text)
    t.canvas.object_page=0;t.start_inline(obj);pump(lambda:not t.queue.jobs)
    editor=t.inline_editor;cursor=editor.textCursor();cursor.movePosition(QTextCursor.End);editor.setTextCursor(cursor)
    return editor


def test_preview_keeps_only_latest_draft_and_never_waits_on_engine(ui,monkeypatch):
    app,w,t,pump=ui;editor=begin(t,pump)
    entered=threading.Event();release=threading.Event();calls=[];original=text_preview.render
    def slow(*args):
        calls.append(args)
        if len(calls)==1:entered.set();assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(text_preview,'render',slow)
    editor.insertPlainText('X');editor.preview_timer.stop();t.preview_inline()
    assert entered.wait(2)
    try:
        started=time.perf_counter()
        for letter in 'YZ':
            editor.insertPlainText(letter);editor.preview_timer.stop();t.preview_inline()
        assert time.perf_counter()-started<.25
        assert len(calls)==1 and editor.preview_job in w.queue.jobs
        QTest.qWait(100);assert len(calls)==1
    finally:release.set()
    pump(lambda:not w.queue.jobs and getattr(editor,'preview_text',None)==editor.toPlainText())
    assert len(calls)==2
    assert not t.document.dirty
    # No already-running preview: the lock held by another PDF operation must
    # likewise defer font resolution without blocking the event loop.
    with busy_engine():
        editor.insertPlainText('Q');editor.preview_timer.stop();started=time.perf_counter();t.preview_inline()
        assert time.perf_counter()-started<.15 and editor.preview_timer.isActive()
        t.cancel_inline();assert t.inline_editor is None
    QTest.qWait(100);assert len(calls)==2 and not t.document.dirty


def test_commit_defers_on_busy_engine_and_cancel_remains_available(ui,tmp_path):
    app,w,t,pump=ui;editor=begin(t,pump);editor.insertPlainText('XYZ');editor.preview_timer.stop()
    with busy_engine():
        started=time.perf_counter();t.commit_inline()
        assert time.perf_counter()-started<.15 and editor.commit_pending
        t.cancel_inline();assert t.inline_editor is None
    QTest.qWait(100);assert not t.document.dirty
    editor=begin(t,pump);editor.insertPlainText('XYZ');editor.preview_timer.stop();done=[]
    with busy_engine():
        started=time.perf_counter();t.commit_inline(lambda:done.append(True))
        assert time.perf_counter()-started<.15 and editor.commit_pending
        t.commit_inline(lambda:done.append('superseded action'))
        QTest.qWait(90);assert not done
    pump(lambda:bool(done) and not t.busy and not w.queue.jobs)
    assert done==[True]
    saved=tmp_path/'typed.pdf';t.document.save(saved)
    with fitz.open(saved) as pdf:assert 'XYZ' in pdf[0].get_text()


def test_cancel_deferred_close_clears_its_pending_state(ui):
    app,w,t,pump=ui;editor=begin(t,pump);editor.insertPlainText('XYZ');editor.preview_timer.stop();done=[]
    with busy_engine():
        t.commit_inline(lambda:done.append('navigate'))
        w._close_pending=True
        t.commit_inline(lambda:done.append('close'),lambda:setattr(w,'_close_pending',False))
        t.commit_inline(lambda:done.append('later navigation'))
        t.cancel_inline()
        assert not w._close_pending
    QTest.qWait(100)
    assert not done and not t.document.dirty


def test_family_catalog_refreshes_after_font_registration(monkeypatch):
    monkeypatch.setattr(QFontDatabase,'families',lambda:['Arial'])
    assert matched_family('NewLocalFont')==('Arial',False)
    monkeypatch.setattr(QFontDatabase,'families',lambda:['Arial','NewLocalFont'])
    assert matched_family('NewLocalFont')==('NewLocalFont',True)
