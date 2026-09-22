"""Scalable, high-contrast quick-tool icons, drawn at device pixel ratio."""
from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QIcon,QPixmap,QPainter
from PySide6.QtSvg import QSvgRenderer

PATHS={
 'media_play':'<path d="m7 3 17 11-17 11Z"/>',
 'media_pause':'<path d="M7 4h4v20H7ZM17 4h4v20h-4Z"/>',
 'replay':'<path d="M5 10a10 10 0 1 1-1 9M5 3v8h8"/>',
 'reset_speed':'<circle cx="14" cy="14" r="11"/><path d="m11 9 3-2v14m-3 0h6"/>',

 'triangle':'<path d="M14 3 26 24H2Z"/>',
 'diamond':'<path d="M14 2 26 14 14 26 2 14Z"/>',
 'select_annot':'<path stroke-dasharray="2 3" d="M2 2h24v24H2z"/><path d="m8 7 12 9-6 1-3 6Z"/>',
 'underline':'<path d="M6 4h16M14 4v15M6 24h16"/>',
 'strikeout':'<path d="M6 4h16M14 4v19M3 13h22"/>',
 'replace_text':'<path d="M3 4h12M9 4v12M2 11h15M17 20h9m-4-4 4 4-4 4"/>',
 'freetext':'<path d="M3 5h14M10 5v18M21 4h5m-3 0v20m-2 0h5"/>',
 'highlight':'<path d="m5 17 12-13 6 5-12 13-6-1ZM5 17l6 5M3 26h22"/>',
 'ink':'<path d="m5 15 13-12 5 5-13 12-6 1ZM3 26c5-8 9 4 14-2s5 0 8 0"/>',
 'note':'<path d="M3 3h22v16l-6 6H3ZM19 25v-6h6M7 8h12m-6 0v10"/>',
 'caret':'<path d="m4 19 10-12 10 12M8 25h12"/>',
 'squiggly':'<path d="M5 4h18M14 4v14M3 24q3-6 6 0t6 0t6 0t6 0"/>',
 'add_video':'<path d="M3 5h22v18H3zM11 9l8 5-8 5Z"/>',

 'tabs':'<path d="m6 10 8 8 8-8"/>',
 'minimap':'<path d="M4 3h14v22H4zM21 3h4v22h-4zM4 11h14v7H4z"/>',
 'flip_h':'<path d="M14 2v24M3 7l7 7-7 7ZM25 7l-7 7 7 7Z"/>',
 'flip_v':'<path d="M2 14h24M7 3l7 7 7-7ZM7 25l7-7 7 7Z"/>',
 'annotate':'<path d="m5 19 14-14 4 4-14 14-6 2Z M16 8l4 4"/>',
 'objects':'<path d="M7 7h14v14H7Z"/><path d="M3 3h6v6H3zM19 3h6v6h-6zM3 19h6v6H3zM19 19h6v6h-6z"/>',
 'pages':'<path d="M4 3h8v10H4zM16 3h8v10h-8zM4 17h8v8H4zM16 17h8v8h-8z"/>',
 'extract':'<path d="M4 17v7h20v-7M14 3v14m-5-5 5 5 5-5"/>',
 'text_ops':'<path d="M4 6V3h20v3M14 3v22m-5 0h10"/>',
 'add_image':'<path d="M3 5h22v19H3zM3 20l7-8 6 7 4-4 5 6"/><circle cx="19" cy="10" r="2"/>',
 'vector_edit':'<path d="M5 23C5 7 23 23 23 5M3 21h4v4H3zM21 3h4v4h-4z"/>',
 'colors':'<path d="M14 2C9 9 5 13 5 17a9 9 0 0 0 18 0c0-4-4-8-9-15Z M8 18c0 3 3 5 5 5"/>',
 'print':'<path d="M7 10V3h14v7M7 21H3V10h22v11h-4M7 16h14v9H7zM20 13h2"/>',
 'file_info':'<circle cx="14" cy="14" r="11"/><path d="M14 12v9M14 7v1"/>',
 'page_fit':'<path d="M9 4H4v5m15-5h5v5M4 19v5h5m10 0h5v-5M9 9h10v10H9z"/>',
 'width_fit':'<path d="M3 4v20M25 4v20M4 14h20m-16-4-4 4 4 4m12-8 4 4-4 4"/>',
 'continuous':'<path d="M5 3h18v7H5zM5 14h18v10H5z"/>',
 'region':'<path stroke-dasharray="3 3" d="M3 3h22v22H3z"/>',
 'save':'<path d="M4 3h17l4 4v18H4zM8 3v8h11V3M9 25V16h11v9"/>',
 'delete':'<path d="M4 7h20M10 7V3h8v4M7 7l1 18h12l1-18M11 11v10m6-10v10"/>',
 'blank':'<path d="M5 3h13l5 5v17H5zM14 11v10m-5-5h10"/>',
 'rotate':'<path d="M4 12a10 10 0 1 1 2 10M4 4v8h8"/>',
 'merge':'<path d="M4 3h8v9h-8zM16 3h8v9h-8zM8 12v5h12v-5M14 17v8m-3-3 3 3 3-3"/>',
 'play':'<path d="m4 4 12 10-12 10ZM21 4v20M25 4v20"/>',
 'sidebar':'<path d="M3 4h22v20H3zM10 4v20"/>',
 'line':'<path d="M4 23 24 5"/>',
 'arrow':'<path d="M4 23 24 5m-9 1 9-1-1 9"/>',
 'rectangle':'<path d="M3 5h22v18H3z"/>',
 'ellipse':'<ellipse cx="14" cy="14" rx="11" ry="9"/>',
 'check':'<path d="m4 14 7 7L24 6"/>',
 'close':'<path d="m6 6 16 16M22 6 6 22"/>',
 'tool':'<circle cx="14" cy="14" r="8"/><path d="M14 3v6m0 10v6M3 14h6m10 0h6"/>',

 'select':'<path d="M5 3v19l5-5 4 8 4-2-4-8h8Z"/>',
 'hand':'<path d="M8 14V7a2 2 0 0 1 4 0v6-9a2 2 0 0 1 4 0v9-7a2 2 0 0 1 4 0v8-4a2 2 0 0 1 4 0v8c0 6-3 8-8 8-4 0-6-2-8-5l-4-6c-1-3 2-4 4-1Z"/>',
 'undo':'<path d="m10 5-7 7 7 7M4 12h12c6 0 9 4 8 10"/>',
 'redo':'<path d="m18 5 7 7-7 7m6-7H12c-6 0-9 4-8 10"/>',
 'prev':'<path d="m18 5-9 9 9 9"/>',
 'next':'<path d="m10 5 9 9-9 9"/>',
 'minus':'<path d="M5 14h18"/>',
 'plus':'<path d="M5 14h18M14 5v18"/>',
 'star':'<path d="m14 3 3.5 7 7.5 1-5.5 5.5 1.5 8-7-4-7 4 1.5-8L3 11l7.5-1Z"/>',
 'more':'<circle cx="5" cy="14" r="1.5"/><circle cx="14" cy="14" r="1.5"/><circle cx="23" cy="14" r="1.5"/>'}

def icon(name,dark=False):
    color='#d6dfec' if dark else '#101f35'
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28"><g fill="none" stroke="{color}" stroke-width="{2 if dark else 2.5}" stroke-linecap="round" stroke-linejoin="round">{PATHS.get(name,PATHS["tool"])}</g></svg>'
    pix=QPixmap(84,84);pix.fill(Qt.transparent);painter=QPainter(pix);QSvgRenderer(svg.encode()).render(painter);painter.end();pix.setDevicePixelRatio(3)
    return QIcon(pix)
