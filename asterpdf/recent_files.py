"""Paint recent entries once; leave selection and activation to the item view."""
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QRect
from PySide6.QtGui import QPalette,QFontMetrics
from PySide6.QtWidgets import QStyledItemDelegate,QStyleOptionViewItem,QStyle
from .i18n import L

class RecentDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):
        return QSize(100,max(60,QFontMetrics(option.font).height()*2+22))

    def paint(self,painter,option,index):
        if index.column()!=0:return super().paint(painter,option,index)
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);opt.text=''
        opt.widget.style().drawControl(QStyle.CE_ItemViewItem,opt,painter,opt.widget)
        file=Path(index.data(Qt.UserRole));area=option.rect.adjusted(9,5,-9,-5)
        painter.save();painter.setClipRect(area)
        selected=bool(option.state&QStyle.State_Selected)
        color=option.palette.color(QPalette.HighlightedText if selected else QPalette.Text)
        font=option.font;font.setPointSizeF(font.pointSizeF()+1);painter.setFont(font);painter.setPen(color)
        fm=QFontMetrics(font);height=fm.height()
        painter.drawText(QRect(area.x(),area.y(),area.width(),height),Qt.AlignVCenter,fm.elidedText(file.name,Qt.ElideMiddle,area.width()))
        painter.setFont(option.font);color.setAlpha(190);painter.setPen(color)
        fm=QFontMetrics(option.font)
        painter.drawText(QRect(area.x(),area.y()+height+3,area.width(),fm.height()),Qt.AlignVCenter,fm.elidedText(L('路径：','Path: ')+str(file.parent),Qt.ElideMiddle,area.width()))
        painter.restore()
