"""Markdown + embedded HTML import with bounded, explicitly loaded image resources."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape
from urllib.parse import urljoin,urlsplit,unquote
from urllib.request import Request,urlopen
import base64


def prepare(filename):
    # TeX layout has a deep call graph. Use an explicit bounded stack on every OS;
    # Qt's default Windows worker stack can be too small for nested fractions.
    from PySide6.QtCore import QThread
    class ImportThread(QThread):
        def run(self):
            try:self.result=_prepare(filename)
            except Exception as error:self.error=error
    thread=ImportThread();thread.setStackSize(4*1024*1024);thread.error=None
    thread.start();thread.wait()
    if thread.error:raise thread.error
    return thread.result


def _prepare(filename):
    from markdown_it import MarkdownIt
    from mdit_py_plugins.dollarmath import dollarmath_plugin
    from mdit_py_plugins.tasklists import tasklists_plugin
    from .markdown_math import MathRenderer
    resources={};failures=[];memo={};base=Path(filename).resolve().as_uri()
    math=MathRenderer()
    def formula(tex,options):
        try:
            raw=math.svg(tex,options.get('display_mode',False))
            name=f'aster-math:{len(resources)}';resources[name]=raw
            return '<img src="'+name+'" />'
        except Exception:
            failures.append('Math: '+tex)
            return '<span style="color:#a12622">[Formula: '+escape(tex)+']</span>'
    parser=MarkdownIt('gfm-like',{'html':True})
    parser.use(dollarmath_plugin,allow_labels=False,allow_space=True,allow_digits=False,renderer=formula)
    parser.use(tasklists_plugin)
    parser.renderer.rules['math_block']=lambda tokens,i,options,env: '<p align="center">'+formula(tokens[i].content,{'display_mode':True})+'</p>'
    # GitHub's fenced math blocks use the same offline TeX renderer.
    fence=parser.renderer.rules['fence']
    parser.renderer.rules['fence']=lambda tokens,i,options,env: '<p align="center">'+formula(tokens[i].content,{'display_mode':True})+'</p>' if tokens[i].info.strip()=='math' else fence(tokens,i,options,env)
    html=parser.render(Path(filename).read_text(encoding='utf-8-sig'))
    class Images(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=False);self.output=[];self.table=0;self.skip=0
        def handle_starttag(self,tag,attrs):
            if tag in ('script','style','iframe','object'):self.skip+=1;return
            if self.skip:return
            if tag=='table':self.table+=1
            if tag=='input':
                self.output.append('☑ ' if 'checked' in dict(attrs) else '☐ ');return
            if tag!='img':
                safe=[(k,v) for k,v in attrs if not k.lower().startswith('on')]
                if tag=='table':safe=[(k,v) for k,v in safe if k not in ('width','cellpadding','cellspacing','border')]+[('cellpadding','5'),('cellspacing','0'),('border','1')]
                self.output.append('<'+tag+''.join(' '+k+'="'+escape(v or '',quote=True)+'"' for k,v in safe)+'>');return
            props=dict(attrs);src=props.get('src','');url=urljoin(base,src)
            if src.startswith('aster-math:') and src in resources:
                self.output.append('<img src="'+src+'" />');return
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
                try:width=min(limit,max(1,int(props['width']))) if 'width' in props else 0
                except ValueError:width=0
                sizing=f' width="{width}"' if width else ''
                self.output.append(f'<img src="{name}"{sizing} />')
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
    from PySide6.QtCore import QUrl,Qt,QSize,QBuffer,QByteArray,QIODevice,QSizeF,QMarginsF
    from PySide6.QtGui import QTextDocument,QPageSize,QFont,QTextCursor,QTextCharFormat,QColor,QImage,QPainter,QImageReader,QPdfWriter,QPyTextObject,QTextFormat,QTextOption,QFontDatabase
    from PySide6.QtSvg import QSvgRenderer
    html,resources,failures=prepared if prepared is not None else prepare(filename)
    class LocalDocument(QTextDocument):
        def loadResource(self,kind,url):return None  # Only the preloaded resources may be read.
    doc=LocalDocument();doc.setBaseUrl(QUrl.fromLocalFile(str(Path(filename).resolve().parent)+'/'))
    doc.setDefaultFont(QFont('Microsoft YaHei' if __import__('sys').platform=='win32' else 'sans-serif',11))
    option=doc.defaultTextOption();option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere);doc.setDefaultTextOption(option)
    fixed=QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
    doc.setDefaultStyleSheet('body {color:#111111;background:white;} p {margin-top:5px;margin-bottom:9px;line-height:135%;} h1 {font-size:24pt;margin-top:18px;margin-bottom:12px;} h2 {font-size:18pt;margin-top:16px;margin-bottom:10px;} h3 {font-size:14pt;margin-top:12px;} pre {background:#f3f5f7;white-space:pre-wrap;margin:8px;font-size:9pt;} code {font-family:MONOSPACE;background:#f3f5f7;} th {background:#eef1f5;} td,th {border:1px solid #cdd3dc;} blockquote {margin-left:16px;color:#57606a;}'.replace('MONOSPACE',fixed))
    for name,raw in resources.items():
        if name.startswith('aster-math:'):continue
        if b'<svg' in raw[:2048]:
            svg=QSvgRenderer(raw);size=svg.defaultSize()
            if not svg.isValid() or size.isEmpty():continue
            if size.width()>1600 or size.height()>1600:size.scale(QSize(1600,1600),Qt.KeepAspectRatio)
            image=QImage(size,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
            painter=QPainter(image);svg.render(painter);painter.end()
        else:
            buffer=QBuffer();buffer.setData(QByteArray(raw));buffer.open(QIODevice.ReadOnly);reader=QImageReader(buffer);size=reader.size()
            if size.width()*size.height()>40_000_000:continue
            if size.width()>2400 or size.height()>2400:reader.setScaledSize(size.scaled(QSize(2400,2400),Qt.KeepAspectRatio))
            image=reader.read()
        if not image.isNull():doc.addResource(QTextDocument.ImageResource,QUrl(name),image)
    doc.setHtml(html)
    cursor=QTextCursor(doc);cursor.select(QTextCursor.Document);ink=QTextCharFormat();ink.setForeground(QColor('#111111'));cursor.mergeCharFormat(ink)
    class FormulaObject(QPyTextObject):
        def __init__(self,parent):
            super().__init__(parent);self.svgs={name:QSvgRenderer(raw) for name,raw in resources.items() if name.startswith('aster-math:')}
        def intrinsicSize(self,document,pos,fmt):
            svg=self.svgs[fmt.property(QTextFormat.UserProperty)]
            return QSizeF(svg.defaultSize())
        def drawObject(self,painter,rect,document,pos,fmt):
            self.svgs[fmt.property(QTextFormat.UserProperty)].render(painter,rect)
    handler=FormulaObject(doc);kind=QTextFormat.UserObject+1
    doc.documentLayout().registerHandler(kind,handler)
    fragments=[];block=doc.begin()
    while block.isValid():
        it=block.begin()
        while not it.atEnd():
            fragment=it.fragment()
            if fragment.isValid():fragments.append((fragment.position(),fragment.length(),fragment.charFormat()))
            it+=1
        block=block.next()
    for pos,length,fmt in reversed(fragments):
        cursor=QTextCursor(doc);cursor.setPosition(pos);cursor.setPosition(pos+length,QTextCursor.KeepAnchor)
        if fmt.isImageFormat():
            image=fmt.toImageFormat();name=image.name()
            if name in handler.svgs:
                replacement=QTextCharFormat();replacement.setObjectType(kind);replacement.setProperty(QTextFormat.UserProperty,name);replacement.setVerticalAlignment(QTextCharFormat.AlignMiddle)
                cursor.insertText('\ufffc',replacement)
            else:
                resource=doc.resource(QTextDocument.ImageResource,QUrl(name))
                if isinstance(resource,QImage) and not resource.isNull():
                    width=min(640,image.width() or resource.width());image.setWidth(width);image.setHeight(width*resource.height()/resource.width());cursor.setCharFormat(image)
        elif fmt.isAnchor():
            fmt.setForeground(QColor('#0969da'));cursor.setCharFormat(fmt)
    # QPdfWriter never enumerates or connects to physical/network printers.
    # Pre-paginate so QTextDocument.print_ retains our vector object handler.
    writer=QPdfWriter(str(destination));writer.setResolution(96);writer.setPageSize(QPageSize(QPageSize.A4));writer.setPageMargins(QMarginsF(15,15,15,15))
    doc.documentLayout().setPaintDevice(writer);doc.setPageSize(QSizeF(writer.width(),writer.height()));doc.print_(writer)
    return str(destination)
