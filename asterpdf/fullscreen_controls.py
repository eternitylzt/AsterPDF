"""Small, auto-hiding reading controls for document fullscreen."""
import time
from PySide6.QtCore import Qt,QTimer,QSignalBlocker
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame,QHBoxLayout,QToolButton,QDoubleSpinBox,QApplication,QMenu
from .i18n import L


class FullscreenControls(QFrame):
    def __init__(self,window):
        super().__init__(window);self.host=window;self.until=0;self.viewport_size=None
        self.setObjectName('fullscreenControls');row=QHBoxLayout(self);row.setContentsMargins(7,4,7,4);row.setSpacing(5)
        def button(text,hint,callback):
            b=QToolButton();b.setText(text);b.setToolTip(hint);b.clicked.connect(callback);b.setCursor(Qt.PointingHandCursor);b.setFocusPolicy(Qt.NoFocus);row.addWidget(b);return b
        self.width_button=button(L('宽度','Width'),L('适合宽度','Fit width'),lambda:self.fit(True));self.width_button.setCheckable(True)
        self.page=button(L('整页','Page'),L('适合整页','Fit page'),lambda:self.fit(False));self.page.setCheckable(True)
        button('−',L('缩小','Zoom out'),lambda:self.host.current().zoom_by(1/1.12))
        self.zoom=QDoubleSpinBox();self.zoom.setRange(1.5625,6400);self.zoom.setDecimals(2);self.zoom.setSuffix('%');self.zoom.setKeyboardTracking(False);self.zoom.setFixedWidth(96);self.zoom.setToolTip(L('缩放比例','Zoom'));row.addWidget(self.zoom)
        self.zoom.valueChanged.connect(lambda value:self.host.current().set_zoom(value/100*self.host.current().actual_size_scale()))
        self.zoom.editingFinished.connect(lambda:self.host.current().canvas.setFocus() if self.host.current() else None)
        button('+',L('放大','Zoom in'),lambda:self.host.current().zoom_by(1.12))
        self.options=button(L('视图','View'),L('阅读布局','Reading layout'),self.menu)
        button(L('退出','Exit'),L('退出全屏（Esc / F11）','Exit fullscreen (Esc / F11)'),window.fullscreen)
        self.timer=QTimer(self);self.timer.setInterval(120);self.timer.timeout.connect(self.sync);self.hide()

    def present(self):
        self.until=time.monotonic()+3;self.viewport_size=None;self.timer.start();self.sync()

    def fit(self,width):
        self.until=time.monotonic()+2;self.host.current().fit(width)

    def menu(self):
        t=self.host.current();menu=QMenu(self)
        for label,columns,continuous in [(L('单页','Single page'),1,False),(L('连续滚动','Continuous'),1,True),(L('双页','Two pages'),2,False),(L('双页连续','Two-page continuous'),2,True)]:
            a=menu.addAction(label);a.setCheckable(True);a.setChecked(t.canvas.columns==columns and t.canvas.continuous==continuous)
            a.triggered.connect(lambda checked=False,c=columns,s=continuous:(t.set_view(c,s),t.fit(t.fit_mode!='page_fit')))
        menu.exec(self.options.mapToGlobal(self.options.rect().bottomLeft()));self.until=time.monotonic()+2

    def sync(self):
        w=self.host;t=w.current()
        if not w.document_fullscreen or not t:self.hide();self.timer.stop();return
        size=t.scroll.viewport().size()
        if size!=self.viewport_size:
            self.viewport_size=size
            if t.fit_mode in ('width_fit','page_fit'):t.fit(t.fit_mode=='width_fit')
        with QSignalBlocker(self.zoom):
            if not self.zoom.hasFocus():self.zoom.setValue(t.zoom_factor*100)
        self.width_button.setChecked(t.fit_mode=='width_fit');self.page.setChecked(t.fit_mode=='page_fit')
        background,ink=('#233044','#e5edf7') if t.dark else ('#f1f4f8','#223348')
        style=(background,ink)
        if getattr(self,'colors',None)!=style:
            self.colors=style;self.setStyleSheet(f'QFrame#fullscreenControls{{background:{background};border:1px solid #8190a4;border-radius:5px;}} QToolButton{{color:{ink};padding:4px 6px;}} QToolButton:checked,QToolButton:hover{{background:#688ab0;}}')
        self.adjustSize();self.move(max(4,(w.width()-self.width())//2),5)
        pos=w.mapFromGlobal(QCursor.pos());focus=QApplication.focusWidget()
        active=(self.isVisible() and self.rect().contains(self.mapFromGlobal(QCursor.pos()))) or (focus and self.isAncestorOf(focus)) or QApplication.activePopupWidget()
        if 0<=pos.y()<=36 and 0<=pos.x()<w.width() or active:self.until=time.monotonic()+2
        self.setVisible(time.monotonic()<self.until)
        if self.isVisible():self.raise_()
