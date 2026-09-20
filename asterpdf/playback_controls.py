"""A bounded, topmost in-window media strip. Its grip resizes only the strip."""
from PySide6.QtCore import Qt,QSignalBlocker,QTimer,QSize
from PySide6.QtWidgets import QFrame,QHBoxLayout,QToolButton,QLabel,QSpinBox,QDoubleSpinBox,QComboBox,QWidget,QScrollArea
from .i18n import L,tr
from .ui_icons import icon

class WidthGrip(QWidget):
    def __init__(self,panel):
        super().__init__(panel);self.panel=panel;self.start=None;self.setFixedWidth(12);self.setCursor(Qt.SizeHorCursor);self.setToolTip(L('拖动调整控件宽度','Drag to resize controls'))
    def paintEvent(self,event):
        from PySide6.QtGui import QPainter,QPen,QColor
        p=QPainter(self);p.setPen(QPen(QColor('#718ba7'),2))
        for x in (4,8):p.drawLine(x,8,x,self.height()-8)
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:self.start=(e.globalPosition().x(),self.panel.width());e.accept()
    def mouseMoveEvent(self,e):
        if self.start:
            bounds=self.panel.bounds();width=max(220,min(bounds.right()-self.panel.x()+1,self.start[1]+int(e.globalPosition().x()-self.start[0])))
            self.panel.resize(width,self.panel.height());e.accept()
    def mouseReleaseEvent(self,e):self.start=None;e.accept()

class PlaybackControls(QFrame):
    def __init__(self,tab):
        super().__init__(tab.window);self.tab=tab;self.drag=None;self.placed=False;self.requested=False
        tab.destroyed.connect(self.deleteLater)
        self.setObjectName('playbackControls');self.setFrameShape(QFrame.StyledPanel);self.setAutoFillBackground(True)
        outer=QHBoxLayout(self);outer.setContentsMargins(5,3,2,3);outer.setSpacing(3)
        self.handle=QLabel('⠿');self.handle.setCursor(Qt.SizeAllCursor);self.handle.setAttribute(Qt.WA_TransparentForMouseEvents);outer.addWidget(self.handle)
        area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QFrame.NoFrame);area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);outer.addWidget(area,1)
        content=QWidget();content.setObjectName('playbackContent');row=QHBoxLayout(content);row.setContentsMargins(2,1,2,1);row.setSpacing(7);area.setWidget(content)
        self.choice=QComboBox();self.choice.setMinimumWidth(85);self.choice.setMaximumWidth(130);row.addWidget(self.choice);self.choice.currentIndexChanged.connect(lambda n:tab.media_choice.setCurrentIndex(n))
        def button(key,hint,callback):
            b=QToolButton();b.setIcon(icon(key,tab.dark));b.setIconSize(QSize(21,21));b.setToolTip(hint);b.setCursor(Qt.PointingHandCursor);b.clicked.connect(callback);row.addWidget(b);return b
        self.play=button('media_play',L('播放','Play'),tab.play_selected);button('replay',L('重播','Replay'),tab.replay)
        button('minus',L('减速','Slower'),lambda:self.command('Minus'));self.reset=button('reset_speed',L('默认速度','Default speed'),lambda:self.command('Reset'));button('plus',L('加速','Faster'),lambda:self.command('Plus'))
        row.addWidget(QLabel(L('帧','Frame')));self.frame=QSpinBox();self.frame.setRange(1,999999);self.frame.setKeyboardTracking(False);self.frame.setMaximumWidth(75);self.frame.valueChanged.connect(tab.seek_frame);row.addWidget(self.frame)
        self.rate_label=QLabel(L('播放速率','Rate'));row.addWidget(self.rate_label);self.fps=QDoubleSpinBox();self.fps.setRange(.1,240);self.fps.setDecimals(1);self.fps.setSuffix(' fps');self.fps.setKeyboardTracking(False);self.fps.setMaximumWidth(100);self.fps.valueChanged.connect(self.rate);row.addWidget(self.fps)
        close=QToolButton();close.setIcon(icon('close',tab.dark));close.setToolTip(tr('close'));close.clicked.connect(self.dismiss);outer.addWidget(close);outer.addWidget(WidthGrip(self))
        self.resize(680,62);self.setMinimumWidth(220)
        background='#1a2636' if tab.dark else '#f4f7fb'
        self.setStyleSheet('QFrame#playbackControls{border:1px solid #718ba7;border-radius:5px;background:'+background+';} QWidget#playbackContent{background:'+background+';}QToolButton:hover{background:#6686aa;}QToolButton:pressed{background:#4569b0;}')
        self.timer=QTimer(self);self.timer.setInterval(150);self.timer.timeout.connect(self.sync);self.timer.start();self.hide()
    def bounds(self):
        return self.parentWidget().rect().adjusted(4,self.tab.window.menuBar().height()+3,-4,-4)
    def dismiss(self):self.requested=False;self.hide()
    def present(self):self.requested=True;self.sync();self.reposition()
    def video(self):
        data=self.tab.media_choice.currentData()
        if data and data[0]=='media':
            asset=self.tab.assets[data[1]]
            return next((v for v in self.tab.video_players if v.asset==asset),None)
    def command(self,cmd):
        p=self.tab.chosen_player()
        if p:p.command(cmd)
        else:
            v=self.video()
            if v:v.player.setPlaybackRate(1 if cmd=='Reset' else max(.1,min(8,v.player.playbackRate()*(1.25 if cmd=='Plus' else .8))))
        self.sync()
    def rate(self,value):
        p=self.tab.chosen_player()
        if p:
            p.speed=value/max(.1,p.animation.fps)
            if p.playing:p.start()
        else:
            v=self.video()
            if v:v.player.setPlaybackRate(value)
        self.sync()
    def sync(self):
        t=self.tab
        if t.closed:self.dismiss();self.timer.stop();return
        if t.window.presentation:self.requested=False
        visible=self.requested and t.window.current() is t and not t.window.presentation
        self.setVisible(visible)
        if not visible:return
        with QSignalBlocker(self.choice):
            if self.choice.count()!=t.media_choice.count():
                self.choice.clear()
                for n in range(t.media_choice.count()):self.choice.addItem(t.media_choice.itemText(n))
            self.choice.setCurrentIndex(t.media_choice.currentIndex())
        p=t.chosen_player();v=self.video();self.fps.setEnabled(bool(p or v));self.frame.setEnabled(bool(p))
        if not self.fps.hasFocus():
            with QSignalBlocker(self.fps):
                self.fps.setSuffix(' fps' if p else ' ×');self.fps.setMaximum(240 if p else 8)
                self.fps.setValue(p.animation.fps*p.speed if p else v.player.playbackRate() if v else 1)
        if p and not self.frame.hasFocus():
            with QSignalBlocker(self.frame):self.frame.setMaximum(len(p.animation.frames));self.frame.setValue(p.index+1)
        playing=p.playing if p else bool(v and v.want_playing)
        if getattr(self,'_play_state',None)!=(playing,t.dark):
            self._play_state=(playing,t.dark);self.play.setIcon(icon('media_pause' if playing else 'media_play',t.dark))
        self.play.setToolTip(L('暂停','Pause') if playing else L('播放','Play'))
        self.reposition()
    def reposition(self):
        bounds=self.bounds()
        self.resize(min(self.width(),max(220,bounds.width())),self.height())
        if not self.placed:
            self.move(max(bounds.left(),(bounds.width()-self.width())//2),max(bounds.top(),self.tab.mapTo(self.parentWidget(),self.tab.rect().topLeft()).y()+getattr(self.tab,'reading_inset',0)+4));self.placed=True
        self.move(max(bounds.left(),min(self.x(),bounds.right()-self.width()+1)),max(bounds.top(),min(self.y(),bounds.bottom()-self.height()+1)))
        self.raise_()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:self.drag=(e.globalPosition().toPoint(),self.pos());e.accept()
    def mouseMoveEvent(self,e):
        if self.drag is not None:self.move(self.drag[1]+e.globalPosition().toPoint()-self.drag[0]);self.reposition();e.accept()
    def mouseReleaseEvent(self,e):self.drag=None;e.accept()
