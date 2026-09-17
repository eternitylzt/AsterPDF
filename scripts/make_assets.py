"""Deterministic vector brand and native icon files; no external artwork."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
assets=ROOT/'assets';resources=ROOT/'asterpdf'/'resources'
assets.mkdir(exist_ok=True);resources.mkdir(exist_ok=True)
svg='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><rect width="1024" height="1024" rx="220" fill="#172942"/><path d="M512 130 C554 391 633 470 894 512 C633 554 554 633 512 894 C470 633 391 554 130 512 C391 470 470 391 512 130Z" fill="#b6c6ff"/><path d="M512 252 C542 429 595 482 772 512 C595 542 542 595 512 772 C482 595 429 542 252 512 C429 482 482 429 512 252Z" fill="#f8fbff"/></svg>'''
(assets/'asterpdf.svg').write_text(svg,encoding='utf-8')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray
app=QApplication.instance() or QApplication([])
image=QImage(1024,1024,QImage.Format_ARGB32);image.fill(0)
painter=QPainter(image);QSvgRenderer(QByteArray(svg.encode())).render(painter);painter.end()
image.save(str(assets/'asterpdf.png'))
im=Image.open(assets/'asterpdf.png')
im.save(assets/'asterpdf.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
im.save(assets/'asterpdf.icns',sizes=[(16,16),(32,32),(64,64),(128,128),(256,256),(512,512),(1024,1024)])
im.resize((256,256),Image.Resampling.LANCZOS).save(resources/'asterpdf.png')
logo='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 160"><path d="M80 14 Q90 70 146 80 Q90 90 80 146 Q70 90 14 80 Q70 70 80 14Z" fill="#526fe7"/><text x="174" y="101" font-family="Segoe UI,Arial,sans-serif" font-size="76" font-weight="600" fill="#243c67">AsterPDF</text><text x="179" y="136" font-family="Segoe UI,Arial,sans-serif" font-size="18" fill="#698098">Read · Edit · Animate · Annotate · Extract</text></svg>'''
(assets/'wordmark.svg').write_text(logo,encoding='utf-8')
