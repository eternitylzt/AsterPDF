"""Local editing must preserve shared streams, recovery, and neighboring object geometry."""
import json

import pikepdf as pp
import pymupdf as fitz
import pytest

from asterpdf import objects, text_patch
from asterpdf.core import Document


@pytest.mark.parametrize('new_text', ['Label', 'Label REMVE', 'abel REMOVE'])
def test_native_character_delete_and_public_save(tmp_path, monkeypatch, new_text):
    source = tmp_path/'source.pdf'
    with fitz.open() as pdf:
        p = pdf.new_page()
        p.insert_text((40, 60), 'Label REMOVE')
        p.draw_rect((20, 100, 90, 145))
        p.insert_text((40, 180), 'Keep this caption')
        pdf.save(source)
    doc = Document(source, tmp_path/'history')
    try:
        doc.info()
        models = objects.discover(doc, 0)
        target = models[0]
        run = dict(text=target.text, family=target.details['family'], size=target.size,
                   bold=False, italic=False, color=(0, 0, 0))
        old, new = [[run]], [[dict(run, text=new_text)]]
        splice = text_patch.apply(doc, 0, target, old, new)
        assert splice and doc.stable_references_revision == doc.revision
        assert json.loads((doc.folder/'recovery.json').read_text())['compact_on_save']
        with monkeypatch.context() as m:
            calls = []
            bboxlog = fitz.Page.get_bboxlog
            def count(page, *args, **kwargs):
                calls.append(1)
                return bboxlog(page, *args, **kwargs)
            m.setattr(fitz.Page, 'get_bboxlog', count)
            updated = objects.refresh_text_edit(doc, 0, target, splice, models)
            assert len(calls) == 1
        fresh = objects.discover(doc, 0)
        assert [(o.start,o.end,o.kind,o.text,o.bbox) for o in updated] == [
            (o.start,o.end,o.kind,o.text,o.bbox) for o in fresh]
        assert updated[0].text == new_text
        assert updated[-1].bbox == models[-1].bbox
        doc.undo()
        with fitz.open(doc.path) as pdf:assert 'REMOVE' in pdf[0].get_text()
        doc.redo()
        saved = tmp_path/'public.pdf'
        doc.save(saved)
        with fitz.open(saved) as pdf:
            assert pdf.version_count == 1
            assert pdf[0].get_text().splitlines() == [new_text, 'Keep this caption']
            assert sum(pdf.xref_is_stream(i) for i in range(1, pdf.xref_length())) == 1
    finally:
        doc.close()


def test_shared_page_stream_and_mixed_page_sizes(tmp_path):
    source = tmp_path/'shared.pdf'
    with pp.Pdf.new() as pdf:
        stream = pdf.make_stream(b'q 20 20 50 45 re f Q')
        for i, rotation in enumerate((0, 90, 180, 270)):
            page = pdf.add_blank_page(page_size=(300+i, 500+i))
            page.obj.CropBox = pp.Array([-5, 10, 200+i, 450+i])
            page.obj.Rotate = rotation
            page.obj.UserUnit = 2
            page.Contents = stream
        pdf.save(source)
    doc = Document(source, tmp_path/'history')
    try:
        with fitz.open(source) as pdf:
            sizes = [(p.rect.width,p.rect.height) for p in pdf]
        assert doc.info()['sizes'] == sizes
        model = objects.discover(doc, 1)[0]
        objects.transform(doc, 1, [model], dx=11)
        with fitz.open(doc.path) as pdf:
            assert pdf[0].read_contents() == pdf[2].read_contents() == pdf[3].read_contents()
            assert pdf[1].read_contents() != pdf[0].read_contents()
        stamp = doc.path
        def fail(_):
            raise ValueError('failed edit')
        with pytest.raises(ValueError, match='failed edit'):
            doc.edit_stream(0, 'test', fail)
        assert doc.path == stamp and doc.revision == 1
    finally:
        doc.close()


@pytest.mark.parametrize('stream', [
    b'q 20 20 40 40 re W n 12 w 5 5 80 80 re S Q q 10 20 m 150 120 l S Q',
    b'2 w 1 0 0 rg 10 20 m 50 80 l 70 100 l f 4 w 90 10 150 90 re S',
    b'q 20 20 40 40 re W 0 0 20 45 re n 0 0 200 200 re f Q 40 40 90 90 re S',
])
def test_compact_measurements_match_full_graphics_state(tmp_path,monkeypatch,stream):
    source=tmp_path/'paths.pdf'
    with pp.Pdf.new() as pdf:
        pdf.add_blank_page().Contents=pdf.make_stream(stream)
        pdf.save(source)
    doc=Document(source,tmp_path/'history')
    try:
        fast=objects.discover(doc,0)
        def full_background(commands):
            data=bytearray(stream);offsets={0:0}
            for cmd in commands:
                offsets[cmd.end]=cmd.end
                if cmd.op in objects.PAINT:
                    data[cmd.start:cmd.end]=b'n'.rjust(cmd.end-cmd.start,b' ')
            return bytes(data),offsets
        monkeypatch.setattr(objects,'_measurement_background',full_background)
        monkeypatch.setattr(objects,'_independent_scopes',lambda _:[])
        assert fast == objects.discover(doc,0)
    finally:
        doc.close()
