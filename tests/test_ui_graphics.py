"""Object property callbacks and native path styles survive saving and history.

The property dialog stays hidden: no desktop window is shown or activated.
"""
import io
from types import SimpleNamespace

import pymupdf as fitz
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QFileDialog, QWidget

from asterpdf import figures, objects
from asterpdf.core import Document
from asterpdf.dialogs import FormDialog
from asterpdf.properties import PropertiesMixin
from asterpdf.tab import DocumentTab


class PropertyHost(QWidget):
    """Run the real tab callbacks synchronously without opening a tab/window."""
    selected_objects = DocumentTab.selected_objects

    def __init__(self, document, kind):
        super().__init__()
        self.document = document
        models = objects.discover(document, 0)
        target = next(o for o in models if o.kind == kind)
        self.canvas = SimpleNamespace(objects=models, selected=[target.id], object_page=0)
        self.keep_image_ratio = QCheckBox()
        self.keep_image_ratio.setChecked(True)

    def run(self, label, action, **options):
        result = action(None)
        self.canvas.objects = result if options.get('fast_objects') and result is not None else objects.discover(self.document, 0)

    def error(self, message):
        raise AssertionError(message)


def graphics_fixture(path, kind, rotation=0):
    with fitz.open() as pdf:
        page = pdf.new_page(width=400, height=360)
        rect = fitz.Rect(60, 80, 180, 150)
        if kind == 'image':
            image = Image.new('RGB', (60, 35), 'red')
            image.paste('yellow', (0, 0, 20, 20))
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            page.insert_image(rect, stream=buffer.getvalue())
        elif kind == 'vector':
            page.draw_polyline([rect.tl, rect.tr, rect.br, (110, 125)], color=(0, 0, 0), fill=(1, .5, 0), closePath=True)
        else:
            with fitz.open() as source:
                p = source.new_page(width=120, height=70)
                p.draw_rect((0, 0, 120, 70), color=None, fill=(0, .6, 0))
                p.insert_text((10, 35), 'Form text')
                page.show_pdf_page(rect, source, 0)
        page.insert_text((220, 280), 'Keep this neighbor')
        page.draw_rect((220, 300, 280, 320), color=None, fill=(0, 0, 1))
        page.set_rotation(rotation)
        pdf.save(path)


def snapshot(path):
    with fitz.open(path) as pdf:
        page = pdf[0]
        return page.get_pixmap().samples, page.get_text(), page.rotation


@pytest.mark.parametrize('kind', ['image', 'vector', 'group'])
@pytest.mark.parametrize('rotation', [0, 90])
def test_property_transform_matches_gesture_callbacks_and_history(tmp_path, monkeypatch, kind, rotation):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / 'source.pdf'
    graphics_fixture(source, kind, rotation)
    numeric = Document(source, tmp_path / 'numeric-history')
    gesture = Document(source, tmp_path / 'gesture-history')
    numeric_host = PropertyHost(numeric, kind)
    gesture_host = PropertyHost(gesture, kind)
    before = numeric.path.read_bytes()
    original = numeric_host.selected_objects()[0]
    shown = []

    def accept_values(dialog):
        shown.append(dialog)
        assert not dialog.isVisible()
        assert 'rotate' in dialog.inputs
        assert dialog.inputs['rotate'].minimum() == -360
        assert dialog.inputs['rotate'].maximum() == 360
        for key, value in {'dx': 12, 'dy': 7, 'sx': 1.4, 'sy': .8, 'rotate': 31}.items():
            dialog.inputs[key].setValue(value)
        dialog.inputs['ratio'].setChecked(False)
        return QDialog.Accepted

    monkeypatch.setattr(FormDialog, 'exec', accept_values)
    try:
        DocumentTab.transform_dialog(numeric_host)
        assert len(shown) == 1 and numeric.index == 1
        DocumentTab.move_objects(gesture_host, 12, 7)
        width = original.bbox[2] - original.bbox[0]
        height = original.bbox[3] - original.bbox[1]
        DocumentTab.resize_objects(gesture_host, width * .4, height * -.2, free=True)
        if kind == 'image':
            gesture_host.run('rotate', lambda job: figures.rotate(gesture, 0, gesture_host.selected_objects(), 31))
        else:
            PropertiesMixin.rotate_shapes(gesture_host, 31)
        assert gesture.index == 3
        numeric_model = next(o for o in objects.discover(numeric, 0) if o.kind == kind)
        gesture_model = next(o for o in objects.discover(gesture, 0) if o.kind == kind)
        assert numeric_model.bbox == pytest.approx(gesture_model.bbox, abs=.002)
        assert snapshot(numeric.path) == snapshot(gesture.path)
        edited = numeric.path.read_bytes()
        numeric.undo()
        assert numeric.path.read_bytes() == before
        numeric.redo()
        assert numeric.path.read_bytes() == edited
        for _ in range(3):
            gesture.undo()
        assert gesture.path.read_bytes() == before
        for _ in range(3):
            gesture.redo()
        assert snapshot(gesture.path) == snapshot(numeric.path)
        target = tmp_path / 'saved.pdf'
        numeric.save(target)
        reopened = Document(target, tmp_path / 'reopened-history')
        try:
            assert snapshot(reopened.path) == snapshot(numeric.path)
            assert 'Keep this neighbor' in snapshot(reopened.path)[1]
            assert snapshot(reopened.path)[2] == rotation
        finally:
            reopened.close()
    finally:
        numeric_host.close()
        gesture_host.close()
        numeric.close()
        gesture.close()


def path_fixture(path, content):
    with fitz.open() as pdf:
        page = pdf.new_page(width=300, height=300)
        xref = pdf.get_new_xref()
        pdf.update_object(xref, '<<>>')
        pdf.update_stream(xref, content)
        page.set_contents(xref)
        pdf.save(path)


@pytest.mark.parametrize('keep_ratio', [True, False])
def test_replace_image_menu_uses_aspect_ratio_choice_and_reopens(tmp_path, monkeypatch, keep_ratio):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / 'source.pdf'
    graphics_fixture(source, 'image')
    replacement = tmp_path / 'portrait.png'
    Image.new('RGB', (30, 90), 'purple').save(replacement)
    document = Document(source, tmp_path / 'history')
    host = PropertyHost(document, 'image')
    host.keep_image_ratio.setChecked(keep_ratio)
    original = document.path.read_bytes()
    before = fitz.Rect(host.selected_objects()[0].bbox)

    class ReplaceMenu:
        def __init__(self, parent):
            self.items = []

        def addAction(self, text):
            action = object()
            self.items.append(action)
            return action

        def exec(self, position):
            return self.items[0]

    monkeypatch.setattr('asterpdf.tab.QMenu', ReplaceMenu)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(replacement), ''))
    try:
        DocumentTab.modify_object(host)
        assert document.index == 1
        target = tmp_path / 'replaced.pdf'
        document.save(target)
        with fitz.open(target) as pdf:
            image = pdf[0].get_image_info(xrefs=True)[0]
            after = fitz.Rect(image['bbox'])
            assert image['width'] == 30 and image['height'] == 90
            expected_width = before.height / 3 if keep_ratio else before.width
            assert after.width == pytest.approx(expected_width, abs=.002)
            assert after.height == pytest.approx(before.height, abs=.002)
            assert tuple((after.tl + after.br) / 2) == pytest.approx(tuple((before.tl + before.br) / 2), abs=.002)
            assert 'Keep this neighbor' in pdf[0].get_text()
        document.undo()
        assert document.path.read_bytes() == original
        document.redo()
        assert snapshot(document.path) == snapshot(target)
    finally:
        host.close()
        document.close()


@pytest.mark.parametrize('paint,fill,expected', [
    ('f*', (1, 0, 0), 'B*'),
    ('B*', (1, 0, 0), 'B*'),
    ('b*', (1, 0, 0), 'b*'),
    ('b*', None, 's'),
    ('s', (1, 0, 0), 'b'),
    ('s', None, 's'),
])
def test_path_style_keeps_even_odd_and_closed_paint_after_reopen(tmp_path, paint, fill, expected):
    source = tmp_path / 'source.pdf'
    path = b'50 50 120 120 re 80 80 60 60 re ' if '*' in paint else b'50 50 m 150 50 l 100 140 l '
    path_fixture(source, b'q 0 0 0 rg 2 w ' + path + paint.encode() + b' Q')
    document = Document(source, tmp_path / 'history')
    try:
        obj = objects.discover(document, 0)[0]
        figures.style_vectors(document, 0, [obj], (0, 0, 1), fill, 2)
        target = tmp_path / 'styled.pdf'
        document.save(target)
        with fitz.open(target) as pdf:
            paints = [c.op for c in objects.commands(pdf[0].read_contents()) if c.op in objects.PAINT]
            assert paints == [expected]
            drawing = pdf[0].get_drawings()[0]
            if '*' in expected:
                assert drawing['even_odd']
                assert pdf[0].get_pixmap().pixel(110, 190) == (255, 255, 255)
            if expected in ('s', 'b', 'b*') and '*' not in paint:
                # The closing triangle edge passes through (75, 205).
                assert pdf[0].get_pixmap().pixel(75, 205) != (255, 255, 255)
    finally:
        document.close()


def test_path_style_replays_original_state_for_neighbor_and_undo(tmp_path):
    source = tmp_path / 'source.pdf'
    path_fixture(source, b'50 50 m 120 50 l 1 0 0 RG 5 w [3 2] 0 d S\n200 50 m 260 50 l S')
    document = Document(source, tmp_path / 'history')
    try:
        with fitz.open(document.path) as pdf:
            before = pdf[0].get_pixmap(clip=(190, 240, 275, 260)).samples
        original = document.path.read_bytes()
        figures.style_vectors(document, 0, [objects.discover(document, 0)[0]], (0, 1, 0), None, 1)
        with fitz.open(document.path) as pdf:
            assert pdf[0].get_pixmap(clip=(190, 240, 275, 260)).samples == before
            assert pdf[0].get_drawings()[0]['color'] == (0., 1., 0.)
        styled = document.path.read_bytes()
        document.undo()
        assert document.path.read_bytes() == original
        document.redo()
        assert document.path.read_bytes() == styled
        target = tmp_path / 'neighbor-preserved.pdf'
        document.save(target)
        with fitz.open(target) as pdf:
            assert pdf[0].get_pixmap(clip=(190, 240, 275, 260)).samples == before
    finally:
        document.close()
