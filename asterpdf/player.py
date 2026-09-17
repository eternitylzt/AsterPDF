import time
from collections import OrderedDict
from PySide6.QtCore import QObject, QTimer, Signal, QUrl, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QSlider, QHBoxLayout
from . import media
from .i18n import tr, L


class AnimationPlayer(QObject):
    changed = Signal()
    def __init__(self,tab,animation):
        super().__init__(tab)
        self.tab,self.animation=tab,animation;self.filename=None;self.renderer=None
        self.index=0;self.direction=1;self.loop=tab.window.settings.value('animation/loop',True,type=bool);self.speed=tab.window.settings.value('animation/speed',1.,type=float);self.playing=False
        self.preparing=self.pending=False;self.cache=OrderedDict();self.cache_bytes=0;self.cache_limit=32*1024*1024
        self.rendered_frames=0;self.requests={};self.epoch=0;self.wanted=0;self.displayed_times=[];self.deadline=0;self.skipped_frames=0
        self.timer=QTimer(self);self.timer.setTimerType(Qt.PreciseTimer);self.timer.timeout.connect(self.tick)

    def prepare(self):
        if self.filename or self.preparing:return
        self.preparing=True;epoch=self.epoch
        def done(filename):
            self.preparing=False
            if self.tab.closed or epoch!=self.epoch:return
            from .rendering import FrameRenderer
            self.filename=filename;self.renderer=FrameRenderer(filename);self.show_frame(self.index)
            if self.playing:self.start()
        def error(message):self.preparing=False;self.stop();self.tab.error(message)
        self.tab.queue.submit(lambda j:media.prepare_animation(self.tab.document,self.animation),done,error)

    def interval(self):
        rates=self.animation.variable_fps
        fps=rates[self.index] if self.index<len(rates) and rates[self.index]>0 else self.animation.fps
        return max(4,round(1000/(fps*self.speed)))

    def start(self):
        self.playing=True
        if not self.filename:self.prepare();return
        if self.pending or (self.wanted,self.width()) not in self.cache:self.show_frame(self.wanted)
        self.deadline=time.monotonic()+self.interval()/1000;self.timer.start(min(16,self.interval()));self.warm_ahead();self.changed.emit()

    def stop(self):
        self.playing=False;self.timer.stop();self.changed.emit()

    def toggle(self):
        if self.playing:self.stop();self.show_frame(self.index)
        else:self.start()

    def tick(self):
        if self.pending or not self.playing:return
        now=time.monotonic();n=self.index;steps=0
        # Wall-clock pacing keeps speed and reverse consistent even when a
        # complex frame takes longer to render. Late frames are skipped.
        while self.deadline<=now and steps<1000:
            n+=self.direction;steps+=1
            if not 0<=n<len(self.animation.frames):
                if self.loop:n%=len(self.animation.frames)
                else:self.stop();return
            rates=self.animation.variable_fps
            fps=rates[n] if n<len(rates) and rates[n]>0 else self.animation.fps
            self.deadline+=max(.004,1/(fps*self.speed))
        if steps:
            self.skipped_frames+=max(0,steps-1);self.show_frame(n)

    def width(self):
        native=max(16,round((self.animation.rect[2]-self.animation.rect[0])*self.tab.canvas.scale*self.tab.canvas.devicePixelRatioF()))
        quality=self.tab.window.settings.value('animation/quality','auto')
        return min(native,1280 if quality=='auto' else 960) if self.playing and quality!='native' else native

    def show_frame(self,index):
        self.wanted=max(0,min(index,len(self.animation.frames)-1))
        if not self.filename:self.prepare();return
        key=(self.wanted,self.width())
        if key in self.cache:
            self.index=self.wanted;self.cache.move_to_end(key);self.pending=False;self.display(self.cache[key]);self.warm_ahead();return
        self.pending=True;self.request_frame(*key)

    def request_frame(self,index,width):
        key=(index,width)
        if key in self.requests or key in self.cache or self.tab.closed:return
        epoch=self.epoch
        def done(image):
            self.requests.pop(key,None)
            if self.tab.closed or epoch!=self.epoch:return
            pix=QPixmap.fromImage(image);self.cache[key]=pix;self.cache_bytes+=pix.width()*pix.height()*4
            while self.cache_bytes>self.cache_limit and len(self.cache)>1:
                _,old=self.cache.popitem(last=False);self.cache_bytes-=old.width()*old.height()*4
            if index==self.wanted and width==self.width():
                self.index=index;self.pending=False;self.display(pix)
            self.warm_ahead()
        def error(message):
            self.requests.pop(key,None);self.pending=False;self.stop()
            if not self.tab.closed:self.tab.error(message)
        renderer=self.renderer
        self.requests[key]=self.tab.queue.submit(lambda j:renderer.image(index,width),done,error,priority=2 if index==self.wanted else -2)

    def warm_ahead(self):
        if not self.playing or not self.filename or len(self.requests)>=1:return
        for step in (1,):
            n=self.index+self.direction*step
            if self.loop:n%=len(self.animation.frames)
            if 0<=n<len(self.animation.frames):self.request_frame(n,self.width())

    def display(self,pix):
        import time
        self.rendered_frames+=1;self.displayed_times.append(time.monotonic());self.displayed_times=self.displayed_times[-120:]
        self.tab.canvas.frame_pixmaps[(self.animation.page,self.animation.key)]=pix
        self.tab.canvas.update(self.tab.canvas.page_rect(self.animation.page,self.animation.rect).toAlignedRect())
        if self.playing:self.timer.setInterval(min(16,self.interval()))
        self.changed.emit()

    def resolution_changed(self):
        self.epoch+=1
        for job in self.requests.values():job.cancelled=True
        self.requests.clear();self.cache.clear();self.cache_bytes=0;self.pending=False
        if self.filename and not self.tab.closed:self.show_frame(self.index)

    def release(self):
        self.stop();self.epoch+=1;self.preparing=False
        for job in self.requests.values():job.cancelled=True
        self.requests.clear();self.cache.clear();self.cache_bytes=0;self.pending=False
        renderer=self.renderer;self.renderer=None;self.filename=None
        if renderer:self.tab.queue.submit(lambda j:renderer.close(),priority=-4)

    def command(self,command):
        if command.startswith(('Play','Pause')):
            direction=-1 if command.endswith('Left') else 1
            if command.startswith('Pause'):self.stop();self.show_frame(self.index);return
            same=self.direction==direction
            self.direction=direction
            if command.startswith('PlayPause') and self.playing and same:self.stop();self.show_frame(self.index)
            else:self.start()
        elif command in ('EndLeft','EndRight','StepLeft','StepRight'):
            self.stop();n={'EndLeft':0,'EndRight':len(self.animation.frames)-1,'StepLeft':self.index-1,'StepRight':self.index+1}[command];self.show_frame(n)
        elif command in ('Plus','Minus','Reset'):
            self.speed=1 if command=='Reset' else max(.125,min(8,self.speed*(1.25 if command=='Plus' else .8)))
            if self.playing:self.start()


class VideoPlayer(QWidget):
    def __init__(self, tab, asset, filename):
        super().__init__(tab.canvas)
        # Lazy imports keep multimedia initialization out of ordinary startup.
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.asset, self.tab = asset, tab
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.65)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget(self)
        self.player.setVideoOutput(self.video)
        self.actual_video_frames = 0
        self.video.videoSink().videoFrameChanged.connect(self.frame_received)
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(2)
        if asset.kind == 'video': layout.addWidget(self.video, 1)
        else: layout.addWidget(QLabel('♫  '+asset.name))
        controls = QHBoxLayout(); layout.addLayout(controls)
        play = QPushButton('▶ / Ⅱ'); controls.addWidget(play)
        play.clicked.connect(lambda: self.player.pause() if self.player.playbackState() == QMediaPlayer.PlayingState else self.player.play())
        replay = QPushButton('↺'); controls.addWidget(replay)
        replay.clicked.connect(lambda: (self.player.setPosition(0), self.player.play()))
        self.slider = QSlider(Qt.Horizontal); controls.addWidget(self.slider, 1)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.player.durationChanged.connect(lambda d: self.slider.setRange(0, d))
        self.player.positionChanged.connect(lambda n: self.slider.setValue(n) if not self.slider.isSliderDown() else None)
        loop = QPushButton('∞'); loop.setCheckable(True); controls.addWidget(loop)
        loop.toggled.connect(lambda b: self.player.setLoops(QMediaPlayer.Infinite if b else QMediaPlayer.Once))
        close = QPushButton('×'); controls.addWidget(close); close.clicked.connect(self.shutdown)
        self.message = QLabel(''); self.message.setWordWrap(True); layout.addWidget(self.message)
        self.player.errorOccurred.connect(lambda e, msg: self.message.setText(L('播放失败：','Playback failed')+msg))
        self.player.setSource(QUrl.fromLocalFile(filename))
        self.setStyleSheet('VideoPlayer {background:#101822;} QPushButton {padding:3px;}')
        self.show(); self.player.play()

    def frame_received(self, frame):
        if frame.isValid(): self.actual_video_frames += 1

    def shutdown(self):
        self.player.stop(); self.player.setSource(QUrl()); self.hide()
