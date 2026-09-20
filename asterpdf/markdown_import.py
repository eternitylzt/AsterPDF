"""Markdown + embedded HTML import with bounded, explicitly loaded image resources."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape
from urllib.parse import urljoin,urlsplit,unquote
from urllib.request import Request,urlopen
import base64


def prepare(filename):
    import markdown
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.sane_lists import SaneListExtension
    html=markdown.markdown(Path(filename).read_text(encoding='utf-8-sig'),extensions=[TableExtension(),FencedCodeExtension(),SaneListExtension()])
    resources={};failures=[];memo={};base=Path(filename).resolve().as_uri()
    class Images(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=False);self.output=[];self.table=0;self.skip=0
        def handle_starttag(self,tag,attrs):
            if tag in ('script','style','iframe','object'):self.skip+=1;return
            if self.skip:return
            if tag=='table':self.table+=1
            if tag!='img':
                safe=[(k,v) for k,v in attrs if not k.lower().startswith('on')]
                if tag=='table':safe=[(k,v) for k,v in safe if k not in ('width','cellpadding')]+[('cellpadding','3')]
                self.output.append('<'+tag+''.join(' '+k+'="'+escape(v or '',quote=True)+'"' for k,v in safe)+'>');return
            props=dict(attrs);src=props.get('src','');url=urljoin(base,src)
            try:
                if url not in memo:
                    if len(memo)>=80:raise ValueError('Image limit exceeded')
                    parts=urlsplit(url)
                    if parts.scheme=='file':
                        from PySide6.QtCore import QUrl
                        file=Path(QUrl(url).toLocalFile())
                        if file.stat().st_size>16*1024*1024:raise ValueError('Image exceeds 16 MB')
                        raw=file.read_bytes()
                    elif parts.scheme in ('https','http'):
                        with urlopen(Request(url,headers={'User-Agent':'AsterPDF Markdown image loader'}),timeout=5) as response:raw=response.read(16*1024*1024+1)
                    elif parts.scheme=='data' and ';base64,' in src:raw=base64.b64decode(src.split(',',1)[1],validate=True)
                    else:raise ValueError('Unsupported image URL')
                    if len(raw)>16*1024*1024:raise ValueError('Image exceeds 16 MB')
                    name=f'aster-image:{len(resources)}';resources[name]=raw;memo[url]=name
                name=memo[url];limit=180 if self.table else 600
                try:width=min(limit,max(20,int(props.get('width',limit))))
                except ValueError:width=limit
                self.output.append(f'<img src="{name}" width="{width}" />')
            except Exception as error:
                failures.append(src);self.output.append('<p>[Image unavailable: '+escape(props.get('alt') or src)+']</p>')
        def handle_endtag(self,tag):
            if tag in ('script','style','iframe','object'):
                self.skip=max(0,self.skip-1);return
            if self.skip:return
            if tag=='table':self.table=max(0,self.table-1)
            self.output.append('</'+tag+'>')
        def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
        def handle_data(self,data):
            if not self.skip:self.output.append(data)
        def handle_entityref(self,name):
            if not self.skip:self.output.append('&'+name+';')
        def handle_charref(self,name):
            if not self.skip:self.output.append('&#'+name+';')
    parser=Images();parser.feed(html);parser.close()
    return ''.join(parser.output),resources,failures


def render(filename,destination,prepared=None):
    from PySide6.QtCore import QUrl,Qt,QSize,QBuffer,QByteArray,QIODevice
    from PySide6.QtGui import QTextDocument,QPageSize,QFont,QTextCursor,QTextCharFormat,QColor,QImage,QPainter,QImageReader
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtPrintSupport import QPrinter
    html,resources,failures=prepared if prepared is not None else prepare(filename)
    class LocalDocument(QTextDocument):
        def loadResource(self,kind,url):return None  # Only the preloaded resources may be read.
    doc=LocalDocument();doc.setBaseUrl(QUrl.fromLocalFile(str(Path(filename).resolve().parent)+'/'))
    doc.setDefaultFont(QFont('Microsoft YaHei' if __import__('sys').platform=='win32' else 'sans-serif',11))
    doc.setDefaultStyleSheet('body {color:#111111;background:white;} p {margin-top:5px;margin-bottom:7px;} pre {background:#f3f5f7;} th {background:#eef1f5;}')
    for name,raw in resources.items():
        if b'<svg' in raw[:2048]:
            svg=QSvgRenderer(raw);size=svg.defaultSize()
            if not svg.isValid() or size.isEmpty():continue
            size.scale(QSize(1600,1600),Qt.KeepAspectRatio);image=QImage(size,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
            painter=QPainter(image);svg.render(painter);painter.end()
        else:
            buffer=QBuffer();buffer.setData(QByteArray(raw));buffer.open(QIODevice.ReadOnly);reader=QImageReader(buffer);size=reader.size()
            if size.width()*size.height()>40_000_000:continue
            if size.width()>2400 or size.height()>2400:reader.setScaledSize(size.scaled(QSize(2400,2400),Qt.KeepAspectRatio))
            image=reader.read()
        if not image.isNull():doc.addResource(QTextDocument.ImageResource,QUrl(name),image)
    doc.setHtml(html)
    cursor=QTextCursor(doc);cursor.select(QTextCursor.Document);ink=QTextCharFormat();ink.setForeground(QColor('#111111'));cursor.mergeCharFormat(ink)
    printer=QPrinter(QPrinter.HighResolution);printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(str(destination));printer.setPageSize(QPageSize(QPageSize.A4));doc.print_(printer)
    return str(destination)
