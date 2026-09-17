from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QComboBox, QCheckBox, QTextEdit, QLabel, QFileDialog, QPushButton, QHBoxLayout)
from .i18n import tr, L


class FormDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.form = QFormLayout(self)
        self.inputs = {}

    def text(self, key, label, value=''):
        w = QLineEdit(str(value)); self.inputs[key] = w; self.form.addRow(label, w)
        return w

    def number(self, key, label, value, minimum=0, maximum=10000, decimals=0):
        w = QDoubleSpinBox() if decimals else QSpinBox()
        if decimals: w.setDecimals(decimals)
        w.setRange(minimum, maximum); w.setValue(value)
        self.inputs[key] = w; self.form.addRow(label, w)
        return w

    def choice(self, key, label, choices):
        w = QComboBox()
        for name, value in choices: w.addItem(name, value)
        self.inputs[key] = w; self.form.addRow(label, w)
        return w

    def check(self, key, label, checked=True):
        w = QCheckBox(); w.setChecked(checked); self.inputs[key] = w; self.form.addRow(label, w)
        return w

    def note(self, text):
        w = QLabel(text); w.setWordWrap(True); self.form.addRow(w)

    def finish(self):
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr('apply'));buttons.button(QDialogButtonBox.Cancel).setText(tr('cancel'))
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)
        return self

    def values(self):
        data = {}
        for k, w in self.inputs.items():
            if isinstance(w, QLineEdit): data[k] = w.text()
            elif isinstance(w, QComboBox): data[k] = w.currentData()
            elif isinstance(w, QCheckBox): data[k] = w.isChecked()
            else: data[k] = w.value()
        return data

class MergeList(__import__('PySide6.QtWidgets',fromlist=['QListWidget']).QListWidget):
    def __init__(self,dialog):
        super().__init__(dialog);self.dialog=dialog
        from PySide6.QtWidgets import QAbstractItemView
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDefaultDropAction(Qt.MoveAction);self.setAcceptDrops(True)

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
        else:super().dragEnterEvent(event)

    def dragMoveEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
        else:super().dragMoveEvent(event)

    def dropEvent(self,event):
        if event.mimeData().hasUrls():
            self.dialog.add_files([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]);event.acceptProposedAction()
        else:super().dropEvent(event)


class MergeDialog(QDialog):
    """A standalone queue of immutable input snapshots, producing a new PDF."""
    def __init__(self,parent,include_open=False):
        super().__init__(parent)
        self.host=parent.window if hasattr(parent,'document') else parent
        self.setWindowTitle(tr('merge'));self.resize(700,570)
        from PySide6.QtWidgets import QVBoxLayout
        root=QVBoxLayout(self)
        title=QLabel(L('合并为新 PDF。拖入文件并拖动排序；选中后可移除。','Merge into a new PDF. Drop files, drag to reorder, or select to remove.'));title.setWordWrap(True);root.addWidget(title)
        self.list=MergeList(self);root.addWidget(self.list,1)
        row=QHBoxLayout();root.addLayout(row)
        for label,callback in [(L('添加 PDF','Add PDFs'),self.browse),(L('添加已打开的 PDF','Add open PDFs'),self.add_open),(L('移除','Remove'),self.remove)]:
            button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
        self.note=QLabel(L('输出文件会包含队列中的全部页面。已打开文件使用当前编辑结果。','The output includes all queued pages. Open files use their current edited content.'));self.note.setWordWrap(True);root.addWidget(self.note)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(L('合并…','Merge…'));self.buttons.button(QDialogButtonBox.Cancel).setText(tr('cancel'))
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject);root.addWidget(self.buttons)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        if include_open:self.add_open()

    def accept(self):
        files=self.files()
        if not files:return
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False);self.note.setText(tr('working'))
        def inspect(job):
            import pikepdf
            from .core import feature_warnings
            warnings=[]
            for path in files:
                with pikepdf.open(path) as pdf:warnings.extend(feature_warnings(pdf,True))
            return list(dict.fromkeys(warnings))
        def ready(warnings):
            if not self.isVisible():return
            from PySide6.QtWidgets import QMessageBox
            if warnings and QMessageBox.warning(self,tr('merge'),'\n\n'.join(warnings),QMessageBox.Ok|QMessageBox.Cancel)!=QMessageBox.Ok:
                self.buttons.button(QDialogButtonBox.Ok).setEnabled(True);return
            super(MergeDialog,self).accept()
        self.host.queue.submit(inspect,ready,lambda error:(self.note.setText(str(error)),self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)))

    def browse(self):
        files,_=QFileDialog.getOpenFileNames(self,tr('merge'),'','PDF (*.pdf)');self.add_files(files)

    def add_open(self):
        for tab in self.host.document_tabs():
            self.add_files([str(tab.document.path)],{str(tab.document.path):__import__('pathlib').Path(tab.document.original).name+(' *' if tab.document.dirty else '')})

    def add_files(self,files,names=None):
        from pathlib import Path
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QPixmap,QIcon
        for path in files:
            path=str(path)
            if not path.lower().endswith('.pdf') or not Path(path).is_file():continue
            name=(names or {}).get(path,Path(path).name)
            item=QListWidgetItem(name);item.setData(Qt.UserRole,path);item.setData(Qt.UserRole+1,name)
            item.setToolTip(path);item.setSizeHint(QSize(500,84));self.list.addItem(item);self.list.setIconSize(QSize(58,76))
            def render(job,path=path):
                import pymupdf as fitz
                with fitz.open(path) as doc:
                    return len(doc),doc[0].get_pixmap(matrix=fitz.Matrix(60/doc[0].rect.width,60/doc[0].rect.width)).tobytes('png')
            def ready(result,path=path):
                if not self.isVisible():return
                for i in range(self.list.count()):
                    it=self.list.item(i)
                    if it.data(Qt.UserRole)==path:
                        pix=QPixmap();pix.loadFromData(result[1]);it.setIcon(QIcon(pix));it.setText(it.data(Qt.UserRole+1)+L(f'  ·  {result[0]} 页',f'  ·  {result[0]} pages'))
            self.host.queue.submit(render,ready,lambda error:self.note.setText(str(error)))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.list.count()))

    def remove(self):
        for item in self.list.selectedItems():self.list.takeItem(self.list.row(item))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.list.count()))

    def files(self):return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]
