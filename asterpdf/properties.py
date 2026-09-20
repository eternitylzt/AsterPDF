"""Docked color, image and vector-shape properties."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QImage,QPixmap,QIcon
from PySide6.QtWidgets import QWidget,QVBoxLayout,QPushButton,QColorDialog,QFileDialog,QLabel,QCheckBox,QSpinBox,QScrollArea,QFrame,QGridLayout,QToolButton,QComboBox
from .dialogs import FormDialog
from .chrome import OffsetPanel
from .i18n import L,tr
from .core import pages_from_text
from . import colors,figures

class PropertiesMixin:
    def leave_color_tools(self):
        if getattr(self,'edit_tool',None)=='colors':self.canvas.region=None
        self.canvas.color_boundary=None;self.canvas.show_color_boundary=False
        self.canvas.update()
        if hasattr(self,'color_properties'):del self.color_properties

    def property_pane(self,title):
        self.leave_color_tools()
        self.page_live_operations=[]
        if self.inline_editor:self.suspend_inline()
        self.text_properties.hide();self.text_container.hide();self.document_views.setCurrentWidget(self.scroll)
        if hasattr(self,'property_container'):self.property_container.hide();self.property_container.deleteLater()
        for name in ('figure_place','figure_page','shape_draw_button','shape_properties','image_properties','color_properties','shape_stroke','shape_fill','image_filename','page_properties','shape_buttons','annotation_properties','annotation_text_input','video_list'):
            if hasattr(self,name):delattr(self,name)
        pane=FormDialog(title,self);pane.setWindowFlags(Qt.Widget);pane.setMinimumWidth(220);pane.setMaximumWidth(290)
        heading=QLabel(title);font=heading.font();font.setBold(True);heading.setFont(font);pane.form.insertRow(0,heading)
        scroller=QScrollArea();scroller.setWidgetResizable(True);scroller.setFrameShape(QFrame.NoFrame);scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);scroller.setMinimumWidth(235);scroller.setMaximumWidth(310);scroller.setWidget(pane)
        self.property_container=OffsetPanel(scroller);self.splitter.insertWidget(1,self.property_container)
        self.property_container.show();pane.show();self.position_chrome();return pane

    def close_properties(self):
        self.leave_color_tools()
        if hasattr(self,'property_container'):self.property_container.hide()
        self.edit_tool='text';self.set_mode('objects' if self.active_panel=='objects' else 'select')

    def color_button(self,pane,label,color):
        from .tool_widgets import ColorButton
        button=ColorButton(color,self)
        pane.form.addRow(label,button);return button

    def replace_colors(self):
        from .color_tools import build
        build(self)

    def begin_vector_edit(self):
        pane=self.property_pane(tr('vector_edit'));self.shape_properties=pane;self.canvas.vector_edit=True;self.edit_tool='shape';self.set_mode('objects')
        pane.choice('kind',L('形状','Shape'),[(L('矩形','Rectangle'),'rectangle'),(L('椭圆','Ellipse'),'ellipse'),(L('线条','Line'),'line'),(L('实心箭头','Block arrow'),'arrow'),(L('三角形','Triangle'),'triangle'),(L('菱形','Diamond'),'diamond'),(L('五角星','Star'),'star')])
        self.shape_stroke=self.color_button(pane,L('轮廓','Outline'),QColor(self.window.settings.value('shape/stroke','#243249')));self.shape_fill=self.color_button(pane,L('填充','Fill'),QColor(self.window.settings.value('shape/color','#b6cff4')))
        pane.check('fill',L('填充形状','Fill shape'),self.window.settings.value('shape/fill',False,type=bool));pane.number('width',L('线宽（点）','Width (pt)'),self.window.settings.value('shape/width',1.5,type=float),.1,50,1)
        pane.choice('dash',L('线型','Line style'),[(L('实线','Solid'),'solid'),(L('虚线','Dashed'),'dash'),(L('点线','Dotted'),'dot'),(L('点划线','Dash-dot'),'dashdot')])
        from .ui_icons import icon
        model=pane.inputs['kind'];model.hide();pane.form.labelForField(model).hide()
        grid=QWidget();grid_layout=QGridLayout(grid);grid_layout.setContentsMargins(0,0,0,0);self.shape_buttons={}
        def choose(kind,index,checked):
            model.setCurrentIndex(index)
            self.set_mode('draw_shape' if checked else 'objects')
            for name,button in self.shape_buttons.items():button.setChecked(checked and name==kind)
        for index in range(model.count()):
            kind=model.itemData(index);button=QToolButton();button.setIcon(icon(kind,self.dark));button.setToolTip(model.itemText(index));button.setCheckable(True);button.setFixedSize(46,40)
            button.clicked.connect(lambda checked,k=kind,n=index:choose(k,n,checked));grid_layout.addWidget(button,index//4,index%4);self.shape_buttons[kind]=button
        pane.form.insertRow(1,grid)
        draw=QPushButton(L('绘制形状','Draw shape'));draw.setCheckable(True);draw.clicked.connect(lambda checked:self.set_mode('draw_shape' if checked else 'objects'));pane.form.addRow(draw)
        self.shape_draw_button=draw;draw.hide()
        self.add_layer_controls(pane.form)
        style=QPushButton(L('应用到选中图形','Apply to selected paths'));style.clicked.connect(self.apply_shape_style);pane.form.addRow(style)
        pane.note(L('绘制后直接单击或框选图形；拖动移动，右下角缩放，上方圆柄旋转。橙色节点可调整路径端点。','After drawing, click or marquee to select. Drag to move, resize at the lower-right corner, or rotate using the top handle. Orange nodes edit path vertices.'))
        close=QPushButton(tr('cancel'));close.clicked.connect(self.close_properties);pane.form.addRow(close);self.inspect_objects()

    def shape_values(self):
        v=self.shape_properties.values();return v['kind'],self.shape_stroke.color.getRgbF()[:3],self.shape_fill.color.getRgbF()[:3] if v['fill'] else None,v['width']

    def place_shape(self,page,rect):
        kind,stroke,fill,width=self.shape_values()
        def done(_):
            self.canvas.selected=[];self.pending_shape_selection=True;self.set_mode('objects')
        self.run(tr('vector_edit'),lambda j:figures.draw_shape(self.document,page,rect,kind,stroke,fill,width,self.shape_properties.inputs['dash'].currentData()),done,editing=True,local_edit=True)

    def rotate_shapes(self,angle):
        selected=[o for o in self.selected_objects() if o.kind in ('vector','group')]
        if not selected or abs(angle)<.1:return
        page=self.canvas.object_page
        self.run(tr('vector_edit'),lambda j:figures.rotate(self.document,page,selected,angle),editing=True,local_edit=True)

    def apply_shape_style(self):
        selected=self.selected_objects()
        if not selected:return
        kind,stroke,fill,width=self.shape_values();page=self.canvas.object_page
        self.run(tr('vector_edit'),lambda j:figures.style_vectors(self.document,page,selected,stroke,fill,width,self.shape_properties.inputs['dash'].currentData()),editing=True,local_edit=True)

    def choose_insert_image(self):
        pane=self.property_pane(tr('add_image'));self.image_properties=pane;self.canvas.vector_edit=False;self.edit_tool='image';self.set_mode('objects')
        self.image_filename=QLabel(L('选择图片或矢量 PDF','Choose an image or vector PDF'));self.image_filename.setWordWrap(True);pane.form.addRow(self.image_filename)
        pick=QPushButton(L('选择文件…','Choose file…'));pick.clicked.connect(self.browse_image);pane.form.addRow(pick)
        clip=QPushButton(L('从剪贴板插入','Insert from clipboard'));clip.clicked.connect(lambda:self.paste(True));pane.form.addRow(clip)
        self.figure_page=pane.number('page',L('PDF 页码','PDF page'),1,1,99999)
        self.figure_page.valueChanged.connect(self.clamp_figure_page)
        self.figure_notice=QLabel();self.figure_notice.setWordWrap(True);pane.form.addRow(self.figure_notice)
        ratio=pane.check('ratio',L('保持原比例','Keep aspect ratio'),self.keep_image_ratio.isChecked());ratio.toggled.connect(self.keep_image_ratio.setChecked)
        self.figure_place=QPushButton(L('放置到页面','Place on page'));self.figure_place.setCheckable(True);self.figure_place.setEnabled(bool(getattr(self,'pending_image',None)));self.figure_place.clicked.connect(lambda:self.set_mode('add_image'));pane.form.addRow(self.figure_place)
        copy=QPushButton(L('复制所选对象','Copy selected objects'));copy.clicked.connect(self.copy_objects);pane.form.addRow(copy)
        paste=QPushButton(L('原位粘贴','Paste in place'));paste.clicked.connect(lambda:self.paste(True));pane.form.addRow(paste)
        for label,front in [(L('置于顶层','Bring to front'),True),(L('置于底层','Send to back'),False)]:
            layer=QPushButton(label);layer.clicked.connect(lambda checked=False,f=front:self.stack_images(f));pane.form.addRow(layer)
        delete=QPushButton(L('删除所选对象','Delete selected objects'));delete.clicked.connect(self.delete_objects);pane.form.addRow(delete)
        pane.note(L('PDF 保留原文字与矢量，插入选定页的内容，不导入链接、脚本或批注。EPS/PS 使用本机 Ghostscript（若已安装），不增加安装包体积。','PDF retains text/vectors; the chosen page content is inserted without links, scripts or annotations. EPS/PS uses locally installed Ghostscript without enlarging the app bundle.'))
        close=QPushButton(tr('cancel'));close.clicked.connect(self.close_properties);pane.form.addRow(close)

    def add_layer_controls(self,layout):
        from PySide6.QtWidgets import QHBoxLayout
        row=QHBoxLayout()
        for label,front in [(L('置于顶层','Bring to front'),True),(L('置于底层','Send to back'),False)]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,f=front:self.stack_images(f));row.addWidget(button)
        if hasattr(layout,'addRow'):layout.addRow(row)
        else:layout.addLayout(row)

    def stack_images(self,front=True):
        from . import objects
        if self.inline_editor:
            if self.inline_dirty():
                import pymupdf as fitz
                from PySide6.QtCore import QTimer
                page=self.inline_page;bounds=fitz.Rect(self.inline_object.bbox)
                def arrange():
                    if self.closed:return
                    if self.busy:QTimer.singleShot(30,arrange);return
                    def work(job):
                        candidates=[o for o in objects.discover(self.document,page) if o.kind=='text' and not o.reason and fitz.Rect(o.bbox).intersects(bounds)]
                        if not candidates:raise ValueError(L('请重新选择要调整图层的文字。','Select the text to arrange again.'))
                        selected=max(candidates,key=lambda o:(fitz.Rect(o.bbox)&bounds).get_area())
                        objects.set_stacking(self.document,page,[selected],front)
                    self.run(L('调整图层','Arrange objects'),work,editing=True,local_edit=True)
                self.commit_inline(arrange);return
            self.cancel_inline()
        selected=self.selected_objects();page=self.canvas.object_page
        if not selected:return
        self.run(L('调整图层','Arrange objects'),lambda j:objects.set_stacking(self.document,page,selected,front),editing=True,local_edit=True)

    def clamp_figure_page(self):
        count=getattr(self,'figure_page_count',1);value=self.figure_page.value()
        if value>count:
            self.figure_page.blockSignals(True);self.figure_page.setValue(count);self.figure_page.blockSignals(False)
            self.figure_notice.setText(L(f'共 {count} 页，已使用最后一页。',f'{count} pages; using the last page.'))
        else:self.figure_notice.setText(L(f'共 {count} 页',f'{count} pages'))

    def browse_image(self):
        filename,_=QFileDialog.getOpenFileName(self,tr('add_image'),'','Images / PDF / EPS / PS (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.pdf *.eps *.ps)')
        if not filename:return
        def done(path):
            self.pending_image=path;self.image_filename.setText(Path(filename).name);self.figure_place.setEnabled(True);self.figure_place.setChecked(True);self.set_mode('add_image');self.figure_page_count=1
            if Path(path).suffix.lower()=='.pdf':
                import pymupdf as fitz
                with fitz.open(path) as source:self.figure_page_count=len(source)
            self.clamp_figure_page()
        if Path(filename).suffix.lower() in ('.eps','.ps'):self.run(tr('add_image'),lambda j:figures.prepare(filename,self.document.folder),done)
        else:done(filename)
