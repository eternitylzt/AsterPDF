"""Docked color, image and vector-shape properties."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QImage,QPixmap,QIcon
from PySide6.QtWidgets import QWidget,QVBoxLayout,QPushButton,QColorDialog,QFileDialog,QLabel,QCheckBox,QSpinBox,QScrollArea,QFrame
from .dialogs import FormDialog
from .chrome import OffsetPanel
from .i18n import L,tr
from .core import pages_from_text
from . import colors,figures

class PropertiesMixin:
    def property_pane(self,title):
        self.page_live_operations=[]
        if self.inline_editor:self.suspend_inline()
        self.text_properties.hide();self.text_container.hide();self.document_views.setCurrentWidget(self.scroll)
        if hasattr(self,'property_container'):self.property_container.hide();self.property_container.deleteLater()
        for name in ('figure_place','figure_page','shape_draw_button','shape_properties','image_properties','color_properties','shape_stroke','shape_fill','image_filename','page_properties'):
            if hasattr(self,name):delattr(self,name)
        pane=FormDialog(title,self);pane.setWindowFlags(Qt.Widget);pane.setMinimumWidth(220);pane.setMaximumWidth(290)
        heading=QLabel(title);font=heading.font();font.setBold(True);heading.setFont(font);pane.form.insertRow(0,heading)
        scroller=QScrollArea();scroller.setWidgetResizable(True);scroller.setFrameShape(QFrame.NoFrame);scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);scroller.setMinimumWidth(235);scroller.setMaximumWidth(310);scroller.setWidget(pane)
        self.property_container=OffsetPanel(scroller);self.splitter.insertWidget(1,self.property_container)
        self.property_container.show();pane.show();self.position_chrome();return pane

    def close_properties(self):
        if hasattr(self,'property_container'):self.property_container.hide()
        self.edit_tool='text';self.set_mode('objects' if self.active_panel=='objects' else 'select')

    def color_button(self,pane,label,color):
        button=QPushButton(color.name());button.color=QColor(color)
        def choose():
            picked=QColorDialog.getColor(button.color,self)
            if picked.isValid():button.color=picked;button.setText(picked.name());button.setStyleSheet('border:2px solid '+picked.name())
        button.clicked.connect(choose);pane.form.addRow(label,button);return button

    def replace_colors(self):
        from .color_tools import build
        build(self)

    def begin_vector_edit(self):
        pane=self.property_pane(tr('vector_edit'));self.shape_properties=pane;self.canvas.vector_edit=True;self.edit_tool='shape';self.set_mode('objects')
        pane.choice('kind',L('形状','Shape'),[(L('矩形','Rectangle'),'rectangle'),(L('椭圆','Ellipse'),'ellipse'),(L('线条','Line'),'line'),(L('实心箭头','Block arrow'),'arrow'),(L('三角形','Triangle'),'triangle'),(L('菱形','Diamond'),'diamond'),(L('五角星','Star'),'star')])
        self.shape_stroke=self.color_button(pane,L('轮廓','Outline'),QColor(self.window.settings.value('shape/stroke','#243249')));self.shape_fill=self.color_button(pane,L('填充','Fill'),QColor(self.window.settings.value('shape/color','#b6cff4')))
        pane.check('fill',L('填充形状','Fill shape'),self.window.settings.value('shape/fill',False,type=bool));pane.number('width',L('线宽（点）','Width (pt)'),self.window.settings.value('shape/width',1.5,type=float),.1,50,1)
        draw=QPushButton(L('绘制形状','Draw shape'));draw.setCheckable(True);draw.clicked.connect(lambda checked:self.set_mode('draw_shape' if checked else 'objects'));pane.form.addRow(draw)
        self.shape_draw_button=draw
        style=QPushButton(L('应用到选中图形','Apply to selected paths'));style.clicked.connect(self.apply_shape_style);pane.form.addRow(style)
        pane.note(L('绘制后直接单击或框选图形；拖动移动，右下角缩放，上方圆柄旋转。橙色节点可调整路径端点。','After drawing, click or marquee to select. Drag to move, resize at the lower-right corner, or rotate using the top handle. Orange nodes edit path vertices.'))
        close=QPushButton(tr('cancel'));close.clicked.connect(self.close_properties);pane.form.addRow(close);self.inspect_objects()

    def shape_values(self):
        v=self.shape_properties.values();return v['kind'],self.shape_stroke.color.getRgbF()[:3],self.shape_fill.color.getRgbF()[:3] if v['fill'] else None,v['width']

    def place_shape(self,page,rect):
        kind,stroke,fill,width=self.shape_values()
        def done(_):
            self.canvas.selected=[];self.pending_shape_selection=True;self.set_mode('objects')
        self.run(tr('vector_edit'),lambda j:figures.draw_shape(self.document,page,rect,kind,stroke,fill,width),done,editing=True,local_edit=True)

    def rotate_shapes(self,angle):
        selected=[o for o in self.selected_objects() if o.kind in ('vector','group')]
        if not selected or abs(angle)<.1:return
        page=self.canvas.object_page
        self.run(tr('vector_edit'),lambda j:figures.rotate(self.document,page,selected,angle),editing=True,local_edit=True)

    def apply_shape_style(self):
        selected=self.selected_objects()
        if not selected:return
        kind,stroke,fill,width=self.shape_values();page=self.canvas.object_page
        self.run(tr('vector_edit'),lambda j:figures.style_vectors(self.document,page,selected,stroke,fill,width),editing=True,local_edit=True)

    def choose_insert_image(self):
        pane=self.property_pane(tr('add_image'));self.image_properties=pane;self.canvas.vector_edit=False;self.edit_tool='image';self.set_mode('objects')
        self.image_filename=QLabel(L('选择图片或矢量 PDF','Choose an image or vector PDF'));self.image_filename.setWordWrap(True);pane.form.addRow(self.image_filename)
        pick=QPushButton(L('选择文件…','Choose file…'));pick.clicked.connect(self.browse_image);pane.form.addRow(pick)
        self.figure_page=pane.number('page',L('PDF 页码','PDF page'),1,1,99999)
        ratio=pane.check('ratio',L('保持原比例','Keep aspect ratio'),self.keep_image_ratio.isChecked());ratio.toggled.connect(self.keep_image_ratio.setChecked)
        self.figure_place=QPushButton(L('放置到页面','Place on page'));self.figure_place.setCheckable(True);self.figure_place.setEnabled(bool(getattr(self,'pending_image',None)));self.figure_place.clicked.connect(lambda:self.set_mode('add_image'));pane.form.addRow(self.figure_place)
        copy=QPushButton(L('复制所选对象','Copy selected objects'));copy.clicked.connect(self.copy_objects);pane.form.addRow(copy)
        paste=QPushButton(L('原位粘贴','Paste in place'));paste.clicked.connect(self.paste);pane.form.addRow(paste)
        delete=QPushButton(L('删除所选对象','Delete selected objects'));delete.clicked.connect(self.delete_objects);pane.form.addRow(delete)
        pane.note(L('PDF 保留原文字与矢量，插入选定页的内容，不导入链接、脚本或批注。EPS/PS 使用本机 Ghostscript（若已安装），不增加安装包体积。','PDF retains text/vectors; the chosen page content is inserted without links, scripts or annotations. EPS/PS uses locally installed Ghostscript without enlarging the app bundle.'))
        close=QPushButton(tr('cancel'));close.clicked.connect(self.close_properties);pane.form.addRow(close)

    def browse_image(self):
        filename,_=QFileDialog.getOpenFileName(self,tr('add_image'),'','Images / PDF / EPS / PS (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.pdf *.eps *.ps)')
        if not filename:return
        def done(path):
            self.pending_image=path;self.image_filename.setText(Path(filename).name);self.figure_place.setEnabled(True);self.figure_place.setChecked(True);self.set_mode('add_image')
        if Path(filename).suffix.lower() in ('.eps','.ps'):self.run(tr('add_image'),lambda j:figures.prepare(filename,self.document.folder),done)
        else:done(filename)
