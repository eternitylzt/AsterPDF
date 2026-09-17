"""Create original, redistributable scientific editing/animation fixtures."""
from pathlib import Path
from io import BytesIO
import math
import sys
import pikepdf as pp
from reportlab.pdfgen import canvas
from PIL import Image,ImageDraw


def create_demo(destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    raw=BytesIO();c=canvas.Canvas(raw,pagesize=(595,842),pageCompression=1)
    c.setTitle('AsterPDF research workspace demo')
    c.setFillColorRGB(.12,.2,.34);c.setFont('Helvetica-Bold',32);c.drawString(48,776,'AsterPDF')
    c.setFont('Helvetica',11);c.setFillColorRGB(.38,.46,.58);c.drawString(48,750,'READ  /  EDIT  /  ANIMATE  /  ANNOTATE  /  EXTRACT')
    c.setFillColorRGB(.15,.22,.34);c.setFont('Helvetica-Bold',21);c.drawString(48,699,'A local workspace for research')
    c.setFont('Helvetica',12)
    for y,text in [(670,'Select this text, copy it, or highlight a passage.'),(650,'Edit the figure label below as a real PDF text object.'),(630,'The plot is vector artwork. The heatmap is an embedded image.')]:c.drawString(48,y,text)
    c.setFont('Helvetica-Bold',16);c.drawString(60,578,'Signal amplitude')
    c.setStrokeColorRGB(.18,.28,.4);c.setLineWidth(1)
    c.line(60,360,60,550);c.line(60,360,535,360)
    c.setStrokeColorRGB(.32,.45,.88);c.setLineWidth(2)
    path=c.beginPath()
    for i in range(230):
        x=60+i*2;y=448+72*math.sin(i/21)*math.exp(-i/350)
        path.moveTo(x,y) if i==0 else path.lineTo(x,y)
    c.drawPath(path)
    c.setFillColorRGB(.38,.46,.58);c.setFont('Helvetica',10);c.drawString(275,340,'Time (s)')
    im=Image.new('RGB',(720,300));pixels=im.load()
    for x in range(720):
        for y in range(300):
            v=(math.sin(x/80)+math.cos(y/40)+2)/4
            pixels[x,y]=(int(35+190*v),int(70+85*v),int(160+70*(1-v)))
    image=BytesIO();im.save(image,format='PNG');image.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(image),60,154,475,150)
    c.setFont('Helvetica',10);c.drawString(60,132,'Embedded raster: 720 x 300 pixels. Extract it without a screenshot.')
    c.setFont('Helvetica',10);c.drawString(48,55,'01  /  Reading, annotations and object editing');c.showPage()
    c.setFillColorRGB(.12,.2,.34);c.setFont('Helvetica-Bold',26);c.drawString(48,775,'Motion belongs in the document')
    c.setFont('Helvetica',12);c.drawString(48,745,'Click the animation, or use the Animation / media menu.')
    c.drawString(48,716,'This original fixture uses the animate widget frame structure.')
    c.setFont('Helvetica',10);c.drawString(48,55,'02  /  24 vector frames, 12 fps');c.showPage()
    c.setFont('Helvetica-Bold',26);c.drawString(48,775,'Build your own reading workflow')
    c.setFont('Helvetica',13)
    for i,text in enumerate(['Ctrl+O  Open a PDF','Ctrl+F  Search across pages','Ctrl+D  Bookmark the current page',
        'Use Select region for high resolution export','Ctrl+S  Save edits','F5  Present; Escape to leave','Ctrl+Z / Ctrl+Shift+Z  Undo / redo']):c.drawString(48,710-i*38,text)
    c.save()
    with pp.open(raw) as pdf:
        frames=[];fields=[]
        for n in range(24):
            x=25+n*15
            content=f'q 0.94 0.96 1 rg 0 0 440 220 re f 0.32 0.44 0.89 rg {x} 80 26 60 re f Q'.encode()
            form=pdf.make_stream(content);form.Type=pp.Name('/XObject');form.Subtype=pp.Name('/Form');form.BBox=pp.Array([0,0,440,220]);form.Resources=pp.Dictionary()
            a=pdf.make_indirect(pp.Dictionary(Type=pp.Name('/Annot'),Subtype=pp.Name('/Widget'),FT=pp.Name('/Btn'),Ff=65536,
                T=pp.String(f'0.{n}'),Rect=pp.Array([70,350,510,570]),F=4 if n==0 else 2,
                AP=pp.Dictionary(N=form),MK=pp.Dictionary(I=form),P=pdf.pages[1].obj))
            frames.append(a);fields.append(a)
        pdf.pages[1].Annots=pp.Array(frames)
        pdf.Root.AcroForm=pp.Dictionary(Fields=pp.Array(fields))
        js=pdf.make_indirect(pp.Dictionary(S=pp.Name('/JavaScript'),JS=pp.String('var a0_fps=12; // static adapter fixture; never execute')))
        pdf.Root.Names=pp.Dictionary(JavaScript=pp.Dictionary(Names=pp.Array([pp.String('animation'),js])))
        pdf.save(destination)
    return destination


if __name__=='__main__':
    print(create_demo(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'examples'/'AsterPDF-demo.pdf'))
