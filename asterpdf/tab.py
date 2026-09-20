from __future__ import annotations
from pathlib import Path
import json
import hashlib
import os
from PySide6.QtCore import Qt, QTimer, QSize, QUrl, Signal, QPointF, QRectF, QEvent
from PySide6.QtGui import QColor, QPixmap, QIcon, QImage, QDesktopServices, QFont, QActionGroup
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QLineEdit, QPushButton,
    QToolBar, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QLabel, QMessageBox,
    QFileDialog, QInputDialog, QProgressBar, QColorDialog, QAbstractItemView, QApplication,
    QStackedWidget, QMenu, QDialog, QPlainTextEdit, QFontComboBox, QTextEdit, QToolButton)
from .i18n import tr, L
from .core import pages_from_text
from .canvas import Canvas, ReaderScroll, qrect
from .dialogs import FormDialog, MergeDialog
from .fonts import matched_family, font_bytes
from .ui_icons import icon
from .chrome import ChromeMixin, OffsetPanel, decorate, translate_tree
from .text_editing import TextEditingMixin
from .ui_details import NavSplitter,AnnotationDelegate,ToolbarStrip
from .properties import PropertiesMixin
from .page_tools import PageToolsMixin
from . import objects, media
from .player import AnimationPlayer, VideoPlayer


class ThumbnailList(QListWidget):
    reordered=Signal(object)
    zoomed=Signal(float)
    MIME='application/x-asterpdf-page-order'

    def __init__(self,parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QFrame
        self.setAcceptDrops(True);self.viewport().setAcceptDrops(True)
        self.drop_line=QFrame(self.viewport());self.drop_line.setStyleSheet('background:#1677e8;border-radius:1px;');self.drop_line.hide()
        self.drag_token=str(id(self)).encode();self.drop_target=None

    def wheelEvent(self,event):
        if event.modifiers()&Qt.ControlModifier and self.viewMode()==QListWidget.IconMode and self.flow()==QListWidget.LeftToRight:
            self.zoomed.emit(event.angleDelta().y()/120);event.accept();return
        super().wheelEvent(event)

    def startDrag(self,actions):
        from PySide6.QtCore import QMimeData,QPoint
        from PySide6.QtGui import QDrag,QPainter
        selected=self.selectedItems()
        if not selected:return
        self.drag_pages=[it.data(Qt.UserRole) for it in selected]
        mime=QMimeData();mime.setData(self.MIME,self.drag_token)
        drag=QDrag(self);drag.setMimeData(mime)
        dpr=self.devicePixelRatioF();pix=QPixmap(round(155*dpr),round(205*dpr));pix.setDevicePixelRatio(dpr);pix.fill(Qt.transparent)
        paint=QPainter(pix);paint.setOpacity(.7)
        for offset,it in reversed(list(enumerate(selected[:3]))):paint.drawPixmap(4+offset*5,4+offset*5,it.icon().pixmap(135,175))
        paint.setOpacity(1);paint.setPen(QColor('#243249'));paint.drawText(7,200,str(len(selected)));paint.end()
        drag.setPixmap(pix);drag.setHotSpot(QPoint(75,100))
        try:drag.exec(Qt.MoveAction)
        finally:self.drop_line.hide();self.drop_target=None;drag.deleteLater()

    def accepts_order(self,event):
        return self.dragEnabled() and bytes(event.mimeData().data(self.MIME))==self.drag_token

    def insertion_at(self,pos):
        if not self.count():return 0,None
        item=self.itemAt(pos)
        if item is None:
            item=min((self.item(n) for n in range(self.count())),key=lambda it:
                max(self.visualItemRect(it).left()-pos.x(),0,pos.x()-self.visualItemRect(it).right())**2+
                max(self.visualItemRect(it).top()-pos.y(),0,pos.y()-self.visualItemRect(it).bottom())**2)
        rect=self.visualItemRect(item);horizontal=self.flow()==QListWidget.LeftToRight
        after=pos.x()>rect.center().x() if horizontal else pos.y()>rect.center().y()
        target=self.row(item)+int(after)
        from PySide6.QtCore import QRect
        line=QRect((rect.right()+2 if after else rect.left()-3),rect.top(),3,rect.height()) if horizontal else QRect(rect.left(),rect.bottom()+2 if after else rect.top()-3,rect.width(),3)
        return target,line

    def dragEnterEvent(self,event):
        if self.accepts_order(event):event.setDropAction(Qt.MoveAction);event.accept()
        else:event.ignore()

    def dragMoveEvent(self,event):
        if not self.accepts_order(event):event.ignore();return
        pos=event.position().toPoint();self.drop_target,line=self.insertion_at(pos)
        if line:self.drop_line.setGeometry(line);self.drop_line.show();self.drop_line.raise_()
        bar=self.verticalScrollBar()
        if pos.y()<24:bar.setValue(bar.value()-18)
        elif pos.y()>self.viewport().height()-24:bar.setValue(bar.value()+18)
        event.setDropAction(Qt.MoveAction);event.accept()

    def dragLeaveEvent(self,event):
        self.drop_line.hide();self.drop_target=None;event.accept()

    def dropEvent(self,event):
        self.drop_line.hide()
        if not self.accepts_order(event):event.ignore();return
        target,_=self.insertion_at(event.position().toPoint())
        ids=[self.item(i).data(Qt.UserRole) for i in range(self.count())]
        selected=getattr(self,'drag_pages',[it.data(Qt.UserRole) for it in self.selectedItems()])
        order=self.reordered_ids(ids,selected,target)
        event.setDropAction(Qt.MoveAction);event.accept()
        if order!=ids:self.reordered.emit(order)

    @staticmethod
    def reordered_ids(ids,selected,target):
        moving=[x for x in ids if x in selected];remaining=[x for x in ids if x not in selected]
        at=sum(x not in selected for x in ids[:target])
        return remaining[:at]+moving+remaining[at:]


class DocumentTab(QWidget,ChromeMixin,TextEditingMixin,PropertiesMixin,PageToolsMixin):
    def __init__(self, window, document, info):
        super().__init__()
        self.window, self.document, self.info = window, document, info
        self.queue = window.queue
        self.closed = self.busy = False
        self.dark, self.night = window.dark, False
        self.animations, self.assets, self.media_warnings = [], [], []
        self.players = {}; self.video_players = []
        self.annot_color, self.annot_width, self.annot_opacity = QColor('#efb43d'), 2, .7
        self.annotations_data = []
        self.object_cache = {}
        self.image_cache = {}
        self.editing_objects = False; self.edit_tool='text'; self.fit_mode=None
        self.inline_editor = None
        self.annot_author = window.settings.value('annotation_author','AsterPDF')
        self.annot_font = 'china-s'
        self.annot_size = 12
        self.annot_end = 5
        self.annot_dashed = False
        self.annot_head_size=10;self.annot_text_border=0;self.annot_border_color=QColor('#243249');self._sync_annotation=False
        from .preferences import annotation_defaults
        annotation_defaults(self)
        self.links = {}
        self.job = None
        self.build()
        key = hashlib.sha256(document.original.encode()).hexdigest()
        self.state_key = 'documents/'+key
        raw = window.settings.value(self.state_key, '{}')
        try: self.state = json.loads(raw)
        except (ValueError, TypeError): self.state = {}
        self.bookmark_pages = set(self.state.get('bookmarks', []));self.bookmark_names=self.state.get('bookmark_names',{})
        self.canvas.columns=window.settings.value('reader/columns',1,type=int);self.canvas.continuous=window.settings.value('reader/continuous',True,type=bool);self.night=window.settings.value('reader/night',False,type=bool)
        self.canvas.sizes = info['sizes'];self.zoom_factor=self.state.get('zoom_factor',1.0);self.canvas.scale=self.zoom_factor*self.actual_size_scale();self.zoom.setCurrentText(f'{self.zoom_factor*100:.3g}%')
        if self.window.windowHandle():self.window.windowHandle().screenChanged.connect(self.screen_zoom_changed)
        self.canvas.layout_pages()
        self.populate_navigation()
        self.goto(min(self.state.get('page', 0), info['count']-1))
        self.queue.submit(lambda j: media.scan(document), self.media_scanned, self.error)
        self.thumbnail_timer = QTimer(self); self.thumbnail_timer.setSingleShot(True)
        self.thumbnail_timer.timeout.connect(self.load_thumbnails)
        self.thumbnail_timer.start(300)
        self.thumbnails.verticalScrollBar().valueChanged.connect(lambda: self.thumbnail_timer.start(100))
        self.organizer.verticalScrollBar().valueChanged.connect(lambda:self.thumbnail_timer.start(100))

    def build(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        nav = QToolBar(); self.navbar = nav; nav.setMovable(False); self.navbar_host=ToolbarStrip(nav);layout.addWidget(self.navbar_host)
        self.quick_actions={};nav.setIconSize(QSize(19,19));nav.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.tools=nav;self.module_actions={};self.module_group=QActionGroup(self);self.module_group.setExclusive(True)
        for key,callback in [('select',self.pointer),('hand',lambda:self.set_mode('hand'))]:
            action=nav.addAction(icon(key,self.dark),'',callback);action.setToolTip(tr(key));self.quick_actions[key]=action
        nav.addSeparator()
        for key in ('annotate','objects','pages','extract'):
            action=decorate(nav.addAction(tr(key),lambda checked=False,k=key:self.set_panel(k)),key,self.dark)
            action.setCheckable(True);self.module_actions[key]=action;self.module_group.addAction(action)
        nav.addSeparator()
        self.page_spin=QSpinBox();self.page_spin.setRange(1,self.info['count']);self.page_spin.setFixedWidth(65)
        self.page_spin.setToolTip(L('页码：输入后回车，或使用上下按钮翻页','Page: type a number or use the up/down buttons'));self.page_spin.setKeyboardTracking(False)
        self.page_spin.valueChanged.connect(lambda n:self.goto(n-1));nav.addWidget(self.page_spin)
        self.page_count=QLabel(f"/ {self.info['count']}");nav.addWidget(self.page_count)
        nav.addSeparator()
        zoom_group=QWidget();zoom_layout=QHBoxLayout(zoom_group);zoom_layout.setContentsMargins(0,0,0,0);zoom_layout.setSpacing(1)
        self.zoom_minus=QToolButton();self.zoom_minus.setIcon(icon('minus',self.dark));self.zoom_minus.setFixedWidth(25);self.zoom_minus.clicked.connect(lambda:self.zoom_by(1/1.2));zoom_layout.addWidget(self.zoom_minus)
        self.zoom=QComboBox();self.zoom.setEditable(True);self.zoom.addItems(['1.5625%','6.25%','25%','50%','75%','100%','125%','150%','200%','400%','800%','1600%','3200%','6400%']);self.zoom.setCurrentText('100%');self.zoom.setFixedWidth(85)
        self.zoom.setToolTip(L('100% 按显示器报告的物理尺寸显示；范围 1.5625%–6400%。','100% uses the physical size reported by the monitor; range 1.5625%–6400%.'))
        self.zoom.activated.connect(self.zoom_changed);self.zoom.lineEdit().returnPressed.connect(self.zoom_changed)
        zoom_layout.addWidget(self.zoom);self.zoom_plus=QToolButton();self.zoom_plus.setIcon(icon('plus',self.dark));self.zoom_plus.setFixedWidth(25);self.zoom_plus.clicked.connect(lambda:self.zoom_by(1.2));zoom_layout.addWidget(self.zoom_plus);nav.addWidget(zoom_group)
        nav.addSeparator()
        for key,callback in [('undo',lambda:self.window.history(False)),('redo',lambda:self.window.history(True)),('page_fit',lambda:self.fit(False)),('width_fit',lambda:self.fit(True)),('bookmark',self.toggle_bookmark),
            ('save',lambda:self.window.save_tab()),('region',lambda:self.set_mode('select' if self.canvas.mode=='region' else 'region')),('copy_region',self.copy_region),('images',self.extract_embedded),('play',self.play_selected),('replay',self.replay),('presentation',self.window.toggle_presentation),
            ('print',lambda:self.window.print_current()),('file_info',lambda:self.window.file_information()),('minimap',lambda:self.minimap.toggle())]:
            self.quick_actions[key]=decorate(nav.addAction(tr(key),callback),key,self.dark)
        for key in ('select','hand','region','page_fit','width_fit','minimap'):self.quick_actions[key].setCheckable(True)
        self.continuous=QCheckBox(tr('continuous'));self.continuous.setChecked(True);self.continuous.toggled.connect(self.set_continuous)
        self.quick_actions['continuous']=nav.addWidget(self.continuous)
        self.search_input=QLineEdit();self.search_input.setPlaceholderText(tr('search_hint'));self.search_input.setMaximumWidth(180);self.search_input.returnPressed.connect(self.search)
        self.quick_actions['search']=decorate(nav.addAction(tr('search'),self.show_search),'search',self.dark)
        self.tool_panels = QStackedWidget(); layout.addWidget(self.tool_panels)
        self.panel_keys = {}
        self.add_panel('read', [('select', lambda: self.set_mode('select')), ('region', lambda: self.set_mode('region'))])
        self.add_panel('annotate', [(k, lambda k=k: self.set_mode(k)) for k in
            ('select_annot','highlight','underline','strikeout','replace_text','squiggly','note','freetext','ink','line','arrow','rectangle','ellipse')])
        annotation_bar = self.tool_panels.widget(self.panel_keys['annotate'])
        self.color_action=annotation_bar.addAction('● '+tr('color'), self.choose_color)
        self.color_action.setIcon(self.color_icon())
        annotation_bar.addAction(L('样式','Style'), self.annotation_settings)
        width = QDoubleSpinBox(); width.setRange(.2, 20); width.setValue(self.annot_width); width.setMaximumWidth(70)
        self.annot_width_widget=width;self.annotation_style_timer=QTimer(self);self.annotation_style_timer.setSingleShot(True);self.annotation_style_timer.timeout.connect(self.apply_annotation_style)
        width.setToolTip(tr('width')); width.valueChanged.connect(lambda v:self.annotation_value('annot_width',v)); annotation_bar.addWidget(QLabel(tr('width')));annotation_bar.addWidget(width)
        opacity = QDoubleSpinBox(); opacity.setRange(5,100); opacity.setSingleStep(5); opacity.setValue(self.annot_opacity*100);opacity.setDecimals(0);opacity.setSuffix('%'); opacity.setMaximumWidth(70)
        self.annot_opacity_widget=opacity
        opacity.setToolTip(tr('opacity')); opacity.valueChanged.connect(lambda v:self.annotation_value('annot_opacity',v/100)); annotation_bar.addWidget(QLabel(tr('opacity')));annotation_bar.addWidget(opacity)
        # Keep compatibility bindings, but expose all styling in the inline pane.
        for action in annotation_bar.actions():
            if not action.property('aster_key'):action.setVisible(False)
        annotation_bar.addAction(L('批注人','Author'),lambda:self.show_annotation_properties(author=True))
        self.add_panel('objects', [('text_ops',self.text_tools),('add_image',self.choose_insert_image),('vector_edit',self.begin_vector_edit),('add_video',lambda:__import__('asterpdf.video_insert',fromlist=['pane']).pane(self)),('colors',self.replace_colors),('reset_document',self.reset_document)])
        object_bar=self.tool_panels.widget(self.panel_keys['objects'])
        self.keep_image_ratio=QCheckBox(L('保持比例（Shift 临时切换）','Keep ratio (Shift toggles)'));self.keep_image_ratio.setChecked(self.window.settings.value('image/ratio',True,type=bool));self.keep_image_ratio.toggled.connect(lambda v:self.window.settings.setValue('image/ratio',v));self.keep_image_ratio.hide()
        self.add_panel('pages', [('organize',self.organize_pages),('rotate', lambda: self.page_op('rotate')),('flip_h',lambda:self.page_tools('flip_h')),('flip_v',lambda:self.page_tools('flip_v')), ('delete_pages',lambda: self.page_op('delete')),
            ('blank', lambda: self.page_op('blank')), ('merge', self.merge),
            ('extract_pages', self.extract_pages), ('crop', lambda:self.page_tools('crop'))])
        pagebar=self.tool_panels.widget(self.panel_keys['pages'])
        self.organizer_zoom=QDoubleSpinBox();self.organizer_zoom.setRange(2,50);self.organizer_zoom.setSuffix('%');self.organizer_zoom.setValue(self.window.settings.value('page/preview_scale',15.,type=float));self.organizer_zoom.setFixedWidth(80);self.organizer_zoom.setToolTip(L('页面预览缩放 · Ctrl+滚轮','Page preview zoom · Ctrl+wheel'));pagebar.addWidget(self.organizer_zoom)
        self.add_panel('extract', [('region', lambda: self.set_mode('region')), ('export_pages', lambda: self.export_images(False)),
            ('export_region', lambda: self.export_images(True)), ('copy_region', self.copy_region),
            ('vector_pdf', self.vector_export), ('images', self.extract_embedded), ('export_settings',self.window.export_settings)])
        self.add_panel('media', [('play', self.play_selected), ('replay', self.replay),
            ('previous', lambda: self.step(-1)), ('next', lambda: self.step(1))])
        media_bar = self.tool_panels.widget(self.panel_keys['media'])
        media_bar.addAction('ⓘ', lambda: QMessageBox.information(self,'AsterPDF', '\n\n'.join(self.media_warnings) or
            L('仅运行已识别的播放控制；不执行 PDF JavaScript。','Only recognized playback controls are used; PDF JavaScript is not executed.')))
        self.media_choice = QComboBox(); self.media_choice.setMinimumWidth(230); media_bar.addWidget(self.media_choice)
        self.frame_slider = QSpinBox(); self.frame_slider.setMinimum(1); self.frame_slider.setMaximumWidth(90)
        self.frame_slider.valueChanged.connect(self.seek_frame); media_bar.addWidget(self.frame_slider)
        self.loop = QCheckBox(tr('loop')); self.loop.setChecked(self.window.settings.value('animation/loop',True,type=bool));self.loop.toggled.connect(lambda v:self.window.settings.setValue('animation/loop',v)); media_bar.addWidget(self.loop)
        self.loop.toggled.connect(lambda b: [setattr(p,'loop',b) for p in self.players.values()])
        self.media_label = QLabel(); media_bar.addWidget(self.media_label)
        content=QWidget();content_layout=QHBoxLayout(content);content_layout.setContentsMargins(0,0,0,0);content_layout.setSpacing(0);layout.addWidget(content,1)
        edge=QWidget();edge_layout=QVBoxLayout(edge);edge_layout.setContentsMargins(0,0,0,0);edge.setFixedWidth(16)
        self.sidebar_toggle=QToolButton();self.sidebar_toggle.setText('‹');self.sidebar_toggle.setFixedSize(16,30);self.sidebar_toggle.setToolTip(L('收起 / 展开导航栏','Collapse / expand navigation'))
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar);self.sidebar_toggle.setContextMenuPolicy(Qt.CustomContextMenu);self.sidebar_toggle.customContextMenuRequested.connect(self.sidebar_menu)
        edge_layout.addWidget(self.sidebar_toggle);edge_layout.addStretch();content_layout.addWidget(edge)
        self.splitter=NavSplitter();self.splitter.tab=self;self.splitter.setHandleWidth(3);content_layout.addWidget(self.splitter,1)
        self.sidebar = QTabWidget(); self.sidebar.setMaximumWidth(440); self.sidebar.setMinimumWidth(185)
        self.sidebar_container=OffsetPanel(self.sidebar);self.splitter.addWidget(self.sidebar_container)
        self.thumbnails = ThumbnailList(); self.thumbnails.setIconSize(QSize(112, 145))
        self.thumbnails.setViewMode(QListWidget.IconMode);self.thumbnails.setFlow(QListWidget.TopToBottom);self.thumbnails.setWrapping(False)
        self.thumbnails.setResizeMode(QListWidget.Adjust);self.thumbnails.setMovement(QListWidget.Snap)
        self.thumbnails.setSpacing(5)
        self.thumbnails.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.thumbnails.setDragDropMode(QAbstractItemView.InternalMove)
        self.thumbnails.setDefaultDropAction(Qt.MoveAction)
        self.thumbnails.itemClicked.connect(lambda item: self.goto(item.data(Qt.UserRole)))
        self.thumbnails.reordered.connect(self.reorder)
        self.thumbnails.setContextMenuPolicy(Qt.CustomContextMenu);self.thumbnails.customContextMenuRequested.connect(lambda pos:self.page_context_menu(self.thumbnails,pos))
        self.sidebar.addTab(self.thumbnails, tr('pages'))
        self.outline = QTreeWidget(); self.outline.setHeaderHidden(True)
        self.outline.setStyleSheet('QTreeWidget::item {padding:5px 3px;min-height:22px;}');self.outline.setIndentation(16);self.outline.setUniformRowHeights(True)
        self.outline.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel);self.outline.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.outline.itemClicked.connect(lambda item,c: self.goto(item.data(0,Qt.UserRole)))
        self.sidebar.addTab(self.outline, tr('outline'))
        from .ui_details import BookmarkDelegate
        self.bookmarks = QListWidget();self.bookmarks.setItemDelegate(BookmarkDelegate(self.bookmarks)); self.bookmarks.itemClicked.connect(lambda item:self.goto(item.data(Qt.UserRole)))
        self.bookmarks.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmarks.customContextMenuRequested.connect(self.bookmark_menu)
        self.sidebar.addTab(self.bookmarks,tr('bookmarks'))
        self.results = QListWidget(); self.results.itemClicked.connect(self.result_clicked)
        self.search_panel=QWidget();search_layout=QVBoxLayout(self.search_panel);search_layout.setContentsMargins(5,5,5,5);self.search_input.setMaximumWidth(16777215);search_layout.addWidget(self.search_input);search_layout.addWidget(self.results)
        navigation=QHBoxLayout()
        for label,step in [(L('上一条','Previous'),-1),(L('下一条','Next'),1)]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,d=step:self.search_step(d));navigation.addWidget(button)
        self.search_count=QLabel('');navigation.addWidget(self.search_count);search_layout.insertLayout(1,navigation)
        self.results.currentItemChanged.connect(lambda item,old:self.result_clicked(item) if item else None)
        self.sidebar.addTab(self.search_panel,tr('search'))
        self.object_list = QListWidget(); self.object_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.object_list.itemSelectionChanged.connect(self.object_list_selected)
        self.object_list.itemDoubleClicked.connect(lambda item:self.modify_object())
        self.object_list.hide()
        self.annotation_sidebar=QWidget();annlayout=QVBoxLayout(self.annotation_sidebar);annlayout.setContentsMargins(5,5,5,5)
        self.show_annotations=QCheckBox(L('显示所有批注','Show all annotations'));self.show_annotations.setChecked(self.window.settings.value('annotation/show',True,type=bool));self.show_annotations.toggled.connect(lambda v:self.window.settings.setValue('annotation/show',v));self.show_annotations.toggled.connect(self.toggle_annotations);annlayout.addWidget(self.show_annotations)
        self.annotation_sort=QComboBox();self.annotation_sort.addItem(L('按文档位置排序','Sort by document position'),'position');self.annotation_sort.addItem(L('按创建时间排序','Sort by creation time'),'time');self.annotation_sort.setCurrentIndex(max(0,self.annotation_sort.findData(self.window.settings.value('annotation/sort','position'))));self.annotation_sort.currentIndexChanged.connect(lambda:self.window.settings.setValue('annotation/sort',self.annotation_sort.currentData()));self.annotation_sort.currentIndexChanged.connect(self.load_annotations);annlayout.addWidget(self.annotation_sort)
        self.annotation_list=QListWidget();self.annotation_list.setWordWrap(True);self.annotation_list.setSelectionMode(QAbstractItemView.ExtendedSelection);self.annotation_list.setItemDelegate(AnnotationDelegate(self.annotation_list));annlayout.addWidget(self.annotation_list)
        self.annotation_text=QTextEdit();self.annotation_text.setReadOnly(True);self.annotation_text.setMaximumHeight(180);annlayout.addWidget(self.annotation_text)
        self.annotation_list.currentItemChanged.connect(self.annotation_selected)
        self.annotation_list.itemDoubleClicked.connect(lambda item:self.edit_selected_annotation())
        annbuttons=QHBoxLayout();annlayout.addLayout(annbuttons)
        for text,callback in [(L('修改','Edit'),self.edit_selected_annotation),(L('删除','Delete'),self.delete_annotation)]:
            button=QPushButton(text);button.clicked.connect(callback);annbuttons.addWidget(button)
        self.sidebar.addTab(self.annotation_sidebar,tr('annotate'))
        self.image_sidebar=QWidget();image_layout=QVBoxLayout(self.image_sidebar);image_layout.setContentsMargins(5,5,5,5)
        self.image_hint=QLabel();self.image_hint.setWordWrap(True);image_layout.addWidget(self.image_hint)
        self.image_list=QListWidget();self.image_list.setIconSize(QSize(72,72));self.image_list.setSelectionMode(QAbstractItemView.ExtendedSelection);image_layout.addWidget(self.image_list,1)
        self.image_list.setContextMenuPolicy(Qt.CustomContextMenu);self.image_list.customContextMenuRequested.connect(self.image_list_menu)
        self.image_list.itemSelectionChanged.connect(self.image_list_selected)
        self.image_extract=QPushButton(tr('extract_image'));self.image_extract.clicked.connect(self.extract_selected_images);image_layout.addWidget(self.image_extract)
        self.image_list.itemDoubleClicked.connect(lambda _:self.extract_selected_images())
        self.sidebar.addTab(self.image_sidebar,L('图片','Images'))
        self.image_revision=None
        self.scroll = ReaderScroll(self); self.canvas = Canvas(self); self.scroll.setWidget(self.canvas)
        self.document_views=QStackedWidget();self.document_views.addWidget(self.scroll)
        self.organizer=ThumbnailList();self.organizer.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel);self.organizer.verticalScrollBar().valueChanged.connect(self.update_organizer_inset);self.organizer.setViewMode(QListWidget.IconMode);self.organizer.setIconSize(QSize(155,205));self.organizer.setGridSize(QSize(180,235));self.organizer.setResizeMode(QListWidget.Adjust)
        self.organizer.setSelectionMode(QAbstractItemView.ExtendedSelection);self.organizer.setDragDropMode(QAbstractItemView.InternalMove);self.organizer.setDefaultDropAction(Qt.MoveAction)
        self.organizer.zoomed.connect(lambda delta:self.organizer_zoom.setValue(self.organizer_zoom.value()+delta));self.organizer_zoom.valueChanged.connect(self.zoom_organizer)
        self.organizer.reordered.connect(self.reorder);self.organizer.setContextMenuPolicy(Qt.CustomContextMenu);self.organizer.customContextMenuRequested.connect(lambda pos:self.page_context_menu(self.organizer,pos))
        self.organizer.itemDoubleClicked.connect(lambda item:(self.document_views.setCurrentWidget(self.scroll),self.goto(item.data(Qt.UserRole))))
        self.document_views.addWidget(self.organizer);self.splitter.addWidget(self.document_views); self.splitter.setSizes([self.sidebar.tabBar().sizeHint().width()+12,1000]);self.splitter.splitterMoved.connect(lambda pos,index:self.toggle_sidebar() if index==1 and pos<8 and self.sidebar.isVisible() else None)
        self.build_text_properties()
        self.scroll.verticalScrollBar().valueChanged.connect(lambda: (self.canvas.update_current(), self.canvas.update()))
        self.canvas.pageChanged.connect(self.current_changed)
        self.canvas.selection.connect(self.selection_finished)
        self.canvas.objectSelected.connect(self.canvas_objects_selected)
        self.canvas.objectMoved.connect(self.move_objects)
        self.canvas.mediaClick.connect(self.media_clicked)
        self.status=QLabel(self);self.status.hide()
        self.progress=QProgressBar(self.scroll.viewport());self.progress.setFixedSize(155,18);self.progress.hide()
        self.cancel=QPushButton(tr('cancel'),self.scroll.viewport());self.cancel.setFixedSize(50,22);self.cancel.hide();self.cancel.clicked.connect(self.cancel_job)
        from .minimap import DocumentMap
        self.minimap=DocumentMap(self)
        for i,(symbol,key) in enumerate([('▦','thumbnails'),('☰','outline'),('☆','bookmarks'),('⌕','search'),('☷','annotate')]):
            self.sidebar.setTabText(i,L('页面','Pages') if i==0 else L('批注','Notes') if i==4 else tr(key));self.sidebar.setTabToolTip(i,tr(key))
        self.sidebar.tabBar().setExpanding(False)
        self.sidebar.tabBar().setStyleSheet('QTabBar::tab {padding:5px 6px;}')
        self.splitter.setStretchFactor(0,0);self.splitter.setStretchFactor(self.splitter.indexOf(self.document_views),1)
        QTimer.singleShot(0,self.initialize_sidebar_width)
        self.sidebar.currentChanged.connect(lambda _:self.extract_embedded() if self.sidebar.currentWidget()==self.image_sidebar and self.canvas.mode!='images' and not self.busy else None)
        self.tool_panels.hide();self.active_panel='read';self.configure_chrome();self.sync_tool_states()
        self.sidebar.setVisible(not self.window.settings.value('sidebar/hidden',False,type=bool))
        for widget in (self.sidebar,self.outline,self.results,self.annotation_list):
            widget.setContextMenuPolicy(Qt.CustomContextMenu)
            widget.customContextMenuRequested.connect(lambda pos,source=widget:self.sidebar_menu(pos,source))

    def add_panel(self, key, actions):
        bar = QToolBar(); bar.setMovable(False);bar.setIconSize(QSize(17,17));bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        for label, callback in actions:
            action=decorate(bar.addAction(tr(label), callback),label,self.dark)
            if key=='annotate' or label in ('text_ops','add_image','vector_edit','colors','region','crop','add_video'):action.setCheckable(True)
        self.panel_keys[key] = self.tool_panels.addWidget(bar)

    def set_panel(self,key):
        if key==self.active_panel and key!='read':key='read'
        self.open_panel(key)

    def open_panel(self,key):
        if self.inline_editor and self.inline_dirty():
            self.leave_inline(lambda:self.open_panel(key));return
        self.leave_color_tools()
        self.active_panel=key
        self.cancel_inline()
        if key!='pages':self.document_views.setCurrentWidget(self.scroll)
        self.text_properties.setVisible(key=='objects' and self.text_properties.isVisible());self.text_container.setVisible(self.text_properties.isVisible())
        self.page_live_operations=[]
        if hasattr(self,'property_container'):self.property_container.hide()
        self.editing_objects = key == 'objects'
        self.tool_panels.setCurrentIndex(self.panel_keys[key]);self.tool_panels.setVisible(key!='read')
        self.module_group.setExclusive(False)
        for name,action in self.module_actions.items():action.setChecked(name==key)
        self.module_group.setExclusive(True)
        self.style_modules()
        if key == 'read':
            self.canvas.selected=[];self.canvas.region=None;self.canvas.word_selection=[];self.canvas.vector_edit=False;self.set_mode('select')
        elif key == 'objects': self.canvas.selected=[];self.text_tools();self.inspect_objects()
        elif key == 'annotate':
            self.set_mode('highlight');self.sidebar.setCurrentWidget(self.annotation_sidebar);self.load_annotations()
        elif key == 'extract': self.set_mode('region')
        elif key == 'pages':self.set_mode('select');self.organize_pages()
        self.position_chrome()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'tool_panels'):self.position_chrome()

    def style_modules(self):
        color='#26364b' if self.window.dark else '#edf1f8'
        alpha=self.window.settings.value('toolbar/opacity',100,type=int)*255//100;c=QColor(color)
        self.tools.setStyleSheet(f'QToolBar {{background:transparent;}} QToolButton:checked {{background:{color};border-bottom:2px solid #647eea;}}')
        self.tool_panels.setStyleSheet(f'QToolBar {{background:rgba({c.red()},{c.green()},{c.blue()},{alpha});}}')

    def pointer(self):
        if self.inline_editor and self.inline_dirty():
            self.leave_inline(self.pointer);return
        self.cancel_inline();self.editing_objects=False;self.set_mode('select')

    def set_mode(self,mode):
        if self.inline_editor and mode != "objects":
            self.leave_inline(lambda:self.set_mode(mode));return
        self.canvas.mode=mode
        from .annotation_tools import KINDS
        if mode in KINDS and hasattr(self,'splitter') and self.active_panel=='annotate':self.show_annotation_properties(mode)
        self.sync_tool_states()
        if mode in ('highlight','underline','strikeout','replace_text','squiggly','note','freetext','ink','line','arrow','rectangle','ellipse') and hasattr(self,'annotation_list'):
            self.annotation_list.setCurrentItem(None);self.annotation_list.clearSelection()
        if hasattr(self,'add_text_button'):self.add_text_button.setChecked(mode=='add_text')
        if hasattr(self,'shape_draw_button'):self.shape_draw_button.setChecked(mode=='draw_shape')
        for kind,button in getattr(self,'shape_buttons',{}).items():
            if mode!='draw_shape':button.setChecked(False)
        if hasattr(self,'figure_place'):self.figure_place.setChecked(mode=='add_image')
        for i in range(self.tool_panels.count()):
            for action in self.tool_panels.widget(i).actions():
                if action.isCheckable():
                    key=action.property('aster_key');tool={'text_ops':'text','add_image':'image','vector_edit':'shape','colors':'colors','add_video':'video'}.get(key)
                    action.setChecked(tool==getattr(self,'edit_tool','text') if tool else key==mode)
        if mode=='freetext' and self.annot_color.name()=='#efb43d':
            self.annot_color=QColor('#243249');self.color_action.setIcon(self.color_icon())
        if mode in ('freetext','ink','line','arrow','rectangle','ellipse'):
            self._sync_annotation=True;self.annot_width_widget.setMinimum(0 if mode=='freetext' else .2)
            self.annot_width_widget.setValue(self.annot_text_border if mode=='freetext' else max(.2,self.annot_width));self._sync_annotation=False
        cursor=Qt.OpenHandCursor if mode=='hand' else Qt.IBeamCursor if mode in ('highlight','underline','strikeout','replace_text','squiggly','freetext','add_text') else Qt.ArrowCursor if mode in ('select','objects','select_annot') else Qt.CrossCursor
        self.canvas.setCursor(cursor)
        self.status.setText(tr(mode)+' · '+(L('Shift 多选 · 拖动移动 · 右下角缩放 · 双击编辑 · Delete 删除','Shift: select several · Drag: move · Corner: resize · Double-click: edit · Delete: remove') if mode=='objects' else L('拖动选择','Drag to select')))
        if mode=='select_annot':self.load_annotations()
        self.canvas.update()

    def show_annotation_properties(self,kind=None,selected=None,author=False):
        from .annotation_tools import build
        build(self,kind or 'select_annot',selected,author)

    def color_icon(self):
        pix=QPixmap(18,18);pix.fill(self.annot_color);return QIcon(pix)

    def choose_color(self):
        color=QColorDialog.getColor(self.annot_color,self)
        if color.isValid():
            self.annot_color=color;self.color_action.setIcon(self.color_icon())
            self.apply_annotation_style()
            from .preferences import remember_annotation
            remember_annotation(self)
            if self.inline_editor:self.inline_color=color.getRgbF()[:3];self.update_inline_style()

    def annotation_settings(self):
        form=FormDialog(L('批注样式','Annotation style'),self)
        form.text('author',L('批注人','Author'),self.annot_author)
        form.number('size',L('文本字号','Text size'),self.annot_size,4,150)
        form.number('head',L('箭头大小（点）','Arrowhead size (pt)'),self.annot_head_size,3,80,1)
        form.number('border',L('文本框边框线宽（0 无边框）','Text border width (0 = none)'),self.annot_text_border,0,20,1)
        form.choice('font',L('文本字体','Text font'),[(L('中文','CJK'),'china-s'),('Helvetica','helv'),('Times','tiro'),('Courier','cour')])
        form.inputs['font'].setCurrentIndex(max(0,form.inputs['font'].findData(self.annot_font)))
        form.choice('end',L('箭头端点','Arrow end'),[(L('实心箭头','Closed arrow'),5),(L('空心箭头','Open arrow'),4),(L('圆','Circle'),2),(L('菱形','Diamond'),3),(L('无','None'),0)])
        form.inputs['end'].setCurrentIndex(max(0,form.inputs['end'].findData(self.annot_end)))
        form.check('dashed',L('虚线','Dashed'),self.annot_dashed)
        border=QPushButton(L('文本框边框颜色…','Text border color…'));form.form.addRow(border)
        def choose_border():
            color=QColorDialog.getColor(self.annot_border_color,form)
            if color.isValid():self.annot_border_color=color
        border.clicked.connect(choose_border)
        if form.finish().exec()==QDialog.Accepted:
            v=form.values();self.annot_author=v['author'];self.annot_size=v['size'];self.annot_font=v['font'];self.annot_end=v['end'];self.annot_dashed=v['dashed']
            self.annot_head_size=v['head'];self.annot_text_border=v['border'];self.apply_annotation_style(text_style=True)
            from .preferences import remember_annotation
            remember_annotation(self)

    def customize_toolbar(self):return ChromeMixin.customize_toolbar(self)

    def error(self, message):
        if not self.closed:
            QMessageBox.warning(self,'AsterPDF',message)

    def cancel_job(self):
        if self.job: self.job.cancelled = True

    def run(self, label, function, success=None, editing=False, cancellable=False, failure=None, fast_objects=False,local_edit=False,page_update=None):
        if self.busy: return
        self.busy = True
        edit_page=self.canvas.page
        self.job_label = label
        self.pause_media()
        self.status.setText(label+' · '+tr('working'))
        self.progress.setRange(0,0);self.progress.move(max(0,self.scroll.viewport().width()-215),8);self.cancel.move(max(0,self.scroll.viewport().width()-55),6)
        progress_timer=QTimer(self);progress_timer.setSingleShot(True)
        progress_timer.timeout.connect(lambda:(self.progress.show(),self.cancel.setVisible(cancellable)) if self.busy else None);progress_timer.start(450)
        self.thumbnails.setDragEnabled(False);self.organizer.setDragEnabled(False)
        def done(result):
            if self.closed: return
            if editing:
                self.info = result[1]
                if page_update is not None:self.refresh_pages(page_update)
                elif local_edit or fast_objects:
                    self.refresh_local(result[0] if fast_objects else None,edit_page)
                else:self.refresh()
                result = result[0]
            if success: success(result)
        def finished():
            progress_timer.stop();progress_timer.deleteLater()
            self.busy = False; self.progress.hide(); self.cancel.hide()
            self.tools.setEnabled(True); self.tool_panels.setEnabled(True)
            self.thumbnails.setDragEnabled(True);self.organizer.setDragEnabled(True)
            if self.status.text()==label+' · '+tr('working'):self.status.setText(tr('ready'))
            self.window.update_title()
            if editing and self.search_input.text().strip():self.refresh_search(False)
            if self.canvas.mode=='images' and self.image_revision!=(self.canvas.page,self.document.revision):QTimer.singleShot(0,self.extract_embedded)
            if self.editing_objects and self.canvas.mode=='objects' and not self.inline_editor and (editing or (label==tr('scan_objects') and getattr(self,'scan_target',self.canvas.page)!=self.canvas.page)):QTimer.singleShot(0,self.inspect_objects)
        def work(job):
            result = function(job)
            return (result,self.info if local_edit or fast_objects else self.document.info()) if editing else result
        self.job = self.queue.submit(work, done, failure or self.error, finished,
                         lambda n,total: (self.progress.setRange(0,total),self.progress.setValue(n)), priority=2)

    def refresh_pages(self,update):
        from PySide6.QtGui import QTransform
        mapping=update.get('mapping')
        if mapping is None:
            oldcount=len(self.canvas.sizes);op=update.get('operation');indices=update.get('indices',[])
            if op=='delete':mapping=[p for p in range(oldcount) if p not in indices]
            elif op=='insert':
                position=update['position'];mapping=list(range(oldcount));mapping[position:position]=[None]*(self.info['count']-oldcount)
            elif op=='blank':
                mapping=[]
                for p in range(oldcount):
                    if p in indices and update.get('before'):mapping.append(None)
                    mapping.append(p)
                    if p in indices and not update.get('before'):mapping.append(None)
            else:mapping=list(range(self.info['count']))
        changed=set(update.get('changed',[]));oldpage=self.canvas.page
        self.canvas.remap_pages(mapping,changed);self.canvas.sizes=self.info['sizes']
        self.canvas.page=mapping.index(oldpage) if oldpage in mapping else min(oldpage,len(mapping)-1)
        for listing in (self.thumbnails,self.organizer):
            scroll=listing.verticalScrollBar().value();listing.setUpdatesEnabled(False);listing.blockSignals(True)
            previous=[listing.takeItem(0) for _ in range(listing.count())]
            for page,old in enumerate(mapping):
                item=previous[old] if old is not None else QListWidgetItem()
                if old is None:item.setSizeHint(QSize(150,174))
                item.setText(f'{page+1:02d}');item.setData(Qt.UserRole,page);item.setTextAlignment(Qt.AlignHCenter)
                item.setData(Qt.UserRole+2,None)
                if page in changed:
                    transform=QTransform();op=update.get('operation')
                    if op=='rotate':transform.rotate(update.get('angle',90))
                    elif op in ('flip_h','flip_v'):transform.scale(-1 if op=='flip_h' else 1,-1 if op=='flip_v' else 1)
                    if not item.icon().isNull():item.setIcon(QIcon(item.icon().pixmap(320,320).transformed(transform,Qt.SmoothTransformation)))
                    item.setData(Qt.UserRole+1,True)
                listing.addItem(item)
            listing.blockSignals(False);listing.setUpdatesEnabled(True);listing.verticalScrollBar().setValue(scroll)
        self.page_spin.blockSignals(True);self.page_spin.setMaximum(self.info['count']);self.page_spin.blockSignals(False);self.page_count.setText(f" / {self.info['count']}  ")
        self.outline.clear();parents={0:self.outline.invisibleRootItem()}
        for level,title,page in self.info['toc']:
            item=QTreeWidgetItem([title]);item.setData(0,Qt.UserRole,max(0,page-1));parents.get(level-1,parents[0]).addChild(item);parents[level]=item
        self.outline.expandToDepth(1);self.refresh_bookmarks();self.zoom_organizer();self.canvas.layout_pages();self.current_changed(self.canvas.page)
        self.links.clear();self.object_cache.clear();self.image_cache.clear();self.load_annotations();self.load_characters(self.canvas.page)
        for p in self.video_players:p.shutdown();p.deleteLater()
        for p in self.players.values():p.release();p.deleteLater()
        self.players={};self.video_players=[];self.animations=[];self.assets=[]
        self.queue.submit(lambda j:media.scan(self.document),lambda data:self.media_scanned(data,False),self.error)
        self.minimap.preserve_pages(mapping,changed);self.thumbnail_timer.start(0)

    def refresh_local(self,models=None,page=None):
        page=self.canvas.page if page is None else page;self.canvas.invalidate_page(page)
        self.object_cache.clear();self.image_cache.pop(page,None);self.links.pop(page,None)
        if models is not None:
            if self.canvas.page==page:self.canvas.objects=models;self.canvas.object_page=page
            self.object_cache[(self.document.revision,page)]=models
        elif self.editing_objects and self.canvas.object_page==page:self.canvas.objects=[]
        for listing in (self.thumbnails,self.organizer):
            item=listing.item(page)
            if item:item.setData(Qt.UserRole+1,True)
        self.thumbnail_timer.start(300);self.load_annotations();self.load_characters(page);self.canvas.update()
        if self.animations or self.assets:self.queue.submit(lambda j:media.scan(self.document),lambda result:self.media_scanned(result,False),self.error)

    def approve_limit(self, structural=False, extra=''):
        warnings = self.document.preflight(structural)  # lightweight metadata inspection under UI lock
        if extra: warnings.append(extra)
        if warnings:
            return QMessageBox.question(self,'AsterPDF','\n\n'.join(warnings),
                QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Ok
        return True

    def refresh(self):
        structural=self.canvas.sizes!=self.info['sizes']
        self.canvas.sizes=self.info['sizes'];self.canvas.page=min(self.canvas.page,self.info['count']-1)
        self.page_spin.blockSignals(True);self.page_spin.setMaximum(self.info['count']);self.page_spin.blockSignals(False)
        self.page_count.setText(f" / {self.info['count']}  ")
        frames=self.canvas.frame_pixmaps.copy()
        selection=self.canvas.selected[:]
        self.canvas.invalidate();self.canvas.selected=selection;self.canvas.frame_pixmaps=frames
        if structural:self.canvas.fallback.clear()
        self.canvas.layout_pages();self.populate_navigation();self.current_changed(self.canvas.page)
        self.links.clear();self.object_cache.clear();self.image_cache.clear();self.object_list.clear()
        self.load_annotations();self.load_characters(self.canvas.page)
        # Annotation/content edits retain existing playback instances. Structural
        # operations can change page references, so discover media again then.
        if structural or getattr(self,'job_label','') in (tr('pages'),tr('merge'),tr('undo'),tr('redo')):
            for p in self.video_players:p.shutdown();p.deleteLater()
            for p in self.players.values():p.release();p.deleteLater()
            self.players={};self.video_players=[];self.animations=[];self.assets=[]
            self.queue.submit(lambda j:media.scan(self.document),self.media_scanned,self.error)
        else:
            self.queue.submit(lambda j:media.scan(self.document),self.media_scanned,self.error)
        self.thumbnail_timer.start(100)

    def populate_navigation(self):
        selected=[i.data(Qt.UserRole) for i in self.organizer.selectedItems()];current=self.organizer.currentRow()
        self.thumbnails.clear();self.organizer.clear()
        for i in range(self.info['count']):
            item=QListWidgetItem(f'{i+1:02d}'); item.setData(Qt.UserRole,i); item.setSizeHint(QSize(150,174))
            item.setTextAlignment(Qt.AlignHCenter); self.thumbnails.addItem(item)
            preview=QListWidgetItem(item);preview.setSizeHint(QSize(172,226));self.organizer.addItem(preview)
        if 0<=current<self.organizer.count():self.organizer.setCurrentRow(current);self.organizer.clearSelection()
        for i in selected:
            if i<self.organizer.count():self.organizer.item(i).setSelected(True)
        self.outline.clear(); parents={0:self.outline.invisibleRootItem()}
        for level,title,page in self.info['toc']:
            item=QTreeWidgetItem([title]);item.setToolTip(0,title); item.setData(0,Qt.UserRole,max(0,page-1))
            parents.get(level-1,parents[0]).addChild(item); parents[level]=item
        self.outline.expandToDepth(1); self.refresh_bookmarks();self.zoom_organizer()

    def zoom_organizer(self,*_):
        scale=self.organizer_zoom.value()/100*96/72;self.window.settings.setValue('page/preview_scale',self.organizer_zoom.value())
        w=max(40,round(max(s[0] for s in self.info['sizes'])*scale));h=max(40,round(max(s[1] for s in self.info['sizes'])*scale))
        self.organizer.setIconSize(QSize(w,h));self.organizer.setGridSize(QSize(w+22,h+30))
        for n in range(self.organizer.count()):self.organizer.item(n).setSizeHint(QSize(w+18,h+26))
        if hasattr(self,'thumbnail_timer'):self.thumbnail_timer.start(0)

    def load_thumbnails(self):
        if self.closed:return
        revision=self.document.revision;target=self.organizer if self.organizer.isVisible() else self.thumbnails
        for row in range(target.count()):
            item=target.item(row)
            if (not item.icon().isNull() and not item.data(Qt.UserRole+1)) or not target.visualItemRect(item).intersects(target.viewport().rect()) or item.data(Qt.UserRole+2)==revision:continue
            page=item.data(Qt.UserRole);item.setData(Qt.UserRole+2,revision)
            if item.icon().isNull():item.setIcon(self.window.icon)
            def done(data,page=page,revision=revision):
                if self.closed or revision!=self.document.revision:return
                pix=QPixmap();pix.loadFromData(data)
                for listing in (self.thumbnails,self.organizer):
                    for n in range(listing.count()):
                        it=listing.item(n)
                        if it.data(Qt.UserRole)==page:it.setIcon(QIcon(pix));it.setData(Qt.UserRole+1,False);break
            self.queue.submit(lambda j,p=page:self.document.render(p,300/self.info['sizes'][p][0]),done,priority=-2)

    def organize_pages(self):
        self.document_views.setCurrentWidget(self.organizer);self.sidebar.setCurrentWidget(self.thumbnails)
        self.organizer.setCurrentRow(self.canvas.page);QTimer.singleShot(0,self.load_thumbnails)

    def page_context_menu(self,listing,pos):
        item=listing.itemAt(pos)
        if item and item not in listing.selectedItems():listing.setCurrentItem(item)
        page=item.data(Qt.UserRole) if item else self.info['count']-1
        insertion=self.info['count']
        if not item and listing.count():
            nearest=min((listing.item(n) for n in range(listing.count())),key=lambda it:(listing.visualItemRect(it).center()-pos).manhattanLength())
            rect=listing.visualItemRect(nearest);before=pos.y()<rect.top() or (pos.y()<=rect.bottom() and pos.x()<rect.center().x())
            insertion=nearest.data(Qt.UserRole)+(0 if before else 1)
        menu=QMenu(self)
        if not item:
            menu.addAction(L('收起 / 展开导航','Collapse / expand navigation'),self.toggle_sidebar)
            auto=menu.addAction(L('自动隐藏导航','Auto-hide navigation'));auto.setCheckable(True);auto.setChecked(self.window.settings.value('sidebar/autohide',False,type=bool));auto.toggled.connect(lambda value:self.window.settings.setValue('sidebar/autohide',value));menu.addSeparator()
        menu.addAction(tr('delete_pages'),lambda:self.page_selection_operation('delete',listing))
        menu.addAction(tr('rotate'),lambda:self.page_tools('rotate'))
        if item:
            menu.addAction(L('在本页前插入 PDF…','Insert PDF before this page…'),lambda:self.insert_pdf_at(page))
        if item:menu.addAction(L('在本页后插入 PDF…','Insert PDF after this page…'),lambda:self.insert_pdf_at(page+1))
        else:menu.addAction(L(f'在第 {insertion} 页之后插入 PDF…',f'Insert PDF after page {insertion}…'),lambda:self.insert_pdf_at(insertion))
        menu.addAction(tr('extract_pages'),self.extract_pages)
        menu.exec(listing.viewport().mapToGlobal(pos))

    def page_selection_operation(self,operation,listing=None):
        listing=listing or (self.organizer if self.organizer.isVisible() else self.thumbnails)
        pages=sorted(it.data(Qt.UserRole) for it in listing.selectedItems())
        if not pages:return
        if operation=='delete' and len(pages)>=self.info['count']:self.error(L('至少保留一页。','Keep at least one page.'));return
        def done(_):
            if operation!='delete':
                for view in (self.thumbnails,self.organizer):
                    for n in range(view.count()):view.item(n).setSelected(view.item(n).data(Qt.UserRole) in pages)
        self.run(tr('pages'),lambda j:self.document.page_operation(operation,pages),done,editing=True,page_update={'operation':operation,'indices':pages,'changed':pages if operation!='delete' else []})

    def insert_pdf_at(self,position):
        files,_=QFileDialog.getOpenFileNames(self,L('插入 PDF','Insert PDFs'),'','PDF (*.pdf)')
        if not files:return
        if not self.approve_limit(True,L('插入只复制源文件的页级内容；不导入文档级目录、脚本和表单树。','Insertion copies page-level content, not document-level outlines, scripts or form trees.')):return
        self.run(tr('pages'),lambda j:self.document.page_operation('insert',[],files=files,position=position),editing=True,page_update={'operation':'insert','position':position})

    def goto(self,page):
        if self.inline_editor:
            if self.inline_dirty():
                self.leave_inline(lambda:self.goto(page));return
            self.cancel_inline()
        page=max(0,min(int(page),self.info['count']-1));self.canvas.page=page
        if not self.canvas.continuous:
            self.canvas.layout_pages();self.scroll.verticalScrollBar().setValue(0)
        elif self.canvas.rects:
            self.canvas.laying_out=True
            self.scroll.verticalScrollBar().setValue(int(self.canvas.rects[page].y()-16-getattr(self,'reading_inset',0)))
            self.canvas.laying_out=False
        self.current_changed(page);self.scroll.sync_document_bar();self.canvas.update()

    def turn_page(self,delta,from_bottom=False):
        self.goto(self.canvas.page+delta*self.canvas.columns)
        if from_bottom:self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def handle_key(self,event):
        key=event.key()
        if event.modifiers() & (Qt.ControlModifier|Qt.AltModifier):return False
        if key==Qt.Key_Escape:self.window.escape();return True
        if key==Qt.Key_Delete and (self.active_panel=='annotate' or self.annotation_list.hasFocus()) and self.annotation_list.selectedItems():self.delete_annotation();return True
        if key==Qt.Key_Delete and self.organizer.isVisible():self.page_selection_operation('delete');return True
        if key==Qt.Key_Delete and self.canvas.mode=='objects':
            if self.selected_objects():self.delete_objects()
            return True
        if key in (Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down) and self.active_panel=='objects' and self.canvas.mode=='objects' and not self.inline_editor and self.selected_objects():
            delta=(10 if event.modifiers()&Qt.ShiftModifier else 1)/self.canvas.scale
            self.move_objects(delta*((key==Qt.Key_Right)-(key==Qt.Key_Left)),delta*((key==Qt.Key_Down)-(key==Qt.Key_Up)));return True
        if key in (Qt.Key_Right,Qt.Key_PageDown):self.turn_page(1);return True
        if key in (Qt.Key_Left,Qt.Key_PageUp):self.turn_page(-1);return True
        if key==Qt.Key_Home:self.goto(0);return True
        if key==Qt.Key_End:self.goto(self.info['count']-1);return True
        if key in (Qt.Key_Up,Qt.Key_Down,Qt.Key_Space):
            delta=-1 if key==Qt.Key_Up or (key==Qt.Key_Space and event.modifiers()&Qt.ShiftModifier) else 1
            if self.window.presentation:self.turn_page(delta);return True
            bar=self.scroll.verticalScrollBar();step=self.scroll.viewport().height()-40 if key==Qt.Key_Space else 45
            if not self.canvas.continuous and ((delta<0 and bar.value()==0) or (delta>0 and bar.value()==bar.maximum())):self.turn_page(delta,delta<0)
            else:bar.setValue(bar.value()+delta*step)
            return True
        return False

    def current_changed(self,page):
        self.update_bookmark_icon()
        self.page_spin.blockSignals(True);self.page_spin.setValue(page+1);self.page_spin.blockSignals(False)
        if page<self.thumbnails.count():
            item=self.thumbnails.item(page)
            if not (QApplication.keyboardModifiers() & (Qt.ControlModifier|Qt.ShiftModifier)):
                self.thumbnails.blockSignals(True);self.thumbnails.setCurrentItem(item);self.thumbnails.blockSignals(False)
            self.thumbnails.scrollToItem(item,QAbstractItemView.EnsureVisible)
        for player in self.players.values():
            if player.animation.page!=page:player.stop()
            elif not player.filename:player.prepare()
        self.position_video()
        if page not in self.links:
            self.links[page]=[]
            self.queue.submit(lambda j:self.document.links(page),lambda links:self.links.update({page:links}))
        self.load_characters(page)
        if hasattr(self,'annotation_list'):self.load_annotations()
        if self.editing_objects and self.canvas.object_page!=page and not self.busy:QTimer.singleShot(0,self.inspect_objects)
        if self.canvas.mode=='images' and self.image_revision!=(page,self.document.revision) and not self.busy:QTimer.singleShot(0,self.extract_embedded)

    def load_characters(self,page):
        if page in self.canvas.words:return
        revision=self.document.revision;self.canvas.words[page]=[]
        def done(chars):
            if not self.closed and revision==self.document.revision:self.canvas.words[page]=chars
        self.queue.submit(lambda j:self.document.characters(page),done,self.error)
        if page not in self.image_cache:
            self.image_cache[page]=[]
            def images_done(images):
                if revision==self.document.revision and not self.closed:self.image_cache[page]=images
            self.queue.submit(lambda j:self.document.image_occurrences(page),images_done,self.error)

    def set_view(self,columns,continuous):
        page=self.canvas.page;self.canvas.columns=columns
        self.continuous.blockSignals(True);self.continuous.setChecked(continuous);self.continuous.blockSignals(False)
        self.canvas.continuous=continuous;self.canvas.layout_pages();self.goto(page)

    def zoom_changed(self,*args):
        try:self.set_zoom(float(self.zoom.currentText().rstrip('%'))/100*self.actual_size_scale())
        except ValueError:self.error(L('缩放范围：1.5625–6400%','Zoom: 1.5625–6400%'))

    def actual_size_scale(self):
        screen=self.window.screen();dpi=screen.physicalDotsPerInch() if screen else 96
        return (dpi if 35<dpi<500 else 96)/72

    def screen_zoom_changed(self,*_):
        if self.closed or not hasattr(self,'zoom_factor'):return
        if self.inline_editor:self.suspend_inline()
        self.set_zoom(self.zoom_factor*self.actual_size_scale())

    def sync_tool_states(self):
        for i in range(self.tool_panels.count()):
            for action in self.tool_panels.widget(i).actions():
                if action.property('aster_key')=='region':action.setChecked(self.canvas.mode=='region')
        for key in ('select','hand','region'):
            self.quick_actions[key].setChecked(self.canvas.mode==key)
        for key in ('page_fit','width_fit'):self.quick_actions[key].setChecked(self.fit_mode==key)
        if hasattr(self,'minimap'):self.quick_actions['minimap'].setChecked(self.minimap.enabled)

    def set_zoom(self,value):
        self.fit_mode=None;self.sync_tool_states()
        unit=self.actual_size_scale();self.zoom_factor=max(1/64,min(64,value/unit));self.canvas.scale=self.zoom_factor*unit
        label='1.5625' if self.zoom_factor==1/64 else f'{self.zoom_factor*100:.2f}'.rstrip('0').rstrip('.')
        self.zoom.setCurrentText(label+'%')
        self.canvas.invalidate(False);self.canvas.layout_pages();self.goto(self.canvas.page)
        for p in self.players.values():
            if p.filename:p.show_frame(p.index)

    def zoom_by(self,factor,anchor=None):
        if anchor is None:self.set_zoom(self.canvas.scale*factor);return
        point=QPointF(self.canvas.mapFromGlobal(anchor.toPoint()));page,local=self.canvas.locate(point)
        if page<0:page=self.canvas.page;local=(point-self.canvas.rects[page].topLeft())/self.canvas.scale
        viewport=QPointF(self.scroll.viewport().mapFromGlobal(anchor.toPoint()))
        self.set_zoom(self.canvas.scale*factor)
        destination=self.canvas.rects[page].topLeft()+local*self.canvas.scale
        self.canvas.laying_out=True
        self.scroll.horizontalScrollBar().setValue(round(destination.x()-viewport.x()));self.scroll.verticalScrollBar().setValue(round(destination.y()-viewport.y()))
        self.canvas.laying_out=False


    def fit(self,width):
        w,h=self.info['sizes'][self.canvas.page]
        if self.canvas.columns==2:
            row=(self.canvas.page//2)*2
            w=sum(size[0] for size in self.info['sizes'][row:row+2])+16
            h=max(size[1] for size in self.info['sizes'][row:row+2])
        available=self.scroll.viewport().size()
        self.set_zoom((available.width()-56)/w if width else min((available.width()-56)/w,(available.height()-getattr(self,'reading_inset',0)-40)/h))
        self.fit_mode='width_fit' if width else 'page_fit';self.sync_tool_states()

    def set_continuous(self,value):
        if not hasattr(self,'canvas'):return
        page=self.canvas.page;self.canvas.continuous=value;self.canvas.layout_pages();self.goto(page)

    def update_bookmark_icon(self):
        from PySide6.QtGui import QPixmap,QPainter,QIcon,QFont
        if not hasattr(self,'bookmark_pages'):return
        active=self.canvas.page in self.bookmark_pages
        dpr=self.devicePixelRatioF();pix=QPixmap(round(24*dpr),round(24*dpr));pix.setDevicePixelRatio(dpr);pix.fill(Qt.transparent);p=QPainter(pix);p.setPen(QColor('#e2a226' if active else '#b9cbe3' if self.dark else '#344c6c'));f=QFont();f.setPixelSize(23);p.setFont(f);p.drawText(QRectF(0,0,24,24),Qt.AlignCenter,'★' if active else '☆');p.end()
        self.quick_actions['bookmark'].setIcon(QIcon(pix));self.quick_actions['bookmark'].setCheckable(True);self.quick_actions['bookmark'].setChecked(active)

    def refresh_bookmarks(self):
        self.bookmarks.clear();sizes=self.canvas.sizes;total=sum(h for w,h in sizes)
        for page in sorted(self.bookmark_pages):
            if page<self.info['count']:
                name=self.bookmark_names.get(str(page),str(page+1))
                item=QListWidgetItem(name);item.setData(Qt.UserRole,page);item.setData(Qt.UserRole+1,f'{page+1} · {sum(h for w,h in sizes[:page])/max(1,total)*100:.1f}%');self.bookmarks.addItem(item)
        self.update_bookmark_icon()

    def toggle_bookmark(self):
        page=self.canvas.page
        if page in self.bookmark_pages:self.bookmark_pages.remove(page)
        else:self.bookmark_pages.add(page)
        self.refresh_bookmarks()

    def bookmark_menu(self,pos):
        item=self.bookmarks.itemAt(pos)
        if not item:return
        menu=QMenu(self);rename=menu.addAction(L('重命名','Rename'));remove=menu.addAction(L('删除','Remove'));action=menu.exec(self.bookmarks.mapToGlobal(pos))
        page=item.data(Qt.UserRole)
        if action==remove:self.bookmark_pages.discard(page)
        elif action==rename:
            name,ok=QInputDialog.getText(self,L('重命名书签','Rename bookmark'),L('名称','Name'),text=item.text())
            if ok and name.strip():self.bookmark_names[str(page)]=name.strip()
        self.refresh_bookmarks()

    def save_state(self):
        state={'page':self.canvas.page,'zoom_factor':self.zoom_factor,'bookmarks':sorted(self.bookmark_pages),'bookmark_names':self.bookmark_names}
        self.window.settings.setValue(self.state_key,json.dumps(state))

    def show_search(self):
        self.sidebar.show();self.sidebar.setCurrentWidget(self.search_panel);self.search_input.setFocus();self.search_input.selectAll()

    def search(self):
        if self.suspended_inline:self.restore_inline()
        if self.inline_editor:
            self.commit_inline(self.search);return
        self.refresh_search(True)

    def refresh_search(self,navigate=False):
        query=self.search_input.text().strip()
        if not query:
            self.results.clear();self.canvas.search_hits={};self.canvas.active_search=None;self.canvas.update();self.search_count.setText('');return
        if navigate:self.sidebar.setCurrentWidget(self.search_panel)
        revision=self.document.revision
        request=getattr(self,'search_request',0)+1;self.search_request=request
        old=self.results.currentRow()
        def done(hits):
            if self.closed or request!=self.search_request or revision!=self.document.revision:return
            self.results.blockSignals(True);self.results.clear();self.canvas.search_hits=dict(hits);self.canvas.active_search=None
            for page,rects in hits:
                for rect in rects:
                    item=QListWidgetItem(f'{page+1}   {query}');item.setData(Qt.UserRole,(page,rect));self.results.addItem(item)
            self.results.blockSignals(False)
            if self.results.count():
                if navigate:self.results.setCurrentRow(0)
                else:
                    self.results.blockSignals(True);self.results.setCurrentRow(min(max(0,old),self.results.count()-1));self.results.blockSignals(False)
                    self.canvas.active_search=self.results.currentItem().data(Qt.UserRole)
                self.search_count.setText(f'{self.results.currentRow()+1} / {self.results.count()}')
            else:self.search_count.setText(L('无结果','No results'))
            self.canvas.update();self.minimap.update()
        if navigate:
            if self.busy:QTimer.singleShot(50,lambda:self.refresh_search(True))
            else:self.run(tr('search'),lambda j:self.document.search(query,lambda:j.cancelled),done,cancellable=True)
        else:self.queue.submit(lambda j:self.document.search(query,lambda:j.cancelled),done,self.error,priority=1)

    def search_step(self,step):
        if not self.results.count():self.search();return
        self.results.setCurrentRow((self.results.currentRow()+step)%self.results.count())

    def result_clicked(self,item):
        data=item.data(Qt.UserRole)
        if data:
            page,rect=data;self.canvas.active_search=data;self.goto(page)
            r=self.canvas.page_rect(page,rect)
            self.scroll.ensureVisible(int(r.center().x()),int(r.center().y()),80,100)
            self.search_count.setText(f'{self.results.row(item)+1} / {self.results.count()}');self.canvas.update();self.minimap.update()

    def selected_pages(self):
        listing=self.organizer if self.organizer.isVisible() else self.thumbnails
        result=sorted(item.data(Qt.UserRole) for item in listing.selectedItems())
        return result or [self.canvas.page]

    def ask_pages(self,title):
        default=','.join(str(i+1) for i in self.selected_pages())
        text,ok=QInputDialog.getText(self,title,tr('select_pages'),text=default)
        if ok:
            try:return pages_from_text(text,self.info['count'])
            except ValueError as e:self.error(str(e))
        return None

    def page_op(self,op):
        self.page_tools(op)

    def reorder(self,order):
        self.page_live_operations=[]
        if self.busy:return
        selected=self.selected_pages();current=self.canvas.page
        def done(_):
            self.canvas.page=order.index(current);self.current_changed(self.canvas.page);self.canvas.layout_pages()
            moved=[order.index(p) for p in selected]
            for listing in (self.thumbnails,self.organizer):
                listing.clearSelection()
                for n in moved:listing.item(n).setSelected(True)
                if moved:listing.scrollToItem(listing.item(moved[0]),QAbstractItemView.EnsureVisible)
        self.run(tr('pages'),lambda j:self.document.page_operation('reorder',[],order=order),done,editing=True,page_update={'mapping':order})

    def merge(self):
        self.merge_pane()

    def split(self):
        text,ok=QInputDialog.getText(self,tr('split'),L('每组用分号分隔，例如 1-3;4-6','Separate groups with semicolons'),text='1;2-'+str(self.info['count']))
        if not ok:return
        try:groups=[pages_from_text(group,self.info['count']) for group in text.split(';')]
        except ValueError as e:self.error(str(e));return
        destination=QFileDialog.getExistingDirectory(self,tr('split'))
        if not destination or not self.approve_limit(True):return
        targets=[Path(destination)/f'{Path(self.document.original).stem}_part{i+1:03d}.pdf' for i in range(len(groups))]
        if any(p.exists() for p in targets):self.error(L('输出文件已存在，请选择空目录','Choose a directory without matching output names'));return
        def work(job):
            for n,(group,path) in enumerate(zip(groups,targets)):
                if job.cancelled:break
                self.document.extract_pages(group,path);job.signals.progress.emit(n+1,len(groups))
        self.run(tr('split'),work,cancellable=True)

    def extract_pages(self):
        self.page_tools('extract')

    def region_data(self):
        if not self.canvas.region:self.error(tr('need_region'));return None
        return self.canvas.region

    def crop(self):
        self.page_tools('crop')

    def vector_export(self):
        region=self.region_data()
        if not region:return
        page,rect=region
        destination,_=QFileDialog.getSaveFileName(self,tr('vector_pdf'),'figure.pdf','PDF (*.pdf)')
        if destination and self.approve_limit(True,L('局部 PDF 保留矢量和文字，裁剪框外的内容仍可能被恢复。','Vector crop retains original content outside the visible crop box.')):
            self.run(tr('vector_pdf'),lambda j:self.document.extract_pages([page],destination,self.document.to_pdf_rect(page,rect)))

    def export_images(self,region=False):
        selection=self.region_data() if region else None
        if region and not selection:return
        indices=[selection[0]] if selection else self.ask_pages(tr('export_pages'))
        if not indices:return
        v=self.window.export_options()
        if len(indices)==1:
            suffix=v['format'];name=f'{Path(self.document.original).stem}_p{indices[0]+1:04d}{"_region" if selection else ""}.{suffix}'
            filename,chosen=QFileDialog.getSaveFileName(self,tr('export_region' if selection else 'export_pages'),str(Path(self.document.original).parent/name),'PNG (*.png);;JPEG (*.jpg *.jpeg)', 'PNG (*.png)' if suffix=='png' else 'JPEG (*.jpg *.jpeg)')
            if not filename:return
            target=Path(filename)
            if not target.suffix:target=target.with_suffix('.png' if chosen.startswith('PNG') else '.jpg')
            fmt='png' if target.suffix.lower()=='.png' else 'jpg'
            self.run(tr('export_pages'),lambda j:self.document.export_pages(indices,target.parent,v['dpi'],fmt,v['quality'],selection[1] if selection else None,v['width'] or None,filename=target));return
        directory=QFileDialog.getExistingDirectory(self,tr('export_pages'))
        if directory:self.run(tr('export_pages'),lambda j:self.document.export_pages(indices,directory,v['dpi'],v['format'],v['quality'],selection[1] if selection else None,v['width'] or None,j.signals.progress.emit,lambda:j.cancelled),cancellable=True)

    def copy_region(self):
        region=self.region_data()
        if not region:return
        options=self.window.export_options();scale=options['width']/(region[1][2]-region[1][0]) if options['width'] else options['dpi']/72
        self.run(tr('copy_region'),lambda j:self.document.render(region[0],scale,clip=region[1]),lambda data:QApplication.clipboard().setImage(QImage.fromData(data)))

    def extract_embedded(self):
        self.editing_objects=False;self.set_mode('images');self.module_actions['extract'].setChecked(True)
        self.tool_panels.setCurrentIndex(self.panel_keys['extract']);self.tool_panels.show()
        self.sidebar.setCurrentWidget(self.image_sidebar)
        page=self.canvas.page;revision=self.document.revision;self.image_revision=(page,revision)
        self.image_list.clear();self.image_extract.setEnabled(False);self.image_hint.setText(tr('working'))
        def locate(job):
            import pymupdf as fitz
            occurrences=self.document.image_occurrences(page)
            found={x['xref'] for x in occurrences}
            with fitz.open(self.document.path) as pdf:
                for x in pdf[page].get_images(full=True):
                    if x[0] not in found:
                        occurrences.append(dict(xref=x[0],bbox=None,width=x[2],height=x[3]));found.add(x[0])
                thumbs={}
                for x in occurrences:
                    if x['xref'] in thumbs:continue
                    try:
                        pix=fitz.Pixmap(pdf,x['xref'])
                        if pix.colorspace is None:continue
                        if pix.colorspace.n!=3:pix=fitz.Pixmap(fitz.csRGB,pix)
                        while max(pix.width,pix.height)>160:pix.shrink(1)
                        thumbs[x['xref']]=pix.tobytes('png')
                    except (ValueError,RuntimeError):pass
            return occurrences,thumbs
        def done(result):
            if self.closed or self.image_revision!=(page,revision) or self.canvas.mode!='images':return
            occurrences,thumbs=result
            self.canvas.objects=[];self.canvas.object_page=page;self.canvas.selected=[]
            self.image_list.blockSignals(True)
            for i,x in enumerate(occurrences):
                if x['bbox'] is not None:self.canvas.objects.append(objects.PdfObject(i,'image',0,0,(1,0,0,1,0,0),x['bbox'],xref=x['xref'],details=x))
                label=L(f"图片 {i+1}",f"Image {i+1}")+f" · {x['width']}×{x['height']}"
                if x['bbox'] is None:label+=' · '+L('未定位','Unlocated resource')
                item=QListWidgetItem(label);item.setData(Qt.UserRole,(page,i,x['xref']));item.setToolTip(f"xref {x['xref']}");item.setSizeHint(QSize(230,86))
                if x['xref'] in thumbs:
                    pix=QPixmap();pix.loadFromData(thumbs[x['xref']]);item.setIcon(QIcon(pix))
                self.image_list.addItem(item)
            self.image_list.blockSignals(False);self.canvas.update()
            self.image_hint.setText(L('本页没有可提取的内嵌图片。','No extractable embedded images on this page.') if not occurrences else L('选择列表或页面中的图片；Ctrl / Shift 可多选。提取原始图像通道；软蒙版不自动合成。','Select images in the list or page; Ctrl / Shift selects several. Extracts original channels; soft masks are not composited.'))
            self.status.setText(L(f'第 {page+1} 页 · {len(occurrences)} 张内嵌图片',f'Page {page+1} · {len(occurrences)} embedded images'))
        self.run(tr('images'),locate,done)

    def image_list_menu(self,pos):
        item=self.image_list.itemAt(pos)
        if not item:return
        if not item.isSelected():self.image_list.setCurrentItem(item)
        page,index,xref=item.data(Qt.UserRole);obj=next((o for o in self.canvas.objects if o.id==index),None)
        if obj is None:obj=objects.PdfObject(index,'image',0,0,(1,0,0,1,0,0),(0,0,1,1),xref=xref)
        menu=QMenu(self);menu.addAction(L('复制图片','Copy image'),lambda:self.copy_image(obj));menu.addAction(tr('extract_image'),self.extract_selected_images);menu.exec(self.image_list.viewport().mapToGlobal(pos))

    def image_list_selected(self):
        if self.canvas.mode!='images':
            self.extract_embedded();return
        items=self.image_list.selectedItems();self.canvas.selected=[it.data(Qt.UserRole)[1] for it in items]
        self.image_extract.setEnabled(bool(items));self.canvas.update()
        selected=self.selected_objects()
        if selected:
            rect=self.canvas.page_rect(self.canvas.object_page,selected[-1].bbox)
            self.scroll.ensureVisible(int(rect.center().x()),int(rect.center().y()),30,30)

    def extract_selected_images(self):
        selected=list(dict.fromkeys((it.data(Qt.UserRole)[0],it.data(Qt.UserRole)[2]) for it in self.image_list.selectedItems()))
        if not selected:return
        if len(selected)==1:self.save_image_xref(*selected[0]);return
        directory=QFileDialog.getExistingDirectory(self,tr('extract_image'))
        if directory:
            self.run(tr('extract_image'),lambda j:[self.document.extract_image(page,xref,str(Path(directory)/f'page-{page+1:03d}-image-{xref}')) for page,xref in selected],lambda paths:self.status.setText(L(f'已提取 {len(paths)} 张图片',f'Extracted {len(paths)} images')))

    def save_image_xref(self,page,xref):
        destination,_=QFileDialog.getSaveFileName(self,tr('extract_image'),f'page-{page+1:03d}-image-{xref}',L('图片（自动检测扩展名） (*)','Image (extension detected) (*)'))
        if destination:self.run(tr('extract_image'),lambda j:self.document.extract_image(page,xref,destination),lambda path:self.status.setText(L('已提取：','Extracted: ')+str(path)))

    def selection_finished(self,page,points,mode):
        if self.busy:return
        x0,y0=points[0];x1,y1=points[-1];rect=(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
        if mode in ('region','crop'):
            w,h=self.canvas.sizes[page];rect=(max(0,rect[0]),max(0,rect[1]),min(w,rect[2]),min(h,rect[3]));self.canvas.region=(page,rect);self.canvas.update()
            if mode=='crop':self.crop_selection_changed()
            return
        if mode in ('select','read','highlight','underline','strikeout','replace_text','squiggly'):
            if mode in ('select','read') and abs(x1-x0)+abs(y1-y0)<5:
                for link in self.links.get(page,[]):
                    if qrect(link['from']).contains(x0,y0):
                        self.activate_link(link)
                        return
            def selected(chars):
                self.canvas.words[page]=chars
                chosen=self.canvas.select_characters(page,QPointF(x0,y0),QPointF(x1,y1))
                if mode in ('highlight','underline','strikeout','replace_text','squiggly') and chosen:
                    lines={}
                    for c in chosen:
                        key=c[2:4];lines[key]=lines[key].united(qrect(c[0])) if key in lines else qrect(c[0])
                    rects=[(r.left(),r.top(),r.right(),r.bottom()) for r in lines.values()]
                    from .annotation_tools import content
                    self.add_annotation(page,mode,points,word_rects=rects,text=content(self))
            if self.canvas.words.get(page):selected(self.canvas.words[page])
            else:self.queue.submit(lambda j:self.document.characters(page),selected,self.error)
            return
        elif mode=='select_annot':
            box=qrect(rect);self.annotation_list.blockSignals(True);self.annotation_list.clearSelection();self.annotation_list.setCurrentItem(None)
            for n in range(self.annotation_list.count()):
                it=self.annotation_list.item(n);ann=it.data(Qt.UserRole)
                it.setSelected(ann['page']==page and box.contains(qrect(ann['rect'])))
            self.annotation_list.blockSignals(False);self.canvas.update();self.show_annotation_properties('select_annot',selected=[it.data(Qt.UserRole) for it in self.annotation_list.selectedItems()] or None);return
        if mode=='add_video':
            from .video_insert import insert
            filename=getattr(self,'pending_video',None)
            if filename:self.run(tr('add_video'),lambda j:insert(self.document,page,rect,filename),lambda _:(self.set_mode('objects'),self.queue.submit(lambda j:media.scan(self.document),self.media_scanned,self.error)),editing=True,local_edit=True)
            return
        if mode=='draw_shape':self.place_shape(page,rect);return
        if mode=='add_text':self.add_text(page,rect);return
        if mode=='add_image':
            self.place_image(page,rect)
            return
        text=''
        if mode in ('note','freetext'):
            from .annotation_tools import content
            text=content(self)
            if not text:self.status.setText(L('请在批注设置中填写内容。','Enter text in annotation properties.'));return
            if mode=='freetext':
                try:rect=self.freetext_bounds(page,rect,text,self.annot_size,self.annot_font)
                except ValueError as error:self.error(str(error));return
                points=[rect[:2],rect[2:]]
        self.add_annotation(page,mode,points,text=text)

    def freetext_bounds(self,page,rect,text,size,fontname='china-s'):
        import pymupdf as fitz
        width,height=self.info['sizes'][page];x,y,x1,y1=rect
        x=max(0,min(x,width-30));y=max(0,min(y,height-20));x1=min(width,max(x+30,x1));available=x1-x-5
        try:font=fitz.Font(fontname or 'china-s')
        except (ValueError,RuntimeError):font=fitz.Font('china-s')
        lines=1;used=0
        for char in text:
            advance=font.text_length(char,fontsize=size)
            if char=='\n':lines+=1;used=0
            elif used+advance>available:lines+=1;used=advance
            else:used+=advance
        required=lines*size*1.45+6
        if y+required>height:raise ValueError(L('文字超出页面底部，请向上移动或扩大文本框宽度。','Text exceeds the page bottom. Move it up or widen the text box.'))
        return (x,y,x1,min(height,max(y1,y+required)))

    def create_freetext(self,page,point):
        if page<0 or self.busy:return
        from .annotation_tools import content
        text=content(self)
        if not text:self.status.setText(L('请在批注设置中填写内容。','Enter text in annotation properties.'));return
        try:rect=self.freetext_bounds(page,(point.x(),point.y(),point.x()+210,point.y()+20),text,self.annot_size,self.annot_font)
        except ValueError as error:self.error(str(error));return
        self.add_annotation(page,'freetext',[rect[:2],rect[2:]],text=text)

    def resize_annotation(self,ann,rect):
        try:
            if ann['type']=='FreeText':rect=self.freetext_bounds(ann['page'],rect,ann['text'],ann.get('fontsize',12),ann.get('fontname','china-s'))
        except ValueError as error:self.error(str(error));return
        self.run(tr('annotate'),lambda j:self.document.change_annotation(ann['page'],ann['xref'],rect=rect,color=ann.get('color'),width=ann.get('width',0),opacity=ann['opacity'],dashed=ann.get('dashed',False)),editing=True,local_edit=True)

    def add_annotation(self,page,kind,points,**kwargs):
        color=self.annot_color.getRgbF()[:3]
        self.annotation_list.setCurrentItem(None);self.annotation_list.clearSelection();self.canvas.region=None
        self.canvas.pending_annotation=(page,kind,points,kwargs.get('word_rects',[]),QColor(self.annot_color),self.annot_width,self.annot_opacity)
        self.canvas.update()
        def failed(message):self.canvas.pending_annotation=None;self.canvas.update();self.error(message)
        self.run(tr('annotate'),lambda j:self.document.add_annotation(page,kind,points,color,self.annot_width,self.annot_opacity,author_name=self.annot_author,fontsize=self.annot_size,fontname=self.annot_font,line_end=self.annot_end,dashed=self.annot_dashed,head_size=self.annot_head_size,dash=getattr(self,'annot_dash','solid'),fill=getattr(self,'annot_fill',None),text_border=self.annot_text_border,border_color=self.annot_border_color.getRgbF()[:3],**kwargs),editing=True,local_edit=True,failure=failed)

    def edit_annotation(self,page,annotation):
        self.select_annotation(annotation)
        self.show_annotation_properties('select_annot',[annotation])
        if self.annotation_text_input:self.annotation_text_input.setFocus()

    def copy_objects(self):
        from .object_clipboard import copy_pdf
        from PySide6.QtCore import QMimeData
        chosen=self.selected_objects();page=self.canvas.object_page
        if not chosen:return
        if any(o.start==o.end for o in chosen):
            if len(chosen)==1 and chosen[0].kind=='image':self.copy_image(chosen[0])
            return
        def work(job):
            data=copy_pdf(self.document,page,chosen);png=None
            if len(chosen)==1 and chosen[0].kind=='image':
                import pymupdf as fitz
                with fitz.open(self.document.path) as pdf:
                    obj=chosen[0];entry=pdf.extract_image(obj.xref);pix=fitz.Pixmap(pdf,obj.xref)
                    if entry.get('smask'):pix=fitz.Pixmap(pix,fitz.Pixmap(pdf,entry['smask']))
                    if pix.colorspace and pix.colorspace.n not in (1,3):pix=fitz.Pixmap(fitz.csRGB,pix)
                    png=pix.tobytes('png')
            return data,png
        def done(result):
            data,png=result;mime=QMimeData();mime.setData('application/x-asterpdf-objects',data);mime.setText('\n'.join(o.text for o in chosen if o.text))
            if png:mime.setImageData(QImage.fromData(png))
            QApplication.clipboard().setMimeData(mime)
        self.queue.submit(work,done,self.error)

    def activate_link(self,link):
        uri=str(link.get('uri') or '').strip()
        if uri:
            if uri.lower().startswith(('www.','doi.org/','dx.doi.org/')):uri='https://'+uri
            url=QUrl.fromEncoded(uri.encode('utf-8'))
            if url.scheme().lower() in ('http','https','mailto'):
                if not QDesktopServices.openUrl(url):self.error(L('无法启动默认浏览器。网址：','Could not start the default browser. URL: ')+uri)
                return True
        page=link.get('page');point=link.get('to')
        if isinstance(page,str) and page.isdigit():page=int(page)-1
        if not isinstance(page,int) or page<0:
            name=link.get('nameddest') or link.get('name')
            if name:
                import pymupdf as fitz
                with fitz.open(self.document.path) as pdf:
                    destination=pdf.resolve_names().get(name,{})
                    page=destination.get('page',-1)
                    if 0<=page<len(pdf) and destination.get('to'):point=fitz.Point(destination['to'])*pdf[page].transformation_matrix*pdf[page].rotation_matrix
        if isinstance(page,int) and 0<=page<self.info['count']:
            self.goto(page)
            if point is not None:
                try:
                    pos=self.canvas.page_rect(page,(point[0],point[1],point[0]+1,point[1]+1));self.scroll.ensureVisible(int(pos.x()),int(pos.y()),10,40)
                except (TypeError,IndexError):pass
            return True
        return False

    def reset_document(self):
        if self.busy:return
        if QMessageBox.question(self,L('还原文档','Revert document'),L('还原为最近保存的文件？正文操作可撤销；未应用的文字草稿将放弃。','Restore the last saved file? Document changes can be undone; unapplied text drafts are discarded.'),QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        if self.suspended_inline:self.restore_inline()
        self.cancel_inline();self.run(L('还原文档','Revert document'),lambda j:self.document.reset(),editing=True)

    def copy_text(self):
        focus=QApplication.focusWidget()
        if isinstance(focus,(QTextEdit,QPlainTextEdit,QLineEdit)):
            focus.copy();return
        selected=self.selected_objects()
        if selected and self.canvas.mode=='objects':self.copy_objects();return
        if len(selected)==1 and selected[0].kind=='image':
            self.copy_image(selected[0]);return
        if self.canvas.word_selection:
            words=self.canvas.word_selection[1];lines=[];previous=None
            for w in words:
                key=w[2:4]
                if key!=previous:lines.append([]);previous=key
                lines[-1].append(w[1])
            QApplication.clipboard().setText('\n'.join(''.join(line) for line in lines))

    def add_text(self,page,rect):
        import pikepdf as pp
        import pymupdf as fitz
        x,y,x1,y1=rect;size=self.object_size.value();auto=abs(x1-x)<5;rect=(x,y,max(x1,x+2),max(y1,y+size*1.3))
        with pp.open(self.document.path) as pdf:offset=len(objects.content_bytes(pdf.pages[page]))
        with fitz.open(self.document.path) as pdf:origin=tuple(fitz.Point(x,y+size)*pdf[page].derotation_matrix);rotation_matrix=tuple(pdf[page].rotation_matrix)
        obj=objects.PdfObject(-1,'text',offset,offset,(1,0,0,1,0,0),rect,size=size,
            details={'family':self.object_font.currentText(),'origin':origin,'color':0,'new':True,'page_rotation_matrix':rotation_matrix,'box':{'rect':[x,y,rect[2]-x,rect[3]-y],'angle':0,'auto':auto}})
        self.canvas.object_page=page;self.set_mode('objects');self.start_inline(obj)
        self.inline_editor.setCurrentCharFormat(self.format_for(obj.details['family'],size,(0,0,0)))

    def place_image(self,page,rect,keep_override=None):
        filename=getattr(self,'pending_image',None)
        if not filename:return
        vector=Path(filename).suffix.lower()=='.pdf';source_page=self.figure_page.value()-1 if hasattr(self,'figure_page') else 0;keep=self.keep_image_ratio.isChecked() if keep_override is None else keep_override
        def work(job):
            from .figures import insert_pdf
            x,y,x1,y1=rect;bounds=rect
            if vector:
                import pymupdf as fitz
                with fitz.open(filename) as pdf:
                    if not 0<=source_page<len(pdf):raise ValueError(L('PDF 页码超出范围','PDF page is out of range'))
                    size=pdf[source_page].rect;ratio=size.height/size.width
            else:
                image=QImage(filename)
                if image.isNull():raise ValueError(L('无法读取图片','Cannot read image'))
                ratio=image.height()/max(1,image.width())
            if x1-x<3 or y1-y<3:
                width=min(240,self.info['sizes'][page][0]-x);bounds=(x,y,x+width,y+width*ratio)
            if vector:insert_pdf(self.document,page,bounds,filename,source_page,keep)
            else:self.document.insert_image(page,bounds,filename,keep)
        def done(_):self.set_mode('objects');self.canvas.setToolTip('')
        self.run(tr('add_image'),work,done,editing=True,local_edit=True)

    def copy_image(self,obj):
        import pymupdf as fitz
        from PySide6.QtCore import QMimeData
        def work(job):
            with fitz.open(self.document.path) as pdf:
                entry=pdf.extract_image(obj.xref);data=entry['image'];pix=fitz.Pixmap(pdf,obj.xref)
                if entry.get('smask'):
                    mask=fitz.Pixmap(pdf,entry['smask'])
                    if pix.alpha:pix=fitz.Pixmap(pix,0)
                    pix=fitz.Pixmap(pix,mask)
                if pix.colorspace and pix.colorspace.n not in (1,3):pix=fitz.Pixmap(fitz.csRGB,pix)
                png=pix.tobytes('png');return png if entry.get('smask') else data,png
        def done(result):
            original,png=result;mime=QMimeData();mime.setImageData(QImage.fromData(png));mime.setData('application/x-asterpdf-image',original)
            mime.setData('application/x-asterpdf-image-placement',json.dumps(list(obj.bbox)).encode())
            QApplication.clipboard().setMimeData(mime)
        self.queue.submit(work,done,self.error)

    def paste(self,from_tool=False):
        if self.busy:return
        focus=QApplication.focusWidget()
        if not from_tool and isinstance(focus,(QTextEdit,QPlainTextEdit,QLineEdit)):focus.paste();return
        mime=QApplication.clipboard().mimeData()
        if mime.hasFormat('application/x-asterpdf-objects'):
            from .object_clipboard import paste_pdf
            data=bytes(mime.data('application/x-asterpdf-objects'));page=self.canvas.page
            self.run(tr('objects'),lambda j:paste_pdf(self.document,page,data),editing=True,local_edit=True);return
        if not mime.hasImage():return
        filename=self.document.folder/'clipboard-image.png'
        original=bytes(mime.data('application/x-asterpdf-image'))
        if original and not QImage.fromData(original).isNull():filename.write_bytes(original)
        else:QImage(QApplication.clipboard().image()).save(str(filename))
        self.pending_image=str(filename)
        if self.active_panel!='objects':self.open_panel('objects')
        self.set_mode('add_image')
        placement=(48,48,48,48)
        if mime.hasFormat('application/x-asterpdf-image-placement'):
            try:
                import math
                rect=json.loads(bytes(mime.data('application/x-asterpdf-image-placement')))
                if len(rect)==4 and all(isinstance(v,(float,int)) and math.isfinite(v) for v in rect) and rect[2]>rect[0] and rect[3]>rect[1]:placement=tuple(rect)
            except (ValueError,TypeError):pass
        self.place_image(self.canvas.page,placement,False if placement!=(48,48,48,48) else None)

    def inspect_objects(self):
        if self.closed or self.busy or not self.editing_objects or self.edit_tool=='colors' or getattr(self.window,'_close_pending',False) or getattr(self.window,'_closing_all',False):return
        page=self.canvas.page;self.scan_target=page;key=(self.document.revision,page)
        selected=self.canvas.selected[:] if self.canvas.object_page==page else []
        def done(result):
            if self.canvas.page!=page:return
            self.object_cache[key]=result;self.canvas.objects=result;self.canvas.object_page=page
            self.canvas.selected=[i for i in selected if any(o.id==i for o in result)]
            if getattr(self,'pending_shape_selection',False):
                self.pending_shape_selection=False
                vectors=[o for o in result if o.kind=='vector']
                self.canvas.selected=[max(vectors,key=lambda o:o.start).id] if vectors else []
            self.canvas.update()
        if key in self.object_cache:done(self.object_cache[key]);return
        self.run(tr('scan_objects'),lambda j:objects.discover(self.document,page,j.signals.progress.emit,lambda:j.cancelled),done,cancellable=True)

    def resize_objects(self,dx,dy,free=False):
        selected=self.selected_objects();page=self.canvas.object_page
        if not selected:return
        box=qrect(selected[0].bbox)
        for obj in selected[1:]:box=box.united(qrect(obj.bbox))
        sx=max(.05,(box.width()+dx)/max(1,box.width()));sy=max(.05,(box.height()+dy)/max(1,box.height()))
        if any(o.kind=='image' for o in selected) and self.keep_image_ratio.isChecked()!=free:sy=sx
        self.run(tr('objects'),lambda j:objects.transform(self.document,page,selected,sx=sx,sy=sy,all_objects=self.canvas.objects),editing=True,fast_objects=True)

    def toggle_annotations(self,visible):
        if not hasattr(self,'canvas'):return
        self.canvas.region=None;self.canvas.pending_annotation=None;self.canvas.invalidate(False);self.canvas.fallback.clear();self.canvas.update()

    def load_annotations(self,*_):
        self.annotation_request=getattr(self,'annotation_request',0)+1;request=self.annotation_request
        revision=self.document.revision
        current=self.annotation_list.currentItem();selected_id=current.data(Qt.UserRole).get('id') if current else None
        def done(items):
            if self.closed or revision!=self.document.revision or request!=self.annotation_request:return
            items=sorted(items,key=(lambda a:(a.get('created') or a.get('modified') or '',a['page'],a['rect'][1])) if self.annotation_sort.currentData()=='time' else (lambda a:(a['page'],a['rect'][1],a['rect'][0])))
            self.annotations_data=items;self.annotation_list.blockSignals(True);self.annotation_list.clear();self.annotation_text.clear();self.annotation_text.hide()
            for ann in items:
                kind={'Text':'note','FreeText':'freetext','StrikeOut':'strikeout','Square':'rectangle','Circle':'ellipse','ReplaceText':'replace_text'}.get(ann['type'],ann['type'].lower())
                if ann['type']=='Line' and ann.get('line_end') in (4,5,7,8):kind='arrow'
                stamp=ann.get('created') or ann.get('modified') or ''
                if stamp.startswith('D:') and len(stamp)>=16:stamp=f'{stamp[2:6]}-{stamp[6:8]}-{stamp[8:10]} {stamp[10:12]}:{stamp[12:14]}:{stamp[14:16]}'
                item=QListWidgetItem(f"{ann['page']+1} · {tr(kind)} · {ann['author']}\n{stamp or L('时间未记录','Time not recorded')}\n{ann['text'] or '—'}")
                item.setData(Qt.UserRole,ann);self.annotation_list.addItem(item)
                if selected_id and ann.get('id')==selected_id:
                    self.annotation_list.setCurrentItem(item);self.annotation_text.setPlainText(ann['text']);self.annotation_text.setVisible(bool(ann['text']))
                    if self.active_panel=='annotate' and ann['page']==self.canvas.page and self.show_annotations.isChecked():self.canvas.region=(ann['page'],ann['rect'])
            self.annotation_list.blockSignals(False);self.canvas.update()
            selected=self.annotation_list.currentItem()
            if selected and self.active_panel=='annotate' and selected.data(Qt.UserRole)['page']==self.canvas.page:self.annotation_selected(selected,navigate=False)
        self.queue.submit(lambda j:self.document.annotations(),done,self.error)

    def annotation_selected(self,item,previous=None,navigate=True):
        self.annotation_style_timer.stop()
        if not item:self.annotation_text.hide();return
        ann=item.data(Qt.UserRole);self.annotation_text.setPlainText(ann['text']);self.annotation_text.setVisible(bool(ann['text']))
        if navigate and ann['page']!=self.canvas.page:self.goto(ann['page'])
        self.canvas.region=(ann['page'],ann['rect']) if self.show_annotations.isChecked() else None;self.canvas.update()
        self._sync_annotation=True
        if ann.get('color'):self.annot_color=QColor.fromRgbF(*ann['color']);self.color_action.setIcon(self.color_icon())
        self.annot_width_widget.setMinimum(0 if ann['type']=='FreeText' else .2)
        self.annot_width_widget.setValue(max(0,ann.get('width',2)));self.annot_opacity_widget.setValue(max(.05,ann.get('opacity',1))*100)
        self.annot_head_size=ann.get('head_size',10);self.annot_end=ann.get('line_end') or self.annot_end;self.annot_dashed=ann.get('dashed',False)
        if ann['type']=='FreeText':self.annot_text_border=ann.get('width',0)
        self._sync_annotation=False
        if self.active_panel=='annotate':self.show_annotation_properties('select_annot',[it.data(Qt.UserRole) for it in self.annotation_list.selectedItems()] or [ann])

    def select_annotation(self,ann,additive=False):
        if self.active_panel=='annotate' and self.canvas.mode!='select_annot':self.set_mode('select_annot')
        for i in range(self.annotation_list.count()):
            item=self.annotation_list.item(i)
            if item.data(Qt.UserRole)['xref']==ann['xref']:
                if additive:
                    item.setSelected(not item.isSelected())
                    chosen=[it.data(Qt.UserRole) for it in self.annotation_list.selectedItems()]
                    self.show_annotation_properties('select_annot',chosen or None);self.canvas.update()
                else:self.annotation_list.setCurrentItem(item)
                self.annotation_list.scrollToItem(item);break
        self.sidebar.show();self.sidebar.setCurrentWidget(self.annotation_sidebar)

    def annotation_value(self,name,value):
        item=self.annotation_list.currentItem()
        is_text=(item and item.data(Qt.UserRole)['type']=='FreeText') or (not item and self.canvas.mode=='freetext')
        if name=='annot_width' and is_text:self.annot_text_border=value
        else:setattr(self,name,value)
        if not self._sync_annotation:
            from .preferences import remember_annotation
            remember_annotation(self);self.annotation_style_timer.start(200)

    def apply_annotation_style(self,text_style=False):
        if self._sync_annotation or self.busy:return
        item=self.annotation_list.currentItem()
        if not item:return
        ann=item.data(Qt.UserRole)
        if not ann['own']:return
        page=ann['page'];values=dict(color=self.annot_color.getRgbF()[:3],width=self.annot_text_border if ann['type']=='FreeText' else self.annot_width,opacity=self.annot_opacity,line_end=self.annot_end,head_size=self.annot_head_size,dashed=self.annot_dashed)
        if ann['type']=='FreeText':values.update(border_color=self.annot_border_color.getRgbF()[:3])
        if ann['type']=='FreeText' and text_style:values.update(fontsize=self.annot_size,fontname=self.annot_font)
        self.run(tr('annotate'),lambda j:self.document.change_annotation(page,ann['xref'],**values),editing=True,local_edit=True)

    def edit_selected_annotation(self):
        item=self.annotation_list.currentItem()
        if item:self.edit_annotation(item.data(Qt.UserRole)['page'],item.data(Qt.UserRole))

    def delete_annotation(self):
        chosen=[it.data(Qt.UserRole) for it in self.annotation_list.selectedItems()]
        if not chosen or self.busy:return
        self.annotation_list.setCurrentItem(None);self.annotation_list.clearSelection();self.canvas.region=None
        self.run(tr('annotate'),lambda j:self.document.delete_annotations(chosen),editing=True)

    def object_list_selected(self):
        self.canvas.selected=[item.data(Qt.UserRole) for item in self.object_list.selectedItems()];self.canvas.update()

    def canvas_objects_selected(self,ids):
        if self.canvas.mode=='images':
            self.image_list.blockSignals(True)
            for i in range(self.image_list.count()):
                item=self.image_list.item(i);item.setSelected(item.data(Qt.UserRole)[1] in ids)
                if item.isSelected():self.image_list.scrollToItem(item)
            self.image_list.blockSignals(False);self.image_extract.setEnabled(bool(ids));self.canvas.update()
            return
        self.object_list.blockSignals(True)
        for i in range(self.object_list.count()):
            item=self.object_list.item(i);item.setSelected(item.data(Qt.UserRole) in ids)
        self.object_list.blockSignals(False)

    def selected_objects(self):
        return [o for o in self.canvas.objects if o.id in self.canvas.selected]

    def move_objects(self,dx,dy):
        selected=self.selected_objects();page=self.canvas.object_page
        if selected:self.run(tr('objects'),lambda j:objects.transform(self.document,page,selected,dx,dy,all_objects=self.canvas.objects),editing=True,fast_objects=True)

    def transform_dialog(self):
        selected=self.selected_objects();page=self.canvas.object_page
        if not selected:self.error(tr('need_object'));return
        form=FormDialog(tr('transform'),self)
        form.number('dx','Δ X (pt)',0,-10000,10000,2);form.number('dy','Δ Y (pt)',0,-10000,10000,2)
        form.number('sx',L('横向缩放','Scale X'),1,.01,100,3);form.number('sy',L('纵向缩放','Scale Y'),1,.01,100,3)
        form.check('ratio',L('保持比例','Keep aspect ratio'),True)
        if form.finish().exec()==QDialog.Accepted:
            v=form.values()
            if v.pop('ratio'):v['sy']=v['sx']
            self.run(tr('objects'),lambda j:objects.transform(self.document,page,selected,**v),editing=True)

    def delete_objects(self):
        selected=self.selected_objects();page=self.canvas.object_page
        if selected:self.run(tr('delete_object'),lambda j:objects.transform(self.document,page,selected,delete=True,all_objects=self.canvas.objects),editing=True,fast_objects=True)
        else:self.error(tr('need_object'))

    def modify_object(self):
        selected=self.selected_objects();page=self.canvas.object_page
        if len(selected)!=1:self.transform_dialog();return
        obj=selected[0]
        if obj.kind=='text':
            self.start_inline(obj)
        elif obj.kind=='image':
            menu=QMenu(self);replace=menu.addAction(tr('replace_image'));extract=menu.addAction(tr('extract_image'));move=menu.addAction(tr('transform'))
            action=menu.exec(self.cursor().pos())
            if action==replace:
                filename,_=QFileDialog.getOpenFileName(self,tr('replace_image'),'',L('图片 (*.png *.jpg *.jpeg *.tif *.webp)','Images (*.png *.jpg *.jpeg *.tif *.webp)'))
                if filename:self.run(tr('replace_image'),lambda j:objects.replace_image(self.document,page,obj,filename),editing=True)
            elif action==extract:self.save_image_xref(page,obj.xref)
            elif action==move:self.transform_dialog()
        else:self.transform_dialog()

    def move_vertex(self,obj,index,point):
        page=self.canvas.object_page
        self.run(tr("vector_edit"),lambda j:objects.move_vertex(self.document,page,obj,index,point),editing=True)

    def find_fonts(self):
        from .font_library import FontDialog
        dialog=FontDialog(self)
        QTimer.singleShot(0,dialog.search)
        if dialog.exec()==QDialog.Accepted and dialog.family:
            self.object_font.setCurrentFont(QFont(dialog.family))
            self.font_notice.setText(L('输入字体：','Input font: ')+dialog.family)

    def eventFilter(self,obj,event):
        if obj is self.inline_editor and event.type()==QEvent.KeyPress:
            if event.key()==Qt.Key_Escape:self.cancel_inline();return True
            if event.key() in (Qt.Key_Return,Qt.Key_Enter) and event.modifiers()&Qt.ControlModifier:self.commit_inline();return True
        return super().eventFilter(obj,event)

    def media_scanned(self,result,invalidate=True):
        if self.closed:return
        self.animations,self.assets,self.media_warnings=result
        from .video_insert import refresh_selection
        refresh_selection(self)
        self.media_choice.clear()
        for a in self.animations:
            key=(a.page,a.key);p=self.players.get(key)
            if p:p.animation=a
            else:
                p=AnimationPlayer(self,a);self.players[key]=p;p.changed.connect(self.player_changed)
            self.media_choice.addItem(f'{a.page+1} · animate {a.key} · {len(a.frames)} frames · {a.fps:g} fps',('animation',key))
            if a.page==self.canvas.page and self.window.current() is self:p.prepare()
        for index,m in enumerate(self.assets):self.media_choice.addItem(f'{m.page+1} · {m.name}',('media',index))
        if self.media_warnings:
            self.status.setText(L(f'⚠ {len(self.media_warnings)} 条媒体兼容性提示 · ⓘ',f'⚠ {len(self.media_warnings)} media notices · ⓘ'));self.status.setToolTip('\n'.join(self.media_warnings))
            self.media_label.setText('⚠ '+str(len(self.media_warnings)));self.media_label.setToolTip('\n'.join(self.media_warnings))
        self.rebuild_media_controls()
        if invalidate:self.canvas.invalidate(False)
        else:self.canvas.update()

    def export_embedded_media(self,asset,animation=False):
        from pathlib import Path
        name=f'animation-page-{asset.page+1}-{asset.key}.zip' if animation else asset.name
        filename,_=QFileDialog.getSaveFileName(self,L('保存动画源帧（PDF 与帧率）','Save source animation frames (PDF and timing)') if animation else L('保存原始媒体','Save original media'),str(Path(self.document.original).parent/name),'ZIP (*.zip)' if animation else 'Media (*'+Path(name).suffix+')')
        if not filename:return
        def work(job):
            if animation:return media.export_animation(self.document,asset,filename)
            import shutil
            return shutil.copyfile(media.extract_media(self.document,asset),filename)
        self.run(L('提取媒体','Extract media'),work)

    def media_context_menu(self,page,point,global_pos):
        from PySide6.QtWidgets import QMenu
        animation=next((a for a in self.animations if a.page==page and (qrect(a.rect).contains(point) or any(qrect(b[0]).contains(point) for b in getattr(a,'buttons',[])))),None)
        asset=next((a for a in reversed(self.assets) if a.page==page and qrect(a.rect).contains(point)),None)
        if not animation and not asset:return False
        menu=QMenu(self)
        if animation:
            self.media_choice.setCurrentIndex(self.animations.index(animation))
            menu.addAction(L('保存动画源帧…','Save animation source frames…'),lambda:self.export_embedded_media(animation,True))
        else:
            self.media_choice.setCurrentIndex(len(self.animations)+self.assets.index(asset))
            menu.addAction(L('保存原始媒体…','Save original media…'),lambda:self.export_embedded_media(asset))
        menu.addAction(L('多媒体控件','Playback controls'),self.show_playback_controls)
        if asset:
            menu.addSeparator();menu.addAction(L('置于顶层','Bring to front'),lambda:self.stack_media(asset,True));menu.addAction(L('置于底层','Send to back'),lambda:self.stack_media(asset,False))
        menu.exec(global_pos);return True

    def select_media(self,asset):
        self.selected_media=asset;self.canvas.selected=[]
        if self.canvas.page!=asset.page:self.goto(asset.page)
        from .video_insert import refresh_selection
        refresh_selection(self,False)

    def stack_media(self,asset,front=True):
        if asset is None or self.busy:return
        self.select_media(asset)
        from .video_insert import set_stacking
        def done(token):
            asset.annotation_name=token;self.selected_media=asset
        self.run(L('调整媒体图层','Arrange media'),lambda j:set_stacking(self.document,asset,front),done,editing=True,local_edit=True)

    def show_playback_controls(self):
        from .playback_controls import PlaybackControls
        if not hasattr(self,'playback_panel'):self.playback_panel=PlaybackControls(self)
        self.playback_panel.present()

    def rebuild_media_controls(self):
        for bar in getattr(self,'media_controls',[]):bar.deleteLater()
        self.media_controls=[]
        for a in self.animations:
            if a.buttons:continue
            player=self.players[(a.page,a.key)]
            bar=QToolBar(self.canvas);bar.animation=a
            bar.play_action=bar.addAction(icon('media_pause' if player.playing else 'media_play',self.dark),L('播放 / 暂停','Play / pause'),player.toggle);bar.addAction(icon('replay',self.dark),L('重播','Replay'),lambda checked=False,p=player:(p.stop(),p.show_frame(0),p.start()))
            loop=QCheckBox(tr('loop'));loop.setChecked(player.loop);loop.toggled.connect(lambda b,p=player:setattr(p,'loop',b));bar.addWidget(loop)
            bar.adjustSize();self.media_controls.append(bar)
        self.position_video()

    def chosen_player(self):
        data=self.media_choice.currentData()
        return self.players.get(tuple(data[1])) if data and data[0]=='animation' else None

    def play_selected(self):
        data=self.media_choice.currentData()
        if not data:self.error(tr('no_media')+'\n'+'\n'.join(self.media_warnings));return
        if data[0]=='animation':
            p=self.chosen_player();self.goto(p.animation.page);p.toggle()
        else:self.open_media(self.assets[data[1]])

    def replay(self):
        p=self.chosen_player()
        if p:p.stop();p.show_frame(0);p.start()
        elif hasattr(self,'playback_panel'):
            v=self.playback_panel.video()
            if v:v.want_playing=True;v.player.setPosition(0);v.player.play()

    def step(self,direction):
        p=self.chosen_player()
        if p:p.stop();p.show_frame(p.index+direction)

    def seek_frame(self,n):
        p=self.chosen_player()
        if p:p.stop();p.show_frame(n-1)

    def player_changed(self):
        p=self.chosen_player()
        if p:
            self.frame_slider.blockSignals(True);self.frame_slider.setMaximum(len(p.animation.frames));self.frame_slider.setValue(p.index+1);self.frame_slider.blockSignals(False)
            self.media_label.setText(f'{p.index+1}/{len(p.animation.frames)} · {p.animation.fps*p.speed:g} fps'+(' · '+L('播放中','Playing') if p.playing else ' · '+L('已暂停','Paused')))

        for bar in getattr(self,'media_controls',[]):
            player=self.players.get((bar.animation.page,bar.animation.key))
            if player:bar.play_action.setIcon(icon('media_pause' if player.playing else 'media_play',self.dark))
        if hasattr(self,'playback_panel'):self.playback_panel.sync()

    def media_clicked(self,page,point):
        for i,a in enumerate(self.animations):
            if a.page!=page:continue
            p=self.players[(a.page,a.key)]
            command=media.control_at(a,point)
            if command:self.media_choice.setCurrentIndex(i);p.command(command);return
            if qrect(a.rect).contains(point):self.media_choice.setCurrentIndex(i);p.toggle();return
        for asset in reversed(self.assets):
            if asset.page==page and qrect(asset.rect).contains(point):self.open_media(asset);return

    def open_media(self,asset):
        self.goto(asset.page)
        for player in self.video_players:
            if player.asset==asset:player.show();player.toggle();return
        def ready(filename):
            player=VideoPlayer(self,asset,filename);self.video_players.append(player);self.position_video()
        self.queue.submit(lambda j:media.extract_media(self.document,asset),ready,self.error)

    def position_video(self):
        if not hasattr(self,'canvas'):return
        for bar in getattr(self,'media_controls',[]):
            a=bar.animation
            if a.page<len(self.canvas.rects) and not self.canvas.rects[a.page].isEmpty():
                r=self.canvas.page_rect(a.page,a.rect);bar.move(int(r.left()),int(r.bottom()));bar.show()
            else:bar.hide()
        for player in sorted(self.video_players,key=lambda p:next((n for n,a in enumerate(self.assets) if a==p.asset),-1)):
            page=player.asset.page
            if page<len(self.canvas.rects) and not self.canvas.rects[page].isEmpty():
                r=self.canvas.page_rect(page,player.asset.rect);r.setHeight(max(70,r.height()+42))
                player.setGeometry(r.toRect())
                from PySide6.QtGui import QRegion
                mask=QRegion(player.rect());order=self.assets.index(player.asset) if player.asset in self.assets else len(self.assets)
                for above in self.assets[order+1:]:
                    if above.page==page:
                        cover=self.canvas.page_rect(page,above.rect).toAlignedRect().translated(-player.pos());mask-=QRegion(cover)
                player.setMask(mask if not mask.isEmpty() else QRegion(-2,-2,1,1))
                player.raise_()
            else:player.want_playing=False;player.player.pause();player.hide()

    def pause_media(self):
        for p in self.players.values():p.stop()
        for p in self.video_players:p.want_playing=False;p.player.pause()

    def release_memory(self):
        self.pause_media();self.canvas.release_cache();self.minimap.release()
        for player in self.players.values():player.release()
        for player in self.video_players:player.shutdown();player.deleteLater()
        self.video_players=[];self.object_cache.clear();self.image_cache.clear();self.canvas.words.clear()
        self.queue.submit(lambda j:self.document.release_rendering(),priority=-3)
