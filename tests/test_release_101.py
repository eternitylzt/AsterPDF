"""Focused 1.0.1 regressions: only overview, recent files, palette and shapes."""
from pathlib import Path
import pymupdf as fitz
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtTest import QTest
from asterpdf.core import Document
from asterpdf.tab import DocumentTab
from asterpdf import colors
from test_practical_ui import ui,drag,point


def test_each_new_document_fits_its_own_overview(ui,tmp_path):
    app,w,t,pump=ui;t.minimap.auto_size=False;t.minimap.resize(140,380)
    w.settings.setValue('minimap/auto_size',False);w.settings.setValue('minimap/height',380)
    heights=[];tabs=[]
    for count in (1,2,1):
        path=tmp_path/f'pages-{len(tabs)}.pdf'
        with fitz.open() as pdf:
            for _ in range(count):pdf.new_page(width=595,height=842)
            pdf.save(path)
        doc=Document(path,tmp_path/'recovery-more');tab=DocumentTab(w,doc,doc.info());tabs.append(tab);w.tabs.addTab(tab,path.name);w.tabs.setCurrentWidget(tab)
        pump(lambda:not w.queue.jobs);tab.minimap.sync();assert tab.minimap.auto_size
        heights.append(tab.minimap.height())
    assert heights[0]<heights[1] and abs(heights[2]-heights[0])<=1
    w.tabs.setCurrentWidget(t);t.minimap.sync();assert not t.minimap.auto_size and t.minimap.height()==380
    for tab in tabs:
        tab.closed=True;tab.release_memory();w.tabs.removeTab(w.tabs.indexOf(tab));pump(lambda:not w.queue.jobs);tab.document.close()


def test_recent_file_columns_and_language(ui):
    app,w,t,pump=ui;w.settings.setValue('recent',[t.document.original]);w.refresh_recent();w.tabs.setCurrentWidget(w.welcome);pump()
    tree=w.home_recent;assert tree.columnCount()==3 and tree.topLevelItemCount()==1
    assert tree.headerItem().text(1) in ('大小','Size') and tree.headerItem().text(2) in ('打开时间','Opened')
    item=tree.topLevelItem(0);assert '\n' in item.text(0) and 'MB' in item.text(1) and item.data(0,Qt.UserRole)==t.document.original
    w.change_language('en');assert tree.headerItem().text(0)=='Recent files' and tree.headerItem().text(2)=='Opened'
    w.home_recent.grab()


def test_palette_grid_tolerance_and_source_pick(ui):
    app,w,t,pump=ui;t.replace_colors();pane=t.color_properties;pump(lambda:pane.inputs['source'].count()>0 and not w.queue.jobs)
    grid=pane.inputs['source'];assert pane.inputs['tolerance'].value()==8 and grid.count()<=32
    assert grid.layout().columnCount()==4 and grid.layout().rowCount()==8
    QTest.mouseClick(grid.buttons[0],Qt.LeftButton);assert grid.currentData() is not None
    t.set_color_source((.123,.456,.789));assert grid.currentData()==(.123,.456,.789) and grid.count()<=32
    pane.add_pair();assert pane.pairs[0][0]==(.123,.456,.789)
    assert all('%' not in button.text() for button in grid.buttons)
    low=colors.inventory(t.document,0,tolerance=0);high=colors.inventory(t.document,0,tolerance=.08)
    assert len(high['colors'])<=32 and len(high['colors'])<=len(low['colors'])
    pane.inputs['invert'].setChecked(True);pane.apply_colors();pump(lambda:not t.busy and not w.queue.jobs)
    assert t.document.dirty


def test_draw_select_marquee_move_resize_rotate_and_reopen(ui,tmp_path):
    app,w,t,pump=ui;t.open_panel('objects');pump(lambda:not t.busy and not w.queue.jobs);t.begin_vector_edit();pump(lambda:not t.busy and not w.queue.jobs)
    t.shape_properties.inputs['kind'].setCurrentIndex(3);t.shape_properties.inputs['fill'].setChecked(True)
    t.shape_draw_button.click();drag(t,point(t,(300,470,300,470)),point(t,(440,520,440,520)))
    pump(lambda:not t.busy and not w.queue.jobs)
    assert t.canvas.mode=='objects' and not t.shape_draw_button.isChecked() and t.canvas.selected
    obj=t.selected_objects()[0];assert obj.kind=='vector'
    t.canvas.selected=[];QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,point(t,obj.bbox));assert t.canvas.selected==[obj.id]
    box=t.canvas.selection_box();start=box.center().toPoint();drag(t,start,start+QPoint(15,15));pump(lambda:not t.busy and not w.queue.jobs)
    obj=t.selected_objects()[0];assert obj.bbox[0]>300
    start=t.canvas.resize_handle().center().toPoint();drag(t,start,start+QPoint(10,4));pump(lambda:not t.busy and not w.queue.jobs)
    box=t.canvas.selection_box();t.canvas.selected=[]
    drag(t,box.topLeft().toPoint()-QPoint(10,10),box.bottomRight().toPoint()+QPoint(10,10));assert t.canvas.selected
    start=t.canvas.shape_rotation_handle().center().toPoint();center=t.canvas.selection_box().center();radius=center.y()-start.y()
    drag(t,start,QPoint(round(center.x()+radius),round(center.y())));pump(lambda:not t.busy and not w.queue.jobs)
    obj=t.selected_objects()[0];assert obj.bbox[3]-obj.bbox[1]>obj.bbox[2]-obj.bbox[0]
    target=tmp_path/'rotated-shape.pdf';t.document.save(target)
    with fitz.open(target) as pdf:assert pdf[0].get_drawings() and 'AsterPDF' in pdf[0].get_text()
    t.canvas.grab()
