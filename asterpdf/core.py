"""Transactional PDF storage. pikepdf owns the PDF; MuPDF renders and authors annotations.

Every edit produces a separate recovery revision, then commits. The original is
replaced only by an explicit save, using an atomic file-system replacement.
"""
from __future__ import annotations
from .i18n import L
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import uuid
from datetime import datetime
import pikepdf as pp
import pymupdf as fitz
from PIL import Image

ENGINE_LOCK = threading.RLock()  # MuPDF must never execute concurrently in threads.


class Unsupported(ValueError):
    """A specific, user-visible capability limit, with no partial mutation."""


def pages_from_text(text: str, count: int) -> list[int]:
    if text.strip().lower() in ('all', '*', '全部', ''):
        return list(range(count))
    result = []
    for part in text.replace('，', ',').split(','):
        bits = part.strip().split('-')
        if len(bits) == 1:
            values = [int(bits[0])]
        elif len(bits) == 2:
            a, b = map(int, bits)
            if b < a:
                raise ValueError(L('请使用递增页码范围。','Use increasing page ranges'))
            values = range(a, b + 1)
        else:
            raise ValueError(L('页码范围无效。','Invalid page range'))
        for n in values:
            if not 1 <= n <= count:
                raise ValueError(L(f'页码 {n}：1–{count}',f'Page {n}: 1–{count}'))
            if n - 1 not in result:
                result.append(n - 1)
    return result


def atomic_json(path: Path, data):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(tmp, path)


def pdf_bytes(pdf):
    output = io.BytesIO()
    pdf.save(output)
    return output.getvalue()


def annotation_inventory(pdf):
    counts = {}
    for page in pdf.pages:
        for a in page.obj.get('/Annots', []):
            typ = str(a.get('/Subtype', 'Unknown'))
            counts[typ] = counts.get(typ, 0) + 1
    return counts


def feature_warnings(pdf, structural=False):
    counts = annotation_inventory(pdf)
    warnings = []
    if pdf.Root.get('/Perms'):
        warnings.append(L('编辑会使数字签名失效。','Digital signatures will be invalidated'))
    if structural and (pdf.Root.get('/AcroForm') or pdf.Root.get('/Names') or pdf.Root.get('/Outlines')
                       or any(k in counts for k in ['/Link', '/RichMedia', '/Movie', '/Screen'])):
        warnings.append(L('页面重排、删除或导入可能影响依赖页码的脚本、目标和表单导航。导入/导出选页不会带入文档级脚本、目录与表单树；保留页的媒体与批注字典会保留。','Page order/deletion/import may change page-number based scripts, destinations and form navigation. Import/export of selected pages does not import document-level scripts, outlines or form trees. Existing page dictionaries, media and annotations are retained on kept pages.'))
    return warnings


class Document:
    def __init__(self, filename, recovery_root, password=''):
        self.original = str(Path(filename).resolve())
        self.password = password
        self.folder = Path(recovery_root) / uuid.uuid4().hex
        self.folder.mkdir(parents=True, exist_ok=True)
        from PySide6.QtCore import QLockFile
        self.session_lock=QLockFile(str(self.folder/'session.lock'));self.session_lock.setStaleLockTime(0);self.session_lock.tryLock(0)
        initial = self.folder / '0000.pdf'
        with pp.open(filename, password=password) as pdf:
            if pdf.is_encrypted:
                # Editing encrypted documents is intentionally excluded from this release.
                raise Unsupported(L('请先提供未加密的 PDF 副本。','Encrypted PDF: open an unencrypted local copy'))
        shutil.copyfile(filename, initial)
        self.history = [initial]
        self.index = 0
        self.saved_revision = str(initial)
        self.serial = 0
        self.revision = 0
        self._metadata()

    @property
    def path(self):
        return self.history[self.index]

    @property
    def dirty(self):
        return str(self.path) != self.saved_revision

    def _metadata(self):
        atomic_json(self.folder / 'recovery.json', {'original': self.original,
                    'revision': str(self.path), 'dirty': self.dirty})

    def info(self):
        with fitz.open(self.path) as doc, pp.open(self.path) as pdf:
            return {'count': len(doc), 'sizes': [(p.rect.width, p.rect.height) for p in doc],
                    'toc': doc.get_toc(), 'metadata': doc.metadata,
                    'annotations': annotation_inventory(pdf),
                    'warnings': feature_warnings(pdf)}

    def preflight(self, structural=False):
        with pp.open(self.path) as pdf:
            return feature_warnings(pdf, structural)

    def edit(self, label, callback):
        self.release_rendering()
        self.serial += 1
        dest = self.folder / f'{self.serial:04d}.pdf'
        try:
            with pp.open(self.path) as pdf:
                callback(pdf)
                if not pdf.pages:
                    raise ValueError(L('至少保留一页。','A PDF needs at least one page'))
                pdf.save(dest)
            with fitz.open(dest) as check:
                if check.page_count == 0:
                    raise ValueError('Empty PDF')
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        for obsolete in self.history[self.index + 1:]:
            obsolete.unlink(missing_ok=True)
        self.history = self.history[:self.index + 1] + [dest]
        self.index += 1
        # Disk based history, bounded by count and approximately 2 GiB.
        while len(self.history) > 2 and (len(self.history) > 21 or
                sum(p.stat().st_size for p in self.history) > 2 * 1024**3):
            self.history.pop(0).unlink(missing_ok=True)
            self.index -= 1
        self.revision += 1
        self._metadata()
        return label

    def undo(self):
        self.release_rendering()
        if self.index > 0:
            self.index -= 1
            self.revision += 1
            self._metadata()

    def redo(self):
        self.release_rendering()
        if self.index + 1 < len(self.history):
            self.index += 1
            self.revision += 1
            self._metadata()

    def save(self, filename=None):
        destination = Path(filename or self.original)
        fd, temporary = tempfile.mkstemp(prefix='.asterpdf-', suffix='.pdf', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as out, self.path.open('rb') as src:
                shutil.copyfileobj(src, out)
                out.flush()
                os.fsync(out.fileno())
            with pp.open(temporary) as checked:
                if len(checked.pages) == 0:
                    raise ValueError('Invalid saved PDF')
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.original = str(destination.resolve())
        self.saved_revision = str(self.path)
        self._metadata()

    def release_rendering(self):
        renderer=getattr(self,'_renderer',None)
        if renderer:renderer.close();self._renderer=None

    def render_tile(self,page,scale,clip,night=False,hide=(),show_annotations=True):
        from .rendering import PageRenderer
        if getattr(self,'_renderer',None) is None:self._renderer=PageRenderer()
        return self._renderer.tile(self.path,page,scale,clip,night,hide,show_annotations)

    def close(self):
        self.release_rendering()
        fitz.TOOLS.store_shrink(100)
        # Only called after a successful save or explicit discard.
        self.session_lock.unlock()
        if self.folder.exists():shutil.rmtree(self.folder)

    def page_operation(self, operation, indices, **options):
        indices = sorted(set(indices))
        def mutate(pdf):
            if operation in ('rotate','flip_h','flip_v'):
                apply_page_transform(pdf,operation,indices,options.get('angle',90))
            elif operation == 'delete':
                for i in reversed(indices):
                    del pdf.pages[i]
            elif operation == 'reorder':
                order = options['order']
                if sorted(order) != list(range(len(pdf.pages))):
                    raise ValueError('Invalid page permutation')
                original = list(pdf.pages)
                del pdf.pages[:]
                for i in order:
                    pdf.pages.append(original[i])
            elif operation == 'blanks':
                for i in reversed(indices):
                    box=pdf.pages[i].obj.get('/CropBox',pdf.pages[i].obj.MediaBox)
                    w,h=float(box[2]-box[0]),float(box[3]-box[1])
                    if int(pdf.pages[i].obj.get('/Rotate',0))%180:w,h=h,w
                    new=pdf.add_blank_page(page_size=(w,h));pos=i if options.get('before') else i+1
                    pdf.pages.insert(pos,new);del pdf.pages[-1]
            elif operation == 'blank':
                pos = options.get('position', len(pdf.pages))
                new = pdf.add_blank_page(page_size=options.get('size', (595, 842)))
                if pos < len(pdf.pages) - 1:
                    pdf.pages.insert(pos, new)
                    del pdf.pages[-1]
            elif operation == 'crop':
                for i in indices:
                    pdf.pages[i].obj.CropBox = pp.Array(options['pdf_rect'])
            elif operation=='insert':
                position=options['position']
                for filename in options['files']:
                    with pp.open(filename) as other:
                        for page in other.pages:pdf.pages.insert(position,page);position+=1
            elif operation == 'merge':
                for filename in options['files']:
                    with pp.open(filename) as other:
                        pdf.pages.extend(other.pages)
            else:
                raise ValueError(operation)
        return self.edit(operation, mutate)

    def render(self, page, scale=1.0, clip=None, night=False, max_pixels=32_000_000, hide=None):
        with fitz.open(self.path) as pdf:
            for xref in hide or []:
                pdf.xref_set_key(xref, 'F', '2')
            p = pdf[page]
            r = fitz.Rect(clip) if clip else p.rect
            if r.is_empty or r.width * r.height * scale * scale > max_pixels:
                raise ValueError(L('输出过大：每页上限 3200 万像素。','Output too large (32 megapixel limit per page)'))
            pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=r, alpha=False)
            if night:
                pix.invert_irect()
                pix.tint_with(0x18202C, 0xD7DDE5)
            return pix.tobytes('png')

    def characters(self, page):
        with fitz.open(self.path) as pdf:
            p=pdf[page]; result=[]
            for bi,block in enumerate(p.get_text('rawdict',flags=fitz.TEXTFLAGS_TEXT,sort=True)['blocks']):
                for li,line in enumerate(block.get('lines',[])):
                    for span in line['spans']:
                        for c in span['chars']:
                            result.append((tuple(fitz.Rect(c['bbox'])*p.rotation_matrix),c['c'],bi,li))
            return result

    def words(self, page):
        with fitz.open(self.path) as pdf:
            p = pdf[page]
            matrix = p.rotation_matrix
            return [(tuple(fitz.Rect(w[:4]) * matrix), w[4], w[5], w[6], w[7])
                    for w in p.get_text('words', sort=True)]

    def links(self, page):
        with fitz.open(self.path) as pdf:
            p = pdf[page]
            result = []
            for link in p.get_links():
                if link.get('from'):
                    link['from'] = tuple(link['from'] * p.rotation_matrix)
                    result.append(link)
            return result

    def search(self, query, cancel=None, progress=None):
        result = []
        with fitz.open(self.path) as pdf:
            for i, p in enumerate(pdf):
                if cancel and cancel():
                    break
                hits = [tuple(r * p.rotation_matrix) for r in p.search_for(query)]
                if hits:
                    result.append((i, hits))
                if progress:
                    progress(i + 1, len(pdf))
        return result

    def export_pages(self, indices, directory, dpi=300, fmt='png', quality=95,
                     clip=None, width=None, progress=None, cancel=None,filename=None):
        outputs = []
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with fitz.open(self.path) as pdf:
            for j, i in enumerate(indices):
                if cancel and cancel():
                    break
                p = pdf[i]
                rect = fitz.Rect(clip) if clip else p.rect
                scale = width / rect.width if width else dpi / 72
                if rect.width * rect.height * scale**2 > 32_000_000:
                    raise ValueError(L('输出超过 3200 万像素，请降低 DPI 或尺寸。','Output exceeds 32 MP'))
                pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
                name = f'{Path(self.original).stem}_p{i+1:04d}{"_region" if clip else ""}.{fmt}'
                target = Path(filename) if filename else directory / name
                if target.exists() and not filename:
                    target = directory / f'{target.stem}_{uuid.uuid4().hex[:6]}.{fmt}'
                image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                image.save(target, quality=quality, dpi=(round(scale * 72), round(scale * 72)))
                outputs.append(str(target))
                if progress:
                    progress(j + 1, len(indices))
        return outputs

    def extract_pages(self, indices, destination, crop=None):
        with pp.open(self.path) as src, pp.Pdf.new() as dst:
            for i in indices:
                dst.pages.append(src.pages[i])
                if crop:
                    dst.pages[-1].obj.CropBox = pp.Array(crop)
                    dst.pages[-1].obj.MediaBox = pp.Array(crop)
            dst.save(destination)

    def image_occurrences(self,page):
        with fitz.open(self.path) as pdf:
            p=pdf[page]
            return [dict(x,bbox=tuple(fitz.Rect(x['bbox'])*p.rotation_matrix)) for x in p.get_image_info(xrefs=True) if x.get('xref')]

    def embedded_images(self, page):
        with fitz.open(self.path) as pdf:
            return [{'xref': r[0], 'width': r[2], 'height': r[3], 'name': r[7], 'smask': r[1]}
                    for r in pdf[page].get_images(full=True)]

    def extract_image(self, page, xref, destination):
        with pp.open(self.path) as pdf:
            obj = pdf.get_object((xref, 0))
            img = pp.PdfImage(obj)
            # extract_to preserves JPEG/JPX encoded bytes when supported, else decodes losslessly.
            return img.extract_to(fileprefix=str(Path(destination).with_suffix('')))

    def to_pdf_rect(self, page, rect):
        with fitz.open(self.path) as pdf:
            p = pdf[page]
            return tuple((fitz.Rect(rect) * p.derotation_matrix) * ~p.transformation_matrix)

    def _mupdf_page_change(self, page_number, callback, content=False):
        """Transplant only modified page data, preserving the authoritative catalog."""
        with fitz.open(self.path) as mp:
            callback(mp[page_number])
            data = mp.tobytes(garbage=0, deflate=True)
        def mutate(pdf):
            with pp.open(io.BytesIO(data)) as authored:
                src = authored.pages[page_number].obj
                dst = pdf.pages[page_number].obj
                if content:
                    for key in ['/Contents', '/Resources']:
                        if key in src:
                            dst[key] = pdf.copy_foreign(authored.make_indirect(src[key]))
                else:
                    # Keep all foreign/interactive annotation objects unchanged. Only AsterPDF annotations move.
                    def owned(a):
                        parent=a.get('/Parent') if a.get('/Subtype')==pp.Name('/Popup') else None
                        owner=parent if parent is not None else a
                        return str(owner.get('/T',''))=='AsterPDF' or str(owner.get('/NM','')).startswith('AsterPDF-')
                    keep = [a for a in dst.get('/Annots', []) if not owned(a)]
                    own = [pdf.copy_foreign(a) for a in src.get('/Annots', []) if owned(a)]
                    for a in own:
                        a['/P'] = dst
                    dst.Annots = pp.Array(keep + own)
        self.edit('content' if content else 'annotation', mutate)

    def add_annotation(self, page, kind, points, color=(0.96, 0.65, 0.12), width=2,
                       opacity=0.7, text='', word_rects=None, author_name='AsterPDF', fontsize=12, fontname='helv', line_end=4, dashed=False,head_size=10,text_border=0,border_color=(0,0,0)):
        def author(p):
            pts = [fitz.Point(x) * p.derotation_matrix for x in points]
            rect = fitz.Rect(pts[0], pts[-1]).normalize()
            if kind in ('highlight', 'underline', 'strikeout'):
                rects = [fitz.Rect(r) * p.derotation_matrix for r in (word_rects or [])]
                if not rects:
                    raise ValueError(L('请先选择文字。','Select text first'))
                a = getattr(p, f'add_{kind}_annot')(rects)
            elif kind == 'note':
                a = p.add_text_annot(pts[0], text)
            elif kind == 'freetext':
                a = p.add_freetext_annot(rect, text, fontsize=fontsize, fontname=fontname, text_color=color,border_width=0)
            elif kind == 'ink':
                a = p.add_ink_annot([[tuple(point) for point in pts]])
            elif kind in ('line', 'arrow'):
                a = p.add_line_annot(pts[0], pts[-1])
                if kind == 'arrow':
                    a.set_line_ends(0, line_end)
            elif kind == 'rectangle':
                a = p.add_rect_annot(rect)
            elif kind == 'ellipse':
                a = p.add_circle_annot(rect)
            else:
                raise ValueError(kind)
            stamp=datetime.now().astimezone().strftime('D:%Y%m%d%H%M%S%z')
            a.set_info(title=author_name, content=text,creationDate=stamp,modDate=stamp)
            p.parent.xref_set_key(a.xref,'NM',fitz.get_pdf_str('AsterPDF-'+uuid.uuid4().hex))
            if kind != 'freetext':
                a.set_colors(stroke=color,fill=color if kind=='arrow' and line_end in (5,8) else None)
            a.set_opacity(opacity)
            if kind not in ('highlight', 'underline', 'strikeout', 'note'):
                a.set_border(width=0 if kind=='freetext' else width, dashes=[4,3] if dashed else [])
            a.update()
            if kind=='arrow':
                from .annotation_style import line_appearance
                line_appearance(p,a,head_size)
            if kind=='freetext':
                from .annotation_style import freetext_border
                freetext_border(p,a,text_border,border_color,dashed)
        # New annotations need only a blank page with the same coordinate system,
        # not a second serialized copy of all page content and embedded media.
        with fitz.open(self.path) as original,fitz.open() as scratch:
            src=original[page];p=scratch.new_page(width=src.mediabox.width,height=src.mediabox.height)
            p.set_mediabox(src.mediabox);p.set_cropbox(src.cropbox);p.set_rotation(src.rotation);author(p);data=scratch.tobytes()
        def mutate(pdf):
            with pp.open(io.BytesIO(data)) as authored:
                dst=pdf.pages[page].obj;items=list(dst.get('/Annots',[]))
                for item in authored.pages[0].obj.get('/Annots',[]):
                    copied=pdf.copy_foreign(item);copied['/P']=dst;items.append(copied)
                dst.Annots=pp.Array(items)
        self.edit('annotation',mutate)

    def annotations(self, page=None):
        from .annotation_style import text_style
        with fitz.open(self.path) as pdf:
            return [{'page':p.number,'xref': a.xref, 'type': a.type[1], 'rect': tuple(a.rect * p.rotation_matrix),
                     'text': a.info.get('content', ''), 'author': a.info.get('title',''),
                     'created':a.info.get('creationDate',''),'modified':a.info.get('modDate',''),
                     'color': a.colors.get('stroke'), 'width': a.border.get('width',2), 'opacity': a.opacity if a.opacity>=0 else 1,
                     'id':a.info.get('id',''),'dashed':bool(a.border.get('dashes')),
                     'line_end':a.line_ends[1] if a.type[1]=='Line' else None,
                     'head_size':float(pdf.xref_get_key(a.xref,'AsterHeadSize')[1]) if pdf.xref_get_key(a.xref,'AsterHeadSize')[0] in ('int','float') else 10,
                     'own': a.info.get('title') == 'AsterPDF' or a.info.get('id','').startswith('AsterPDF-'),**text_style(a)}
                    for p in ([pdf[page]] if page is not None else pdf) for a in (p.annots() or [])]

    def delete_annotations(self,annotations):
        targets={}
        for a in annotations:targets.setdefault(a['page'],set()).add(a['xref'])
        def mutate(pdf):
            for page,refs in targets.items():
                p=pdf.pages[page];items=list(p.obj.get('/Annots',[]));remove=set(refs)
                for a in items:
                    if a.objgen[0] in refs and a.get('/Popup'):remove.add(a.Popup.objgen[0])
                p.obj.Annots=pp.Array([a for a in items if a.objgen[0] not in remove])
        self.edit('delete annotations',mutate)

    def reset(self):
        """Restore the current original file as a new, undoable revision."""
        self.release_rendering();self.serial+=1;dest=self.folder/f'{self.serial:04d}.pdf'
        shutil.copyfile(self.original,dest)
        with pp.open(dest) as check:
            if not check.pages:raise ValueError('Empty PDF')
        for obsolete in self.history[self.index+1:]:obsolete.unlink(missing_ok=True)
        self.history=self.history[:self.index+1]+[dest];self.index+=1;self.revision+=1
        while len(self.history)>2 and (len(self.history)>21 or sum(p.stat().st_size for p in self.history)>2*1024**3):
            self.history.pop(0).unlink(missing_ok=True);self.index-=1
        self.saved_revision=str(dest);self._metadata()

    def change_annotation(self, page, xref, delete=False, color=None, width=2, opacity=1,
                          text=None, offset=None, fontsize=None, fontname=None, line_end=None, dashed=False,head_size=None,border_color=None,rect=None):
        def author(p):
            a = p.load_annot(xref)
            if a.info.get('title') != 'AsterPDF' and not a.info.get('id','').startswith('AsterPDF-'):
                raise Unsupported(L('仅修改本软件添加的批注。','Only AsterPDF annotations can be changed'))
            if delete:
                p.delete_annot(a)
                return
            if color and a.type[1] != 'FreeText':
                a.set_colors(stroke=color)
            if a.type[1] not in ('Highlight', 'Underline', 'StrikeOut', 'Text'):
                a.set_border(width=width)
            if a.type[1]=='Line' and line_end is not None:
                a.set_line_ends(0,line_end)
                if line_end in (5,8):a.set_colors(fill=color or a.colors.get('stroke') or (0,0,0))
            if a.type[1] not in ('Highlight','Underline','StrikeOut','Text'):a.set_border(width=width,dashes=[4,3] if dashed else [])
            a.set_opacity(opacity)
            if text is not None:
                a.set_info(content=text)
            a.set_info(modDate=datetime.now().astimezone().strftime('D:%Y%m%d%H%M%S%z'))
            if rect is not None:a.set_rect(fitz.Rect(rect)*p.derotation_matrix)
            if offset:
                r = a.rect
                a.set_rect(r + (offset[0], offset[1], offset[0], offset[1]))
            if a.type[1]=='FreeText':
                a.set_border(width=0)
                a.update(fontsize=fontsize or 0,fontname=fontname,text_color=color)
                from .annotation_style import freetext_border
                freetext_border(p,a,width,border_color or (0,0,0),dashed)
            else:a.update()
            if a.type[1]=='Line':
                from .annotation_style import line_appearance
                saved=p.parent.xref_get_key(a.xref,'AsterHeadSize')
                line_appearance(p,a,head_size if head_size is not None else float(saved[1]) if saved[0] in ('int','float') else 10)
        self._mupdf_page_change(page, author)

    def insert_text(self, page, rect, text, fontfile=None, fontsize=12, color=(0, 0, 0), fontbuffer=None):
        font = fitz.Font(fontbuffer=fontbuffer) if fontbuffer else fitz.Font(fontfile=fontfile) if fontfile else fitz.Font('helv')
        if any(not font.has_glyph(ord(ch)) for ch in text if not ch.isspace()):
            raise Unsupported(L('字体缺少字形，请选择包含所需字符的 TTF/OTF 字体。','Font lacks requested glyphs. Select a Unicode TTF/OTF font.'))
        def author(p):
            r = fitz.Rect(rect) * p.derotation_matrix
            name = 'AsterFont'+str(self.serial+1) if fontfile or fontbuffer else 'helv'
            if fontbuffer:
                from .fonts import set_unicode_map
                fx=p.insert_font(fontname=name,fontbuffer=fontbuffer)
                set_unicode_map(p.parent,fx,font,text)
            spare = p.insert_textbox(r, text, fontsize=fontsize, fontname=name,
                                     fontfile=fontfile, color=color)
            if spare < 0:
                raise ValueError(L('文字放不下，请扩大文本框或减小字号。','Text does not fit. Enlarge the box or reduce font size.'))
        self._mupdf_page_change(page, author, content=True)

    def insert_image(self, page, rect, filename, keep_ratio=True):
        from .objects import content_bytes,commands,operands
        with fitz.open(self.path) as original,fitz.open() as scratch:
            src=original[page];p=scratch.new_page(width=src.mediabox.width,height=src.mediabox.height)
            p.set_mediabox(src.mediabox);p.set_cropbox(src.cropbox);p.set_rotation(src.rotation)
            p.insert_image(fitz.Rect(rect)*p.derotation_matrix,filename=filename,keep_proportion=keep_ratio)
            data=scratch.tobytes()
        def mutate(pdf):
            with pp.open(io.BytesIO(data)) as authored:
                dst=pdf.pages[page];src=authored.pages[0];resources=pp.Dictionary(dst.Resources)
                images=pp.Dictionary(resources.get('/XObject',pp.Dictionary()));names={}
                for key,value in src.Resources.XObject.items():
                    name=f'/AsterImage{self.serial}_{len(names)}'
                    while name in images:name+='x'
                    names[key]=name;images[name]=pdf.copy_foreign(value)
                resources.XObject=images;dst.Resources=resources
                drawing=b'\n'.join((names[str(operands(c)[0])]+' Do').encode() if c.op=='Do' else c.raw for c in commands(content_bytes(src)))
                dst.Contents=pdf.make_stream(content_bytes(dst)+b'\n'+drawing)
        self.edit('insert image',mutate)


def merge_files(files,destination):
    """Create a new PDF atomically; source snapshots are never changed."""
    destination=Path(destination)
    fd,temp=tempfile.mkstemp(prefix='.aster-merge-',suffix='.pdf',dir=destination.parent);os.close(fd)
    try:
        with pp.Pdf.new() as merged:
            for filename in files:
                with pp.open(filename) as source:merged.pages.extend(source.pages)
            if not merged.pages:raise ValueError('No pages to merge')
            merged.save(temp)
        with fitz.open(temp) as check:
            if not len(check):raise ValueError('Empty merged PDF')
        os.replace(temp,destination)
    finally:Path(temp).unlink(missing_ok=True)
    return str(destination)


def apply_page_transform(pdf,operation,indices,angle=90):
    from .objects import content_bytes
    for i in indices:
        p=pdf.pages[i]
        if operation=='rotate':p.obj.Rotate=(int(p.obj.get('/Rotate',0))+angle)%360;continue
        if p.obj.get('/Annots'):raise Unsupported(L('含批注、链接或媒体的页面暂不整体镜像，以免交互位置错位。','Mirroring pages with annotations, links or media is currently unavailable.'))
        x,y,x1,y1=map(float,p.obj.get('/CropBox',p.obj.MediaBox));rotation=int(p.obj.get('/Rotate',0))%180
        horizontal=(operation=='flip_h') != bool(rotation)
        matrix=(-1,0,0,1,x+x1,0) if horizontal else (1,0,0,-1,0,y+y1)
        prefix=('q '+' '.join(map(str,matrix))+' cm\n').encode();p.Contents=pdf.make_stream(prefix+content_bytes(p)+b'\nQ')
