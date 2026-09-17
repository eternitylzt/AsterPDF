import io
import pytest
import pymupdf as fitz
import pikepdf as pp
from PIL import Image
from PySide6.QtCore import Qt,QPoint,QPointF,QMimeData
from PySide6.QtGui import QDragEnterEvent,QDragMoveEvent,QDropEvent
from PySide6.QtWidgets import QApplication,QInputDialog,QListWidget,QFileDialog,QDialogButtonBox
from PySide6.QtTest import QTest
from asterpdf.core import Document
from asterpdf.cropping import crop_document
from test_practical_ui import ui,drag,point


def drop_pages(listing,selected,target,after=False):
    listing.clearSelection()
    for i in selected:listing.item(i).setSelected(True)
    listing.drag_pages=[listing.item(i).data(Qt.UserRole) for i in selected]
    mime=QMimeData();mime.setData(listing.MIME,listing.drag_token)
    box=listing.visualItemRect(listing.item(target));horizontal=listing.flow()==QListWidget.LeftToRight
    pos=QPoint(box.right()-2 if after else box.left()+2,box.center().y()) if horizontal else QPoint(box.center().x(),box.bottom()-2 if after else box.top()+2)
    enter=QDragEnterEvent(pos,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(listing.viewport(),enter);assert enter.isAccepted()
    move=QDragMoveEvent(pos,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(listing.viewport(),move);assert move.isAccepted() and listing.drop_line.isVisible()
    event=QDropEvent(QPointF(pos),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(listing.viewport(),event);assert event.isAccepted() and not listing.drop_line.isVisible()


def test_organizer_real_drop_events_both_directions_and_multiple(ui,monkeypatch,tmp_path):
    app,w,t,pump=ui;monkeypatch.setattr(t,'approve_limit',lambda *a:True)
    t.open_panel('pages');pump(lambda:not w.queue.jobs)
    with fitz.open(t.document.path) as pdf:original=[p.get_text() for p in pdf]
    drop_pages(t.organizer,[2],0);pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert [p.get_text() for p in pdf]==[original[2],original[0],original[1]]
    drop_pages(t.organizer,[0],2,True);pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert [p.get_text() for p in pdf]==original
    drop_pages(t.organizer,[0,1],2,True);pump(lambda:not t.busy)
    target=tmp_path/'reordered.pdf';t.document.save(target)
    with fitz.open(target) as pdf:assert [p.get_text() for p in pdf]==[original[2],original[0],original[1]]


def test_docked_crop_resize_cancel_rotation_and_ranges(ui,monkeypatch):
    app,w,t,pump=ui
    monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:pytest.fail('Unexpected page-range dialog'))
    t.open_panel('pages');t.page_tools('crop');pump();pane=t.page_properties
    assert not pane.isWindow() and not pane.inputs['keep'].isChecked()
    t.fit(False);pump();revision=t.document.revision
    drag(t,point(t,(80,100,80,100)),point(t,(500,720,500,720)))
    assert t.document.revision==revision and pane.apply_button.isEnabled()
    before=t.canvas.region[1];corner=t.canvas.page_rect(*t.canvas.region).bottomRight().toPoint()
    drag(t,corner,corner-QPoint(20,15));assert t.canvas.region[1][2]<before[2]
    t.cancel_page_tools();assert not t.property_container.isVisible() and t.canvas.region is None and t.document.revision==revision
    t.page_tools('crop');pane=t.page_properties;pane.inputs['keep'].setChecked(True)
    t.canvas.region=(0,(80,100,500,720));t.crop_selection_changed();pane.inputs['scope'].setCurrentIndex(2);pane.inputs['pages'].setText('1,3');pane.apply_button.click();pump(lambda:not t.busy)
    assert t.info['sizes'][0]==pytest.approx((420,620)) and t.info['sizes'][2]==pytest.approx((420,620))
    t.page_tools('rotate');pane=t.page_properties;pane.inputs['scope'].setCurrentIndex(1);pane.apply_button.click();pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert all(p.rotation==90 for p in pdf)
    pane.apply_button.click();pump(lambda:not t.busy)
    with fitz.open(t.document.path) as pdf:assert all(p.rotation==180 for p in pdf)


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_destructive_crop_saved_data_resources_undo_and_unmodified_page(tmp_path,rotation):
    source=tmp_path/'input.pdf'
    image=Image.new('RGB',(320,60),(255,0,0));image.paste((0,255,0),(80,0,240,60));buf=io.BytesIO();image.save(buf,format='PNG')
    with fitz.open() as pdf:
        p=pdf.new_page(width=400,height=400);p.insert_text((20,40),'OUTSIDE_SECRET');p.insert_text((155,175),'INSIDE')
        p.draw_rect((155,185,220,215),color=(0,0,1));p.draw_line((20,220),(380,220));p.insert_image((40,240,360,300),stream=buf.getvalue());p.set_rotation(rotation)
        p=pdf.new_page(width=400,height=400);p.insert_text((30,50),'UNTOUCHED');pdf.save(source)
    document=Document(source,tmp_path/'recovery');before=source.read_bytes()
    try:
        with fitz.open(document.path) as pdf:
            # Use visual coordinates for the same unrotated area on every rotation.
            visual=tuple(fitz.Rect(120,100,280,320)*pdf[0].rotation_matrix);untouched=pdf[1].read_contents()
        crop_document(document,[0],0,visual,False);target=tmp_path/'cropped.pdf';document.save(target)
        with fitz.open(target) as pdf:
            p=pdf[0];assert 'INSIDE' in p.get_text() and 'OUTSIDE_SECRET' not in p.get_text(clip=fitz.INFINITE_RECT())
            assert len(p.get_drawings())==1 and pdf[1].read_contents()==untouched
            for entry in p.get_images():
                pix=fitz.Pixmap(pdf,entry[0]);rgb=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                assert (255,0,0) not in {color for count,color in rgb.getcolors(rgb.width*rgb.height)},'Original outside image pixels retained'
            assert sorted((p.rect.width,p.rect.height))==[160,220]
        with pp.open(target) as pdf:
            streams=b'\n'.join(o.read_bytes() for o in pdf.objects if isinstance(o,pp.Stream))
            assert b'OUTSIDE_SECRET' not in streams
        document.undo();assert document.path.read_bytes()==before
        crop_document(document,[0],0,visual,True)
        with fitz.open(document.path) as pdf:
            p=pdf[0];p.set_cropbox(p.mediabox);assert 'OUTSIDE_SECRET' in p.get_text()
        assert source.read_bytes()==before
    finally:document.close()


def test_overview_auto_scale_and_two_page_mapping(ui):
    app,w,t,pump=ui;m=t.minimap
    m.set_auto_scale(True);m.sync();assert m.percent==10
    t.set_view(2,True);m.sync();assert m.rects[0].top()==m.rects[1].top() and m.rects[0].right()<m.rects[1].left()
    t.set_view(2,False);t.set_zoom(2);m.sync();m.seek(m.rects[1].center());assert t.canvas.page==1
    old=t.canvas.sizes[:];t.canvas.sizes=old*8;m.sync();assert m.percent==5 and len(m.rows)==12
    t.canvas.sizes=old;m.sync();assert m.percent==10


def test_blank_extract_delete_and_merge_from_side_panes(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui;t.open_panel('pages');t.page_tools('blank');pane=t.page_properties
    pane.inputs['scope'].setCurrentIndex(1);pane.apply_button.click();pump(lambda:not t.busy);assert t.info['count']==6
    with fitz.open(t.document.path) as pdf:assert all(not pdf[i].get_text() for i in (1,3,5))
    t.page_tools('delete');pane=t.page_properties;pane.inputs['scope'].setCurrentIndex(2);pane.inputs['pages'].setText('2,4,6');pane.apply_button.click();pump(lambda:not t.busy);assert t.info['count']==3
    target=tmp_path/'extracted.pdf';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),'PDF'))
    t.extract_pages();pane=t.page_properties;pane.inputs['scope'].setCurrentIndex(2);pane.inputs['pages'].setText('1,3');pane.apply_button.click();pump(lambda:not t.busy)
    with fitz.open(target) as pdf:assert len(pdf)==2
    t.merge_pane();dialog=t.page_properties.findChild(__import__('asterpdf.dialogs',fromlist=['MergeDialog']).MergeDialog)
    dialog.add_files([str(target)]);output=tmp_path/'merged.pdf';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(output),'PDF'))
    dialog.buttons.button(QDialogButtonBox.Ok).click();pump(lambda:not t.busy and not w.queue.jobs)
    with fitz.open(output) as pdf:assert len(pdf)==5
    for tab in w.document_tabs():
        if tab is not t:tab.document.close()


def test_destructive_crop_refuses_animation_atomically(document):
    from asterpdf.core import Unsupported
    before=document.path;revision=document.revision
    with pytest.raises(Unsupported):crop_document(document,[0,1],0,(40,40,500,700),False)
    assert document.path==before and document.revision==revision
