"""Opt-in OFL font discovery and app-private cache. No system installation."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import time
import urllib.request
from urllib.parse import quote
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QListWidget,QListWidgetItem,QFileDialog
from .i18n import L,tr
from .jobs import Queue

RAW='https://raw.githubusercontent.com/google/fonts/main/'

def get_bytes(url,limit=24*1024*1024):
    request=urllib.request.Request(url,headers={'User-Agent':'AsterPDF-fonts','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=25) as response:
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError(L('字体资源超过下载大小限制。','Font resource exceeds the download size limit.'))
    return data

def catalog(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);cache=root/'catalog.json'
    if cache.exists() and time.time()-cache.stat().st_mtime<30*86400:
        return json.loads(cache.read_text(encoding='utf-8'))
    try:
        tree=json.loads(get_bytes('https://api.github.com/repos/google/fonts/git/trees/main?recursive=1'))
        if tree.get('truncated'):raise ValueError('Font catalog was truncated')
        groups={}
        for entry in tree['tree']:
            path=entry['path'];parts=path.split('/')
            if len(parts)==3 and parts[0]=='ofl' and (path.endswith('.ttf') or parts[-1]=='OFL.txt'):
                groups.setdefault(parts[1],[]).append(path)
        data={k:v for k,v in groups.items() if any(p.endswith('OFL.txt') for p in v) and any(p.endswith('.ttf') for p in v)}
        cache.write_text(json.dumps(data),encoding='utf-8');return data
    except Exception:
        if cache.exists():return json.loads(cache.read_text(encoding='utf-8'))
        raise

def normalized(name):
    name=name.split('+')[-1]
    return re.sub('[^a-z0-9]','',re.sub(r'(?i)(-?(bolditalic|regular|bold|italic|oblique|psmt))$','',name).lower())

def suggestions(name,data):
    wanted=normalized(name)
    aliases={'arial':'arimo','helvetica':'arimo','timesnewroman':'tinos','timesroman':'tinos','couriernew':'cousine','courier':'cousine','cmr10':'notoserif','cmr12':'notoserif','cmss10':'notosans','simsun':'notoserifsc','simhei':'notosanssc'}
    scores=[]
    for folder,files in data.items():
        names=[Path(p).stem.split('[')[0].split('-')[0] for p in files if p.endswith('.ttf')]
        display=names[0]
        score=max(difflib.SequenceMatcher(None,wanted,normalized(display)).ratio(),difflib.SequenceMatcher(None,wanted,folder).ratio())
        if folder==aliases.get(wanted):score=.98
        scores.append((score,display,folder,files,normalized(display)==wanted))
    return sorted(scores,reverse=True)[:30]

def download(root,folder,paths):
    if not re.fullmatch('[a-z0-9]+',folder):raise ValueError('Invalid font family')
    allowed=[p for p in paths if p.startswith('ofl/'+folder+'/') and len(p.split('/'))==3 and (p.endswith('.ttf') or p.endswith('/OFL.txt'))]
    license_path=next(p for p in allowed if p.endswith('/OFL.txt'))
    license_data=get_bytes(RAW+quote(license_path),1024*1024)
    if b'SIL OPEN FONT LICENSE' not in license_data.upper():raise ValueError('Unrecognized font license')
    folder_path=Path(root)/folder;folder_path.mkdir(parents=True,exist_ok=True)
    (folder_path/'OFL.txt').write_bytes(license_data)
    records=[]
    for path in sorted(allowed,key=lambda p:(not p.endswith('-Regular.ttf'),p)):
        if not path.endswith('.ttf'):continue
        data=get_bytes(RAW+quote(path))
        if data[:4] not in (b'\0\1\0\0',b'OTTO'):raise ValueError('Invalid font data')
        target=folder_path/Path(path).name;temporary=target.with_suffix('.part');temporary.write_bytes(data);temporary.replace(target)
        records.append({'file':target.name,'url':RAW+quote(path),'sha256':hashlib.sha256(data).hexdigest()})
    (folder_path/'source.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    return [folder_path/r['file'] for r in records]

def register_cache(root):
    registered=[]
    for path in Path(root).glob('*/*'):
        if path.suffix.lower() in ('.ttf','.otf'):
            fid=QFontDatabase.addApplicationFont(str(path))
            if fid>=0:registered.extend(QFontDatabase.applicationFontFamilies(fid))
    return registered

class FontDialog(QDialog):
    def __init__(self,tab):
        super().__init__(tab);self.tab=tab;self.root=tab.window.font_root;self.family=None;self.catalog_data={}
        self.queue=Queue(self);self.setWindowTitle(L('查找与缓存字体','Find and cache fonts'));self.resize(640,550)
        root=QVBoxLayout(self)
        original=tab.inline_object.details.get('family','') if tab.inline_editor else tab.object_font.currentFont().family()
        label=QLabel(L('原字体：','Original font: ')+original);label.setTextInteractionFlags(Qt.TextSelectableByMouse);root.addWidget(label)
        row=QHBoxLayout();root.addLayout(row);self.query=QLineEdit(original);row.addWidget(self.query)
        search=QPushButton(L('搜索开放字体','Search open fonts'));search.clicked.connect(self.search);row.addWidget(search);self.query.returnPressed.connect(self.search)
        self.list=QListWidget();root.addWidget(self.list,1)
        self.note=QLabel(L('按名称搜索 Google Fonts 的开放字体。相近字体不保证版式相同；商业字体可能没有下载结果。打开在线字体库后联网获取推荐。','Search open fonts in Google Fonts by name. Similar fonts may change layout; commercial fonts may be unavailable. Opening the online library requests recommendations.'));self.note.setWordWrap(True);root.addWidget(self.note)
        cache=QLabel(L('缓存目录：','Cache: ')+str(self.root));cache.setWordWrap(True);cache.setTextInteractionFlags(Qt.TextSelectableByMouse);root.addWidget(cache)
        row=QHBoxLayout();root.addLayout(row)
        self.fetch=QPushButton(L('下载并使用所选字体','Download and use selected font'));self.fetch.setEnabled(False);self.fetch.clicked.connect(self.fetch_font);row.addWidget(self.fetch)
        local=QPushButton(L('导入本地字体…','Import local font…'));local.clicked.connect(self.import_local);row.addWidget(local)
        close=QPushButton(tr('cancel'));close.clicked.connect(self.reject);row.addWidget(close)
        self.list.currentItemChanged.connect(lambda *_:self.fetch.setEnabled(self.list.currentItem() is not None))
        self.search_button=search

    def search(self):
        name=self.query.text().strip()
        if not name:return
        self.search_button.setEnabled(False);self.fetch.setEnabled(False);self.list.clear();self.note.setText(tr('working'))
        def ready(data):
            self.catalog_data=data
            for score,display,folder,files,exact in suggestions(name,data):
                item=QListWidgetItem(display+' · '+L('同名字体' if exact else '相近候选','Same family name' if exact else 'Similar candidate')+' · OFL')
                item.setData(Qt.UserRole,(folder,files));self.list.addItem(item)
            self.note.setText(L('请选择候选字体。同名不保证与 PDF 使用同一版本；输入后请检查结果。下载保留 OFL 许可证，仅供本程序使用。','Choose a candidate. The same name may have a different version; review edited text. Downloads retain the OFL license and are private to this app.'))
        self.queue.submit(lambda _:catalog(self.root),ready,self.fail,lambda:self.search_button.setEnabled(True),engine=False)

    def fetch_font(self):
        item=self.list.currentItem()
        if not item:return
        folder,files=item.data(Qt.UserRole);self.fetch.setEnabled(False);self.note.setText(tr('working'))
        self.queue.submit(lambda _:download(self.root,folder,files),self.use_files,self.fail,engine=False)

    def use_files(self,files):
        families=[]
        for path in files:
            fid=QFontDatabase.addApplicationFont(str(path))
            if fid>=0:families.extend(QFontDatabase.applicationFontFamilies(fid))
        if not families:self.fail(L('字体已缓存，但当前平台无法加载。','Font cached, but this platform could not load it.'));return
        self.family=next((family for family in families if normalized(family)==normalized(self.query.text())),families[0]);self.accept()

    def import_local(self):
        source,_=QFileDialog.getOpenFileName(self,L('导入字体','Import font'),'','Fonts (*.ttf *.otf)')
        if not source:return
        import shutil
        destination=self.root/'imported';destination.mkdir(parents=True,exist_ok=True)
        target=destination/Path(source).name
        if Path(source).resolve()!=target.resolve():shutil.copyfile(source,target)
        self.use_files([target])

    def fail(self,error):
        self.note.setText(L('无法获取字体。可以选择本机字体，或导入已获得的字体文件。\n','Could not obtain font. Choose an installed font or import a font file you already have.\n')+str(error));self.fetch.setEnabled(bool(self.list.currentItem()))

    def done(self,result):
        # Own worker queue must outlive its network requests. Hiding the dialog
        # does not destroy it; the tab owns it until all jobs have finished.
        super().done(result)
