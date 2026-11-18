"""Reload external PDF changes without giving up the current readable snapshot."""
from pathlib import Path

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtWidgets import QMessageBox

from .core import Document
from .i18n import L, tr


def reload_file(window):
    from .tab import DocumentTab

    old = window.current()
    if not old or old.busy or Path(old.document.original).suffix.lower() != '.pdf':
        return
    dirty = old.document.dirty or old.inline_dirty() or old.suspended_inline or old.form_dirty()
    if dirty:
        choice = QMessageBox.question(window, tr('reload'), L(
            '刷新将放弃本标签页尚未保存的修改，并读取磁盘上的最新 PDF。是否继续？',
            'Reload will discard unsaved changes in this tab and read the latest PDF from disk. Continue?'),
            QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
        if choice != QMessageBox.Discard:
            return

    old.save_state()
    page = old.canvas.page
    anchor = QPointF(old.scroll.viewport().width() / 2, getattr(old, 'reading_inset', 0) + 20)
    scroll = QPointF(old.scroll.horizontalScrollBar().value(), old.scroll.verticalScrollBar().value())
    local = (scroll + anchor - old.canvas.rects[page].topLeft()) / old.canvas.scale
    zoom, fit = old.zoom_factor, old.fit_mode
    columns, continuous = old.canvas.columns, old.canvas.continuous
    compact, night = old.canvas.compact_pages, old.night
    old.busy = True
    old.setEnabled(False)
    old.pause_media()
    window.update_title()

    def work(job):
        document = Document(old.document.original, window.recovery_root)
        try:
            return document, document.info()
        except Exception:
            document.close()
            raise

    def done(result):
        document, info = result
        if old.closed:
            window.queue.submit(lambda job: document.close(), priority=-5)
            return
        try:
            replacement = DocumentTab(window, document, info)
        except Exception:
            window.queue.submit(lambda job: document.close(), priority=-5)
            raise
        index = window.tabs.indexOf(old)
        active = window.current() is old
        fullscreen = active and window.document_fullscreen
        presentation = active and window.presentation
        return_view = window._presentation_state[:2] if presentation else (columns, continuous)
        return_zoom = window._fullscreen_zoom if fullscreen else None
        # Retire the old snapshot only after the new one is fully readable.
        if old.inline_editor:
            old.cancel_inline()
        if presentation:
            window.toggle_presentation()
        if fullscreen:
            window.fullscreen()
        old.closed = True
        old.release_memory()
        window.tabs.blockSignals(True)
        window.tabs.removeTab(index)
        window.tabs.insertTab(index, replacement, Path(document.original).name)
        window.tabs.setTabToolTip(index, document.original)
        if active:
            window.tabs.setCurrentWidget(replacement)
        window.tabs.blockSignals(False)
        if window._previous_tab is old:
            window._previous_tab = None
        if active:
            window.tab_changed(window.tabs.currentIndex())
        else:
            window.update_title()
        window.queue.submit(lambda job: old.document.close(), finished=old.deleteLater, priority=-5)

        def restore_view():
            if replacement.closed:
                return
            replacement.canvas.compact_pages = compact
            replacement.night = night
            replacement.set_view(*return_view)
            replacement.goto(min(page, info['count'] - 1))
            if active and fullscreen and not window.document_fullscreen:
                window.fullscreen(auto_fit=False)
                window._fullscreen_zoom = return_zoom
            elif active and presentation and not window.presentation:
                window.toggle_presentation(auto_fit=False)
            if fit:
                replacement.fit(fit == 'width_fit')
            else:
                replacement.set_zoom(zoom * replacement.actual_size_scale())
            target = replacement.canvas.rects[replacement.canvas.page].topLeft() + local * replacement.canvas.scale
            replacement.canvas.laying_out = True
            replacement.scroll.horizontalScrollBar().setValue(round(target.x() - anchor.x()))
            replacement.scroll.verticalScrollBar().setValue(round(target.y() - anchor.y()))
            replacement.canvas.laying_out = False
            replacement.scroll.sync_document_bar()
            replacement.canvas.update()
            window.update_title()

        QTimer.singleShot(0, restore_view)

    def finished():
        if not old.closed:
            old.busy = False
            old.setEnabled(True)
        window.update_title()

    window.queue.submit(work, done, old.error, finished, priority=3)
