"""Collect license texts supplied by installed runtime wheels, without bundling dev tools."""
from pathlib import Path
from importlib import metadata
import shutil
import json

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'licenses';target.mkdir(exist_ok=True)
packages=['PySide6','PySide6-Essentials','PySide6-Addons','shiboken6','PyMuPDF','pikepdf',
          'Pillow','lxml','Deprecated','wrapt','packaging','Markdown']
inventory=[]
for name in packages:
    dist=metadata.distribution(name)
    files=[]
    for f in dist.files or []:
        text=str(f).lower()
        if ('.dist-info/' in text and any(word in text for word in ('license','copying','notice'))) or text.endswith('licenses-for-wheels.txt'):
            src=Path(dist.locate_file(f))
            if src.is_file():
                dst=target/name/str(f).split('.dist-info/')[-1]
                dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);files.append(str(dst.relative_to(ROOT)))
    inventory.append({'name':name,'version':dist.version,'license':dist.metadata.get('License-Expression',dist.metadata.get('License','')),'files':files})
(target/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
print(f'Collected runtime licenses for {len(inventory)} distributions')
