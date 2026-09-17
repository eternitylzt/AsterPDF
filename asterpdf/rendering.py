"""Native-pixel tile rendering; persistent display lists avoid reparsing per tile."""
from collections import OrderedDict
import pymupdf as fitz
from PySide6.QtGui import QImage


def image_from_pixmap(pix):
    fmt=QImage.Format_RGBA8888_Premultiplied if pix.alpha else QImage.Format_RGB888
    return QImage(pix.samples,pix.width,pix.height,pix.stride,fmt).copy()


class PageRenderer:
    def __init__(self):
        self.pdf=None;self.signature=None;self.lists=OrderedDict()

    def close(self):
        self.lists.clear()
        if self.pdf:self.pdf.close()
        self.pdf=None;self.signature=None

    def tile(self,path,page,scale,clip,night=False,hide=(),show_annotations=True):
        signature=(str(path),tuple(hide),show_annotations)
        if self.signature!=signature:
            self.close();self.pdf=fitz.open(path);self.signature=signature
            for xref in hide:self.pdf.xref_set_key(xref,'F','2')
        if page not in self.lists:
            if not show_annotations:
                for annot in self.pdf[page].annots() or []:self.pdf.xref_set_key(annot.xref,'F','2')
            self.lists[page]=self.pdf[page].get_displaylist()
            while len(self.lists)>2:self.lists.popitem(last=False)
        display=self.lists[page];self.lists.move_to_end(page)
        pix=display.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=fitz.Rect(clip),alpha=False)
        if night:pix.invert_irect();pix.tint_with(0x18202C,0xD7DDE5)
        return image_from_pixmap(pix),pix.x,pix.y


class FrameRenderer:
    def __init__(self,filename):self.filename=filename;self.pdf=None;self.frames=0
    def image(self,index,width):
        if self.pdf is None:self.pdf=fitz.open(self.filename)
        page=self.pdf[index];scale=width/page.rect.width
        # Bound a single decoded frame; reading tiles have their own byte budget.
        if page.rect.width*page.rect.height*scale*scale>12_000_000:
            scale=(12_000_000/(page.rect.width*page.rect.height))**.5
        result=image_from_pixmap(page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=True))
        self.frames+=1
        # Drop old decoded image resources periodically; the small display
        # cache above already owns the frames that can be replayed immediately.
        if self.frames%16==0:fitz.TOOLS.store_shrink(75)
        return result
    def close(self):
        if self.pdf:self.pdf.close()
        self.pdf=None
