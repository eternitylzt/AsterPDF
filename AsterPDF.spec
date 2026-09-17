# Build separately on each target OS: python -m PyInstaller --noconfirm AsterPDF.spec
from pathlib import Path
import sys
import os
import runpy
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
version=runpy.run_path(str(root/'asterpdf/__init__.py'))['__version__']
data = [(str(root/'asterpdf'/'resources'), 'asterpdf/resources'),
        (str(root/'LICENSE'), 'licenses'),
        (str(root/'THIRD_PARTY_NOTICES.md'), 'licenses'),
        (str(root/'licenses'), 'licenses/third-party')]
a = Analysis([str(root/'run.py')], pathex=[str(root)], binaries=[], datas=data,
    hiddenimports=['PySide6.QtMultimedia','PySide6.QtMultimediaWidgets','pikepdf._core'],
    excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick',
              'PySide6.Qt3DCore','PySide6.Qt3DRender','PySide6.Qt3DExtras','PySide6.QtPdf',
              'tkinter','pytest','reportlab','imageio_ffmpeg','numpy','matplotlib'],
    noarchive=False)
if sys.platform == 'win32':
    # Qt's Windows ICU imports target the OS API. A broad developer PATH can
    # make dependency scanners collect a different ICU from e.g. Poppler.
    # Such DLLs export version-suffixed symbols and break QtCore at startup.
    import PySide6
    qt_dir = Path(PySide6.__file__).parent
    runtimes = {p.name.lower(): p for p in qt_dir.glob('*.dll')
                if p.name.lower().startswith(('msvcp140', 'vcruntime140', 'concrt140'))}
    filtered = []
    for dest, source, kind in a.binaries:
        basename = Path(dest).name.lower()
        if basename.startswith(('api-ms-win-', 'icudt')) or basename in ('icuuc.dll','ucrtbase.dll'):
            continue
        filtered.append((dest, str(runtimes[basename]) if basename in runtimes else source, kind))
    existing = {entry[0].lower() for entry in filtered}
    filtered.extend((p.name, str(p), 'BINARY') for p in runtimes.values() if p.name.lower() not in existing)
    a.binaries = filtered
pyz = PYZ(a.pure)
icon = root/'assets'/('asterpdf.icns' if sys.platform=='darwin' else 'asterpdf.ico')
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='AsterPDF',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=bool(os.environ.get('ASTERPDF_CONSOLE')),icon=str(icon))
collection = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='AsterPDF')
if sys.platform == 'darwin':
    app = BUNDLE(collection,name='AsterPDF.app',icon=str(icon),bundle_identifier='org.asterpdf.desktop',
        info_plist={'CFBundleName':'AsterPDF','CFBundleShortVersionString':version,
                    'NSHighResolutionCapable':True,'LSMinimumSystemVersion':'13.0',
                    'CFBundleDocumentTypes':[{'CFBundleTypeName':'PDF document',
                    'CFBundleTypeExtensions':['pdf'],'CFBundleTypeRole':'Editor'}]})
