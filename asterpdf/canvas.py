from __future__ import annotations
from collections import OrderedDict
import math
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSize, QTimer, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QFont, QPolygonF, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QWidget, QScrollArea, QToolTip
from .i18n import tr, L


def qrect(rect):
    return QRectF(rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1])


class Canvas(QWidget):
    selection = Signal(int, object, str)
    pageChanged = Signal(int)
    objectSelected = Signal(object)
    objectMoved = Signal(float, float)
    mediaClick = Signal(int, object)
    clicked = Signal(int, object)

    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.scale = 1.2
        self.continuous = True
        self.columns = 1
        self.laying_out = False
        self.fallback = {}
        self.cache_bytes=0;self.cache_limit=64*1024*1024;self.last_dpr=self.devicePixelRatioF();self.render_jobs={}
        self.pan_anchor = None
        self.resizing = False
        self.page = 0
        self.sizes = []
        self.rects = []
        self.cache = OrderedDict()
        self.pending = set()
        self.failed = {}
        self.generation = 0
        self.mode = 'select'
        self.drag_page = -1
        self.points = []
        self.drag_objects = False
        self.region = None
        self.word_selection = []
        self.words = {}
        self.search_hits = {}
        self.objects = []
        self.object_page = -1
        self.selected = []
        self.frame_pixmaps = {}
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def invalidate(self, full=True):
        self.generation += 1
        # Retain only tiny temporary previews during an edit, never a second
        # full-resolution page cache.
        if self.cache:
            self.fallback={k[1:]: (v[0].scaled(256,256,Qt.KeepAspectRatio,Qt.SmoothTransformation),v[1],v[2],v[0].width(),v[0].height()) for k,v in self.cache.items()}
        for job in self.render_jobs.values():job.cancelled=True
        self.render_jobs.clear();self.cache.clear();self.cache_bytes=0;self.pending.clear();self.failed.clear()
        if full:
            self.words.clear(); self.objects = []; self.selected = []
            self.word_selection = []; self.search_hits = {}; self.region = None
            self.frame_pixmaps.clear()
        self.update()

    def invalidate_page(self,page):
        """Keep other pages and sharp visible tiles while one page is updated."""
        self.generation+=1
        for job in self.render_jobs.values():job.cancelled=True
        self.render_jobs.clear();self.pending.clear();self.failed.clear();self.fallback.clear()
        retained=OrderedDict();budget=24*1024*1024
        for key,value in self.cache.items():
            pix,x,y=value
            if key[1]!=page:retained[(self.generation,)+key[1:]]=value
            elif budget>=pix.width()*pix.height()*4:
                self.fallback[key[1:]]=(pix,x,y,pix.width(),pix.height());budget-=pix.width()*pix.height()*4
        self.cache=retained;self.cache_bytes=sum(p.width()*p.height()*4 for p,_,_ in retained.values())
        self.words.pop(page,None);self.word_selection=[];self.update()

    def remap_pages(self,mapping,changed=()):
        """Retain sharp tiles belonging to unchanged physical pages."""
        self.generation+=1
        for job in self.render_jobs.values():job.cancelled=True
        self.render_jobs.clear();self.pending.clear();self.failed.clear();self.fallback.clear()
        reverse={old:new for new,old in enumerate(mapping) if old is not None};changed=set(changed);retained=OrderedDict()
        for key,value in self.cache.items():
            if key[1] not in reverse:continue
            page=reverse[key[1]];newkey=(self.generation,page)+key[2:]
            if page not in changed:retained[newkey]=value
            else:
                pix,x,y=value;self.fallback[newkey[1:]]=(pix,x,y,pix.width(),pix.height())
        self.cache=retained;self.cache_bytes=sum(p.width()*p.height()*4 for p,_,_ in retained.values())
        self.words={reverse[p]:v for p,v in self.words.items() if p in reverse and reverse[p] not in changed}
        self.objects=[];self.selected=[];self.word_selection=[];self.search_hits={};self.region=None
        self.frame_pixmaps.clear();self.update()

    def layout_pages(self):
        self.laying_out = True
        available = max(100, self.tab.scroll.viewport().width())
        cols = self.columns
        rows = [list(range(i, min(i+cols, len(self.sizes)))) for i in range(0, len(self.sizes), cols)]
        if not self.continuous:
            rows = [row for row in rows if self.page in row]
        width = max(available, int(max((sum(self.sizes[i][0]*self.scale for i in row)+16*(len(row)-1) for row in rows), default=600)+32))
        self.rects = [QRectF() for _ in self.sizes]
        inset=getattr(self.tab,'reading_inset',0)
        viewport_height=self.tab.scroll.viewport().height()
        y = inset+16
        if not self.continuous and rows:
            height=max(self.sizes[i][1]*self.scale for i in rows[0])
            y=inset+max(16,(viewport_height-inset-height)/2)
        for row in rows:
            rowwidth = sum(self.sizes[i][0]*self.scale for i in row)+16*(len(row)-1)
            x = (width-rowwidth)/2
            for i in row:
                w,h = self.sizes[i]
                self.rects[i] = QRectF(x,y,w*self.scale,h*self.scale)
                x += w*self.scale+16
            y += max(self.sizes[i][1]*self.scale for i in row)+28
        self.resize(width, max(int(y if self.continuous else max((r.bottom()+16 for r in self.rects),default=0)), viewport_height))
        self.laying_out = False
        self.tab.position_video()
        self.tab.position_inline()
        self.tab.scroll.sync_document_bar()
        self.update()

    def locate(self, point):
        point=QPointF(point)
        for i, rect in enumerate(self.rects):
            if rect.contains(point):
                return i, (point-rect.topLeft()) / self.scale
        return -1, QPointF()

    def page_rect(self, page, rect):
        r = qrect(rect)
        origin = self.rects[page].topLeft()
        return QRectF(origin + r.topLeft()*self.scale, r.size()*self.scale)

    def release_cache(self):
        self.generation+=1
        for job in self.render_jobs.values():job.cancelled=True
        self.render_jobs.clear();self.cache.clear();self.cache_bytes=0;self.pending.clear();self.fallback.clear();self.frame_pixmaps.clear()

    def event(self,event):
        if event.type()==QEvent.DevicePixelRatioChange and hasattr(self,'cache'):
            self.last_dpr=self.devicePixelRatioF();self.invalidate(False)
            for player in self.tab.players.values():player.resolution_changed()
            QTimer.singleShot(0,self.tab.screen_zoom_changed)
        return super().event(event)

    def tile_key(self,page,column,row):
        return (self.generation,page,round(self.scale,5),round(self.devicePixelRatioF(),5),self.tab.night,column,row)

    def request_page(self,page,column=0,row=0):
        key=self.tile_key(page,column,row)
        if self.tab.closed or key in self.cache or key in self.pending or key in self.failed:return
        self.pending.add(key);generation=self.generation
        scale=self.scale*self.devicePixelRatioF();width,height=self.sizes[page]
        clip=(column*1024/scale,row*1024/scale,min(width,(column+1)*1024/scale),min(height,(row+1)*1024/scale))
        hidden=[x for a in self.tab.animations for x in a.hide]
        def finished(result):
            self.pending.discard(key);self.render_jobs.pop(key,None)
            if generation!=self.generation or self.tab.closed:return
            image,x,y=result;pix=QPixmap.fromImage(image)
            self.cache[key]=(pix,x,y);self.cache_bytes+=pix.width()*pix.height()*4
            while self.cache_bytes>self.cache_limit and len(self.cache)>1:
                _,entry=self.cache.popitem(last=False);self.cache_bytes-=entry[0].width()*entry[0].height()*4
            self.fallback.pop(key[1:],None);self.update()
            if not any(k[1]==page for k in self.pending):self.pending_annotation=None
        def error(message):
            self.pending.discard(key);self.render_jobs.pop(key,None)
            if generation==self.generation:self.failed[key]=message;self.update()
        show_annotations=self.tab.show_annotations.isChecked()
        self.render_jobs[key]=self.tab.queue.submit(lambda j:self.tab.document.render_tile(page,scale,clip,self.tab.night,hidden,show_annotations),finished,error,priority=3)

    def paint_page(self,painter,page,rect,exposed):
        dpr=self.devicePixelRatioF()
        if abs(dpr-self.last_dpr)>.001:
            self.last_dpr=dpr;self.invalidate(False)
        visible=exposed.intersected(rect)
        if visible.isEmpty():return
        left=max(0,math.floor((visible.left()-rect.left())*dpr/1024))
        top=max(0,math.floor((visible.top()-rect.top())*dpr/1024))
        right=math.ceil((visible.right()-rect.left())*dpr/1024)
        bottom=math.ceil((visible.bottom()-rect.top())*dpr/1024)
        painter.save();painter.setClipRect(rect)
        for row in range(top,bottom):
            for column in range(left,right):
                key=self.tile_key(page,column,row);entry=self.cache.get(key)
                if entry:
                    self.cache.move_to_end(key);pix,x,y=entry
                    target=QRectF(rect.left()+x/dpr,rect.top()+y/dpr,pix.width()/dpr,pix.height()/dpr)
                    painter.drawPixmap(target,pix,QRectF(pix.rect()))
                else:
                    self.request_page(page,column,row);old=self.fallback.get(key[1:])
                    if old:
                        pix,x,y,w,h=old;painter.drawPixmap(QRectF(rect.left()+x/dpr,rect.top()+y/dpr,w/dpr,h/dpr),pix,QRectF(pix.rect()))
                    elif key in self.failed:
                        painter.setPen(QColor('#a85050'));painter.drawText(visible,Qt.AlignCenter|Qt.TextWordWrap,self.failed[key])
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor('#111923' if self.tab.dark else '#e9edf2'))
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        visible = []
        for i, rect in enumerate(self.rects):
            if rect.isEmpty() or not rect.intersects(QRectF(event.rect())):
                continue
            visible.append(i)
            painter.fillRect(rect.translated(0, 3), QColor(0, 0, 0, 22))
            painter.fillRect(rect, QColor('#18202c' if self.tab.night else 'white'))
            self.paint_page(painter,i,rect,QRectF(event.rect()))
            painter.setPen(QColor('#8190a4'))
            painter.drawText(QRectF(rect.x(), rect.bottom()+3, rect.width(), 22), Qt.AlignCenter, str(i+1))
            for a in self.tab.animations:
                if a.page == i:
                    frame = self.frame_pixmaps.get((a.page, a.key))
                    if frame:
                        r = self.page_rect(i, a.rect)
                        painter.drawPixmap(r, frame, QRectF(frame.rect()))
                    else:
                        r = self.page_rect(i, a.rect)
                        painter.fillRect(r, QColor(37, 63, 96, 35))
                        painter.setPen(QColor('#5471e8'))
                        painter.drawText(r, Qt.AlignCenter, '▶  '+tr('media'))
            pressed=getattr(self,'media_press',None)
            if pressed and pressed[0]==i:painter.fillRect(self.page_rect(i,pressed[1]),QColor(70,135,230,85))
            for media_index,asset in enumerate(self.tab.assets):
                if asset.page == i and not any(p.asset == asset and p.isVisible() for p in self.tab.video_players):
                    r = self.page_rect(i, asset.rect)
                    from PySide6.QtGui import QRegion
                    visible=QRegion(r.toAlignedRect())
                    for above in self.tab.assets[media_index+1:]:
                        if above.page==i:visible-=QRegion(self.page_rect(i,above.rect).toAlignedRect())
                    painter.save();painter.setClipRegion(visible,Qt.IntersectClip)
                    painter.fillRect(r, QColor(37, 63, 96, 50))
                    painter.setPen(QColor('#526fe7'))
                    painter.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, '▶  '+asset.name)
                    painter.restore()
            for r in self.search_hits.get(i, []):
                current=getattr(self,'active_search',None)==(i,r)
                painter.fillRect(self.page_rect(i, r), QColor(255, 125 if current else 200, 20, 165 if current else 90))
                if current:
                    painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#f47e15'),2));painter.drawRect(self.page_rect(i,r))
            selected_media=getattr(self.tab,'selected_media',None)
            if self.tab.active_panel=='objects' and self.tab.edit_tool=='video' and selected_media and selected_media.page==i:
                painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#579cf7'),3));painter.drawRect(self.page_rect(i,selected_media.rect).adjusted(-3,-3,3,3))
            boundary=getattr(self,'color_boundary',None)
            if boundary and boundary[0]==i and getattr(self,'show_color_boundary',True):
                painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#18c6ae'),1.8,Qt.DashLine));painter.drawRect(self.page_rect(*boundary))
            if self.region and self.region[0] == i and (self.tab.edit_tool!='colors' or getattr(self,'show_color_boundary',False)):
                painter.setBrush(QColor(82, 111, 231, 25)); painter.setPen(QPen(QColor('#526fe7'), 1.5, Qt.DashLine))
                box=self.page_rect(i,self.region[1]);painter.drawRect(box)
                if self.mode=='crop':
                    painter.setBrush(Qt.white);painter.setPen(QPen(QColor('#246dde'),1.5))
                    for _,handle in self.annotation_handles(box):painter.drawRect(handle)
            if self.word_selection and self.word_selection[0] == i:
                for w in self.word_selection[1]:
                    painter.fillRect(self.page_rect(i, w[0]), QColor(66, 140, 245, 85))
            preview=getattr(self,'pending_annotation',None)
            if preview and preview[0]==i:
                _,kind,points,rects,color,width,opacity=preview;painter.save();painter.setOpacity(opacity)
                painter.setPen(QPen(color,width*self.scale));painter.setBrush(Qt.NoBrush)
                if kind in ('highlight','underline','strikeout'):
                    for bounds in rects:
                        area=self.page_rect(i,bounds)
                        if kind=='highlight':painter.fillRect(area,color)
                        else:
                            y=area.bottom() if kind=='underline' else area.center().y();painter.drawLine(QPointF(area.left(),y),QPointF(area.right(),y))
                elif kind in ('ellipse','rectangle'):
                    area=QRectF(self.rects[i].topLeft()+QPointF(*points[0])*self.scale,self.rects[i].topLeft()+QPointF(*points[-1])*self.scale).normalized()
                    if kind=='ellipse':painter.drawEllipse(area)
                    else:painter.drawRect(area)
                else:
                    for a,b in zip(points,points[1:]):painter.drawLine(self.rects[i].topLeft()+QPointF(*a)*self.scale,self.rects[i].topLeft()+QPointF(*b)*self.scale)
                painter.restore()
            if self.object_page == i and self.mode in ('objects', 'images', 'select'):
                for obj in self.objects:
                    if self.mode == 'images' and obj.kind != 'image': continue
                    if self.mode == 'select' and obj.id not in self.selected:continue
                    if self.mode=='objects' and self.tab.edit_tool=='shape' and obj.kind not in ('vector','group'):continue
                    selected = obj.id in self.selected
                    color = '#9866e8' if selected else '#3f98a5'
                    painter.setPen(QPen(QColor(color), 2 if selected else 0.7, Qt.SolidLine if selected else Qt.DotLine))
                    painter.setBrush(QColor(152, 102, 232, 25) if selected else Qt.NoBrush)
                    box = self.page_rect(i, obj.bbox)
                    if selected and self.drag_objects and len(self.points) > 1 and not getattr(self,'vertex_drag',None):
                        delta=(self.points[-1]-self.points[0])*self.scale
                        if self.resizing:
                            union=self.selection_box();factor=max(.05,(union.width()+delta.x())/max(1,union.width()))
                            free=bool(getattr(self,'drag_modifiers',Qt.NoModifier)&Qt.ShiftModifier)
                            keep=any(o.kind=='image' for o in self.tab.selected_objects()) and self.tab.keep_image_ratio.isChecked()!=free
                            fy=factor if keep else max(.05,(union.height()+delta.y())/max(1,union.height()))
                            box=QRectF(union.left()+(box.left()-union.left())*factor,union.top()+(box.top()-union.top())*fy,box.width()*factor,box.height()*fy)
                        else:box.translate(delta)
                    if selected and self.drag_objects and len(self.points)>1 and obj.kind=='vector' and obj.details.get('hit_path'):
                        original=qrect(obj.bbox);painter.save();painter.translate(box.topLeft());painter.scale(box.width()/max(.001,original.width()),box.height()/max(.001,original.height()));painter.translate(-original.topLeft());painter.setBrush(Qt.NoBrush);pen=QPen(QColor('#aa72ef'),2);pen.setCosmetic(True);painter.setPen(pen);painter.drawPath(self.vector_path(obj));painter.restore()
                    if selected and self.drag_objects and len(self.points)>1 and getattr(self,'drag_preview',None):
                        painter.save();painter.setOpacity(.85);painter.drawPixmap(box,self.drag_preview,QRectF(self.drag_preview.rect()));painter.restore()
                    painter.drawRect(box)
                if self.selected and self.mode == "objects":
                    box = self.selection_box()
                    if box:
                        painter.setBrush(QColor("#9866e8")); painter.drawRect(self.resize_handle())
                    handle=self.shape_rotation_handle()
                    if not handle.isEmpty():
                        painter.setPen(QPen(QColor('#9866e8'),1.5));painter.drawLine(QPointF(box.center().x(),box.top()),handle.center());painter.drawEllipse(handle)
                    rotation=getattr(self,'shape_rotation',None)
                    if rotation:
                        center,start,angle,frame,preview=rotation;painter.save();painter.translate(center);painter.rotate(angle);painter.setOpacity(.7)
                        painter.drawPixmap(frame.translated(-center),preview,QRectF(preview.rect()));painter.restore()
                    painter.setBrush(QColor('#fa9d42'))
                    for obj,index,handle in self.vertex_handles():
                        if getattr(self,'vertex_drag',None)==(obj,index) and len(self.points)>1:
                            delta=(self.points[-1]-self.points[0])*self.scale
                            painter.drawLine(handle.center(),handle.center()+delta);handle=handle.translated(delta)
                        painter.drawEllipse(handle)
        if self.drag_page >= 0 and self.points and not self.drag_objects and self.mode not in ('select','highlight','underline','strikeout','hand'):
            origin = self.rects[self.drag_page].topLeft()
            painter.setPen(QPen(self.tab.annot_color, self.tab.annot_width if self.mode == 'ink' else 1.5))
            painter.setBrush(Qt.NoBrush)
            if self.mode=='draw_shape':
                import math
                kind,stroke,fill,width=self.tab.shape_values();painter.setPen(QPen(QColor.fromRgbF(*stroke),width*self.scale));painter.setBrush(QColor.fromRgbF(*fill) if fill else Qt.NoBrush)
                box=QRectF(origin+self.points[0]*self.scale,origin+self.points[-1]*self.scale).normalized();x,y,x1,y1=box.left(),box.top(),box.right(),box.bottom();cx,cy=box.center().x(),box.center().y();w,h=box.width(),box.height()
                if kind=='rectangle':painter.drawRect(box)
                elif kind=='ellipse':painter.drawEllipse(box)
                elif kind=='line':painter.drawLine(box.bottomLeft(),box.topRight())
                else:
                    if kind=='arrow':points=[(x,cy-h*.15),(x+w*.65,cy-h*.15),(x+w*.65,y),(x1,cy),(x+w*.65,y1),(x+w*.65,cy+h*.15),(x,cy+h*.15)]
                    elif kind=='triangle':points=[(cx,y),(x1,y1),(x,y1)]
                    elif kind=='diamond':points=[(cx,y),(x1,cy),(cx,y1),(x,cy)]
                    else:points=[(cx+math.cos(-math.pi/2+n*math.pi/5)*w/2*(1 if n%2==0 else .42),cy+math.sin(-math.pi/2+n*math.pi/5)*h/2*(1 if n%2==0 else .42)) for n in range(10)]
                    painter.drawPolygon(QPolygonF([QPointF(x,y) for x,y in points]))
            elif self.mode in ('ink', 'line', 'arrow'):
                for a, b in zip(self.points, self.points[1:]):
                    painter.drawLine(origin+a*self.scale, origin+b*self.scale)
            elif self.mode=='ellipse' or self.mode=='draw_shape' and self.tab.shape_values()[0]=='ellipse':
                painter.drawEllipse(QRectF(origin+self.points[0]*self.scale,origin+self.points[-1]*self.scale).normalized())
            else:
                painter.drawRect(QRectF(origin+self.points[0]*self.scale,
                                        origin+self.points[-1]*self.scale).normalized())
        if self.tab.active_panel=='annotate' and self.tab.show_annotations.isChecked():
            ann=self.active_text_annotation()
            if ann and ann['page']==self.page:
                bounds=getattr(self,'annotation_preview',None) or ann['rect'];box=self.page_rect(ann['page'],bounds)
                painter.setPen(QPen(QColor('#6742b8'),1.5));painter.setBrush(Qt.NoBrush);painter.drawRect(box)
                painter.setBrush(QColor('#6742b8'))
                if ann['type']=='FreeText':
                    for _,handle in self.annotation_handles(box):painter.drawRect(handle)
            painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#6742b8'),1.5))
            for it in self.tab.annotation_list.selectedItems():
                chosen=it.data(Qt.UserRole)
                if chosen['page']==self.page:painter.drawRect(self.page_rect(chosen['page'],chosen['rect']))
        painter.end()

    def active_text_annotation(self):
        item=self.tab.annotation_list.currentItem()
        if not item:return None
        ann=item.data(Qt.UserRole)
        return ann if ann['type'] in ('FreeText','Text') and ann['own'] else None

    def annotation_handles(self,box):
        return [(key,QRectF(x-4,y-4,8,8)) for key,x,y in [('lt',box.left(),box.top()),('t',box.center().x(),box.top()),('rt',box.right(),box.top()),('r',box.right(),box.center().y()),('rb',box.right(),box.bottom()),('b',box.center().x(),box.bottom()),('lb',box.left(),box.bottom()),('l',box.left(),box.center().y())]]

    def update_current(self):
        if self.laying_out or not self.continuous: return
        top = self.tab.scroll.verticalScrollBar().value()
        mid = top + min(200, self.tab.scroll.viewport().height()/3)
        for i, rect in enumerate(self.rects):
            if not rect.isEmpty() and rect.bottom() >= mid:
                if i != self.page:
                    self.page = i; self.pageChanged.emit(i)
                break

    def selection_box(self):
        boxes = [self.page_rect(self.object_page,o.bbox) for o in self.objects if o.id in self.selected]
        if not boxes: return None
        box = boxes[0]
        for b in boxes[1:]: box = box.united(b)
        return box

    def vertex_handles(self):
        if not getattr(self,'vector_edit',False) or self.mode!='objects':return []
        out=[]
        for obj in self.objects:
            if obj.id in self.selected and obj.kind=='vector':
                for index,x,y in obj.details.get('vertices',[]):
                    point=self.rects[self.object_page].topLeft()+QPointF(x,y)*self.scale
                    out.append((obj,index,QRectF(point.x()-5,point.y()-5,10,10)))
        return out

    def vector_path(self,obj):
        path=QPainterPath()
        for op,coords in obj.details['hit_path']:
            pts=[QPointF(x,y) for x,y in coords]
            if op=='m':path.moveTo(pts[0])
            elif op=='l':path.lineTo(pts[0])
            elif op=='c':path.cubicTo(*pts)
            elif op=='v':path.cubicTo(path.currentPosition(),*pts)
            elif op=='y':path.cubicTo(pts[0],pts[1],pts[1])
            elif op=='h':path.closeSubpath()
            elif op=='poly':path.addPolygon(QPolygonF(pts+[pts[0]]))
        return path

    def shape_hit(self,obj,point):
        if self.tab.edit_tool!='shape' or obj.kind!='vector' or not obj.details.get('hit_path'):return True
        path=self.vector_path(obj)
        stroker=QPainterPathStroker();stroker.setWidth(8/self.scale)
        return bool(obj.details.get('filled') and path.contains(point) or stroker.createStroke(path).contains(point))

    def shape_rotation_handle(self):
        selected=[o for o in self.objects if o.id in self.selected]
        if self.mode!='objects' or self.tab.edit_tool!='shape' or not selected or any(o.kind not in ('vector','group') for o in selected):return QRectF()
        box=self.selection_box()
        return QRectF(box.center().x()-6,box.top()-30,12,12) if box else QRectF()

    def resize_handle(self):
        box = self.selection_box()
        return QRectF(box.right()-5,box.bottom()-5,10,10) if box else QRectF()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.tab.busy: return
        if self.tab.inline_editor:
            self.tab.leave_inline(lambda:None);return
        self.setFocus()
        if self.mode=='color_pick':
            page,point=self.locate(event.position())
            if page>=0:
                def sample(job):
                    import pymupdf as fitz
                    with fitz.open(self.tab.document.path) as pdf:
                        pix=pdf[page].get_pixmap(clip=fitz.Rect(point.x(),point.y(),point.x()+1,point.y()+1),colorspace=fitz.csRGB,alpha=False,annots=False)
                        return tuple(v/255 for v in pix.pixel(0,0))
                self.tab.queue.submit(sample,lambda rgb:self.tab.set_color_source(rgb),self.tab.error)
            return
        handle=self.shape_rotation_handle()
        if not handle.isEmpty() and handle.contains(event.position()):
            box=self.selection_box();center=box.center();delta=event.position()-center
            self.shape_rotation=(center,math.atan2(delta.y(),delta.x()),0.,box,self.grab(box.toAlignedRect()));self.drag_page=-1;return
        ann=self.active_text_annotation()
        if ann and ann['page']==self.page and self.tab.active_panel=='annotate' and self.tab.show_annotations.isChecked():
            box=self.page_rect(ann['page'],ann['rect'])
            handle=next((key for key,r in self.annotation_handles(box) if ann['type']=='FreeText' and r.contains(event.position())),None)
            if handle:
                self.annotation_drag=(ann,handle,event.position());self.annotation_preview=ann['rect'];return
        if self.mode == 'hand':
            self.hand_press=event.position()
            self.pan_anchor = (event.globalPosition(), self.tab.scroll.horizontalScrollBar().value(),self.tab.scroll.verticalScrollBar().value())
            self.setCursor(Qt.ClosedHandCursor); return
        if self.region and self.mode=='crop':
            page,rect=self.region;box=self.page_rect(page,rect)
            handle=next((key for key,r in self.annotation_handles(box) if r.contains(event.position())),None)
            border=box.adjusted(-5,-5,5,5).contains(event.position()) and not box.adjusted(6,6,-6,-6).contains(event.position())
            if handle or border:self.crop_drag=(page,rect,handle or 'move',event.position());return
        if self.region and self.mode!='region':
            self.region=None;self.update()
        i, point = self.locate(event.position())
        if i < 0: return
        if self.mode=='objects' and self.tab.edit_tool=='video':
            asset=next((a for a in reversed(self.tab.assets) if a.page==i and qrect(a.rect).contains(point)),None)
            if asset:
                self.tab.select_media(asset);self.drag_page=-1;event.accept();return
            self.tab.selected_media=None
        if i != self.page:
            self.page = i; self.pageChanged.emit(i)
        if self.mode in ('select', 'read'):
            if any(qrect(link['from']).contains(point) for link in self.tab.links.get(i,[])):
                self.drag_page=i;self.points=[point];self.drag_objects=False;return
            for a in self.tab.animations:
                if a.page == i and (qrect(a.rect).contains(point) or any(qrect(b[0]).contains(point) for b in a.buttons)):
                    self.media_press=(i,next((b[0] for b in a.buttons if qrect(b[0]).contains(point)),a.rect));self.update();self.drag_page=-1;event.accept();self.mediaClick.emit(i, point); return
            for m in self.tab.assets:
                if m.page == i and qrect(m.rect).contains(point):
                    self.drag_page=-1;event.accept();self.mediaClick.emit(i, point); return
        if self.mode=='select':
            images=[x for x in self.tab.image_cache.get(i,[]) if qrect(x['bbox']).contains(point)]
            if images and not any(qrect(c[0]).contains(point) for c in self.words.get(i,[])):
                from .objects import PdfObject
                x=min(images,key=lambda x:qrect(x['bbox']).width()*qrect(x['bbox']).height())
                self.objects=[PdfObject(0,'image',0,0,(1,0,0,1,0,0),x['bbox'],xref=x['xref'])]
                self.object_page=i;self.selected=[0];self.region=(i,x['bbox']);self.update()
                self.tab.status.setText(L('已选择图片 · 右键提取原图','Image selected · Right-click to extract'));return
            self.selected=[]
        if self.tab.show_annotations.isChecked() and (self.tab.active_panel=='annotate' or self.mode in ('select','read')):
            candidates=[a for a in self.tab.annotations_data if a['page']==i and (self.tab.active_panel=='annotate' or a['type'] in ('Text','FreeText')) and qrect(a['rect']).contains(point)]
            if candidates:
                ann=candidates[-1];self.tab.select_annotation(ann,bool(event.modifiers()&Qt.ControlModifier));self.drag_page=-1
                if ann['type'] in ('FreeText','Text') and ann['own'] and self.tab.active_panel=='annotate':self.annotation_drag=(ann,'move',event.position());self.annotation_preview=ann['rect']
                return
        if self.tab.active_panel=='annotate' and self.mode=='select_annot':
            self.tab.annotation_list.setCurrentItem(None);self.tab.annotation_list.clearSelection();self.region=None
            self.tab.show_annotation_properties('select_annot')
        self.drag_page, self.points, self.drag_objects = i, [point], False
        self.vertex_drag=None
        for obj,index,handle in self.vertex_handles():
            if handle.contains(event.position()):
                self.vertex_drag=(obj,index);self.drag_objects=True;return
        self.resizing = self.mode == 'objects' and self.resize_handle().contains(event.position())
        if self.resizing:
            self.drag_objects = True;self.drag_preview=None;return
        if self.mode in ('objects','images') and i == self.object_page:
            candidates = [o for o in self.objects if (self.mode != 'images' or o.kind == 'image') and (self.tab.edit_tool!='shape' or o.kind in ('vector','group')) and qrect(o.bbox).adjusted(-2,-2,2,2).contains(point) and self.shape_hit(o,point)]
            if candidates:
                obj = min(candidates,key=lambda o:qrect(o.bbox).width()*qrect(o.bbox).height())
                if event.modifiers() & (Qt.ShiftModifier|Qt.ControlModifier):
                    if obj.id in self.selected: self.selected.remove(obj.id)
                    else: self.selected.append(obj.id)
                elif obj.id not in self.selected: self.selected = [obj.id]
                self.drag_objects = obj.id in self.selected
                self.drag_preview=self.grab(self.page_rect(i,obj.bbox).toAlignedRect()) if obj.kind=='image' else None
                self.objectSelected.emit(self.selected)
                if self.mode == 'images':
                    self.drag_page = -1
                    self.update(); return
            elif not event.modifiers() & Qt.ShiftModifier:
                self.selected = []; self.objectSelected.emit([])
        self.update()

    def mouseMoveEvent(self, event):
        if getattr(self,'shape_rotation',None):
            center,start,angle,box,preview=self.shape_rotation;delta=event.position()-center
            angle=math.degrees(math.atan2(delta.y(),delta.x())-start)
            if event.modifiers()&Qt.ShiftModifier:angle=round(angle/15)*15
            self.shape_rotation=(center,start,angle,box,preview);self.setCursor(Qt.ClosedHandCursor);self.update();return
        if getattr(self,'crop_drag',None):
            page,rect,handle,start=self.crop_drag;delta=(event.position()-start)/self.scale
            x,y,x1,y1=rect;w,h=self.sizes[page]
            if handle=='move':
                dx=max(-x,min(delta.x(),w-x1));dy=max(-y,min(delta.y(),h-y1));x+=dx;x1+=dx;y+=dy;y1+=dy
            else:
                if 'l' in handle:x=max(0,min(x1-1,x+delta.x()))
                if 'r' in handle:x1=min(w,max(x+1,x1+delta.x()))
                if 't' in handle:y=max(0,min(y1-1,y+delta.y()))
                if 'b' in handle:y1=min(h,max(y+1,y1+delta.y()))
            self.region=(page,(x,y,x1,y1));self.tab.crop_selection_changed();self.update();return
        if self.mode=='crop' and self.region and self.drag_page<0:
            box=self.page_rect(*self.region)
            handle=next((key for key,r in self.annotation_handles(box) if r.contains(event.position())),None)
            cursors={'lt':Qt.SizeFDiagCursor,'rb':Qt.SizeFDiagCursor,'rt':Qt.SizeBDiagCursor,'lb':Qt.SizeBDiagCursor,'l':Qt.SizeHorCursor,'r':Qt.SizeHorCursor,'t':Qt.SizeVerCursor,'b':Qt.SizeVerCursor}
            border=box.adjusted(-5,-5,5,5).contains(event.position()) and not box.adjusted(6,6,-6,-6).contains(event.position())
            self.setCursor(cursors[handle] if handle else Qt.SizeAllCursor if border else Qt.CrossCursor);return
        if getattr(self,'annotation_drag',None):
            ann,handle,start=self.annotation_drag;delta=(event.position()-start)/self.scale;x,y,x1,y1=ann['rect']
            if handle=='move':x+=delta.x();x1+=delta.x();y+=delta.y();y1+=delta.y()
            else:
                if 'l' in handle:x=min(x1-30,x+delta.x())
                if 'r' in handle:x1=max(x+30,x1+delta.x())
                if 't' in handle:y=min(y1-20,y+delta.y())
                if 'b' in handle:y1=max(y+20,y1+delta.y())
            self.annotation_preview=(x,y,x1,y1);self.update();return
        if self.pan_anchor:
            origin,x,y = self.pan_anchor
            delta = event.globalPosition()-origin
            self.tab.scroll.horizontalScrollBar().setValue(int(x-delta.x()))
            self.tab.scroll.verticalScrollBar().setValue(int(y-delta.y())); return
        if self.drag_page < 0:
            if self.mode == 'objects': self.setCursor(Qt.OpenHandCursor if self.shape_rotation_handle().contains(event.position()) else Qt.SizeFDiagCursor if self.resize_handle().contains(event.position()) else Qt.ArrowCursor)
            elif self.mode == 'select':
                i,p = self.locate(event.position())
                over = any(qrect(c[0]).contains(p) for c in self.words.get(i,[]))
                link=any(qrect(link['from']).contains(p) for link in self.tab.links.get(i,[]))
                self.setCursor(Qt.PointingHandCursor if link else Qt.IBeamCursor if over else Qt.ArrowCursor)
            i,p=self.locate(event.position())
            annotations=[a for a in self.tab.annotations_data if a['page']==i and qrect(a['rect']).contains(p)] if self.tab.show_annotations.isChecked() else []
            ann=annotations[-1] if annotations else None
            self.setToolTip(ann['text'] if ann and ann.get('text') else '')
            if self.mode in ('select','read'):
                from .media import control_at
                for animation in self.tab.animations:
                    if animation.page!=i:continue
                    command=control_at(animation,p)
                    if command or qrect(animation.rect).contains(p):
                        self.setCursor(Qt.PointingHandCursor)
                        self.setToolTip({'Minus':L('减速','Slower'),'Plus':L('加速','Faster'),'Reset':L('默认速度','Default speed'),'StepLeft':L('上一帧','Previous frame'),'StepRight':L('下一帧','Next frame'),'EndLeft':L('第一帧','First frame'),'EndRight':L('最后一帧','Last frame')}.get(command,L('播放 / 暂停','Play / pause')))
                if any(asset.page==i and qrect(asset.rect).contains(p) for asset in self.tab.assets):self.setCursor(Qt.PointingHandCursor)
            if ann and self.tab.active_panel=='annotate'  and ann['type'] in ('Text','FreeText'):
                self.setCursor(Qt.SizeAllCursor)
            selected=self.active_text_annotation()
            if selected and self.tab.active_panel=='annotate' and selected['type']=='FreeText':
                box=self.page_rect(selected['page'],selected['rect'])
                cursors={'lt':Qt.SizeFDiagCursor,'rb':Qt.SizeFDiagCursor,'rt':Qt.SizeBDiagCursor,'lb':Qt.SizeBDiagCursor,'l':Qt.SizeHorCursor,'r':Qt.SizeHorCursor,'t':Qt.SizeVerCursor,'b':Qt.SizeVerCursor}
                handle=next((key for key,r in self.annotation_handles(box) if r.contains(event.position())),None)
                if handle:self.setCursor(cursors[handle])
            return
        self.drag_modifiers=event.modifiers()
        r = self.rects[self.drag_page]
        point = (event.position()-r.topLeft())/self.scale
        point.setX(max(0,min(point.x(),r.width()/self.scale)))
        point.setY(max(0,min(point.y(),r.height()/self.scale)))
        if self.mode == 'ink': self.points.append(point)
        else: self.points = [self.points[0],point]
        if self.mode in ('select','highlight','underline','strikeout','replace_text','squiggly'):
            self.select_characters(self.drag_page,self.points[0],point)
        self.update()

    def select_characters(self,page,start,end):
        chars = self.words.get(page,[])
        if not chars: return []
        def caret(point):
            # Choose the nearest line, then a character boundary on that line.
            lines = {}
            for idx,c in enumerate(chars): lines.setdefault(c[2:4],[]).append((idx,c))
            row = min(lines.values(),key=lambda row:min(max(c[0][1]-point.y(),0,point.y()-c[0][3]) for _,c in row))
            nearest = min(row,key=lambda ic:abs((ic[1][0][0]+ic[1][0][2])/2-point.x()))
            idx,c = nearest
            return idx + (point.x() >= (c[0][0]+c[0][2])/2)
        a,b = sorted((caret(start),caret(end)))
        chosen = chars[a:b]
        self.word_selection = (page,chosen); self.update()
        return chosen

    def mouseReleaseEvent(self, event):
        if event.button()==Qt.RightButton:
            self.open_context_menu(event.position().toPoint(),event.globalPosition().toPoint());event.accept();return
        self.media_press=None;self.update()
        if getattr(self,'shape_rotation',None):
            angle=self.shape_rotation[2];self.shape_rotation=None;self.unsetCursor();self.tab.rotate_shapes(angle);self.update();return
        if getattr(self,'crop_drag',None):self.crop_drag=None;self.tab.crop_selection_changed();self.update();return
        if getattr(self,'annotation_drag',None):
            ann,handle,start=self.annotation_drag;rect=self.annotation_preview;self.annotation_drag=None;self.annotation_preview=None
            if (event.position()-start).manhattanLength()>3:self.tab.resize_annotation(ann,rect)
            self.setToolTip(ann.get('text',''));self.update();return
        if self.pan_anchor:
            if (event.position()-getattr(self,'hand_press',event.position())).manhattanLength()<4:
                page,point=self.locate(event.position())
                link=next((link for link in self.tab.links.get(page,[]) if qrect(link['from']).contains(point)),None)
                if link:self.tab.activate_link(link)
            self.pan_anchor = None; self.setCursor(Qt.OpenHandCursor); return
        if self.drag_page < 0: return
        i,points = self.drag_page,self.points[:]
        end=(event.position()-self.rects[i].topLeft())/self.scale
        if self.mode!='ink':points=[points[0],end]
        elif len(points)==1:points.append(end)
        delta = points[-1]-points[0]
        distance = abs(delta.x())+abs(delta.y())
        self.drag_page = -1
        if self.drag_objects:
            if distance > 2 and self.mode == 'objects':
                if getattr(self,'vertex_drag',None):
                    obj,index=self.vertex_drag;self.tab.move_vertex(obj,index,(end.x(),end.y()))
                elif self.resizing: self.tab.resize_objects(delta.x(),delta.y(),bool(event.modifiers() & Qt.ShiftModifier))
                else: self.objectMoved.emit(delta.x(),delta.y())
        elif self.mode == 'objects':
            box = QRectF(points[0],points[-1]).normalized()
            self.selected = [o.id for o in self.objects if (self.tab.edit_tool!='shape' or o.kind in ('vector','group')) and box.contains(qrect(o.bbox))]
            self.objectSelected.emit(self.selected)
        elif distance > 2 or self.mode in ('select','note','select_annot','add_image','add_text'):
            self.selection.emit(i,[(p.x(),p.y()) for p in points],self.mode)
        self.points = []; self.drag_objects = False; self.resizing = False; self.vertex_drag=None;self.drag_preview=None; self.update()

    def mouseDoubleClickEvent(self,event):
        page,point=self.locate(event.position())
        over_note=self.tab.show_annotations.isChecked() and any(a['page']==page and a['type'] in ('Text','FreeText') and qrect(a['rect']).contains(point) for a in self.tab.annotations_data)
        if self.mode=='freetext' and not over_note:
            self.drag_page=-1;self.points=[];self.annotation_drag=None;self.annotation_preview=None;self.tab.create_freetext(page,point);return
        if self.tab.active_panel=='annotate' or over_note:
            self.drag_page=-1;self.points=[];self.annotation_drag=None;self.annotation_preview=None;self.tab.edit_selected_annotation();return
        if self.mode == 'objects' and self.selected and not self.tab.busy:
            self.drag_page = -1; self.points = []; self.tab.modify_object()

    def contextMenuEvent(self,event):
        self.open_context_menu(event.pos(),event.globalPos());event.accept()

    def open_context_menu(self,pos,global_pos):
        page,point=self.locate(pos)
        if self.tab.media_context_menu(page,point,global_pos):return
        from PySide6.QtWidgets import QMenu
        menu=QMenu(self)
        if self.mode in ('objects','select') and self.selected:
            selected=self.tab.selected_objects()
            if len(selected)==1 and selected[0].kind=='image':
                menu.addAction(L('复制图片','Copy image'),lambda:self.tab.copy_image(selected[0]))
                menu.addAction(tr('extract_image'),lambda:self.tab.save_image_xref(self.object_page,selected[0].xref))
            if self.mode=='objects':
                if selected:
                    menu.addAction(L('置于顶层','Bring to front'),lambda:self.tab.stack_images(True))
                    menu.addAction(L('置于底层','Send to back'),lambda:self.tab.stack_images(False))
                menu.addAction(tr('modify'),self.tab.modify_object);menu.addAction(tr('delete_object'),self.tab.delete_objects)
        if self.word_selection:menu.addAction(L('复制','Copy'),self.tab.copy_text)
        if self.region:menu.addAction(tr('copy_region'),self.tab.copy_region)
        if menu.actions():menu.exec(global_pos)

    def keyPressEvent(self,event):
        if not self.tab.handle_key(event): super().keyPressEvent(event)

    def wheelEvent(self,event):
        if event.modifiers() & Qt.ControlModifier:
            self.tab.zoom_by(1.12 if event.angleDelta().y()>0 else 1/1.12,event.globalPosition());event.accept()
        else: event.ignore()


class ReaderScroll(QScrollArea):
    def __init__(self,tab):
        super().__init__(); self.tab=tab
        self.setWidgetResizable(False); self.setFrameShape(QScrollArea.NoFrame)
        self.verticalScrollBar().valueChanged.connect(self.sync_document_bar)
        self.verticalScrollBar().rangeChanged.connect(self.sync_document_bar)

    def sync_document_bar(self,*_):
        # The overview owns document-level navigation; this bar scrolls the current spread.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded);self.setViewportMargins(0,0,0,0)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self.tab,'canvas'): self.tab.canvas.layout_pages();self.sync_document_bar()

    def keyPressEvent(self,event):
        if not self.tab.handle_key(event): super().keyPressEvent(event)

    def wheelEvent(self,event):
        if event.modifiers() & Qt.ControlModifier:
            self.tab.zoom_by(1.12 if event.angleDelta().y()>0 else 1/1.12,event.globalPosition());event.accept();return
        delta=event.angleDelta().y() or event.pixelDelta().y()
        bar=self.verticalScrollBar()
        if not self.tab.canvas.continuous and delta and ((delta<0 and bar.value()>=bar.maximum()) or (delta>0 and bar.value()<=bar.minimum())):
            self.tab.turn_page(1 if delta<0 else -1,from_bottom=delta>0);event.accept();return
        super().wheelEvent(event)
