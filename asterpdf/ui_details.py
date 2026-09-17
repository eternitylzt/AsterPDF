"""Small desktop interactions shared by property panels and navigation."""
from PySide6.QtCore import Qt,QSize,QRectF
from PySide6.QtGui import QColor,QTextDocument,QPalette
from PySide6.QtWidgets import QSplitter,QSplitterHandle,QStyledItemDelegate,QStyle,QStyleOptionViewItem

class NavSplitter(QSplitter):
    def createHandle(self):
        owner=self
        class Handle(QSplitterHandle):
            def mouseDoubleClickEvent(self,event):
                if self is owner.handle(1):owner.tab.toggle_sidebar();event.accept()
                else:super().mouseDoubleClickEvent(event)
        return Handle(self.orientation(),self)

class AnnotationDelegate(QStyledItemDelegate):
    def document(self,index,width,palette,selected=False):
        import html
        text=index.data(Qt.DisplayRole) or '';lines=text.split('\n',2)
        meta=html.escape(' · '.join(lines[:2]));body=html.escape(lines[2] if len(lines)>2 else '').replace('\n','<br>')
        color=palette.color(QPalette.HighlightedText if selected else QPalette.Text).name()
        muted=palette.color(QPalette.HighlightedText).name() if selected else '#9eafc4' if palette.color(QPalette.Base).lightness()<100 else '#65768d'
        d=QTextDocument();d.setDefaultFont(self.parent().font());d.setDocumentMargin(5)
        d.setHtml(f'<span style="font-size:11px;color:{muted}">{meta}</span><br><span style="color:{color}">{body}</span>')
        d.setTextWidth(max(80,width));return d
    def sizeHint(self,option,index):
        d=self.document(index,self.parent().viewport().width()-4,option.palette)
        return QSize(int(d.idealWidth()),min(180,int(d.size().height()+4)))
    def paint(self,painter,option,index):
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);opt.text=''
        option.widget.style().drawControl(QStyle.CE_ItemViewItem,opt,painter,option.widget)
        painter.save();painter.setClipRect(option.rect);painter.translate(option.rect.topLeft())
        self.document(index,option.rect.width(),option.palette,bool(option.state&QStyle.State_Selected)).drawContents(painter)
        painter.restore()


class ToolbarStrip(__import__('PySide6.QtWidgets',fromlist=['QWidget']).QWidget):
    """Horizontal tool strip: overflow stays accessible at every screen width."""
    def __init__(self,toolbar):
        from PySide6.QtWidgets import QHBoxLayout,QToolButton,QScrollArea,QFrame
        from PySide6.QtCore import QTimer
        super().__init__();self.setAutoFillBackground(True);self.toolbar=toolbar;layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.left=QToolButton();self.left.setText('‹');self.right=QToolButton();self.right.setText('›')
        self.scroller=QScrollArea();self.scroller.setFrameShape(QFrame.NoFrame);self.scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.scroller.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.scroller.setWidget(toolbar)
        layout.addWidget(self.left);layout.addWidget(self.scroller,1);layout.addWidget(self.right)
        for button,delta in [(self.left,-160),(self.right,160)]:
            button.setFixedWidth(22);button.setAutoRepeat(True);button.clicked.connect(lambda checked=False,d=delta:self.scroller.horizontalScrollBar().setValue(self.scroller.horizontalScrollBar().value()+d))
        self.scroller.horizontalScrollBar().valueChanged.connect(self.arrows)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.reflow);toolbar.installEventFilter(self);self.timer.start(0)
    def arrows(self):
        bar=self.scroller.horizontalScrollBar();self.left.setEnabled(bar.value()>0);self.right.setEnabled(bar.value()<bar.maximum())
    def eventFilter(self,obj,event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.ActionAdded,QEvent.ActionRemoved,QEvent.ActionChanged,QEvent.LayoutRequest,QEvent.StyleChange):self.timer.start(0)
        return False
    def reflow(self):
        natural=self.toolbar.sizeHint();height=natural.height()
        self.setFixedHeight(height);overflow=natural.width()>self.width()
        self.left.setVisible(overflow);self.right.setVisible(overflow)
        self.toolbar.resize(max(natural.width(),self.scroller.viewport().width()),height);self.arrows();self.scroller.viewport().update();self.toolbar.update();self.update()
        if self.parentWidget():self.parentWidget().update()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'timer'):self.timer.start(0)
    def sizeHint(self):return QSize(600,self.toolbar.sizeHint().height())


class BookmarkDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(210,max(32,option.fontMetrics.height()+12))
    def paint(self,painter,option,index):
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);opt.text=''
        option.widget.style().drawControl(QStyle.CE_ItemViewItem,opt,painter,option.widget)
        painter.save();painter.setClipRect(option.rect);rect=option.rect.adjusted(7,0,-7,0)
        meta=index.data(Qt.UserRole+1) or '';width=option.fontMetrics.horizontalAdvance(meta)+12
        painter.setPen(QColor('#8693a5'));painter.drawText(rect,Qt.AlignRight|Qt.AlignVCenter,meta)
        rect.setRight(rect.right()-width);painter.setPen(option.palette.color(QPalette.Text));painter.drawText(rect,Qt.AlignLeft|Qt.AlignVCenter,option.fontMetrics.elidedText(index.data(),Qt.ElideRight,int(rect.width())))
        painter.restore()
