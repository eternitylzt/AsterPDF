"""Floating, virtualized document overview. Coordinates are independent of reader zoom."""
from collections import OrderedDict
from bisect import bisect_right
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QMenu, QInputDialog, QGraphicsOpacityEffect, QScrollBar
from .i18n import L


class DocumentMap(QWidget):
    HEADER = 26
    FOOTER = 22

    def __init__(self, tab):
        super().__init__(tab.scroll.viewport())
        self.tab = tab
        settings = tab.window.settings
        self.enabled = settings.value('minimap/enabled', True, type=bool)
        self.auto_scale=settings.value('minimap/auto_scale',not settings.contains('minimap/scale'),type=bool)
        self.page_count=tab.info['count']
        self.percent=(5. if self.page_count>20 else 10.) if self.auto_scale else max(.5,min(20.,settings.value('minimap/scale',10.,type=float)))
        self.corner = settings.value('minimap/corner', 'top-right')
        self.resize(settings.value('minimap/width', 148, type=int), settings.value('minimap/height', 370, type=int))
        self.auto_size=True  # Each newly opened document starts with its own fitted size.
        self.opacity=settings.value('minimap/opacity',80,type=int)
        effect=QGraphicsOpacityEffect(self);effect.setOpacity(self.opacity/100);self.setGraphicsEffect(effect)
        self.offset = 0.
        self.rail=QScrollBar(Qt.Vertical,self);self.rail.setStyleSheet('QScrollBar:vertical{background:rgba(80,120,150,35);width:9px;margin:0;border-radius:4px;} QScrollBar::handle:vertical{background:#64a9ba;min-height:18px;border-radius:4px;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}')
        self.rail.valueChanged.connect(self.scroll_preview)
        self.rects = []; self.starts = []; self.total = 1.
        self.signature = None; self.view_signature = None
        self.cache = OrderedDict(); self.cache_bytes = 0; self.pending = None; self.failed = set()
        self.generation = 0; self.drag = None; self.markers = []
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(120); self.timer.timeout.connect(self.sync); self.timer.start()
        self.setToolTip(L('点击跳转；拖动蓝框浏览；滚轮或按住右键拖动预览；边缘缩放；右键设置。',
                          'Click to jump; drag the blue viewport; wheel or right-drag to pan; resize at edges; right-click for settings.'))

    def scroll_preview(self,value):
        self.offset=float(value);self.update();self.request_visible()

    def toggle(self):
        self.enabled = not self.enabled
        self.tab.window.settings.setValue('minimap/enabled', self.enabled)
        self.sync();self.tab.sync_tool_states()

    def release(self):
        self.generation += 1
        if self.pending:self.pending.cancelled = True
        self.pending = None; self.cache.clear(); self.cache_bytes = 0; self.failed.clear()

    def body(self):
        return QRectF(5, self.HEADER, self.width()-10, max(1, self.height()-self.HEADER-self.FOOTER))

    def sync(self):
        t = self.tab
        if t.closed:
            self.timer.stop(); self.release(); self.hide(); return
        visible = self.enabled and t.isVisible() and t.scroll.isVisible() and not t.window.presentation
        self.setVisible(visible)
        if not visible:
            if self.cache or self.pending:self.release()
            return
        parent = self.parentWidget(); inset = getattr(t, 'reading_inset', 0)
        if self.page_count!=len(t.canvas.sizes):
            self.page_count=len(t.canvas.sizes)
            if self.auto_scale:self.percent=5. if self.page_count>20 else 10.
        # Physical screen changes arrive as logical viewport changes; stay inside it.
        if self.auto_size:
            scale=self.percent/100*96/72;columns=t.canvas.columns
            rows=[t.canvas.sizes[i:i+columns] for i in range(0,len(t.canvas.sizes),columns)]
            natural_width=max((sum(w for w,h in row)*scale+5*(len(row)-1) for row in rows),default=80)+26
            natural_height=sum(max(h for w,h in row)*scale+7 for row in rows)+self.HEADER+self.FOOTER+5
            self.resize(round(max(100,min(natural_width,parent.width()-20))),round(max(100,min(natural_height,(parent.height()-inset)*.8,parent.height()-inset-20))))
        width = min(max(100, self.width()), max(100, parent.width()-20))
        height = min(max(100, self.height()), max(100, parent.height()-inset-20))
        if (width,height) != (self.width(),self.height()):self.resize(width,height)
        x = 8 if self.corner.endswith('left') else max(0,parent.width()-self.width()-8)
        y = inset+8 if self.corner.startswith('top') else max(inset+8,parent.height()-self.height()-8)
        if not self.drag or self.drag[0] != 'resize':self.move(x,y)
        self.raise_()
        signature = (t.canvas.columns,t.document.revision, tuple(t.canvas.sizes), self.percent, self.width(), round(self.devicePixelRatioF(),3), t.night)
        if signature != self.signature:
            if getattr(self,'preserve_next',False):self.preserve_next=False
            else:self.release()
            self.signature = signature; self.rects = []; self.starts = []
            scale = self.percent/100 * 96/72
            self.rows=[list(range(i,min(i+t.canvas.columns,len(t.canvas.sizes)))) for i in range(0,len(t.canvas.sizes),t.canvas.columns)]
            widest=max((sum(t.canvas.sizes[i][0] for i in row) for row in self.rows),default=1)
            gap=5*(t.canvas.columns-1)
            scale=min(scale,(self.body().width()-16-gap)/widest)
            y=5.
            for row in self.rows:
                self.starts.append(y);row_width=sum(t.canvas.sizes[i][0]*scale for i in row)+5*(len(row)-1)
                x=(self.width()-row_width)/2
                for i in row:
                    w,h=t.canvas.sizes[i];self.rects.append(QRectF(x,y,w*scale,h*scale));x+=w*scale+5
                y+=max(t.canvas.sizes[i][1]*scale for i in row)+7
            self.total=y
        if self.auto_size:
            desired=round(max(80,min(self.total+self.HEADER+self.FOOTER,(parent.height()-inset)*.8,parent.height()-inset-20)))
            if self.height()!=desired:self.resize(self.width(),desired)
        canvas=t.canvas; vb=t.scroll.verticalScrollBar(); hb=t.scroll.horizontalScrollBar()
        current=(canvas.page,canvas.scale,canvas.columns,canvas.continuous,vb.value(),hb.value(),t.scroll.viewport().size(),getattr(t,'reading_inset',0))
        self.compute_markers()
        if current != self.view_signature and self.drag is None:
            self.view_signature = current
            if self.markers:
                focus=self.markers[0]
                if focus.top()<self.offset or focus.bottom()>self.offset+self.body().height():
                    self.offset = focus.center().y()-self.body().height()/2
        self.clamp_offset()
        from PySide6.QtCore import QSignalBlocker
        with QSignalBlocker(self.rail):
            self.rail.setGeometry(self.width()-12,self.HEADER,9,int(self.body().height()));self.rail.setRange(0,round(max(0,self.total-self.body().height())));self.rail.setPageStep(round(self.body().height()));self.rail.setValue(round(self.offset))
        self.rail.setVisible(self.rail.maximum()>0);self.rail.raise_()
        self.update(); self.request_visible()

    def preserve_pages(self,mapping,changed):
        if self.pending:self.pending.cancelled=True
        self.pending=None;self.generation+=1
        self.cache=OrderedDict((new,self.cache[old]) for new,old in enumerate(mapping) if old in self.cache and new not in changed)
        self.cache_bytes=sum(p.width()*p.height()*4 for p in self.cache.values());self.failed.clear();self.preserve_next=True;self.signature=None

    def clamp_offset(self):
        self.offset=max(0.,min(self.offset,max(0.,self.total-self.body().height())))

    def compute_markers(self):
        self.markers=[]
        canvas=self.tab.canvas; viewport=self.tab.scroll.viewport()
        origin=canvas.mapFrom(viewport,viewport.rect().topLeft())
        view=QRectF(origin.x(),origin.y()+getattr(self.tab,'reading_inset',0),viewport.width(),viewport.height()-getattr(self.tab,'reading_inset',0))
        for page,rect in enumerate(canvas.rects):
            if page>=len(self.rects) or rect.isEmpty() or not rect.intersects(view):continue
            hit=rect.intersected(view); mini=self.rects[page]
            self.markers.append(QRectF(mini.x()+(hit.x()-rect.x())/rect.width()*mini.width(),
                mini.y()+(hit.y()-rect.y())/rect.height()*mini.height(),
                hit.width()/rect.width()*mini.width(), max(3.,hit.height()/rect.height()*mini.height())))

    def visible_pages(self):
        if not self.rects:return []
        first=max(0,bisect_right(self.starts,self.offset)-1)
        last=min(len(self.rows),bisect_right(self.starts,self.offset+self.body().height())+1)
        return [p for row in self.rows[first:last] for p in row]

    def request_visible(self):
        if self.pending or self.tab.busy or not self.isVisible():return
        page=next((p for p in self.visible_pages() if p not in self.cache and p not in self.failed),None)
        if page is None:return
        generation=self.generation; width=self.rects[page].width()*self.devicePixelRatioF()
        scale=width/self.tab.canvas.sizes[page][0]; document=self.tab.document; night=self.tab.night
        def done(data):
            if self.tab.closed or generation!=self.generation:return
            pix=QPixmap();pix.loadFromData(data);self.cache[page]=pix;self.cache_bytes+=pix.width()*pix.height()*4
            while self.cache_bytes>8*1024*1024 and len(self.cache)>1:
                _,old=self.cache.popitem(last=False);self.cache_bytes-=old.width()*old.height()*4
            self.update()
        def failed(message):
            if generation==self.generation:self.failed.add(page);self.update()
        def finished():
            if generation==self.generation:self.pending=None
        self.pending=self.tab.queue.submit(lambda job:document.render(page,scale,night=night,max_pixels=1_000_000),done,failed,finished,priority=-3)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform)
        dark=self.tab.dark
        p.setPen(QPen(QColor('#7186a4' if dark else '#8c9fb9'),1));p.setBrush(QColor('#202c3a' if dark else '#f2f6fc'));p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),6,6)
        p.setPen(QColor('#e2ebf8' if dark else '#243d60'))
        p.drawText(QRectF(10,2,self.width()-38,22),Qt.AlignVCenter,L('速览窗','Overview'))
        p.drawText(QRectF(self.width()-27,2,22,22),Qt.AlignCenter,'×')
        p.save();p.setClipRect(self.body());p.translate(0,self.HEADER-self.offset)
        for page in self.visible_pages():
            rect=self.rects[page];p.fillRect(rect,Qt.white)
            if page in self.cache:p.drawPixmap(rect,self.cache[page],QRectF(self.cache[page].rect()))
            else:
                p.setPen(QColor('#66778c'));p.drawText(rect,Qt.AlignCenter,('!' if page in self.failed else str(page+1)))
        # Oversized translucent match bands remain visible at tiny preview scales.
        for page in self.visible_pages():
            mini=self.rects[page];height=self.tab.canvas.sizes[page][1]
            rows=set(round((rect[1]+rect[3])/2/height*mini.height()) for rect in self.tab.canvas.search_hits.get(page,[]))
            for y in rows:
                for spread,alpha in ((5,50),(3,110),(1.5,230)):
                    p.fillRect(QRectF(mini.x()-1,mini.y()+y-spread,mini.width()+2,spread*2),QColor(248,255,20,alpha))
        p.setPen(QPen(QColor('#2389ed'  if dark else '#006ee6'),2));p.setBrush(QColor(25,126,245,66))
        for rect in self.markers:p.drawRect(rect)
        p.restore()
        p.setPen(QColor('#a9bbd2' if dark else '#475f80'))
        p.drawText(QRectF(6,self.height()-self.FOOTER,self.width()-12,self.FOOTER),Qt.AlignCenter,f'{self.tab.canvas.page+1} / {len(self.rects)} · {self.reading_progress():.0f}%')

    def reading_progress(self):
        if not self.rects:return 0.
        progress=self.tab.canvas.page/len(self.rects)
        for marker in self.markers:
            for page,rect in enumerate(self.rects):
                if rect.intersects(marker):
                    fraction=max(0.,min(1.,(marker.bottom()-rect.top())/rect.height()))
                    progress=max(progress,(page+fraction)/len(self.rects))
        return min(100.,progress*100)

    def document_point(self,point):
        return QPointF(point.x(),point.y()-self.HEADER+self.offset)

    def seek(self,point,center=True):
        if not self.rects:return
        if self.tab.inline_editor:
            if self.tab.inline_dirty():
                self.drag=None;self.tab.leave_inline(lambda:self.seek(point,center));return
            self.tab.cancel_inline()
        row=self.rows[max(0,min(len(self.rows)-1,bisect_right(self.starts,point.y())-1))]
        page=min(row,key=lambda i:abs(self.rects[i].center().x()-point.x()));mini=self.rects[page]
        fx=max(0.,min(1.,(point.x()-mini.x())/mini.width()));fy=max(0.,min(1.,(point.y()-mini.y())/mini.height()))
        t=self.tab
        if not t.canvas.continuous and t.canvas.page!=page:t.goto(page)
        rect=t.canvas.rects[page];viewport=t.scroll.viewport();inset=getattr(t,'reading_inset',0)
        t.scroll.verticalScrollBar().setValue(round(rect.y()+fy*rect.height()-(inset+(viewport.height()-inset)/2 if center else inset)))
        t.scroll.horizontalScrollBar().setValue(round(rect.x()+fx*rect.width()-(viewport.width()/2 if center else 0)))
        t.canvas.update_current();self.compute_markers();self.update()

    def edges(self,pos):
        return (pos.x()<6,pos.x()>self.width()-6,pos.y()<5,pos.y()>self.height()-5)

    def mousePressEvent(self,event):
        pos=event.position()
        if event.button()==Qt.RightButton:
            self.drag=('pan',pos,self.offset,False);event.accept();return
        if event.button()!=Qt.LeftButton:return
        if pos.y()<self.HEADER and pos.x()>self.width()-29:self.enabled=True;self.toggle();return
        edges=self.edges(pos)
        if any(edges):self.auto_size=False;self.drag=('resize',event.globalPosition(),self.geometry(),edges);return
        if pos.y()<self.HEADER:return
        point=self.document_point(pos)
        marker=next((r for r in self.markers if r.adjusted(-3,-3,3,3).contains(point)),None)
        if marker:self.drag=('viewport',point-marker.topLeft())
        else:self.seek(point);self.drag=('viewport',QPointF())
        self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self,event):
        pos=event.position()
        if self.drag:
            kind=self.drag[0]
            if kind=='pan':
                _,start,offset,moved=self.drag;delta=pos-start
                self.drag=('pan',start,offset,moved or delta.manhattanLength()>4)
                self.offset=offset-delta.y();self.clamp_offset();self.update();self.request_visible();self.setCursor(Qt.ClosedHandCursor)
            elif kind=='viewport':
                if pos.y()<self.HEADER+10:self.offset-=8
                elif pos.y()>self.height()-self.FOOTER-10:self.offset+=8
                self.clamp_offset();self.seek(self.document_point(pos)-self.drag[1],center=False)
            elif kind=='resize':
                _,start,rect,edges=self.drag;delta=event.globalPosition()-start;left,right,top,bottom=edges
                width=max(100,min(self.parentWidget().width()-16,rect.width()+round(delta.x())*(1 if right else -1 if left else 0)))
                height=max(140,min(self.parentWidget().height()-getattr(self.tab,'reading_inset',0)-16,rect.height()+round(delta.y())*(1 if bottom else -1 if top else 0)))
                self.resize(width,height)
                if left:self.move(rect.right()-width+1,self.y())
                if top:self.move(self.x(),rect.bottom()-height+1)
            return
        left,right,top,bottom=self.edges(pos)
        cursor=Qt.SizeFDiagCursor if (left and top) or (right and bottom) else Qt.SizeBDiagCursor if (left and bottom) or (right and top) else Qt.SizeHorCursor if left or right else Qt.SizeVerCursor if top or bottom else Qt.OpenHandCursor if any(r.contains(self.document_point(pos)) for r in self.markers) else Qt.PointingHandCursor
        self.setCursor(cursor)

    def mouseReleaseEvent(self,event):
        drag=self.drag;self.drag=None;self.unsetCursor()
        if drag and drag[0]=='pan' and not drag[3]:self.menu(event.globalPosition().toPoint())
        if drag and drag[0]=='resize':
            self.auto_size=False  # Manual resize belongs only to this open document.
        self.view_signature=None if drag and drag[0]=='viewport' else self.view_signature
        self.sync()

    def contextMenuEvent(self,event):event.accept()  # Right-drag must not open the native context menu.

    def wheelEvent(self,event):
        if event.modifiers()&Qt.ControlModifier:
            self.set_scale(self.percent+(event.angleDelta().y()/120 if event.angleDelta().y() else event.pixelDelta().y()/40));event.accept();return
        self.offset-=(event.pixelDelta().y() or event.angleDelta().y()/2);self.clamp_offset();self.update();self.request_visible();event.accept()

    def menu(self,global_pos):
        menu=QMenu(self)
        for key,label in [('top-right',L('右上角','Top right')),('bottom-right',L('右下角','Bottom right')),('top-left',L('左上角','Top left')),('bottom-left',L('左下角','Bottom left'))]:
            action=menu.addAction(label);action.setCheckable(True);action.setChecked(self.corner==key);action.triggered.connect(lambda checked=False,k=key:self.set_corner(k))
        menu.addSeparator();menu.addAction(L('缩略比例…','Preview scale…'),self.scale_dialog)
        auto=menu.addAction(L('按页数自动缩放（20 页以上 5%）','Automatic scale (5% above 20 pages)'));auto.setCheckable(True);auto.setChecked(self.auto_scale);auto.toggled.connect(self.set_auto_scale)
        menu.addAction(L('透明度…','Opacity…'),self.opacity_dialog)
        menu.addAction(L('自动适应窗口大小','Fit overview size'),lambda:(setattr(self,'auto_size',True),self.sync()))
        menu.addAction(L('跟随当前阅读位置','Follow reading position'),lambda:(setattr(self,'view_signature',None),self.sync()))
        menu.addAction(L('关闭速览窗','Close overview'),self.toggle);menu.exec(global_pos)

    def set_corner(self,corner):
        self.corner=corner;self.tab.window.settings.setValue('minimap/corner',corner);self.sync()

    def set_auto_scale(self,enabled):
        self.auto_scale=enabled;self.tab.window.settings.setValue('minimap/auto_scale',enabled)
        if enabled:self.percent=5. if len(self.tab.canvas.sizes)>20 else 10.
        self.view_signature=None;self.sync()

    def scale_dialog(self):
        value,ok=QInputDialog.getDouble(self,L('缩略比例','Preview scale'),L('比例（%；默认 20 页以内 10%，超过 20 页 5%）','Scale (%; default 10% up to 20 pages, 5% above 20)'),self.percent,.5,20,1)
        if ok:self.set_scale(value)

    def set_scale(self,value):
        self.auto_scale=False;self.percent=max(.5,min(20.,round(value,2)))
        self.tab.window.settings.setValue('minimap/auto_scale',False);self.tab.window.settings.setValue('minimap/scale',self.percent);self.view_signature=None;self.sync()

    def opacity_dialog(self):
        value,ok=QInputDialog.getInt(self,L('速览窗透明度','Overview opacity'),L('不透明度（%）','Opacity (%)'),self.opacity,20,100)
        if ok:
            self.tab.window.settings.setValue('minimap/opacity',value)
            for tab in self.tab.window.document_tabs():tab.minimap.opacity=value;tab.minimap.graphicsEffect().setOpacity(value/100)
