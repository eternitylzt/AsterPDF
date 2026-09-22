from __future__ import annotations
import argparse
import json
import logging
import os
from pathlib import Path
import re
import sys
import urllib.request
from PySide6.QtCore import Qt, QSettings, QStandardPaths, QTimer, QUrl, QEvent, QTranslator, QLibraryInfo
from PySide6.QtGui import QAction, QIcon, QKeySequence, QDesktopServices, QFont, QCursor, QPalette, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QInputDialog, QDialog, QHBoxLayout, QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox, QTabBar, QToolButton, QMenu, QStyle, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QHeaderView)
from . import __version__, i18n
from .i18n import tr, L
from .core import Document
from .jobs import Queue
from .tab import DocumentTab
from .dialogs import FormDialog, MergeDialog
from .chrome import translate_tree


def resource(name):
    return Path(__file__).parent / 'resources' / name


LIGHT = '''
QMainWindow,QDialog,QWidget {font-family:"Microsoft YaHei UI","Segoe UI","Noto Sans","Arial";font-size:13px;color:#243249;}
QMainWindow,QDialog {background:#f7f9fc;}
QToolBar {background:#fff;border:0;border-bottom:1px solid #e3e8ef;spacing:3px;padding:3px;}
QToolButton,QPushButton {border:1px solid transparent;border-radius:5px;padding:3px 5px;background:transparent;}
QToolButton:hover,QPushButton:hover {background:#eaf0ff;border-color:#d7e0fc;}
QToolButton:pressed,QPushButton:pressed {background:#cfddf7;border-color:#829acb;}
QPushButton {background:#eef2f8;border-color:#dce3ed;}
QToolButton:checked,QPushButton:checked {background:#dce6ff;border-color:#aebfed;}
QWidget:disabled {color:#94a0b1;}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit,QPlainTextEdit {background:#fff;border:1px solid #d9e1ec;border-radius:5px;padding:3px;}
QListWidget,QTreeWidget {background:#f7f9fc;border:0;outline:0;}
QListWidget::item:selected,QTreeWidget::item:selected {background:#dce6ff;color:#263d79;border-radius:5px;}
QTabWidget::pane {border:0;}
QTabBar::tab {background:#eef2f7;padding:5px 10px;max-width:190px;border:0;}
QTabBar::tab:selected {background:#fff;color:#4565d8;border-top:2px solid #526fe7;}
QTabBar::tab:hover {background:#e2e9f6;}
QSplitter::handle {background:#dde4ed;width:1px;}
QMenuBar,QMenu {background:#fff;color:#243249;}
QMenu::item:selected {background:#e3ebff;}
QProgressBar {border:0;background:#e4eaf2;border-radius:4px;text-align:center;}
QProgressBar::chunk {background:#647eea;}
QScrollBar:vertical {background:#edf1f7;width:12px;margin:0;border:0;}
QScrollBar:horizontal {background:#edf1f7;height:12px;margin:0;border:0;}
QScrollBar::handle {background:#8295ae;border-radius:4px;min-height:28px;min-width:28px;margin:2px;}
QScrollBar::handle:hover,QScrollBar::handle:pressed {background:#486c9c;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}
QLabel#hero {color:#243c67;font-size:44px;font-weight:600;}
QLabel#subtitle {color:#698098;font-size:16px;}
'''
DARK = '''
QMainWindow,QDialog,QWidget {font-family:"Microsoft YaHei UI","Segoe UI","Noto Sans","Arial";font-size:13px;color:#d6dfec;}
QMainWindow,QDialog {background:#141d2a;}
QToolBar {background:#1a2636;border:0;border-bottom:1px solid #2c3b51;spacing:3px;padding:3px;}
QToolButton,QPushButton {border:1px solid transparent;border-radius:5px;padding:3px 5px;background:transparent;}
QToolButton:hover,QPushButton:hover {background:#304267;border-color:#42577e;}
QToolButton:pressed,QPushButton:pressed {background:#47628c;border-color:#91aad0;}
QPushButton {background:#27364c;border-color:#3c4e67;}
QToolButton:checked,QPushButton:checked {background:#3e527a;border-color:#8299cb;}
QWidget:disabled {color:#77859c;}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit,QPlainTextEdit {background:#182334;border:1px solid #3b4b62;border-radius:5px;padding:3px;}
QListWidget,QTreeWidget {background:#192333;border:0;outline:0;}
QListWidget::item:selected,QTreeWidget::item:selected {background:#30466e;color:#edf3ff;border-radius:5px;}
QTabWidget::pane {border:0;}
QTabBar::tab {background:#172232;padding:5px 10px;max-width:190px;border:0;}
QTabBar::tab:selected {background:#253650;color:#a5b8ff;border-top:2px solid #8399ff;}
QTabBar::tab:hover {background:#2a3b55;}
QSplitter::handle {background:#314158;width:1px;}
QMenuBar,QMenu {background:#1a2636;color:#d6dfec;}
QMenu::item:selected {background:#35486e;}
QProgressBar {border:0;background:#283850;border-radius:4px;text-align:center;}
QProgressBar::chunk {background:#647eea;}
QScrollBar:vertical {background:#182333;width:12px;margin:0;border:0;}
QScrollBar:horizontal {background:#182333;height:12px;margin:0;border:0;}
QScrollBar::handle {background:#6b829f;border-radius:4px;min-height:28px;min-width:28px;margin:2px;}
QScrollBar::handle:hover,QScrollBar::handle:pressed {background:#9bb6dc;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}
QLabel#hero {color:#e0e8fc;font-size:44px;font-weight:600;}
QLabel#subtitle {color:#8da1bc;font-size:16px;}
'''


class Window(QMainWindow):
    def __init__(self, data_dir=None):
        super().__init__()
        self.settings=QSettings(str(Path(data_dir)/'settings.ini'),QSettings.IniFormat) if data_dir else QSettings('AsterPDF','AsterPDF')
        if not self.settings.value('color/palette32',False,type=bool):
            if self.settings.value('color/tolerance',2.,type=float)==2.:self.settings.setValue('color/tolerance',8.)
            self.settings.setValue('color/palette32',True)
        self.data_dir=Path(data_dir or QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        self.font_root=self.data_dir/'fonts';self.font_root.mkdir(parents=True,exist_ok=True)
        from .font_library import register_cache
        register_cache(self.font_root)
        self.recovery_root=Path(self.settings.value('recovery/folder',str(self.data_dir/'recovery')));self.recovery_root.mkdir(parents=True,exist_ok=True)
        i18n.LANGUAGE=self.settings.value('language','zh')
        self.dark=self.settings.value('dark',True,type=bool)
        self.icon=QIcon(str(resource('asterpdf.png')));self.setWindowIcon(self.icon)
        self.queue=Queue(self)
        self.opening=set();self.presentation=False;self._previous_tab=None
        self.setAcceptDrops(True);self.resize(1380,920)
        self.build();QApplication.instance().installEventFilter(self);self.apply_theme();self.setWindowTitle('✦ AsterPDF')
        self.position_timer=QTimer(self);self.position_timer.timeout.connect(self.persist_positions);self.position_timer.start(15000)
        QTimer.singleShot(500,self.offer_recovery)
        self.chrome_timer=QTimer(self);self.chrome_timer.timeout.connect(self.tick_chrome);self.chrome_timer.start(500)
        self.statusBar().hide()

    def showEvent(self,event):
        super().showEvent(event)
        if not getattr(self,'_sized_on_screen',False):
            self._sized_on_screen=True
            def size_on_screen():
                available=self.screen().availableGeometry()
                self.resize(min(1380,available.width()-30),min(920,available.height()-60))
            QTimer.singleShot(0,size_on_screen)

    def changeEvent(self,event):
        if event.type()==QEvent.WindowStateChange:
            if self.isMinimized():
                # normalGeometry survives minimize even when Windows temporarily
                # reports the primary monitor as the window's current screen.
                self._restore_rect=self.normalGeometry()
                self._restore_screen=QApplication.screenAt(self._restore_rect.center()) or self.screen()
            elif event.oldState() & Qt.WindowMinimized and hasattr(self,'_restore_rect'):
                rect=self._restore_rect;screen=self._restore_screen
                def restore_monitor():
                    if screen not in QApplication.screens() or self.isMinimized():return
                    if self.screen()!=screen:
                        self.windowHandle().setScreen(screen)
                        if not self.isMaximized():self.setGeometry(rect)
                        else:self.showNormal();self.setGeometry(rect);self.showMaximized()
                QTimer.singleShot(0,restore_monitor)
        super().changeEvent(event)

    def build(self):
        app=QApplication.instance()
        previous=getattr(app,'aster_translator',None)
        if previous:app.removeTranslator(previous)
        translator=QTranslator(app)
        if i18n.LANGUAGE=='zh':
            translator.load('qtbase_zh_CN',QLibraryInfo.path(QLibraryInfo.TranslationsPath));app.installTranslator(translator)
        app.aster_translator=translator
        self.tabs=QTabWidget();self.tabs.setTabsClosable(True);self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab);self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.setDocumentMode(True);self.tabs.tabBar().setUsesScrollButtons(True);self.tabs.tabBar().setElideMode(Qt.ElideRight);self.tabs.tabBar().setExpanding(False)
        self.setCentralWidget(self.tabs)
        self.welcome=QWidget();layout=QVBoxLayout(self.welcome);layout.addStretch()
        logo=QLabel('✦  AsterPDF');logo.setObjectName('hero');logo.setAlignment(Qt.AlignCenter);layout.addWidget(logo)
        subtitle=QLabel(L('阅读 · 编辑 · 动画 · 批注 · 提取','Read · Edit · Animate · Annotate · Extract'));subtitle.setObjectName('subtitle');subtitle.setAlignment(Qt.AlignCenter);layout.addWidget(subtitle)
        layout.addSpacing(34)
        message=QLabel(tr('empty'));message.setAlignment(Qt.AlignCenter);layout.addWidget(message)
        label=QLabel(tr('drop'));label.setObjectName('subtitle');label.setAlignment(Qt.AlignCenter);layout.addWidget(label)
        row=QHBoxLayout();row.addStretch();button=QPushButton(tr('open'));button.setFixedSize(210,42);button.clicked.connect(self.open_dialog);row.addWidget(button)
        for text,callback in [(tr('merge'),self.merge_documents),(L('合并已打开的 PDF','Merge open PDFs'),lambda:self.merge_documents(True))]:
            item=QPushButton(text);item.setFixedSize(210,42);item.clicked.connect(callback);row.addWidget(item)
        row.addStretch();layout.addLayout(row)
        layout.addSpacing(24)
        self.home_recent=QTreeWidget();self.home_recent.setColumnCount(3);self.home_recent.setRootIsDecorated(False);self.home_recent.setItemsExpandable(False)
        self.home_recent.setMaximumSize(740,225);self.home_recent.setMinimumWidth(680)
        self.home_recent.header().setStretchLastSection(False);self.home_recent.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.home_recent.header().setSectionResizeMode(1,QHeaderView.Fixed);self.home_recent.header().setSectionResizeMode(2,QHeaderView.Fixed)
        self.home_recent.setColumnWidth(1,90);self.home_recent.setColumnWidth(2,175)
        self.home_recent.setStyleSheet('QHeaderView::section {padding:4px 8px;} QTreeView::item {padding:6px;}')
        from .recent_files import RecentDelegate
        self.home_recent.setItemDelegate(RecentDelegate(self.home_recent))
        self.home_recent.itemActivated.connect(lambda item,column:self.open_file(item.data(0,Qt.UserRole)))
        self.home_recent.setContextMenuPolicy(Qt.CustomContextMenu);self.home_recent.customContextMenuRequested.connect(self.recent_context_menu)
        layout.addWidget(self.home_recent,0,Qt.AlignHCenter)
        layout.addStretch();self.home_footer=QLabel();self.home_footer.setAlignment(Qt.AlignCenter);self.home_footer.setStyleSheet('color:#71829a;padding:18px;line-height:150%;');layout.addWidget(self.home_footer);self.update_home_footer()
        home=self.tabs.addTab(self.welcome,L('首页','Home'))
        for side in (QTabBar.LeftSide,QTabBar.RightSide):self.tabs.tabBar().setTabButton(home,side,None)
        self.document_switcher=QToolButton();self.document_switcher.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown));self.document_switcher.setFixedWidth(30);self.document_switcher.setAutoFillBackground(True)
        self.document_switcher.setToolTip(L('所有文档标签','All document tabs'));self.document_switcher.setPopupMode(QToolButton.InstantPopup)
        switch_menu=QMenu(self.document_switcher);switch_menu.aboutToShow.connect(lambda:self.populate_tab_menu(switch_menu));self.document_switcher.setMenu(switch_menu);self.tabs.setCornerWidget(self.document_switcher)
        self.menuBar().clear()
        file=self.menuBar().addMenu(tr('file'));self.action(file,'open',self.open_dialog,'Ctrl+O')
        self.recent=file.addMenu(tr('recent'));self.refresh_recent()
        file.addSeparator();self.action(file,'save',lambda:self.save_tab(False),'Ctrl+S')
        self.action(file,'save_as',lambda:self.save_tab(True),'Ctrl+Shift+S');self.action(file,'close',lambda:self.close_tab(self.tabs.currentIndex()),'Ctrl+W')
        self.action(file,'file_info',self.file_information);self.action(file,'print',self.print_current,'Ctrl+P')
        edit=self.menuBar().addMenu(tr('edit'));self.action(edit,'undo',lambda:self.history(False),'Ctrl+Z')
        self.action(edit,'redo',lambda:self.history(True),'Ctrl+Shift+Z')
        edit.addSeparator()
        edit.addAction(L('还原文档…','Revert document…'),lambda:self.with_tab(lambda t:t.reset_document()))
        edit.addAction(L('恢复未保存的文档…','Recover unsaved documents…'),self.offer_recovery)
        edit.addAction(tr('colors'),lambda:self.with_tab(lambda t:t.replace_colors()))
        copy=edit.addAction(L('复制','Copy'));copy.setShortcut(QKeySequence.Copy);copy.triggered.connect(lambda:self.with_tab(lambda t:t.copy_text()))
        paste=edit.addAction(L('粘贴','Paste'));paste.setShortcut(QKeySequence.Paste);paste.triggered.connect(lambda:self.with_tab(lambda t:t.paste()))
        view=self.menuBar().addMenu(tr('view'))
        self.action(view,'minimap',lambda:self.with_tab(lambda t:t.minimap.toggle()))
        for label,columns,continuous in [(L('单页视图','Single page'),1,False),(L('启用滚动','Continuous'),1,True),(L('双页视图','Two pages'),2,False),(L('双页并排滚动','Continuous two pages'),2,True)]:
            view.addAction(label,lambda c=columns,b=continuous:self.with_tab(lambda t:t.set_view(c,b)))
        view.addAction(L('自定义工具栏…','Customize toolbar…'),self.customize_toolbar)
        for label,key in [(L('显示 / 隐藏工具栏','Show / hide toolbar'),'hidden'),(L('自动隐藏工具栏','Auto-hide toolbar'),'autohide')]:
            view.addAction(label,lambda k=key:self.with_tab(lambda t:t.set_chrome_option(k,not self.settings.value('toolbar/'+k,False,type=bool))))
        view.addAction(L('工具栏透明度…','Toolbar opacity…'),lambda:self.with_tab(lambda t:t.toolbar_opacity()))
        view.addAction(L('收起 / 展开导航栏','Collapse / expand navigation'),lambda:self.with_tab(lambda t:t.toggle_sidebar()))
        view.addAction(L('自动隐藏导航栏','Auto-hide navigation'),lambda:self.settings.setValue('sidebar/autohide',not self.settings.value('sidebar/autohide',False,type=bool)))
        edit.addSeparator()
        for key in ('annotate','objects','pages','extract'):
            action=edit.addAction(tr(key),lambda checked=False,k=key:self.with_tab(lambda t:t.set_panel(k)))
            if key=='objects':action.setShortcut('Ctrl+E')
        media_menu=self.menuBar().addMenu(tr('media'))
        for key,callback in [('play',lambda t:t.play_selected()),('replay',lambda t:t.replay()),('previous',lambda t:t.step(-1)),('next',lambda t:t.step(1)),('playback_controls',lambda t:t.show_playback_controls())]:
            media_menu.addAction(tr(key),lambda checked=False,f=callback:self.with_tab(f))
        quality_menu=media_menu.addMenu(L('动画画质','Animation quality'))
        from PySide6.QtGui import QActionGroup
        quality_group=QActionGroup(self);quality_group.setExclusive(True);self.quality_actions={}
        for label,key in [(L('自动（播放优先流畅，暂停显示原像素）','Auto (smooth playback, native pixels when paused)'),'auto'),(L('原像素','Native pixels'),'native'),(L('流畅','Smooth'),'smooth')]:
            action=quality_menu.addAction(label);action.setCheckable(True);action.setChecked(self.settings.value('animation/quality','auto')==key);quality_group.addAction(action);self.quality_actions[key]=action
            action.triggered.connect(lambda checked=False,k=key:self.animation_quality(k))
        self.action(view,'search',lambda:self.with_tab(lambda t:t.show_search()),'Ctrl+F')
        next_hit=view.addAction(L('下一条搜索结果','Next search match'),lambda:self.with_tab(lambda t:t.search_step(1)));next_hit.setShortcut('F3')
        previous_hit=view.addAction(L('上一条搜索结果','Previous search match'),lambda:self.with_tab(lambda t:t.search_step(-1)));previous_hit.setShortcut('Shift+F3')
        self.action(view,'page_fit',lambda:self.with_tab(lambda t:t.fit(False)),'Ctrl+0')
        self.action(view,'width_fit',lambda:self.with_tab(lambda t:t.fit(True)),'Ctrl+1')
        self.action(view,'bookmark',lambda:self.with_tab(lambda t:t.toggle_bookmark()),'Ctrl+D')
        self.action(view,'fullscreen',self.fullscreen,'F11');self.action(view,'presentation',self.toggle_presentation,'F5')
        dark=view.addAction(tr('dark'));self.dark_action=dark;dark.setCheckable(True);dark.setChecked(self.dark);dark.toggled.connect(self.set_dark)
        night=view.addAction(tr('night'));self.night_action=night;night.setCheckable(True);night.toggled.connect(lambda b:self.with_tab(lambda t:(setattr(t,'night',b),t.canvas.invalidate(False))))
        language=view.addMenu('语言/Language');self.language_menu=language
        for label,code in [('中文','zh'),('English','en')]:language.addAction(label,lambda c=code:self.change_language(c))
        settingsmenu=self.menuBar().addMenu('Settings');self.settings_menu=settingsmenu;preferences=settingsmenu.addAction(L('首选项…','Preferences…'));preferences.setShortcut('Ctrl+,');preferences.triggered.connect(self.preferences)
        settingsmenu.addMenu(language)
        settingsmenu.addAction(L('自定义工具栏…','Customize toolbar…'),self.customize_toolbar)
        settingsmenu.addAction(L('恢复未保存的文档…','Recover unsaved documents…'),self.offer_recovery)
        helpmenu=self.menuBar().addMenu(tr('help'));self.action(helpmenu,'details',self.compatibility)
        self.action(helpmenu,'update',self.check_updates);self.action(helpmenu,'about',self.about)
    def animation_quality(self,key):
        self.settings.setValue("animation/quality",key)
        for name,action in self.quality_actions.items():action.setChecked(name==key)
        for tab in self.document_tabs():
            for player in tab.players.values():player.resolution_changed()

    def export_options(self):
        defaults={'dpi':300,'width':0,'quality':95,'format':'png'}
        return {k:self.settings.value('export/'+k,v,type=type(v)) for k,v in defaults.items()}

    def export_settings(self):
        values=self.export_options();form=FormDialog(tr('export_settings'),self)
        form.number('dpi',L('分辨率（DPI）','Resolution (DPI)'),values['dpi'],36,1200)
        form.number('width',L('输出宽度（像素，0 表示使用 DPI）','Width in pixels (0 uses DPI)'),values['width'],0,16000)
        form.number('quality',L('JPG 质量','JPG quality'),values['quality'],1,100)
        form.choice('format',L('图片格式','Image format'),[('PNG','png'),('JPG','jpg')]);form.inputs['format'].setCurrentIndex(form.inputs['format'].findData(values['format']))
        form.note(L('应用于页面、区域导出和高清复制。设置会保存，下次导出不再询问分辨率。','Used for page/region export and high-resolution copy. Defaults are remembered.'))
        if form.finish().exec()==QDialog.Accepted:
            for key,value in form.values().items():self.settings.setValue('export/'+key,value)

    def document_tabs(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count()) if isinstance(self.tabs.widget(i),DocumentTab)]

    def merge_documents(self,include_open=False):
        tabs=self.document_tabs()
        for tab in tabs:
            if tab.busy:
                QMessageBox.information(self,'AsterPDF',tr('working'));return
            if tab.inline_editor:
                tab.commit_inline(lambda:self.merge_documents(include_open));return
        dialog=MergeDialog(self,include_open=bool(include_open))
        if dialog.exec()!=QDialog.Accepted or not dialog.files():return
        files=dialog.files()
        target,_=QFileDialog.getSaveFileName(self,tr('merge'),L('合并文档.pdf','merged.pdf'),'PDF (*.pdf)')
        if not target:return
        sources={str(Path(p).resolve()) for p in files}|{t.document.original for t in tabs}
        if str(Path(target).resolve()) in sources:
            QMessageBox.warning(self,'AsterPDF',L('请为合并结果选择新文件名。','Choose a new filename for the merged document.'));return
        from .core import merge_files
        self.statusBar().showMessage(tr('working'))
        self.queue.submit(lambda j:merge_files(files,target),lambda _:self.open_file(target),lambda e:QMessageBox.warning(self,'AsterPDF',str(e)),self.statusBar().clearMessage,priority=2)

    def eventFilter(self,obj,event):
        from shiboken6 import isValid
        if hasattr(self,'tabs') and not isValid(self.tabs):return False
        if event.type() in (QEvent.Resize,QEvent.LayoutRequest) and hasattr(self,'tabs') and obj in (self.tabs,self.tabs.tabBar()):QTimer.singleShot(0,self.sync_tab_corner)
        if event.type()!=QEvent.KeyPress:return False
        tab=self.current()
        if not tab or not isinstance(obj,QWidget) or QWidget.window(obj)!=self:return super().eventFilter(obj,event)
        text_input=isinstance(obj,(QLineEdit,QTextEdit,QPlainTextEdit,QAbstractSpinBox,QComboBox))
        if event.type()==QEvent.KeyPress:
            if self.presentation and event.key()==Qt.Key_Escape:self.escape();return True
            if text_input:return False
            if event.key() in (Qt.Key_Escape,Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down,Qt.Key_PageUp,Qt.Key_PageDown,Qt.Key_Home,Qt.Key_End,Qt.Key_Space,Qt.Key_Delete):
                # Preserve native thumbnail multi-select navigation outside presentation.
                if not self.presentation and obj in (tab.thumbnails,tab.annotation_list,tab.organizer) and event.key() not in (Qt.Key_Escape,Qt.Key_Delete):return False
                if event.key()==Qt.Key_Delete and obj in (tab.thumbnails,tab.organizer):tab.page_selection_operation('delete',obj);return True
                return tab.handle_key(event)
        return super().eventFilter(obj,event)

    def action(self,menu,key,callback,shortcut=None):
        action=menu.addAction(tr(key));action.triggered.connect(callback)
        if shortcut:action.setShortcut(shortcut)
        return action

    def current(self):
        tab=self.tabs.currentWidget()
        return tab if isinstance(tab,DocumentTab) else None

    def with_tab(self,callback):
        tab=self.current()
        if tab and not tab.busy:return callback(tab)

    def open_dialog(self):
        files,_=QFileDialog.getOpenFileNames(self,tr('open'),'','Documents (*.pdf *.eps *.ps *.md *.markdown);;PDF (*.pdf);;PostScript (*.eps *.ps);;Markdown (*.md *.markdown)')
        for filename in files:self.open_file(filename)

    def open_file(self,filename):
        filename=str(Path(filename).resolve())
        if not Path(filename).is_file():
            QMessageBox.warning(self,'AsterPDF',L('文件已失效或被移动：','File is missing or moved: ')+filename);return
        if filename in self.opening:return
        for i in range(self.tabs.count()):
            tab=self.tabs.widget(i)
            if isinstance(tab,DocumentTab) and tab.document.original==filename:self.tabs.setCurrentIndex(i);return
        loading=QLabel(tr('working')+' '+Path(filename).name);loading.setAlignment(Qt.AlignCenter)
        loading_index=self.tabs.addTab(loading,Path(filename).name);self.tabs.setCurrentIndex(loading_index)
        self.opening.add(filename);self.statusBar().showMessage(tr('working')+' '+Path(filename).name)
        source=filename
        import tempfile
        temporary=None
        if Path(filename).suffix.lower() in ('.md','.markdown'):
            from .file_open import markdown_pdf
            temporary=tempfile.TemporaryDirectory(prefix='aster-import-')
        def work(job):
            converted=source
            if Path(filename).suffix.lower() in ('.eps','.ps'):
                from .figures import prepare
                with tempfile.TemporaryDirectory(prefix='aster-import-') as folder:
                    converted=prepare(filename,folder);doc=Document(converted,self.recovery_root)
            else:doc=Document(converted,self.recovery_root)
            if Path(filename).suffix.lower()!='.pdf':
                import shutil
                doc.original=filename;shutil.copyfile(doc.path,doc.folder/'imported-base.pdf');doc._metadata()
            try:return doc,doc.info()
            except Exception:doc.close();raise
        def done(result):
            doc,info=result;tab=DocumentTab(self,doc,info)
            index=self.tabs.addTab(tab,Path(filename).name);self.tabs.setCurrentIndex(index)
            self.tabs.setTabToolTip(index,filename)
            recent=self.settings.value('recent',[],type=list)
            self.settings.setValue('recent',([filename]+[x for x in recent if x!=filename])[:15])
            import hashlib,datetime
            self.settings.setValue('recent_opened/'+hashlib.sha256(filename.encode()).hexdigest(),datetime.datetime.now().isoformat(timespec='seconds'));self.refresh_recent()
        def cleanup():
            self.opening.discard(filename);self.tabs.removeTab(self.tabs.indexOf(loading));loading.deleteLater()
            if temporary:temporary.cleanup()
            self.statusBar().clearMessage()
        def failed(message):QMessageBox.warning(self,'AsterPDF',str(message))
        def submit():self.queue.submit(work,done,failed,cleanup,priority=3)
        if temporary:
            from .markdown_import import prepare
            def ready(prepared):
                nonlocal source
                try:source=markdown_pdf(filename,Path(temporary.name)/'document.pdf',prepared)
                except Exception as error:failed(error);cleanup();return
                submit()
            self.queue.submit(lambda j:prepare(filename),ready,lambda message:(failed(message),cleanup()),priority=3)
        else:submit()

    def customize_toolbar(self,parent=None):
        from .chrome import customize_window_toolbar
        customize_window_toolbar(self,parent if isinstance(parent,QWidget) else self)

    def preferences(self):
        from .preferences import Preferences
        dialog=Preferences(self);dialog.exec()

    def recent_context_menu(self,pos):
        item=self.home_recent.itemAt(pos)
        if not item:return
        path=item.data(0,Qt.UserRole);menu=QMenu(self)
        menu.addAction(L('复制文件名','Copy filename'),lambda:QApplication.clipboard().setText(Path(path).name))
        menu.addAction(L('复制路径','Copy path'),lambda:QApplication.clipboard().setText(path))
        def remove():
            self.settings.setValue('recent',[p for p in self.settings.value('recent',[],type=list) if p!=path]);self.refresh_recent()
        menu.addAction(L('移除记录','Remove from recent'),remove);menu.exec(self.home_recent.viewport().mapToGlobal(pos))

    def refresh_recent(self):
        self.recent.clear();self.home_recent.clear()
        self.home_recent.setVisible(self.settings.value('home/recent',True,type=bool))
        self.home_recent.setHeaderLabels([L('最近文件','Recent files'),L('大小','Size'),L('打开时间','Opened')])
        self.home_recent.headerItem().setTextAlignment(1,Qt.AlignRight|Qt.AlignVCenter)
        for path in self.settings.value('recent',[],type=list):
            self.recent.addAction(Path(path).name,lambda p=path:self.open_file(p))
            import hashlib
            file=Path(path);opened=self.settings.value('recent_opened/'+hashlib.sha256(path.encode()).hexdigest(),L('时间未记录','Time not recorded')).replace('T',' ')
            try:size=f'{file.stat().st_size/1024/1024:.2f} MB'
            except OSError:size=L('文件不可用','Unavailable')
            item=QTreeWidgetItem([f'{file.name}\n{file.parent}',size,opened]);item.setData(0,Qt.UserRole,path);item.setToolTip(0,path);item.setTextAlignment(1,Qt.AlignRight|Qt.AlignVCenter);self.home_recent.addTopLevelItem(item)
            item.setSizeHint(0,__import__('PySide6.QtCore',fromlist=['QSize']).QSize(660,60))


    def update_title(self):
        for i in range(self.tabs.count()):
            tab=self.tabs.widget(i)
            if isinstance(tab,DocumentTab):self.tabs.setTabText(i,Path(tab.document.original).name+(' *' if tab.document.dirty or tab.inline_dirty() or tab.suspended_inline else ''))
        tab=self.current()
        if hasattr(self,'dark_action'):
            self.dark_action.blockSignals(True);self.dark_action.setChecked(self.dark);self.dark_action.blockSignals(False)
            self.night_action.blockSignals(True);self.night_action.setChecked(bool(tab and tab.night));self.night_action.blockSignals(False)
        if tab:
            tab.quick_actions['undo'].setEnabled(tab.inline_editor.document().isUndoAvailable() if tab.inline_editor else tab.document.index>0)
            tab.quick_actions['redo'].setEnabled(tab.inline_editor.document().isRedoAvailable() if tab.inline_editor else tab.document.index+1<len(tab.document.history))
        self.setWindowTitle((Path(tab.document.original).name+(' *' if tab.document.dirty or tab.inline_dirty() or tab.suspended_inline else '')+' — ' if tab else '')+'AsterPDF')

    def tab_changed(self,index):
        if isinstance(self._previous_tab,DocumentTab) and self._previous_tab is not self.current():self._previous_tab.release_memory()
        self._previous_tab=self.current();self.update_title()
        if self.current():self.current().current_changed(self.current().canvas.page);self.current().canvas.update()

    def save_tab(self,save_as=False,after=None,on_failure=None):
        tab=self.current()
        if not tab or tab.busy:return
        if tab.suspended_inline:tab.restore_inline()
        if tab.inline_editor:
            tab.commit_inline(lambda:self.save_tab(save_as,after,on_failure),on_failure=on_failure);return
        destination=None
        if save_as or Path(tab.document.original).suffix.lower()!='.pdf':
            destination,_=QFileDialog.getSaveFileName(self,tr('save_as'),str(Path(tab.document.original).with_suffix('.pdf')),'PDF (*.pdf)')
            if not destination:
                if after:self._close_pending=False;self._closing_all=False
                return
        tab.run(tr('save'),lambda j:tab.document.save(destination),lambda _:after() if after else None,failure=on_failure)

    def history(self,redo):
        tab=self.current()
        if tab and tab.suspended_inline:tab.restore_inline()
        if tab and tab.inline_editor:
            tab.inline_editor.redo() if redo else tab.inline_editor.undo();return
        if tab and not tab.busy:tab.page_live_operations=[];tab.run(tr('redo' if redo else 'undo'),lambda j:tab.document.redo() if redo else tab.document.undo(),editing=True)

    def close_tab(self,index,discard=False):
        tab=self.tabs.widget(index)
        if not isinstance(tab,DocumentTab):return True
        if getattr(self,'_close_pending',False):return False
        if tab.busy:
            QMessageBox.information(self,'AsterPDF',tr('working'));return False
        self._close_pending=True
        if tab.document.dirty or tab.inline_dirty() or tab.suspended_inline:self.tabs.setCurrentWidget(tab)
        if tab.suspended_inline:tab.restore_inline()
        dirty=tab.document.dirty or tab.inline_dirty()
        if dirty and not discard:
            choice=QMessageBox.question(self,'AsterPDF',tr('unsaved'),QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
            if choice==QMessageBox.Cancel:
                self._close_pending=False;self._closing_all=False;return False
            if choice==QMessageBox.Save:
                def failed(message=None):
                    self._close_pending=False;self._closing_all=False
                    if message:tab.error(message)
                def saved(_=None):QTimer.singleShot(0,lambda:self.finish_close_tab(tab))
                def save():
                    if tab.busy:QTimer.singleShot(20,save);return
                    self.save_tab(after=saved,on_failure=failed) if Path(tab.document.original).suffix.lower()!='.pdf' else tab.run(tr('save'),lambda j:tab.document.save(),saved,failure=failed)
                if tab.inline_editor:tab.commit_inline(save,on_failure=failed)
                else:save()
                return False
        self.finish_close_tab(tab);return True

    def finish_close_tab(self,tab):
        if tab.closed:return
        if tab.inline_editor:tab.cancel_inline()
        tab.pause_media();tab.save_state();tab.closed=True;tab.release_memory()
        for player in tab.video_players:player.shutdown()
        self.tabs.removeTab(self.tabs.indexOf(tab))
        self.queue.submit(lambda j:tab.document.close(),finished=tab.deleteLater,priority=-5)
        self._close_pending=False
        if getattr(self,'_closing_all',False):QTimer.singleShot(0,self.close)

    def closeEvent(self,event):
        # Process one document at a time. Never queue another close inside a
        # modal save prompt: nested close events used to bypass/duplicate it.
        event.ignore()
        if getattr(self,'_close_pending',False) or getattr(self,'_confirm_close_pending',False):return
        if not getattr(self,'_closing_all',False) and len(self.document_tabs())>1 and self.settings.value('window/confirm_close',True,type=bool):
            from PySide6.QtWidgets import QCheckBox
            prompt=QMessageBox(self);prompt.setWindowTitle(L('关闭 AsterPDF','Close AsterPDF'));prompt.setText(L('关闭当前标签页，还是关闭所有标签页并退出？','Close the current tab, or close all tabs and quit?'))
            current=prompt.addButton(L('当前标签页','Current tab'),QMessageBox.ActionRole);current.setEnabled(self.current() is not None)
            all_tabs=prompt.addButton(L('所有标签页并退出','All tabs and quit'),QMessageBox.AcceptRole);prompt.addButton(QMessageBox.Cancel)
            remember=QCheckBox(L('不再提示（以后直接退出，仍询问保存修改）','Do not ask again (still prompt to save changes)'));prompt.setCheckBox(remember)
            self._confirm_close_pending=True
            try:prompt.exec()
            finally:self._confirm_close_pending=False
            if prompt.clickedButton() not in (current,all_tabs):return
            if remember.isChecked():self.settings.setValue('window/confirm_close',False)
            if prompt.clickedButton()==current:self.close_tab(self.tabs.currentIndex());return
        self._closing_all=True
        if self.opening or any(t.busy for t in self.document_tabs()):
            QTimer.singleShot(150,lambda:self.close() if getattr(self,'_closing_all',False) else None);return
        tabs=self.document_tabs()
        if tabs:
            tab=next((t for t in reversed(tabs) if t.document.dirty or t.inline_dirty() or t.suspended_inline),tabs[-1])
            self.close_tab(self.tabs.indexOf(tab));return
        self.queue.pool.waitForDone(30000)
        self._closing_all=False;self.settings.sync();event.accept()

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() and u.toLocalFile().lower().endswith(('.pdf','.eps','.ps','.md','.markdown')) for u in event.mimeData().urls()):event.acceptProposedAction()

    def dropEvent(self,event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith(('.pdf','.eps','.ps','.md','.markdown')):self.open_file(url.toLocalFile())

    def set_dark(self,value):
        self.dark=value;self.settings.setValue('dark',value);self.apply_theme()

    def apply_theme(self):
        palette=QApplication.style().standardPalette()
        if self.dark:
            for role,color in [(QPalette.Window,'#17202d'),(QPalette.WindowText,'#d9e2ee'),(QPalette.Base,'#1b2737'),(QPalette.Text,'#d9e2ee'),(QPalette.Button,'#26364b'),(QPalette.ButtonText,'#d9e2ee'),(QPalette.Highlight,'#536daa'),(QPalette.HighlightedText,'#ffffff')]:palette.setColor(role,QColor(color))
        else:
            for role,color in [(QPalette.Window,'#f7f9fc'),(QPalette.WindowText,'#243249'),(QPalette.Base,'#ffffff'),(QPalette.Text,'#243249'),(QPalette.Button,'#edf1f8'),(QPalette.ButtonText,'#243249'),(QPalette.Highlight,'#dce6ff'),(QPalette.HighlightedText,'#263d79')]:palette.setColor(role,QColor(color))
        QApplication.instance().setPalette(palette)
        checkbox='QCheckBox::indicator {width:14px;height:14px;border:1px solid '+('#708198' if self.dark else '#aab7c9')+';border-radius:3px;background:'+('#223147' if self.dark else '#ffffff')+';} QCheckBox::indicator:checked {background:#536fd3;border-color:#536fd3;image:url("'+resource('check-white.svg').as_posix()+'");} QCheckBox::indicator:hover {border-color:#647eea;}'
        fontsize={'small':12,'medium':13,'large':15}.get(self.settings.value('ui/font_size','medium'),13)
        QApplication.instance().setStyleSheet((DARK if self.dark else LIGHT).replace('font-size:13px',f'font-size:{fontsize}px')+checkbox+('QSplitter::handle {background:#29394d;} QSplitter::handle:hover {background:#667b96;}' if self.dark else 'QSplitter::handle {background:#c9d2df;} QSplitter::handle:hover {background:#8e9eb5;}')+'''QTabBar QToolButton {padding:0px;min-width:20px;max-width:20px;} QTabBar::scroller {width:44px;} QSpinBox::up-button,QSpinBox::down-button,QDoubleSpinBox::up-button,QDoubleSpinBox::down-button {width:16px;} QToolBar {font-size:12px;spacing:2px;}  QToolTip {padding:5px;}''')
        current_style=QApplication.instance().styleSheet()
        QApplication.instance().setStyleSheet(current_style.replace('font-size:12px',f'font-size:{fontsize-1}px'))
        for i in range(self.tabs.count()):
            tab=self.tabs.widget(i)
            if isinstance(tab,DocumentTab):
                tab.dark=self.dark;tab.apply_chrome_opacity();tab.canvas.update()
                from .ui_icons import icon
                for key in ('select','hand','undo','redo'):tab.quick_actions[key].setIcon(icon(key,self.dark))
                from .chrome import decorate
                for action in tab.findChildren(QAction):
                    key=action.property('aster_key')
                    if key:decorate(action,key,self.dark)
                tab.zoom_minus.setIcon(icon('minus',self.dark));tab.zoom_plus.setIcon(icon('plus',self.dark));tab.update_bookmark_icon();tab.navbar_host.timer.start(0)
        if sys.platform=='win32':
            import ctypes
            value=ctypes.c_int(1 if self.dark else 0)
            for attribute in (20,19):
                try:ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()),attribute,ctypes.byref(value),ctypes.sizeof(value))
                except (AttributeError,OSError):pass
        self.applied_font_size=self.settings.value('ui/font_size','medium')
        QTimer.singleShot(0,self.sync_tab_corner)

    def sync_tab_corner(self):
        from shiboken6 import isValid
        if not isValid(self) or not isValid(self.tabs):return
        from .ui_icons import icon
        bar=self.tabs.tabBar();button=self.document_switcher
        if getattr(self,'_corner_dark',None)!=self.dark:
            button.setIcon(icon('tabs',self.dark));self._corner_dark=self.dark
        if button.height()!=bar.height():button.setFixedHeight(bar.height())
        button.move(self.tabs.width()-button.width(),bar.y())
        style='QToolButton {border:0;border-radius:0;padding:0;background:'+('#172232' if self.dark else '#eef2f7')+';} QToolButton::menu-indicator {image:none;width:0;height:0;}'
        if button.styleSheet()!=style:button.setStyleSheet(style)

    def change_language(self,code):
        # Translate existing controls; documents, canvases, drafts, players and
        # scroll positions remain the same objects with the same state.
        self.settings.setValue('language',code);i18n.LANGUAGE=code
        app=QApplication.instance();old=getattr(app,'aster_translator',None)
        if old:app.removeTranslator(old)
        translator=QTranslator(app)
        if code=='zh':translator.load('qtbase_zh_CN',QLibraryInfo.path(QLibraryInfo.TranslationsPath));app.installTranslator(translator)
        app.aster_translator=translator
        translate_tree(self);self.settings_menu.setTitle('Settings');self.language_menu.setTitle('语言/Language');self.update_home_footer();self.refresh_recent()
        for tab in self.document_tabs():
            tab.sidebar.setTabText(0,L('页面','Pages'));tab.sidebar.setTabText(4,L('批注','Notes'));tab.style_modules();tab.load_annotations()
        self.update_title()

    def update_home_footer(self):
        from .release import REPOSITORY
        repository=REPOSITORY or self.settings.value('repository','')
        address='https://github.com/'+repository if repository else L('仓库地址：待设置','Repository: not configured')
        self.home_footer.setTextFormat(Qt.RichText);self.home_footer.setOpenExternalLinks(True)
        self.home_footer.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.home_footer.setText(L('版本 ','Version ')+__version__+f'<br><a href="{address}">{address}</a><br>'+L('开发者：','Developer: ')+'Zhentong Li (<a href="mailto:eternitylzt@gmail.com">eternitylzt@gmail.com</a>)')

    def populate_tab_menu(self,menu):
        menu.clear()
        for index in range(self.tabs.count()):
            widget=self.tabs.widget(index);action=menu.addAction(self.tabs.tabText(index));action.setCheckable(True);action.setChecked(widget is self.tabs.currentWidget())
            action.triggered.connect(lambda checked=False,w=widget:self.tabs.setCurrentWidget(w))

    def tick_chrome(self):
        tab=self.current()
        if not tab or self.presentation or QApplication.mouseButtons()!=Qt.NoButton:return
        pos=self.mapFromGlobal(QCursor.pos())
        if self.settings.value('toolbar/autohide',False,type=bool):
            near_top=pos.y()<self.menuBar().height()+self.tabs.tabBar().height()+tab.navbar.height()+12
            tab.apply_chrome_visibility(not near_top and tab.inline_editor is None)
        if self.settings.value('sidebar/autohide',False,type=bool):
            edge=tab.sidebar_toggle.mapFromGlobal(QCursor.pos()).x()
            inside=tab.sidebar.isVisible() and tab.sidebar.rect().contains(tab.sidebar.mapFromGlobal(QCursor.pos()))
            tab.sidebar.setVisible(inside or 0<=edge<24);tab.sidebar_toggle.setText('‹' if tab.sidebar.isVisible() else '›')

    def file_information(self):
        tab=self.current()
        if not tab:return
        from .printing import information
        information(tab)

    def print_current(self):
        tab=self.current()
        if not tab:return
        if tab.inline_editor:tab.commit_inline(self.print_current);return
        from .printing import print_document
        print_document(tab)

    def fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def toggle_presentation(self):
        tab=self.current()
        if not tab:return
        if tab.inline_editor:
            tab.leave_inline(self.toggle_presentation);return
        if not self.presentation:
            self._presentation_state=(tab.canvas.columns,tab.continuous.isChecked(),tab.canvas.mode,tab.tool_panels.isVisible(),self.isMaximized())
            self._presentation_widgets=[(widget,widget.isVisible()) for widget in (self.menuBar(),self.tabs.tabBar(),self.document_switcher,tab.minimap,tab.navbar_host,tab.navbar,tab.tool_panels,tab.sidebar,tab.sidebar_toggle,tab.text_properties)]
            if hasattr(tab,'property_container'):self._presentation_widgets.append((tab.property_container,tab.property_container.isVisible()))
            self._presentation_view=tab.document_views.currentWidget();self._presentation_editing=tab.editing_objects
            self.presentation=True;tab.editing_objects=False
            if hasattr(tab,'playback_panel'):tab.playback_panel.dismiss()
            for widget,_ in self._presentation_widgets:widget.hide()
            tab.document_views.setCurrentWidget(tab.scroll);tab.set_mode('select');tab.set_view(1,False)
            self.showFullScreen();tab.canvas.setFocus();QTimer.singleShot(100,lambda:tab.fit(False) if self.presentation and not tab.closed else None)
        else:
            self.presentation=False
            for widget,visible in self._presentation_widgets:widget.setVisible(visible)
            tab.set_view(self._presentation_state[0],self._presentation_state[1]);tab.set_mode(self._presentation_state[2]);tab.editing_objects=self._presentation_editing
            tab.document_views.setCurrentWidget(self._presentation_view)
            self.showMaximized() if self._presentation_state[4] else self.showNormal()
            if tab.editing_objects:QTimer.singleShot(0,tab.inspect_objects)

    def keyPressEvent(self,event):
        if self.presentation and self.current():
            tab=self.current()
            if event.key() in (Qt.Key_Right,Qt.Key_Down):tab.goto(tab.canvas.page+1);return
            if event.key() in (Qt.Key_Left,Qt.Key_Up):tab.goto(tab.canvas.page-1);return
            if event.key()==Qt.Key_Space:
                players=[p for p in tab.players.values() if p.animation.page==tab.canvas.page]
                if players:players[0].toggle()
                else:tab.goto(tab.canvas.page+1)
                return
        super().keyPressEvent(event)

    def escape(self):
        if self.presentation:self.toggle_presentation()
        elif self.isFullScreen():self.showNormal()
        else:self.with_tab(lambda t:t.set_mode('select'))

    def persist_positions(self):
        for i in range(self.tabs.count()):
            tab=self.tabs.widget(i)
            if isinstance(tab,DocumentTab):tab.save_state()

    def recovery_settings(self):
        folder=QFileDialog.getExistingDirectory(self,L('恢复副本文件夹（自动记录未保存操作）','Recovery folder (automatically records unsaved changes)'),str(self.recovery_root))
        if not folder:return
        previous=self.settings.value('recovery/previous',[],type=list)
        self.settings.setValue('recovery/previous',list(dict.fromkeys(previous+[str(self.recovery_root)])))
        self.recovery_root=Path(folder);self.settings.setValue('recovery/folder',folder)

    def offer_recovery(self):
        from PySide6.QtCore import QLockFile
        roots=list(dict.fromkeys([str(self.recovery_root)]+self.settings.value('recovery/previous',[],type=list)))
        active={str(t.document.folder) for t in self.document_tabs()}
        for root in roots:
            for manifest in Path(root).glob('*/recovery.json'):
                if str(manifest.parent) in active:continue
                lock=QLockFile(str(manifest.parent/'session.lock'));lock.setStaleLockTime(0)
                if not lock.tryLock(0):continue
                try:
                    data=json.loads(manifest.read_text(encoding='utf-8'));revision=Path(data.get('revision',''));draft=manifest.parent/'draft.json'
                    if not data.get('dirty') and not draft.exists():continue
                    if not revision.is_file() or revision.parent.resolve()!=manifest.parent.resolve():continue
                    data['draft']=json.loads(draft.read_text(encoding='utf-8')) if draft.exists() else None
                    answer=QMessageBox.question(self,L('恢复未保存文档','Recover unsaved document'),Path(data.get('original','')).name+'\n'+L('发现意外退出前的修改。恢复后可另存为；原文件不会自动覆盖。','Unsaved changes were found. Recover and use Save As; the original is never overwritten automatically.'),QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)
                    if answer==QMessageBox.Yes:self.open_recovery(data,manifest)
                except (OSError,ValueError):continue
                finally:lock.unlock()

    def open_recovery(self,data,manifest):
        def work(job):
            doc=Document(data['revision'],self.recovery_root);doc.original=data['original'];doc.saved_revision='';doc._metadata();return doc,doc.info()
        def done(result):
            doc,info=result;tab=DocumentTab(self,doc,info);index=self.tabs.addTab(tab,Path(doc.original).name+' *');self.tabs.setCurrentIndex(index)
            if data.get('draft'):
                tab.restore_recovery_draft(data['draft'])
                if data['draft'].get('source')!=data['revision']:tab.inline_source_path=data['draft'].get('source','stale-recovery-draft')
            # Mark the old snapshot as offered/recovered only after the new one
            # exists. Retain its PDF until normal cleanup, avoiding any data loss.
            from .core import atomic_json
            old=dict(data);old.pop('draft',None);old['dirty']=False;atomic_json(manifest,old);(manifest.parent/'draft.json').unlink(missing_ok=True)
            self.update_title()
        self.queue.submit(work,done,lambda e:QMessageBox.warning(self,'AsterPDF',e))

    def about(self):
        QMessageBox.about(self,'AsterPDF',f'<h2>✦ AsterPDF {__version__}</h2><p>'+L('阅读 · 编辑 · 动画 · 批注 · 提取','Read · Edit · Animate · Annotate · Extract')+'</p><p>'+L('面向科研文档的本地 PDF 工具','A local PDF workspace for research')+'</p><p>'+L('作者：','Author: ')+'Zhentong Li<br>eternitylzt@gmail.com<br><a href="https://github.com/eternitylzt">github.com/eternitylzt</a></p><p>AGPL-3.0-only · Qt / PySide6 · MuPDF · pikepdf / qpdf</p>')

    def compatibility(self):
        path=resource('HELP.zh-CN.md' if i18n.LANGUAGE=='zh' else 'HELP.en.md')
        dialog=QDialog(self);dialog.setWindowTitle(tr('details'));dialog.resize(850,700)
        from PySide6.QtWidgets import QTextBrowser
        layout=QVBoxLayout(dialog);browser=QTextBrowser();browser.setOpenExternalLinks(False)
        browser.setMarkdown(path.read_text(encoding='utf-8') if path.exists() else 'See docs/COMPATIBILITY.md in the source distribution.')
        layout.addWidget(browser);dialog.exec()

    def check_updates(self):
        from .release import REPOSITORY
        repository=REPOSITORY or self.settings.value('repository','')
        if not repository:
            QMessageBox.information(self,tr('update'),L('本项目尚未配置发布仓库，暂时无法检查更新。','The release repository is not configured yet.'))
            return
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):return
        self.statusBar().showMessage(L('正在检查更新','Checking for updates…'))
        def fetch(job):
            from .network import fetch_latest_release
            return fetch_latest_release(repository,__version__)
        def done(data):
            tag=data.get('tag_name','?');url=data.get('html_url','')
            if not url.startswith(f'https://github.com/{repository}/releases/'):
                QMessageBox.warning(self,'AsterPDF',L('发布链接无效','Unexpected release URL'));return
            from .release import newer
            if not newer(tag,__version__):
                QMessageBox.information(self,tr('update'),L('已是最新版本：','Up to date: ')+__version__);return
            dialog=QMessageBox(self);dialog.setWindowTitle(tr('update'));dialog.setText(L(f'发现新版本：{tag}\n当前版本：{__version__}',f'New version: {tag}\nInstalled: {__version__}'))
            download=dialog.addButton(L('下载','Download'),QMessageBox.AcceptRole);dialog.addButton(QMessageBox.Cancel);dialog.exec()
            if dialog.clickedButton()==download:QDesktopServices.openUrl(QUrl(url))
        self.queue.submit(fetch,done,lambda e:QMessageBox.warning(self,tr('update'),str(e)),self.statusBar().clearMessage)


def main():
    parser=argparse.ArgumentParser(description='AsterPDF desktop')
    parser.add_argument('--verify-update',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('files',nargs='*');parser.add_argument('--data-dir');parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--verify-desktop',metavar='OUTPUT_DIRECTORY',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.verify_update:
        from .network import fetch_latest_release
        from .release import REPOSITORY
        print(json.dumps(fetch_latest_release(REPOSITORY,__version__)))
        return 0
    from .file_open import DesktopApplication
    app=DesktopApplication(sys.argv[:1]);app.setApplicationName('AsterPDF');app.setApplicationVersion(__version__)
    app.setOrganizationName('AsterPDF');app.setStyle('Fusion')
    window=Window(args.data_dir)
    for filename in args.files:window.open_file(filename)
    app.bind(window);window.show()
    if args.verify_desktop:
        from .diagnostics import start
        start(window,args.verify_desktop,len(args.files))
    if args.smoke_test:QTimer.singleShot(4000,app.quit)
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
