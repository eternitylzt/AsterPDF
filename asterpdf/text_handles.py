"""Direct border resizing and rotation for authored text boxes."""
import math
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPainter,QColor,QPen,QRegion,QFontMetricsF
from PySide6.QtWidgets import QWidget

class Handles(QWidget):
    def __init__(self,tab):
        super().__init__(tab.canvas);self.tab=tab;self.drag=None;self.setMouseTracking(True)
        self.setToolTip('拖动边角调整宽度并换行；拖动圆点旋转 / Resize borders to wrap; drag circle to rotate')
    def arrange(self,rect):
        self.setGeometry(rect.adjusted(-6,-23,6,6).toRect());self.box=QRectF(6,23,max(2,rect.width()),max(12,rect.height()))
        self.knob=QPointF(self.box.center().x(),7)
        outer=self.box.adjusted(-5,-5,5,5).toRect();inner=self.box.adjusted(5,5,-5,-5).toRect()
        mask=QRegion(outer)-QRegion(inner);mask|=QRegion(int(self.knob.x()-7),0,14,16);self.setMask(mask);self.show();self.raise_();self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor('#7657bc'),1));p.setBrush(Qt.NoBrush);p.drawRect(self.box);p.drawEllipse(self.knob,4,4);p.setBrush(QColor('#f4efff'))
        for x in (self.box.left(),self.box.center().x(),self.box.right()):
            for y in (self.box.top(),self.box.center().y(),self.box.bottom()):
                if x==self.box.center().x() and y==self.box.center().y():continue
                p.drawRect(QRectF(x-2,y-2,4,4))
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:return
        box=self.tab.inline_object.details['box'];pos=event.position();self.initial_angle=box.get('angle',0)
        self.drag=('rotate' if pos.y()<18 else 'resize',event.globalPosition(),list(box['rect']),pos.x()<self.box.center().x(),pos.y()<self.box.center().y());event.accept()
    def mouseMoveEvent(self,event):
        if not self.drag:self.setCursor(Qt.SizeAllCursor if event.position().y()<18 else Qt.SizeFDiagCursor);return
        kind,start,rect,left,top=self.drag;t=self.tab;box=t.inline_object.details['box']
        if kind=='rotate':
            origin=t.canvas.page_rect(t.inline_page,(rect[0],rect[1],rect[0]+1,rect[1]+1)).topLeft();point=QPointF(t.canvas.mapFromGlobal(event.globalPosition().toPoint()))-origin
            initial=QPointF(t.canvas.mapFromGlobal(start.toPoint()))-origin
            angle=self.initial_angle+math.degrees(math.atan2(point.y(),point.x())-math.atan2(initial.y(),initial.x()));angle=(angle+180)%360-180;t.change_box(angle=round(angle))
        else:
            delta=(event.globalPosition()-start)/t.canvas.scale;x,y,w,h=rect
            newwidth=max(2,w+delta.x()*(-1 if left else 1));newheight=max(t.inline_object.size*1.3,h+delta.y()*(-1 if top else 1))
            box['rect']=[x+w-newwidth if left else x,y+h-newheight if top else y,newwidth,newheight];t.change_box(width=newwidth)
        t._sync_text=True;t.box_width.setValue(box['rect'][2]);t.box_angle.setValue(box.get('angle',0));t._sync_text=False
    def mouseReleaseEvent(self,event):self.drag=None;self.tab.inline_editor.setFocus()

def position_box(tab):
    editor=tab.inline_editor;frame=tab.inline_object.details['box'];x,y,w,h=frame['rect'];scale=tab.canvas.scale
    if frame.get('auto',True):
        # The PDF preview supplies authoritative bounds; QTextDocument supplies
        # the immediate typing size before that short asynchronous render arrives.
        w=max(2,editor.document().idealWidth()/scale*frame.get('xscale',1));h=max(h,editor.document().size().height()/scale)
        frame['rect'][2]=w;frame['rect'][3]=h
    if getattr(editor,'preview_glyphs',None) and getattr(editor,'preview_angle',0)==frame.get('angle',0):
        import pymupdf as fitz
        inverse=~(fitz.Matrix(1,0,0,1,-x,-y)*fitz.Matrix(frame.get('angle',0))*fitz.Matrix(1,0,0,1,x,y))
        rotation=fitz.Matrix(tab.inline_object.details.get('page_rotation_matrix',(1,0,0,1,0,0)))
        h=max(h,max((fitz.Point(g[2])*rotation*inverse).y-y for g in editor.preview_glyphs)+tab.inline_object.size*.35);frame['rect'][3]=h
    tab._sync_text=True;tab.box_width.setValue(w);tab.box_angle.setValue(frame.get('angle',0));tab._sync_text=False
    rect=tab.canvas.page_rect(tab.inline_page,(x,y,x+w,y+h));box=QRectF(rect).adjusted(-2,-2,3,3)
    if hasattr(editor,'preview_bounds'):
        px,py,pw,ph=editor.preview_bounds;box=box.united(tab.canvas.page_rect(tab.inline_page,(px,py,px+pw,py+ph)))
    box.setWidth(max(8,box.width()));box.setHeight(max(18,box.height()));editor.setGeometry(box.toRect())
    if not hasattr(editor,'handles'):editor.handles=Handles(tab)
    editor.handles.arrange(rect)
