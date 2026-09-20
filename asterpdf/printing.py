"""Qt native printing with one rasterized print page in memory at a time."""
from pathlib import Path
import pymupdf as fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QDialog,QVBoxLayout,QTextBrowser,QPushButton,QProgressDialog
from .i18n import L,tr


def information(tab):
    def inspect(job):
        with fitz.open(tab.document.path) as pdf:
            return pdf.metadata,[(p.rect.width,p.rect.height) for p in pdf],len(pdf),len(pdf.embfile_names())
    def show(result):
        import html
        metadata,sizes,count,attachments=result
        from .metadata_display import readable
        raw={k:str(v) for k,v in metadata.items() if k in ('title','author') and v and readable(v)!=str(v).strip()}
        metadata={k:readable(v) if k in ('title','author') else v for k,v in metadata.items()}
        lines=[L('文件：','File: ')+tab.document.original,L('大小：','Size: ')+f'{Path(tab.document.original).stat().st_size/1024**2:.2f} MB',L('页数：','Pages: ')+str(count),L('附件：','Attachments: ')+str(attachments)]
        labels={'title':L('标题','Title'),'author':L('作者','Author'),'subject':L('主题','Subject'),'creator':L('创建程序','Creator'),'producer':L('生成程序','Producer'),'creationDate':L('创建时间','Created'),'modDate':L('修改时间','Modified'),'format':L('格式','Format')}
        lines.extend(labels.get(k,k)+': '+str(v) for k,v in metadata.items() if v and k in labels)
        if raw:lines.append(L('元数据含排版标记或损坏尾段，已整理显示；可展开查看原始值。','Metadata contains layout commands or a malformed tail. You can show the original values below.'))
        lines.extend(L(f'第 {n+1} 页：',f'Page {n+1}: ')+f'{w*25.4/72:.1f} × {h*25.4/72:.1f} mm' for n,(w,h) in enumerate(sizes[:200]))
        dialog=QDialog(tab);dialog.setWindowTitle(tr('file_info'));dialog.resize(570,480);layout=QVBoxLayout(dialog);browser=QTextBrowser();browser.setPlainText('\n'.join(lines));layout.addWidget(browser)
        if raw:
            original=QTextBrowser();original.setPlainText('\n\n'.join(labels.get(k,k)+': '+v for k,v in raw.items()));original.hide();toggle=QPushButton(L('显示 / 隐藏原始元数据','Show / hide original metadata'));toggle.clicked.connect(lambda:original.setVisible(not original.isVisible()));layout.addWidget(toggle);layout.addWidget(original)
        button=QPushButton(L('关闭','Close'));button.clicked.connect(dialog.accept);layout.addWidget(button);dialog.exec()
    tab.queue.submit(inspect,show,tab.error)


def print_document(tab,printer=None,completed=None):
    from PySide6.QtPrintSupport import QPrinter,QPrintDialog
    from .rendering import image_from_pixmap
    if printer is None:
        printer=QPrinter(QPrinter.HighResolution);printer.setResolution(300)
        dialog=QPrintDialog(printer,tab);dialog.setMinMax(1,tab.info['count']);dialog.setOption(QPrintDialog.PrintPageRange)
        if dialog.exec()!=QDialog.Accepted:return
    if tab.busy:return
    painter=QPainter()
    if not painter.begin(printer):tab.error(L('无法启动打印机。','Could not start the printer.'));return
    start=max(0,printer.fromPage()-1);end=min(tab.info['count'],printer.toPage() or tab.info['count'])
    progress=QProgressDialog(tr('print'),tr('cancel'),start,end,tab);progress.setWindowModality(Qt.WindowModal);progress.setMinimumDuration(0);progress.show()
    resolution=printer.resolution();state={'page':start};path=str(tab.document.path);tab.busy=True
    def finish(error=None,cancelled=False):
        painter.end();progress.close();tab.busy=False
        if error:tab.error(str(error))
        if completed:completed(error is None and not cancelled)
    def next_page():
        if progress.wasCanceled():printer.abort();finish(cancelled=True);return
        n=state['page']
        if n>=end:finish();return
        def render(job):
            with fitz.open(path) as pdf:
                page=pdf[n];scale=resolution/72
                if page.rect.width*page.rect.height*scale*scale>32_000_000:scale=(32_000_000/(page.rect.width*page.rect.height))**.5
                return image_from_pixmap(page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False))
        def done(image):
            if n>start and not printer.newPage():finish(L('打印机拒绝下一页。','Printer refused a new page.'));return
            area=printer.pageLayout().paintRectPixels(printer.resolution());size=image.size().scaled(area.size(),Qt.KeepAspectRatio)
            from PySide6.QtCore import QRect
            target=QRect(area.x()+(area.width()-size.width())//2,area.y()+(area.height()-size.height())//2,size.width(),size.height())
            painter.drawImage(target,image);state['page']+=1;progress.setValue(state['page']);next_page()
        tab.queue.submit(render,done,finish)
    # Retain printer/painter through callbacks until all pages or cancellation.
    next_page()
