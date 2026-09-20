"""Page-local solid color edits. Shared Form/image resources are cloned."""
from collections import Counter
import math
import pikepdf as pp
from PIL import Image, ImageOps, ImageChops
from .objects import commands,operands,content_bytes
from .core import Unsupported
from .i18n import L


def rgb(command):
    values=list(map(float,operands(command)))
    if command.op in ('g','G'):return (values[0],)*3
    if command.op in ('rg','RG'):return tuple(values)
    if command.op in ('k','K'):
        c,m,y,k=values;return tuple(1-min(1,v+k) for v in (c,m,y))
    return None


def inventory(document,page,region=None,tolerance=.08):
    """Bounded visible-pixel palette, weighted by sampled visible area.

    Sampling deliberately excludes annotations/night display. The palette is an
    estimate; gradients are clustered, and the picker can select any exact color.
    """
    import pymupdf as fitz
    indices=[page] if isinstance(page,int) else list(dict.fromkeys(page))
    counts=Counter();exact=Counter();images=0
    with fitz.open(document.path) as pdf:
        for index in indices:
            p=pdf[index];area=fitz.Rect(region) if region else p.rect
            area &= p.rect
            if area.is_empty:continue
            scale=min(1,256/max(area.width,area.height))
            pix=p.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=area,alpha=False,annots=False,colorspace=fitz.csRGB)
            sample=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            # Fixed bins prevent arbitrarily long gradients across many pages.
            sample=sample.quantize(colors=64).convert('RGB')
            weight=area.width*area.height/max(1,pix.width*pix.height)
            for count,c in sample.getcolors(pix.width*pix.height) or []:
                key=tuple(min(255,round(v/4)*4) for v in c)
                counts[key]+=count*weight
            # Thin glyphs disappear into gray antialiased pixels at palette resolution.
            # Seed actual PDF ink colors before clustering the sampled image colors.
            for block in p.get_text('dict',flags=fitz.TEXTFLAGS_TEXT)['blocks']:
                for line in block.get('lines',[]):
                    for span in line['spans']:
                        bounds=fitz.Rect(span['bbox'])*p.rotation_matrix
                        if bounds.intersects(area):
                            value=span['color'];key=((value>>16)&255,(value>>8)&255,value&255)
                            exact[key]+=max(1,(bounds&area).get_area()*.12)
            images+=sum(1 for entry in p.get_image_info() if (fitz.Rect(entry['bbox'])*p.rotation_matrix).intersects(area))
    total=sum(counts.values())+sum(exact.values()) or 1
    # No huge UI lists, regardless of document length or gradient complexity.
    clustered=Counter(dict(exact.most_common(24)))
    for color,weight in counts.most_common():
        representative=next((c for c in clustered if max(abs(a-b) for a,b in zip(c,color))<=tolerance*255),color)
        if representative in clustered or len(clustered)<32:clustered[representative]+=weight
    palette=Counter({tuple(v/255 for v in c):n for c,n in clustered.most_common(32)})
    return {'colors':palette,'total':total,'images':images,'unsupported':[], 'estimated':True}


def recolor_image(image,pairs,tolerance,invert=False):
    image=image.convert('RGB')
    if invert:return ImageOps.invert(image)
    output=image.copy()
    for source,target in pairs:
        channels=output.split()
        masks=[channel.point([255 if abs(v/255-source[n])<=tolerance else 0 for v in range(256)]) for n,channel in enumerate(channels)]
        mask=ImageChops.darker(ImageChops.darker(masks[0],masks[1]),masks[2])
        output.paste(tuple(round(v*255) for v in target),(0,0),mask)
    return output


def replace(document,page,source=None,target=None,invert=False,images=False,tolerance=.01,region=None,progress=None,pairs=None):
    pairs=list(pairs or ([(source,target)] if source is not None and target is not None else []))
    if not invert and not pairs:raise ValueError('Choose source and target colors')
    def changed(c):
        if invert:return tuple(1-max(0,min(1,x)) for x in c)
        for source,target in pairs:
            if max(abs(a-b) for a,b in zip(c,source))<=tolerance:c=tuple(target)
        return c
    def rewrite(data):
        pieces=[];start=0
        for command in commands(data):
            if command.op not in ('g','G','rg','RG','k','K'):continue
            before=rgb(command);after=changed(before)
            if after==before:continue
            op='RG' if command.op.isupper() else 'rg'
            value=(' '+' '.join(f'{v:.7f}' for v in after)+' '+op+' ').encode()
            pieces.extend((data[start:command.start],value));start=command.end
        pieces.append(data[start:]);return b''.join(pieces)
    indices=[page] if isinstance(page,int) else list(dict.fromkeys(page))
    def mutate_page(pdf,page_index):
        p=pdf.pages[page_index];memo={};active=set();original_data=content_bytes(p);original_resources=p.Resources
        def clone_resources(resources,depth=0):
            if depth>32:raise Unsupported('Nested resource depth exceeds limit')
            result=pp.Dictionary(resources);xobjects=pp.Dictionary()
            for name,obj in resources.get('/XObject',{}).items():
                identity=obj.objgen;kind=str(obj.get('/Subtype',''))
                if kind not in ('/Form','/Image') or kind=='/Image' and not images:
                    xobjects[name]=obj;continue
                if identity in active:raise Unsupported('Cyclic Form resource cannot be edited')
                if identity in memo:xobjects[name]=memo[identity];continue
                if kind=='/Form':
                    active.add(identity);copy=pdf.make_stream(rewrite(obj.read_bytes()))
                    for k,v in obj.items():
                        if k not in ('/Length','/Filter','/DecodeParms','/Resources'):copy[k]=v
                    copy.Resources=clone_resources(obj.get('/Resources',resources),depth+1);active.remove(identity)
                else:
                    if obj.get('/ImageMask',False) or isinstance(obj.get('/Mask'),pp.Array):
                        raise Unsupported(L('此图片使用模板或颜色键蒙版，暂不支持图片换色；请关闭同时修改栅格图片。','Stencil/color-key mask images cannot be recolored; turn off raster image changes.'))
                    image=pp.PdfImage(obj).as_pil_image().convert('RGB')
                    image=recolor_image(image,pairs,tolerance,invert)
                    copy=pdf.make_stream(image.tobytes());copy.Type=pp.Name('/XObject');copy.Subtype=pp.Name('/Image');copy.Width=image.width;copy.Height=image.height;copy.BitsPerComponent=8;copy.ColorSpace=pp.Name('/DeviceRGB')
                    for key in ('/SMask','/Mask','/Interpolate'):
                        if key in obj:copy[key]=obj[key]
                memo[identity]=copy;xobjects[name]=copy
            if xobjects:result.XObject=xobjects
            return result
        p.Resources=clone_resources(p.Resources)
        prefix=b'';default=changed((0,0,0))
        background=changed((1,1,1))
        if background!=(1,1,1):
            box=list(map(float,p.obj.get('/CropBox',p.obj.MediaBox)));x,y,x1,y1=box
            prefix=('q '+' '.join(f'{c:.7f}' for c in background)+f' rg {x:.7f} {y:.7f} {x1-x:.7f} {y1-y:.7f} re f Q\n').encode()
        if default!=(0,0,0):prefix+=(' '.join(f'{c:.7f}' for c in default)+' rg '+' '.join(f'{c:.7f}' for c in default)+' RG\n').encode()
        edited=prefix+rewrite(original_data)
        if region is None:p.Contents=pdf.make_stream(edited)
        else:
            import pymupdf as fitz
            with fitz.open(document.path) as source_pdf:
                source_page=source_pdf[page_index]
                area=fitz.Rect(region)*source_page.derotation_matrix*~source_page.transformation_matrix
            box=p.obj.get('/MediaBox');x,y,x1,y1=map(float,box)
            def form(data,resources):
                value=pdf.make_stream(data);value.Type=pp.Name('/XObject');value.Subtype=pp.Name('/Form');value.BBox=pp.Array(box);value.Resources=resources;return value
            outside=form(original_data,original_resources);inside=form(edited,p.Resources)
            rect=f'{area.x0:.7f} {area.y0:.7f} {area.width:.7f} {area.height:.7f} re'
            content=f'q {x} {y} {x1-x} {y1-y} re {rect} W* n /Outside Do Q\nq {rect} W n /Inside Do Q'
            p.Resources=pp.Dictionary(XObject=pp.Dictionary(Outside=outside,Inside=inside));p.Contents=pdf.make_stream(content.encode())
    def mutate(pdf):
        for n,index in enumerate(indices):
            mutate_page(pdf,index)
            if progress:progress(n+1,len(indices))
    document.edit('page colors',mutate)
