"""Stage a desktop bundle and its complete corresponding AsterPDF source archive."""
from pathlib import Path
import platform
import shutil
import sys
import zipfile
import runpy
import tarfile

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
if sys.platform == 'darwin':
    installer = dist / 'Install asterpdf command.command'
    installer.write_text('''#!/bin/sh
set -eu
folder=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
app="$folder/AsterPDF.app"
if [ ! -d "$app" ]; then app=/Applications/AsterPDF.app; fi
if [ ! -d "$app" ]; then app="$HOME/Applications/AsterPDF.app"; fi
"$app/Contents/MacOS/AsterPDF" --install-cli
''', encoding='utf-8', newline='\n')
    installer.chmod(0o755)
elif sys.platform == 'win32':
    (bundle / 'Install asterpdf command.cmd').write_text(
        '@echo off\r\n"%~dp0AsterPDF.exe" --install-cli\r\n'
        'if errorlevel 1 (\r\n'
        '  echo Could not register the command. Open AsterPDF and use Settings - Install asterpdf command for details.\r\n'
        ') else (\r\n'
        '  echo The asterpdf command is ready. Reopen your terminal before using it.\r\n'
        ')\r\npause\r\n', encoding='utf-8', newline=''
    )
else:
    installer = bundle / 'install-command.sh'
    installer.write_text('''#!/bin/sh
set -eu
folder=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
exec "$folder/AsterPDF" --install-cli
''', encoding='utf-8', newline='\n')
    installer.chmod(0o755)
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
elif sys.platform == 'darwin':
    archive = str(archive_base) + '.tar.gz'
    with tarfile.open(archive, 'w:gz') as output:
        output.add(bundle, arcname=bundle.name)
        output.add(installer, arcname=installer.name)
else:
    archive=shutil.make_archive(str(archive_base),'gztar',root_dir=dist,base_dir=bundle.name)
import hashlib
checksum=hashlib.sha256(Path(archive).read_bytes()).hexdigest()
Path(archive+'.sha256').write_text(checksum+'  '+Path(archive).name+'\n',encoding='ascii')
print(archive)
