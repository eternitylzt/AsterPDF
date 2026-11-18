"""Desktop open events and offline document import."""
from pathlib import Path
from PySide6.QtCore import QEvent,QTimer,QUrl,Qt
from PySide6.QtWidgets import QApplication

class DesktopApplication(QApplication):
    def __init__(self,args):
        super().__init__(args);self.open_requests=[];self.host=None
    def event(self,event):
        if event.type()==QEvent.FileOpen:
            filename=event.file() or event.url().toLocalFile()
            if filename:
                QTimer.singleShot(0,lambda:self.open_documents([filename]))
                event.accept();return True
        return super().event(event)
    def bind(self,window):
        self.host=window
        for filename in self.open_requests:window.open_file(filename)
        self.open_requests.clear()

    def open_documents(self,filenames):
        if not self.host:
            self.open_requests.extend(filenames);return
        window=self.host
        if window.presentation:window.toggle_presentation()
        if window.isMinimized():window.setWindowState(window.windowState() & ~Qt.WindowMinimized)
        window.show();window.raise_();window.activateWindow()
        for filename in filenames:window.open_file(filename)

def markdown_pdf(filename,destination,prepared=None,*,paginate=False):
    from .markdown_import import render
    return render(filename,destination,prepared,paginate=paginate)
