"""Generate all AsterPDF brand assets from shared, font-free SVG geometry."""
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
RESOURCES = ROOT / 'asterpdf' / 'resources'

# The four curved tips stay recognizable when the badge is only 16 pixels wide.
STAR = 'M64 16C69 45 81 57 112 64C81 71 69 83 64 112C59 83 47 71 16 64C47 57 59 45 64 16Z'
BADGE = f'''<defs>
  <linearGradient id="plate" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop stop-color="#293d68"/><stop offset="1" stop-color="#101a36"/>
  </linearGradient>
  <linearGradient id="edge" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop stop-color="#94b3ff" stop-opacity=".78"/>
    <stop offset=".55" stop-color="#5874b0" stop-opacity=".36"/>
    <stop offset="1" stop-color="#465e9b" stop-opacity=".2"/>
  </linearGradient>
  <linearGradient id="starlight" x1="25%" y1="0%" x2="75%" y2="100%">
    <stop stop-color="#f1f7ff"/><stop offset=".52" stop-color="#c1d4ff"/>
    <stop offset="1" stop-color="#9a9bff"/>
  </linearGradient>
</defs>
<rect x="4" y="4" width="120" height="120" rx="28" fill="url(#plate)"/>
<rect x="5" y="5" width="118" height="118" rx="27" fill="none" stroke="url(#edge)" stroke-width="2"/>
<path d="{STAR}" fill="url(#starlight)"/>
<path d="M64 16C69 45 81 57 112 64L64 64Z" fill="#fff" opacity=".24"/>
<path d="M64 64H112C81 71 69 83 64 112Z" fill="#695cda" opacity=".22"/>
<path d="M64 16C59 45 47 57 16 64" fill="none" stroke="#f1f7ff" stroke-opacity=".64" stroke-width="1.5" stroke-linecap="round"/>'''

# Custom letter shapes keep weight, spacing and appearance independent of fonts.
ASTER = '''<path d="M147 87L166 41L185 87M153 72H179"/>
  <path d="M220 57C216 54 211 52 206 53C199 53 195 56 195 61C195 66 199 68 207 70C215 72 221 74 221 79C221 85 215 88 207 88C202 88 198 86 195 83"/>
  <path d="M235 44V77Q235 88 246 88H252M227 54H252"/>
  <path d="M262 70H292C292 60 286 53 278 53C268 53 262 61 262 70C262 81 269 88 279 88C284 88 288 86 291 84"/>
  <path d="M304 87V54M304 66C307 57 313 53 322 54"/>'''
PDF = '''<path d="M337 87V41H354C365 41 371 47 371 55C371 64 365 70 354 70H337"/>
  <path d="M382 87V41H395C410 41 419 50 419 64C419 78 410 87 395 87Z"/>
  <path d="M431 87V41H459M431 63H454"/>'''


def svg(width, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 128" '
        'role="img" aria-label="AsterPDF">\n'
        f'{body}\n</svg>\n'
    )


def wordmark(ink, accent):
    return svg(471, f'''{BADGE}
<g fill="none" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round">
  <g stroke="{ink}">{ASTER}</g>
  <g stroke="{accent}">{PDF}</g>
</g>''')


def main():
    app = QGuiApplication.instance() or QGuiApplication([])
    badge = svg(128, BADGE)
    designs = {
        'asterpdf.svg': badge,
        'wordmark.svg': wordmark('#172b4c', '#3c54b1'),
        'wordmark-dark.svg': wordmark('#f1f5ff', '#b0bfff'),
    }
    for name, vector in designs.items():
        for directory in (ASSETS, RESOURCES):
            (directory / name).write_text(vector, encoding='utf-8', newline='\n')

    renderer = QSvgRenderer(QByteArray(badge.encode('utf-8')))
    if not renderer.isValid():
        raise ValueError('Invalid AsterPDF badge SVG')
    image = QImage(1024, 1024, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image = image.convertToFormat(QImage.Format_RGBA8888)
    pixels = Image.frombytes('RGBA', (1024, 1024), image.bits())
    pixels.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / 'asterpdf.png')
    pixels.save(ASSETS / 'asterpdf.ico', sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    pixels.save(ASSETS / 'asterpdf.icns')
    # Retain the raster application resource for environments without SVG icons.
    (RESOURCES / 'asterpdf.png').write_bytes((ASSETS / 'asterpdf.png').read_bytes())


if __name__ == '__main__':
    main()
