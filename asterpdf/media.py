"""Static animate adapter and embedded media extraction. No PDF JavaScript VM."""
from __future__ import annotations
from dataclasses import dataclass, field
from .i18n import L
import hashlib
from pathlib import Path
import re
import pikepdf as pp
import pymupdf as fitz
from .core import Unsupported


@dataclass
class Animation:
    key: str
    page: int
    rect: tuple
    frames: list[int]
    fps: float = 12
    method: str = 'icon/widget'
    hide: list[int] = field(default_factory=list)
    buttons: list[tuple] = field(default_factory=list)
    variable_fps: list[float] = field(default_factory=list)
    warning: str = ''


@dataclass
class EmbeddedMedia:
    page: int
    rect: tuple
    name: str
    xref: int
    kind: str
    warning: str = ''
    annotation_xref: int = 0
    annotation_name: str = ''


def field_name(annotation):
    parts, current, seen = [], annotation, set()
    while current is not None and current.objgen not in seen:
        seen.add(current.objgen)
        if current.get('/T'):
            parts.insert(0, str(current.T))
        current = current.get('/Parent')
    return '.'.join(parts)


def _javascript_strings(pdf):
    # Inspect only /JS values, never decode every embedded image/video stream.
    seen = set()
    def visit(obj, depth=0):
        if depth > 12 or not isinstance(obj, (pp.Dictionary, pp.Array, pp.Stream)):
            return
        oid = obj.objgen
        if oid != (0, 0):
            if oid in seen:
                return
            seen.add(oid)
        if isinstance(obj, pp.Array):
            for item in obj:
                yield from visit(item, depth+1)
        else:
            if '/JS' in obj:
                js = obj['/JS']
                if isinstance(js, pp.Stream):
                    raw = js.read_bytes()
                    if len(raw) <= 2_000_000:
                        yield raw.decode('latin1', errors='replace')
                else:
                    yield str(js)[:2_000_000]
            for key in ('/AA', '/A', '/PO', '/PV', '/O', '/D', '/U', '/Next', '/OpenAction',
                        '/Names', '/JavaScript', '/Kids'):
                if key in obj:
                    yield from visit(obj[key], depth+1)
    yield from visit(pdf.Root)
    for page in pdf.pages:
        yield from visit(page.obj)
        for a in page.obj.get('/Annots', []):
            yield from visit(a)


def _name_tree(node):
    if not node:
        return
    names = node.get('/Names', [])
    for i in range(0, len(names)-1, 2):
        yield str(names[i]), names[i+1]
    for kid in node.get('/Kids', []):
        yield from _name_tree(kid)


def scan(document):
    animations, media, warnings = [], [], []
    with pp.open(document.path) as pdf, fitz.open(document.path) as view:
        script = '\n'.join(_javascript_strings(pdf))
        for i, page in enumerate(pdf.pages):
            groups, mains, controls = {}, {}, {}
            coord = view[i].transformation_matrix * view[i].rotation_matrix
            for a in page.obj.get('/Annots', []):
                subtype = str(a.get('/Subtype', ''))
                rect = tuple(fitz.Rect(list(map(float, a.get('/Rect', [0, 0, 1, 1])))) * coord)
                name = field_name(a)
                match = re.fullmatch(r'(\d+)\.(\d+)', name)
                if subtype == '/Widget' and match:
                    key, index = match.groups()
                    ap = a.get('/AP', {}).get('/N')
                    if not isinstance(ap, pp.Stream):
                        ap = a.get('/MK', {}).get('/I')
                    if isinstance(ap, pp.Stream):
                        groups.setdefault(key, []).append((int(index), ap.objgen[0], a.objgen[0], rect))
                elif re.fullmatch(r'anm\d+', name):
                    mains[name[3:]] = (rect, a.objgen[0])
                elif re.fullmatch(r'\d+\.[A-Za-z]+', name):
                    key, action = name.split('.')
                    controls.setdefault(key, []).append((rect, action))
                if subtype in ('/RichMedia', '/Movie', '/Screen', '/Sound'):
                    if subtype == '/Screen' and str(a.get('/AA', {}).get('/PV', {}).get('/S', '')) == '/JavaScript':
                        # animate uses a hidden Screen annotation only as a page-open hook.
                        continue
                    candidates = []
                    if subtype == '/RichMedia':
                        content = a.get('/RichMediaContent', {})
                        candidates = list(_name_tree(content.get('/Assets')))
                    elif subtype == '/Movie':
                        f = a.get('/Movie', {}).get('/F')
                        if isinstance(f, pp.Dictionary):
                            candidates = [(str(f.get('/UF', f.get('/F', 'media'))), f)]
                    elif subtype == '/Screen':
                        action = a.get('/A', a.get('/AA', {}).get('/PV', {}))
                        clip = action.get('/R', {}).get('/C', {})
                        fs = clip.get('/D')
                        if isinstance(fs, pp.Dictionary):
                            candidates = [(str(fs.get('/UF', fs.get('/F', 'media'))), fs)]
                    found = False
                    for filename, fs in candidates:
                        suffix = Path(filename).suffix.lower()
                        if suffix not in ('.mp4', '.m4v', '.mov', '.mp3', '.m4a', '.wav', '.ogg', '.webm', '.flac'):
                            continue
                        ef = fs.get('/EF', {})
                        stream = ef.get('/UF', ef.get('/F'))
                        if isinstance(stream, pp.Stream):
                            media.append(EmbeddedMedia(i, rect, Path(filename.replace('\\', '/')).name,
                                         stream.objgen[0], 'audio' if suffix in ('.mp3', '.m4a', '.wav', '.ogg', '.flac') else 'video',
                                         annotation_xref=a.objgen[0],annotation_name=str(a.get('/NM',''))))
                            found = True
                    if not found:
                        warnings.append(L(f'第 {i+1} 页：{subtype} 媒体结构不受支持；不播放外部网址、Flash、3D 或原始声音流。',f'Page {i+1}: {subtype} has no supported embedded asset; external URLs, Flash, 3D and raw Sound streams are not played.'))
            for key, frames in groups.items():
                frames.sort()
                if len(frames) < 2:
                    continue
                if [x[0] for x in frames] != list(range(len(frames))):
                    warnings.append(L(f'动画 {key}：帧序号不连续。',f'Animation {key}: non-contiguous frame indexes'))
                    continue
                main = mains.get(key)
                r = main[0] if main else frames[0][3]
                m = re.search(r'a'+re.escape(key)+r'_fps\s*=\s*(\d+(?:\.\d+)?)(?:;|\s)', script)
                fps = max(0.1, min(120, float(m[1]))) if m else 12
                variable = re.search(r'a'+re.escape(key)+r'_nFpsAt\s*=\s*new Array\(([^)]+)\)', script)
                rates = []
                if variable and re.fullmatch(r'[\d.,\s+-]+', variable[1]):
                    rates = [max(0.1, min(120, float(v))) for v in variable[1].split(',')]
                hide = [x[2] for x in frames] + ([main[1]] if main else [])
                animations.append(Animation(key, i, r, [x[1] for x in frames], fps,
                    'icon' if main else 'widget', hide, controls.get(key, []), rates,
                    '' if m else L('未识别帧率，使用 12 fps。','Frame rate not found; using 12 fps')))
        oc = pdf.Root.get('/OCProperties', {})
        if any(re.fullmatch(r'\d+\.\d+', str(o.get('/Name', ''))) for o in oc.get('/OCGs', [])):
            warnings.append(L('检测到 OCG 动画，当前版本暂不支持播放，请使用 widget/icon 导出。','animate OCG animation detected: playback adapter not implemented in this version; use a widget/icon export.'))
        if script and not animations:
            warnings.append(L('文档含脚本但不执行，未识别到支持的动画帧序列。','PDF JavaScript is present but is not executed. No supported animate frame sequence found.'))
    return animations, media, warnings


def prepare_animation(document, animation):
    destination = document.folder / f'animation-{document.revision}-{animation.page}-{animation.key}.pdf'
    if destination.exists():
        return str(destination)
    with pp.open(document.path) as src, pp.Pdf.new() as dst:
        for xref in animation.frames:
            original = src.get_object((xref, 0))
            frame = dst.copy_foreign(original)
            bbox = fitz.Rect(list(map(float, original.BBox)))
            matrix = fitz.Matrix(*map(float, original.get('/Matrix', [1, 0, 0, 1, 0, 0])))
            transformed = bbox * matrix
            if transformed.is_empty or transformed.width * transformed.height > 10_000_000:
                raise Unsupported('Invalid animation frame bounds')
            page = dst.add_blank_page(page_size=(transformed.width, transformed.height))
            page.Resources = pp.Dictionary(XObject=pp.Dictionary(Frame=frame))
            page.Contents = dst.make_stream(f'q 1 0 0 1 {-transformed.x0} {-transformed.y0} cm /Frame Do Q'.encode())
        dst.save(destination)
    return str(destination)


def render_frame(filename, index, width):
    with fitz.open(filename) as pdf:
        page = pdf[index]
        scale = min(width / page.rect.width, 4.0)
        return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=True).tobytes('png')


def extract_media(document, asset):
    suffix = Path(asset.name).suffix.lower()
    destination = document.folder / f'media-{document.revision}-{asset.xref}{suffix}'
    if not destination.exists():
        with pp.open(document.path) as pdf:
            stream = pdf.get_object((asset.xref, 0))
            if int(stream.get('/Length', 0)) > 512 * 1024 * 1024:
                raise Unsupported(L('内嵌媒体超过 512 MiB。','Embedded media exceeds 512 MiB'))
            raw = stream.read_bytes()
            if len(raw) > 512 * 1024 * 1024:
                raise Unsupported('Decoded media exceeds 512 MiB')
            signatures = {
                '.mp4': lambda b: b[4:8] in (b'ftyp',b'moov',b'wide',b'mdat'),
                '.m4v': lambda b: b[4:8] in (b'ftyp',b'moov',b'wide',b'mdat'),
                '.mov': lambda b: b[4:8] in (b'ftyp',b'moov',b'wide',b'mdat'),
                '.m4a': lambda b: b[4:8] in (b'ftyp',b'moov'),
                '.wav': lambda b: b[:4] in (b'RIFF',b'RF64') and b[8:12] == b'WAVE',
                '.mp3': lambda b: b[:3] == b'ID3' or (len(b)>1 and b[0] == 255 and b[1]&224 == 224),
                '.ogg': lambda b: b[:4] == b'OggS', '.flac': lambda b: b[:4] == b'fLaC',
                '.webm': lambda b: b[:4] == b'\x1aE\xdf\xa3',
            }
            if not signatures.get(suffix, lambda b: False)(raw):
                raise Unsupported(L('媒体数据与格式不符，不播放外部播放列表或引用。','Media signature does not match its format; playlists and external references are refused.'))
            destination.write_bytes(raw)
    return str(destination)


def control_at(animation,point):
    """animate overlays hidden Play/Pause fields at the same control position."""
    x,y=point.x(),point.y()
    hits=[command for rect,command in animation.buttons if rect[0]<=x<=rect[2] and rect[1]<=y<=rect[3]]
    for direction in ('Left','Right'):
        combined='PlayPause'+direction
        if combined in hits or ('Play'+direction in hits and 'Pause'+direction in hits):return combined
    return hits[0] if hits else None


def export_animation(document,animation,destination):
    """Preserve vector frames and their timing; animate has no original video stream."""
    import zipfile,json
    frames=prepare_animation(document,animation)
    timing={'format':'AsterPDF animation source 1','frame_count':len(animation.frames),'fps':animation.fps,
            'variable_fps':animation.variable_fps,'source_page':animation.page+1,'method':animation.method}
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(frames,'frames.pdf')
        archive.writestr('timing.json',json.dumps(timing,ensure_ascii=False,indent=2))
        archive.writestr('README.txt','LaTeX animate stores PDF frames, not an original MP4.\nframes.pdf contains every original vector frame in order, one per page.\ntiming.json records the detected frame rate and per-frame rate changes.\nNo PDF JavaScript is executed.\n')
    return str(destination)
