"""Build Linux packages and reject binaries requiring glibc newer than 2.28."""
from pathlib import Path
import os,re,runpy,shutil,subprocess,tarfile,json

root=Path(__file__).resolve().parents[1];os.chdir(root)
version=runpy.run_path('asterpdf/__init__.py')['__version__']
dist=root/'dist';bundle=dist/'AsterPDF'
requirements={}
for file in bundle.rglob('*'):
    if not file.is_file() or file.is_symlink():continue
    with file.open('rb') as stream:
        if stream.read(4)!=b'\x7fELF':continue
    output=subprocess.check_output(['readelf','--version-info',str(file)],text=True)
    versions=[tuple(map(int,v.split('.'))) for v in re.findall(r'GLIBC_(\d+\.\d+(?:\.\d+)?)',output)]
    if versions:requirements[str(file.relative_to(bundle))]='.'.join(map(str,max(versions)))
bad={name:v for name,v in requirements.items() if tuple(map(int,v.split('.')))>(2,28)}
if bad:raise SystemExit('glibc baseline exceeded: '+json.dumps(bad))
(dist/'linux-abi.json').write_text(json.dumps({'glibc_max':'2.28','binaries':requirements},indent=2))
subprocess.run(['python3.11','scripts/package.py'],check=True)
shutil.copyfile(dist/f'AsterPDF-{version}-source.zip',dist/f'AsterPDF-{version}-linux-source.zip')
stage=dist/'linux-stage';app=stage/'opt/asterpdf';app.parent.mkdir(parents=True,exist_ok=True)
shutil.copytree(bundle,app,symlinks=True)
paths={'usr/bin/asterpdf':'#!/bin/sh\nexec /opt/asterpdf/AsterPDF "$@"\n'}
for name,content in paths.items():
    p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content);p.chmod(0o755)
for source,target in [('packaging/linux/asterpdf.desktop','usr/share/applications/asterpdf.desktop'),('assets/asterpdf.png','usr/share/icons/hicolor/256x256/apps/asterpdf.png'),('assets/asterpdf.svg','usr/share/icons/hicolor/scalable/apps/asterpdf.svg')]:
    p=stage/target;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,p)
size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())//1024
control=dist/'deb-control';control.mkdir()
(control/'control').write_text(f'''Package: asterpdf
Version: {version}-1
Architecture: amd64
Maintainer: Zhentong Li <eternitylzt@gmail.com>
Section: science
Priority: optional
Installed-Size: {size}
Depends: libc6 (>= 2.28), libgl1, libegl1, libx11-6, libxcb1, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, libdbus-1-3, libasound2 | libasound2t64, fonts-dejavu-core
Homepage: https://github.com/eternitylzt/AsterPDF
Description: Scientific PDF reader, editor and multimedia workspace
 Read animated PDFs, edit and annotate, extract vector figures,
 and read mathematical Markdown offline. Python and Qt are bundled.
''')
refresh='#!/bin/sh\nset -e\nif command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database -q || true; fi\nexit 0\n'
for name in ['postinst','postrm']:(control/name).write_text(refresh);(control/name).chmod(0o755)
def archive(path,directory):
    def owned(info):info.uid=info.gid=0;info.uname=info.gname='root';return info
    with tarfile.open(path,'w:gz',format=tarfile.GNU_FORMAT) as tar:
        for p in directory.iterdir():tar.add(p,arcname='./'+p.name,filter=owned)
archive(dist/'control.tar.gz',control);archive(dist/'data.tar.gz',stage)
(dist/'debian-binary').write_text('2.0\n')
subprocess.run(['ar','rc',f'asterpdf_{version}-1_amd64.deb','debian-binary','control.tar.gz','data.tar.gz'],cwd=dist,check=True)
rpm=dist/'rpmbuild'
for d in ['BUILD','BUILDROOT','RPMS','SOURCES','SPECS','SRPMS']:(rpm/d).mkdir(parents=True,exist_ok=True)
spec=rpm/'SPECS/asterpdf.spec'
spec.write_text(f'''Name: asterpdf
Version: {version}
Release: 1
Summary: Scientific PDF reader, editor and multimedia workspace
License: AGPL-3.0-only AND LGPL-3.0-only AND MIT AND Apache-2.0
URL: https://github.com/eternitylzt/AsterPDF
BuildArch: x86_64
AutoReqProv: no
Requires: glibc >= 2.28, mesa-libGL, mesa-libEGL, libX11, libxcb, libxkbcommon, libxkbcommon-x11, fontconfig, dbus-libs, alsa-lib, dejavu-sans-fonts
%description
Read, edit, animate, annotate and extract scientific PDF documents.
Includes Python, Qt, offline mathematical Markdown and matching source.
%install
mkdir -p %{{buildroot}}
cp -a {stage}/. %{{buildroot}}/
%files
/opt/asterpdf
/usr/bin/asterpdf
/usr/share/applications/asterpdf.desktop
/usr/share/icons/hicolor/256x256/apps/asterpdf.png
/usr/share/icons/hicolor/scalable/apps/asterpdf.svg
%post
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || :
%postun
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || :
''')
subprocess.run(['rpmbuild','-bb','--define',f'_topdir {rpm}','--define','__os_install_post %{nil}','--define','_build_id_links none',str(spec)],check=True)
for file in (rpm/'RPMS').rglob('*.rpm'):shutil.copyfile(file,dist/file.name)
print('Linux tar.gz, deb, rpm and source built; all ELF GLIBC requirements <= 2.28.')
