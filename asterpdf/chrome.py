"""Compact, user-configurable desktop chrome."""
from PySide6.QtCore import Qt,QEvent,QObject,QTimer
from PySide6.QtGui import QColor,QAction,QPainter,QPixmap
from PySide6.QtWidgets import (QApplication,QWidget,QLabel,QAbstractButton,QLineEdit,QComboBox,
    QTabWidget,QMenu,QDialog,QGraphicsOpacityEffect,QFontComboBox,QListWidget,QListWidgetItem,QAbstractItemView,QVBoxLayout)
from . import i18n
from .i18n import tr,L
from .dialogs import FormDialog
from .ui_icons import icon

SHORT={
 'reset_document':('还原','Revert'),'flip_h':('水平','Flip H'),'flip_v':('垂直','Flip V'),
 'annotate':('批注','Notes'),'objects':('编辑','Edit'),'pages':('页面','Pages'),'extract':('提取','Export'),
 'text_ops':('文字','Text'),'vector_edit':('图形','Shape'),'colors':('换色','Color'),
 'add_text':('文字','Text'),'add_image':('图片','Image'),'apply':('应用','Apply'),'cancel':('取消','Cancel'),
 'select_annot':('选择','Select'),'highlight':('高亮','Highlight'),'underline':('下划','Underline'),
 'strikeout':('删除线','Strike'),'note':('便笺','Note'),'freetext':('文本','Text'),'ink':('画笔','Pen'),
 'line':('线条','Line'),'arrow':('箭头','Arrow'),'rectangle':('矩形','Rect'),'ellipse':('椭圆','Oval'),
 'rotate':('旋转','Rotate'),'delete_pages':('删除','Delete'),'blank':('空白','Blank'),'merge':('合并','Merge'),
 'extract_pages':('提页','Extract'),'crop':('裁剪','Crop'),'organize':('组织','Arrange'),
 'region':('框选','Region'),'export_pages':('页面','Pages'),'export_region':('区域','Region'),
 'copy_region':('复制','Copy'),'vector_pdf':('矢量','Vector'),'images':('原图','Images'),'export_settings':('设置','Settings'),
 'page_fit':('整页','Fit'),'width_fit':('宽度','Width'),'save':('保存','Save'),'print':('打印','Print'),'file_info':('信息','Info')}
ALIASES={'reset_document':'undo','add_text':'text_ops','apply':'check','cancel':'close','organize':'pages','export_settings':'tool',
 'delete_pages':'delete','crop':'region','images':'add_image','export_pages':'extract','export_region':'extract',
 'copy_region':'extract','extract_pages':'pages','vector_pdf':'vector_edit','highlight':'annotate','ink':'annotate',
 'underline':'text_ops','strikeout':'text_ops','note':'annotate','select_annot':'select','freetext':'text_ops','bookmark':'star','replay':'undo'}


class OffsetPanel(QWidget):
    """Keep side-panel controls clear of a toolbar overlay above the PDF."""
    def __init__(self,child):
        super().__init__();self.child=child
        self.setMinimumWidth(child.minimumWidth());self.setMaximumWidth(child.maximumWidth())
        layout=QVBoxLayout(self);layout.setSpacing(0);layout.setContentsMargins(0,0,0,0);layout.addWidget(child);child.installEventFilter(self)

    def eventFilter(self,obj,event):
        if obj is self.child and event.type() in (QEvent.ShowToParent,QEvent.HideToParent):
            visible=not self.child.isHidden()
            if self.isHidden()==visible:self.setVisible(visible)
        return super().eventFilter(obj,event)


class ToolbarDrag(QObject):
    """Drag the visible button with a translucent preview and insertion marker."""
    def __init__(self,tab):
        super().__init__(tab);self.tab=tab;self.press=None;self.dragging=False;self.ghost=None;self.marker=None;self.before=None
    def group(self,action):
        if action in self.tab.module_actions.values():return 'modules'
        if action in [self.tab.quick_actions[k] for k in ('select','hand')]:return 'pointer'
        if action in self.tab.quick_actions.values():return 'tools'
        return None
    def cleanup(self):
        for w in (self.ghost,self.marker):
            if w:w.hide();w.deleteLater()
        self.ghost=self.marker=None;self.press=None;self.dragging=False;self.before=None
    def eventFilter(self,button,event):
        if event.type()==QEvent.MouseButtonPress and event.button()==Qt.LeftButton:
            self.cleanup();self.press=(button,event.globalPosition(),button.defaultAction())
        elif event.type()==QEvent.MouseMove and self.press and event.buttons()&Qt.LeftButton:
            if not self.dragging and (event.globalPosition()-self.press[1]).manhattanLength()<QApplication.startDragDistance():return False
            if not self.dragging:
                self.dragging=True;button.setDown(False)
                pix=button.grab();transparent=QPixmap(pix.size());transparent.fill(Qt.transparent)
                paint=QPainter(transparent);paint.setOpacity(.65);paint.drawPixmap(0,0,pix);paint.end();transparent.setDevicePixelRatio(pix.devicePixelRatio())
                self.ghost=QLabel(self.tab.window);self.ghost.setPixmap(transparent);self.ghost.adjustSize();self.ghost.setAttribute(Qt.WA_TransparentForMouseEvents);self.ghost.show()
                self.marker=QWidget(self.tab.navbar);self.marker.setStyleSheet('background:#6358c9');self.marker.setAttribute(Qt.WA_TransparentForMouseEvents)
            strip=self.tab.navbar_host;local=strip.scroller.viewport().mapFromGlobal(event.globalPosition().toPoint());bar=strip.scroller.horizontalScrollBar()
            if local.x()<16:bar.setValue(bar.value()-12)
            elif local.x()>strip.scroller.viewport().width()-16:bar.setValue(bar.value()+12)
            point=self.tab.navbar.mapFromGlobal(event.globalPosition().toPoint());source=self.press[2];group=self.group(source)
            candidates=[a for a in self.tab.navbar.actions() if self.group(a)==group and a.isVisible()]
            self.before=next((a for a in candidates if point.x()<self.tab.navbar.actionGeometry(a).center().x()),None)
            bounds=self.tab.navbar.actionGeometry(self.before or candidates[-1]);x=bounds.left() if self.before else bounds.right()+2
            self.marker.setGeometry(x-1,3,2,self.tab.navbar.height()-6);self.marker.show();self.marker.raise_()
            self.ghost.move(self.tab.window.mapFromGlobal(event.globalPosition().toPoint())-self.ghost.rect().center());self.ghost.raise_();return True
        elif event.type()==QEvent.MouseButtonRelease and self.press:
            source=self.press[2];before=self.before;moved=self.dragging;group=self.group(source)
            if moved:
                button.setDown(False)
                actions=self.tab.navbar.actions();members=[a for a in actions if self.group(a)==group];members.remove(source)
                at=members.index(before) if before in members else len(members)
                if before is source:at=sum(self.group(a)==group and a is not source for a in actions[:actions.index(source)])
                members.insert(at,source);iterator=iter(members);desired=[next(iterator) if self.group(a)==group else a for a in actions]
                # Explicitly remove first: insertAction with an action already in
                # the toolbar is platform-dependent when moving backwards.
                for a in actions:
                    if self.group(a)==group:self.tab.navbar.removeAction(a)
                for i in reversed(range(len(desired))):
                    a=desired[i]
                    if self.group(a)==group:self.tab.navbar.insertAction(desired[i+1] if i+1<len(desired) else None,a)
                keys={a:k for k,a in {**self.tab.module_actions,**self.tab.quick_actions}.items()}
                order=[keys[a] for a in desired if a in keys];self.tab.window.settings.setValue('toolbar/order',order)
                self.tab.connect_drag_buttons()
                for tab in self.tab.window.document_tabs():
                    if tab is not self.tab:tab.order_toolbar(order)
            self.cleanup();return moved
        elif event.type()==QEvent.KeyPress and event.key()==Qt.Key_Escape and self.press:self.cleanup();return True
        elif event.type()==QEvent.Hide and self.press:self.cleanup()
        return False


def decorate(action,key,dark=False):
    action.setProperty('aster_key',key)
    action.setText('' if key=='bookmark' else L(*SHORT[key]) if key in SHORT else tr(key))
    action.setToolTip(L('还原文档','Revert document') if key=='reset_document' else L('水平翻转','Flip horizontally') if key=='flip_h' else L('垂直翻转','Flip vertically') if key=='flip_v' else tr(key));action.setIcon(icon(ALIASES.get(key,key),dark))
    return action


def translate_tree(root):
    for obj in [root]+root.findChildren(QWidget)+root.findChildren(QAction):
        if isinstance(obj,(QLabel,QAbstractButton,QAction)):
            obj.setText(i18n.translated(obj.text()))
        if isinstance(obj,QLineEdit):obj.setPlaceholderText(i18n.translated(obj.placeholderText()))
        if isinstance(obj,QComboBox) and not isinstance(obj,QFontComboBox) and not obj.property('font_selector'):
            previous=obj.blockSignals(True)
            for index in range(obj.count()):obj.setItemText(index,i18n.translated(obj.itemText(index)))
            obj.blockSignals(previous)
        if isinstance(obj,QTabWidget):
            for index in range(obj.count()):obj.setTabText(index,i18n.translated(obj.tabText(index)))
        if isinstance(obj,QWidget):obj.setToolTip(i18n.translated(obj.toolTip()))
        if isinstance(obj,QAction) and obj.property('aster_key'):decorate(obj,obj.property('aster_key'),getattr(root,'dark',False))


class ChromeMixin:
    def configure_chrome(self):
        defaults=['annotate','objects','pages','extract','undo','redo','save','width_fit','page_fit','bookmark','continuous','minimap']
        visible=self.window.settings.value('toolbar/tools',defaults,type=list)
        for key,action in self.quick_actions.items():
            if key not in ('select','hand'):action.setVisible(key in visible)
        for key,action in self.module_actions.items():action.setVisible(key in visible)
        self.order_toolbar(self.window.settings.value('toolbar/order',[],type=list))
        if not getattr(self,"_chrome_configured",False):self.connect_chrome_menus()
        self.apply_chrome_opacity();self.apply_chrome_visibility()

    def connect_chrome_menus(self):
        self._chrome_configured=True
        self.toolbar_drag=ToolbarDrag(self);self.connect_drag_buttons()
        self.navbar.setContextMenuPolicy(Qt.CustomContextMenu);self.navbar.customContextMenuRequested.connect(self.toolbar_menu)
        for index in range(self.tool_panels.count()):
            bar=self.tool_panels.widget(index);bar.setContextMenuPolicy(Qt.CustomContextMenu)
            bar.customContextMenuRequested.connect(lambda pos,b=bar:self.toolbar_menu(pos,b))
        self.apply_chrome_opacity()
        self.apply_chrome_visibility()

    def apply_chrome_opacity(self):
        value=self.window.settings.value('toolbar/opacity',100,type=int)/100
        overlay=value<.999
        if getattr(self,'chrome_overlay',False)!=overlay:
            self.chrome_overlay=overlay;layout=self.layout()
            for widget in (self.navbar_host,self.tool_panels):layout.removeWidget(widget)
            if not overlay:layout.insertWidget(0,self.navbar_host);layout.insertWidget(1,self.tool_panels)
        self.position_chrome()
        # Paint translucent backgrounds directly. Graphics effects cache the whole
        # strip and can leave stale pixels after Qt relayouts on mixed-DPI screens.
        for widget in (self.navbar_host,self.tool_panels):widget.setGraphicsEffect(None)
        self.navbar_host.setObjectName('asterstrip');self.navbar_host.setAttribute(Qt.WA_StyledBackground,True);self.navbar_host.setAutoFillBackground(False)
        base='#1a2636' if self.window.dark else '#ffffff';color=QColor(base);alpha=round(value*255)
        self.navbar_host.setStyleSheet(f'QWidget#asterstrip {{background:rgba({color.red()},{color.green()},{color.blue()},{alpha});}} QScrollArea {{background:transparent;border:0;}}')
        self.navbar_host.scroller.viewport().setAutoFillBackground(False);self.navbar_host.scroller.setAutoFillBackground(False)
        self.style_modules();self.navbar_host.update();self.tool_panels.update();self.update()

    def apply_chrome_visibility(self,auto_hidden=False):
        visible=not self.window.settings.value('toolbar/hidden',False,type=bool) and not auto_hidden and not self.window.presentation
        self.navbar_host.setVisible(visible);self.navbar.setVisible(visible)
        self.tool_panels.setVisible(visible and getattr(self,'active_panel','read')!='read')
        self.position_chrome()

    def position_chrome(self):
        y=0
        if getattr(self,'chrome_overlay',False):
            for widget in (self.navbar_host,self.tool_panels):
                if not widget.isHidden():
                    height=widget.sizeHint().height();widget.setGeometry(0,y,self.width(),height);y+=height;widget.raise_()
        for name in ('sidebar_container','text_container','property_container'):
            panel=getattr(self,name,None)
            if panel:panel.layout().setContentsMargins(0,y,0,0)
        if hasattr(self,'organizer'):self.organizer_inset=y;self.update_organizer_inset()
        if getattr(self,'reading_inset',0)!=y:
            self.reading_inset=y
            if hasattr(self,'canvas'):QTimer.singleShot(0,self.canvas.layout_pages)

    def update_organizer_inset(self,*_):
        if getattr(self,'_organizer_layout',False):return
        self._organizer_layout=True
        value=self.organizer.verticalScrollBar().value();inset=max(0,getattr(self,'organizer_inset',0)-value)
        self.organizer.setViewportMargins(0,inset,0,0)
        self._organizer_layout=False

    def toolbar_menu(self,pos,bar=None):
        menu=QMenu(self);menu.addAction(L('自定义工具栏…','Customize toolbar…'),self.customize_toolbar)
        for label,key in [(L('隐藏工具栏','Hide toolbar'),'hidden'),(L('自动隐藏工具栏','Auto-hide toolbar'),'autohide')]:
            action=menu.addAction(label);action.setCheckable(True);action.setChecked(self.window.settings.value('toolbar/'+key,False,type=bool))
            action.toggled.connect(lambda value,k=key:self.set_chrome_option(k,value))
        menu.addAction(L('工具栏透明度…','Toolbar opacity…'),self.toolbar_opacity)
        menu.exec((bar or self.navbar).mapToGlobal(pos))

    def set_chrome_option(self,key,value):
        self.window.settings.setValue('toolbar/'+key,value)
        for tab in self.window.document_tabs():tab.apply_chrome_visibility();tab.apply_chrome_opacity()

    def toolbar_opacity(self):
        form=FormDialog(L('工具栏透明度','Toolbar opacity'),self)
        form.number('opacity',L('不透明度（%）','Opacity (%)'),self.window.settings.value('toolbar/opacity',100,type=int),35,100)
        if form.finish().exec()==QDialog.Accepted:self.set_chrome_option('opacity',form.values()['opacity'])

    def customize_toolbar(self):
        form=FormDialog(L('自定义工具栏与功能区','Customize toolbar and modules'),self)
        form.note(L('勾选显示工具；直接拖动主工具栏上的图标调整顺序。指针、手形、页码和缩放始终保留。','Check tools to show them; drag icons directly on the main toolbar to reorder. Pointer, hand, page number and zoom remain available.'))
        listing=QListWidget();listing.setMinimumHeight(330)
        actions={a:k for k,a in {**self.module_actions,**self.quick_actions}.items() if k not in ('select','hand')}
        for action in self.navbar.actions():
            if action not in actions:continue
            key=actions[action];item=QListWidgetItem(action.icon(),tr(key));item.setData(Qt.UserRole,key);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if action.isVisible() else Qt.Unchecked);listing.addItem(item)
        form.form.addRow(listing)
        form.check('_auto',L('自动隐藏工具栏','Auto-hide toolbar'),self.window.settings.value('toolbar/autohide',False,type=bool))
        if form.finish().exec()==QDialog.Accepted:
            values=form.values();self.window.settings.setValue('toolbar/autohide',values.pop('_auto'))
            self.window.settings.setValue('toolbar/tools',[listing.item(i).data(Qt.UserRole) for i in range(listing.count()) if listing.item(i).checkState()==Qt.Checked])
            for tab in self.window.document_tabs():tab.configure_chrome()

    def connect_drag_buttons(self):
        from PySide6.QtWidgets import QToolButton
        for action in list(self.module_actions.values())+list(self.quick_actions.values()):
            button=self.navbar.widgetForAction(action)
            if isinstance(button,QToolButton):button.installEventFilter(self.toolbar_drag)

    def order_toolbar(self,keys):
        configurable={**self.module_actions,**self.quick_actions};current=self.navbar.actions()
        for group in [list(self.module_actions),['select','hand'],[k for k in self.quick_actions if k not in ('select','hand')]]:
            ordered=[configurable[k] for k in dict.fromkeys(keys+group) if k in group]
            it=iter(ordered);current=[next(it) if a in ordered else a for a in current]
        for action in current:self.navbar.addAction(action)
        if hasattr(self,'toolbar_drag'):self.connect_drag_buttons()

    def initialize_sidebar_width(self):
        if self.closed:return
        width=self.sidebar.tabBar().sizeHint().width()+10;sizes=self.splitter.sizes();index=self.splitter.indexOf(self.document_views)
        sizes[0]=width;sizes[index]=max(100,self.splitter.width()-sum(value for n,value in enumerate(sizes) if n!=index))
        self.splitter.setSizes(sizes)

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())
        if self.sidebar.isVisible():self.splitter.setSizes([self.sidebar.tabBar().sizeHint().width()+12]+[250]*(self.splitter.count()-2)+[1000])
        self.sidebar_toggle.setText('‹' if self.sidebar.isVisible() else '›')
        self.window.settings.setValue('sidebar/hidden',not self.sidebar.isVisible())

    def sidebar_menu(self,pos,source=None):
        menu=QMenu(self);menu.addAction(L('收起 / 展开导航','Collapse / expand navigation'),self.toggle_sidebar)
        action=menu.addAction(L('自动隐藏导航','Auto-hide navigation'));action.setCheckable(True);action.setChecked(self.window.settings.value('sidebar/autohide',False,type=bool))
        action.toggled.connect(lambda b:self.window.settings.setValue('sidebar/autohide',b))
        menu.exec((source or self.sidebar_toggle).mapToGlobal(pos))
