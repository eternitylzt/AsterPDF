"""Markdown PDF export with independent reading and export layouts."""
from pathlib import Path
import os
import tempfile
from PySide6.QtWidgets import QFileDialog,QWidget,QHBoxLayout,QLabel,QComboBox
from .i18n import L


class MarkdownSaveDialog(QFileDialog):
    def __init__(self,window,tab):
        super().__init__(window,L('Markdown 另存为 PDF','Save Markdown as PDF'),str(Path(tab.document.original).with_suffix('.pdf')),'PDF (*.pdf)')
        self.setOption(QFileDialog.DontUseNativeDialog);self.setAcceptMode(QFileDialog.AcceptSave);self.setDefaultSuffix('pdf')
        self.layout_choice=QComboBox()
        self.layout_choice.addItem(L('A4 分页','A4 pages'),True);self.layout_choice.addItem(L('不分页（连续长页）','Unpaginated (one long page)'),False)
        self.layout_choice.setCurrentIndex(0 if window.settings.value('markdown/export_paginate',True,type=bool) else 1)
        row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.addWidget(QLabel(L('PDF 布局','PDF layout')));layout.addWidget(self.layout_choice,1)
        if tab.document.revision:
            self.layout_choice.clear();self.layout_choice.addItem(L('保留当前布局和 PDF 编辑','Keep current layout and PDF edits'),None);self.layout_choice.setEnabled(False)
            layout.addWidget(QLabel(L('重新排版会丢失 PDF 编辑，故保留原样。','Reflow would lose PDF edits; preserving them.')))
        grid=self.layout();grid.addWidget(row,grid.rowCount(),0,1,grid.columnCount())


def export_markdown(tab,destination,paginate):
    """Render the opened snapshot, including every code line, never a viewport screenshot."""
    from .markdown_import import render
    if Path(destination).suffix.lower()!='.pdf':
        raise ValueError(L('请选择 .pdf 文件名；Markdown 源文件不会被覆盖。','Choose a .pdf filename; the Markdown source will not be overwritten.'))
    fd,temporary=tempfile.mkstemp(prefix='.aster-markdown-',suffix='.pdf',dir=Path(destination).parent);os.close(fd)
    try:
        render(tab.document.original,temporary,tab.markdown_prepared,paginate=paginate)
        os.replace(temporary,destination)
    finally:Path(temporary).unlink(missing_ok=True)
