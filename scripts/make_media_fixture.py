"""Original H.264/AAC and PCM fixtures; requires imageio-ffmpeg only for creation."""
from pathlib import Path
import subprocess
import sys
import math
import wave
import struct
import pikepdf as pp
import imageio_ffmpeg


def create_media_fixture(destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    video=destination.with_suffix('.mp4');sound=destination.with_suffix('.wav')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','lavfi','-i','testsrc2=size=480x270:rate=24',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','4','-c:v','libx264','-pix_fmt','yuv420p',
        '-c:a','aac','-movflags','+faststart',str(video)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    with wave.open(str(sound),'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(44100)
        audio.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(2*math.pi*330*n/44100))) for n in range(44100*3)))
    with pp.Pdf.new() as pdf:
        page=pdf.add_blank_page(page_size=(595,842));annotations=[]
        for file,rect,kind in [(video,[55,430,535,700],'/Video'),(sound,[55,300,535,360],'/Sound')]:
            embedded=pdf.make_stream(file.read_bytes());embedded.Type=pp.Name('/EmbeddedFile')
            fs=pdf.make_indirect(pp.Dictionary(Type=pp.Name('/Filespec'),F=pp.String(file.name),UF=pp.String(file.name),EF=pp.Dictionary(F=embedded)))
            config=pdf.make_indirect(pp.Dictionary(Type=pp.Name('/RichMediaConfiguration'),Subtype=pp.Name(kind),
                Instances=pp.Array([pp.Dictionary(Type=pp.Name('/RichMediaInstance'),Subtype=pp.Name(kind),Asset=fs)])))
            annotation=pdf.make_indirect(pp.Dictionary(Type=pp.Name('/Annot'),Subtype=pp.Name('/RichMedia'),Rect=pp.Array(rect),
                RichMediaContent=pp.Dictionary(Assets=pp.Dictionary(Names=pp.Array([pp.String(file.name),fs])),Configurations=pp.Array([config]))))
            annotations.append(annotation)
        page.Annots=pp.Array(annotations);pdf.save(destination)
    video.unlink();sound.unlink()
    return destination


if __name__=='__main__':
    print(create_media_fixture(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'examples'/'AsterPDF-media.pdf'))
