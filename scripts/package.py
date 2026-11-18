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
    installer.write_text(runpy.run_path(str(root/'asterpdf/cli.py'))['posix_installer'](macos=True), encoding='utf-8', newline='\n')
    installer.chmod(0o755)
    command_guide = dist / 'Command installation.txt'
    command_guide.write_text('''AsterPDF terminal command / 终端命令

1. Quit older AsterPDF versions and move AsterPDF.app to Applications.
2. Open AsterPDF, then Settings → Install asterpdf command.
3. Open a new terminal: asterpdf "file.pdf"

Do not use sudo. The command opens a tab in the existing window and leaves the terminal available.
If Terminal cannot access Downloads/Desktop, use the in-app installer. macOS controls folder access in Privacy & Security → Files and Folders.
The included .command script is an alternative per-user installer; it also requires no sudo.

请先退出旧版，把 AsterPDF.app 放入 Applications，启动软件后在 Settings 中安装 asterpdf 命令。
重新打开终端后运行 asterpdf "文件.pdf" 即可，不要使用 sudo，也不需要手动添加 &。
如 Terminal 提示目录无权访问，请改用软件内安装入口，或在系统“隐私与安全性 → 文件与文件夹”中允许对应目录。
''', encoding='utf-8')
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
    installer.write_text(runpy.run_path(str(root/'asterpdf/cli.py'))['posix_installer'](), encoding='utf-8', newline='\n')
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
        output.add(command_guide, arcname=command_guide.name)
else:
    archive=shutil.make_archive(str(archive_base),'gztar',root_dir=dist,base_dir=bundle.name)
import hashlib
checksum=hashlib.sha256(Path(archive).read_bytes()).hexdigest()
Path(archive+'.sha256').write_text(checksum+'  '+Path(archive).name+'\n',encoding='ascii')
print(archive)
