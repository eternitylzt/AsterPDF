"""Desktop open events and offline document import."""
from pathlib import Path
from PySide6.QtCore import QEvent,QTimer,QUrl
from PySide6.QtWidgets import QApplication

class DesktopApplication(QApplication):
    def __init__(self,args):
        super().__init__(args);self.open_requests=[];self.host=None
    def event(self,event):
        if event.type()==QEvent.FileOpen:
            filename=event.file() or event.url().toLocalFile()
            if filename:
                if self.host:QTimer.singleShot(0,lambda:self.host.open_file(filename))
                else:self.open_requests.append(filename)
                event.accept();return True
        return super().event(event)
    def bind(self,window):
        self.host=window
        for filename in self.open_requests:window.open_file(filename)
        self.open_requests.clear()

def markdown_pdf(filename,destination,prepared=None):
    from .markdown_import import render
    return render(filename,destination,prepared)
