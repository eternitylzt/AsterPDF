"""Stage a desktop bundle and its complete corresponding AsterPDF source archive."""
from pathlib import Path
import platform
import shutil
import sys
import zipfile
import runpy

root=Path(__file__).resolve().parents[1];dist=root/'dist';dist.mkdir(exist_ok=True)
version=runpy.run_path(str(root/'asterpdf/__init__.py'))['__version__']
osname={'win32':'windows','darwin':'macos'}.get(sys.platform,'linux')
arch=platform.machine().lower()
source=dist/f'AsterPDF-{version}-source.zip'
excluded={'.git','.venv','dist','build','__pycache__','node_modules','.pytest_cache','_internal'}
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() not in ('.exe','.zip','.gz') and not any(x in excluded or x.endswith('.egg-info') for x in p.relative_to(root).parts):
            z.write(p,'AsterPDF/'+str(p.relative_to(root)))
bundle=dist/('AsterPDF.app' if sys.platform=='darwin' else 'AsterPDF')
if not bundle.exists():raise SystemExit('Build AsterPDF.spec first')
if sys.platform!='darwin':
    shutil.copyfile(source,bundle/source.name)
    for file in ('README.md','README.zh-CN.md','LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(root/file,bundle/file)
    shutil.copytree(root/'examples',bundle/'examples',dirs_exist_ok=True)
    shutil.copytree(root/'docs',bundle/'docs',dirs_exist_ok=True)
    shutil.copytree(root/'assets',bundle/'assets',dirs_exist_ok=True)
archive_base=dist/f'AsterPDF-{version}-{osname}-{arch}'
if sys.platform=='win32':
    archive=shutil.make_archive(str(archive_base),'zip',root_dir=dist,base_dir=bundle.name)
else:
    archive=shutil.make_archive(str(archive_base),'gztar',root_dir=dist,base_dir=bundle.name)
import hashlib
checksum=hashlib.sha256(Path(archive).read_bytes()).hexdigest()
Path(archive+'.sha256').write_text(checksum+'  '+Path(archive).name+'\n',encoding='ascii')
print(archive)
