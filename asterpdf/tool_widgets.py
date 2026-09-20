"""Small property controls with clear, persistent visual feedback."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor,QPixmap,QIcon
from PySide6.QtWidgets import QPushButton,QColorDialog

class ColorButton(QPushButton):
    changed=Signal(object)
    def __init__(self,color,parent=None):
        super().__init__(parent);self.color=color;self.clicked.connect(self.choose)
    @property
    def color(self):return self._color
    @color.setter
    def color(self,value):
        self._color=QColor(value);pix=QPixmap(28,18);pix.fill(self._color)
        self.setIcon(QIcon(pix));self.setText(self._color.name())
    def value(self):return self.color.name()
    def choose(self):
        value=QColorDialog.getColor(self.color,self)
        if value.isValid():self.color=value;self.changed.emit(value)
