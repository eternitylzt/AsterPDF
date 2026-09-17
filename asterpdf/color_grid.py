"""Compact source-color grid shared by palette sampling and the eyedropper."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QGridLayout,QToolButton,QSizePolicy

class ColorGrid(QWidget):
    colorChanged=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent);self.colors=[];self.index=-1;self.buttons=[]
        layout=QGridLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(4)
        for i in range(32):
            button=QToolButton();button.setCheckable(True);button.setMinimumSize(30,21);button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False,n=i:self.setCurrentIndex(n));layout.addWidget(button,i//4,i%4);self.buttons.append(button)
        self.redraw()
    def count(self):return len(self.colors)
    def currentData(self):return self.colors[self.index] if 0<=self.index<len(self.colors) else None
    def value(self):return self.currentData()
    def clear(self):self.colors=[];self.index=-1;self.redraw()
    def addItem(self,icon,text,rgb):
        self.set_color(rgb,select=False)
    def set_color(self,rgb,select=True):
        rgb=tuple(rgb)
        index=next((i for i,c in enumerate(self.colors) if max(abs(a-b) for a,b in zip(c,rgb))<.0001),None)
        if index is None:
            if len(self.colors)==32:index=31;self.colors[index]=rgb
            else:index=len(self.colors);self.colors.append(rgb)
        if select or self.index<0:self.index=index
        self.redraw()
    def setCurrentIndex(self,index):
        if 0<=index<len(self.colors):self.index=index;self.redraw()
    def redraw(self):
        for i,button in enumerate(self.buttons):
            valid=i<len(self.colors);button.setEnabled(valid);button.setChecked(valid and i==self.index)
            color=QColor.fromRgbF(*self.colors[i]).name() if valid else 'transparent'
            button.setToolTip(color if valid else '')
            button.setStyleSheet('QToolButton {background:'+color+';border:1px solid #71849b;border-radius:3px;padding:0;} QToolButton:checked {border:3px solid #579cf7;} QToolButton:hover {border:2px solid #b1cdf8;}')
        self.colorChanged.emit(self.currentData())
