"""Markdown PDF and portable HTML exports from the opened source snapshot."""
from pathlib import Path
import os
import tempfile
from PySide6.QtWidgets import QFileDialog,QWidget,QHBoxLayout,QLabel,QComboBox
from .i18n import L


class MarkdownSaveDialog(QFileDialog):
    def __init__(self,window,tab,allow_html=True):
        source=Path(tab.document.original)
        super().__init__(window,L('Markdown 另存为','Save Markdown as'),str(source.parent),'PDF (*.pdf);;HTML (*.html *.htm)' if allow_html else 'PDF (*.pdf)')
        self.setOption(QFileDialog.DontUseNativeDialog);self.setAcceptMode(QFileDialog.AcceptSave);self.setDefaultSuffix('pdf')
        self.selectFile(source.with_suffix('.pdf').name)
        self.layout_choice=QComboBox()
        self.layout_choice.addItem(L('A4 分页','A4 pages'),True);self.layout_choice.addItem(L('不分页（连续长页）','Unpaginated (one long page)'),False)
        self.layout_choice.setCurrentIndex(0 if window.settings.value('markdown/export_paginate',True,type=bool) else 1)
        row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.addWidget(QLabel(L('PDF 布局','PDF layout')));layout.addWidget(self.layout_choice,1)
        if tab.document.revision:
            self.layout_choice.clear();self.layout_choice.addItem(L('保留当前布局和 PDF 编辑','Keep current layout and PDF edits'),None);self.layout_choice.setEnabled(False)
            layout.addWidget(QLabel(L('重新排版会丢失 PDF 编辑，故保留原样。','Reflow would lose PDF edits; preserving them.')))
        self.pdf_options=row
        self.html_note=QLabel(L('HTML 保存打开时的 Markdown 内容，包含公式和已加载图片；不包含另行添加的 PDF 编辑或批注。','HTML saves the opened Markdown with formulas and loaded images; subsequent PDF edits and annotations are not included.'))
        self.html_note.setWordWrap(True);self.html_note.hide()
        grid=self.layout();grid.addWidget(row,grid.rowCount(),0,1,grid.columnCount());grid.addWidget(self.html_note,grid.rowCount(),0,1,grid.columnCount())
        self.filterSelected.connect(self.format_changed)

    @property
    def html_selected(self):
        return self.selectedNameFilter().startswith('HTML')

    def format_changed(self,*_):
        html=self.html_selected;self.pdf_options.setVisible(not html);self.html_note.setVisible(html)
        selected=self.selectedFiles();suffix='html' if html else 'pdf';self.setDefaultSuffix(suffix)
        if selected:
            path=Path(selected[0])
            if path.suffix.lower() in ('.pdf','.html','.htm'):self.selectFile(path.with_suffix('.'+suffix).name)


def export_markdown_html(tab,destination):
    from .markdown_html import build_html
    if Path(destination).suffix.lower() not in ('.html','.htm'):
        raise ValueError(L('请选择 .html 或 .htm 文件名；Markdown 源文件不会被覆盖。','Choose an .html or .htm filename; the Markdown source will not be overwritten.'))
    html=build_html(getattr(tab,'markdown_source',tab.document.original),tab.markdown_prepared,tab.dark)
    fd,temporary=tempfile.mkstemp(prefix='.aster-markdown-',suffix='.html',dir=Path(destination).parent);os.close(fd)
    try:
        Path(temporary).write_text(html,encoding='utf-8');os.replace(temporary,destination)
    finally:Path(temporary).unlink(missing_ok=True)


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
