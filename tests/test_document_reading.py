"""Document-only fullscreen, Markdown outlines/long pages and page seams."""
import pytest
import pymupdf as fitz
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from asterpdf.markdown_import import render,prepare
from test_practical_ui import ui


def test_document_fullscreen_keeps_controls_and_restores_layout(ui):
    app,w,t,pump=ui
    t.minimap.enabled=True;t.minimap.sync();t.show_playback_controls()
    t.open_panel('pages');pump()
    original=t.document_views.currentWidget()
    w.showMaximized();pump();t.canvas.setFocus()
    QTest.keyClick(t.canvas,Qt.Key_F11);pump()
    assert w.document_fullscreen and w.isFullScreen() and not w.presentation
    assert t.document_views.currentWidget() is t.scroll
    assert all(not widget.isVisible() for widget in (w.menuBar(),w.tabs.tabBar(),w.document_switcher,t.navbar_host,t.tool_panels,t.sidebar_container,t.text_container,t.sidebar_toggle))
    w.tick_chrome();t.minimap.sync();t.playback_panel.sync();pump()
    assert getattr(t,'reading_inset',0)==0 and t.minimap.isVisible() and t.playback_panel.isVisible()
    QTest.keyClick(t.canvas,Qt.Key_Right);pump();assert t.canvas.page==1
    QTest.keyClick(t.canvas,Qt.Key_F11);pump()
    assert not w.document_fullscreen and w.isMaximized() and w.menuBar().isVisible()
    assert t.document_views.currentWidget() is original and t.tool_panels.isVisible()
    # Escape also works when a media spinbox owns keyboard focus.
    w.fullscreen();pump();QTest.keyClick(t.playback_panel.fps,Qt.Key_Escape);pump()
    assert not w.document_fullscreen and w.isMaximized()
    t.minimap.enabled=False;t.minimap.sync();t.playback_panel.dismiss()
    w.fullscreen();pump();t.minimap.sync();t.playback_panel.sync()
    assert not t.minimap.isVisible() and not t.playback_panel.isVisible()
    w.toggle_presentation();pump();assert w.presentation and not w.document_fullscreen
    w.escape();pump()


@pytest.mark.parametrize('paginate',[False,True])
def test_markdown_outline_layout_and_save(ui,tmp_path,paginate):
    app,w,t,pump=ui
    source=tmp_path/'outline.md'
    source.write_text('# Title\n\nIntro\n\n## **Repeated** heading\n\n'+('Paragraph of searchable text.\n\n'*90)+'### Deep child\n\nDetails\n\n## Repeated heading\n\nFinal text\n\n```md\n# Not a heading\n```\n\nLast section\n===\n',encoding='utf8')
    target=tmp_path/'outline.pdf';render(source,target,prepare(source),paginate=paginate)
    with fitz.open(target) as pdf:
        toc=pdf.get_toc(simple=False)
        assert [r[:2] for r in toc]==[[1,'Title'],[2,'Repeated heading'],[3,'Deep child'],[2,'Repeated heading'],[1,'Last section']]
        assert len(pdf)>1 if paginate else len(pdf)==1
        if not paginate:assert pdf[0].rect.height>2500
        for _,title,page,dest in toc:
            assert 1<=page<=len(pdf)
            matches=pdf[page-1].search_for(title)
            assert matches and min(abs(r.y0-dest['to'].y) for r in matches)<25
        pdf.save(tmp_path/'saved.pdf')
    with fitz.open(tmp_path/'saved.pdf') as pdf:assert len(pdf.get_toc())==5
    w.settings.setValue('markdown/paginate',paginate)
    w.open_file(source);pump(lambda:not w.opening and not w.queue.jobs)
    tab=w.current();assert len(tab.info['toc'])==5
    last=tab.outline.topLevelItem(1);tab.set_zoom(1.5)
    tab.outline.itemClicked.emit(last,0);pump()
    assert tab.canvas.page==tab.info['toc'][-1][2]-1
    assert tab.scroll.verticalScrollBar().value()>0


def test_double_click_page_gap_closes_and_reopens_without_edit(ui):
    app,w,t,pump=ui
    t.set_view(1,True);t.set_zoom(.45);pump();t.pointer()
    revision=t.document.revision
    a,b=t.canvas.rects[:2];assert b.top()-a.bottom()==pytest.approx(28)
    pos=QPointF(a.center().x(),(a.bottom()+b.top())/2).toPoint()
    QTest.mouseDClick(t.canvas,Qt.LeftButton,Qt.NoModifier,pos);pump()
    assert t.canvas.compact_pages and t.canvas.rects[0].bottom()==t.canvas.rects[1].top()
    pos=QPointF(t.canvas.rects[0].center().x(),t.canvas.rects[0].bottom()).toPoint()
    QTest.mouseDClick(t.canvas,Qt.LeftButton,Qt.NoModifier,pos);pump()
    assert not t.canvas.compact_pages and t.document.revision==revision
    t.set_view(2,True);t.canvas.toggle_page_gaps();pump()
    assert t.canvas.rects[0].right()==t.canvas.rects[1].left()
    assert t.canvas.rects[2].top()==max(t.canvas.rects[0].bottom(),t.canvas.rects[1].bottom())


@pytest.mark.parametrize('columns,hand',[(1,False),(1,True),(2,False),(2,True)])
def test_visible_seam_mouse_cursor_and_repeat_expand(ui,columns,hand):
    app,w,t,pump=ui
    t.set_view(columns,True);t.set_zoom(.55);pump()
    t.set_mode('hand') if hand else t.pointer()
    revision=t.document.revision;canvas=t.canvas
    for axis in (('y',) if columns==1 else ('x','y')):
        for repeat in range(4):
            seam=next(s for s in canvas.page_seams() if s[3]==axis);pos=seam[0].center().toPoint()
            t.scroll.ensureVisible(pos.x(),pos.y(),20,80);pump()
            QTest.mouseMove(canvas,pos);pump()
            assert canvas.cursor().shape()==Qt.BitmapCursor and canvas.toolTip()
            # A real double-click includes a first press/release. It must not pan,
            # select text, activate media, or move the target before the second click.
            QTest.mouseClick(canvas,Qt.LeftButton,Qt.NoModifier,pos)
            QTest.mouseDClick(canvas,Qt.LeftButton,Qt.NoModifier,pos);pump()
            assert canvas.compact_pages==(repeat%2==0)
            assert canvas.pan_anchor is None and canvas.drag_page<0
            if canvas.compact_pages:
                    new=next(s for s in canvas.page_seams() if s[3]==axis)
                    pixel=canvas.grab(new[0].toAlignedRect()).toImage()
                    # The one-pixel line is antialiased at fractional zoom / DPI.
                    colors=[pixel.pixelColor(x,y) for x in range(pixel.width()//2-3,pixel.width()//2+4) for y in range(pixel.height()//2-3,pixel.height()//2+4)]
                    assert any(100<c.red()<245 and c.blue()>=c.red() for c in colors)
    assert not canvas.compact_pages and t.document.revision==revision
