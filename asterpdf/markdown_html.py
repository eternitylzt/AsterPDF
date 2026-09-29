"""Self-contained, offline HTML previews for the user's system browser."""
import base64
import hashlib
import io
import os
import re
import secrets
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from .i18n import L


class PreviewHTML(HTMLParser):
    tags=set('p div span a h1 h2 h3 h4 h5 h6 ul ol li blockquote pre code em strong b i s del u sub sup br hr table thead tbody tfoot tr th td img details summary kbd samp dl dt dd abbr'.split())
    def __init__(self,resources):
        super().__init__(convert_charrefs=True);self.resources=resources;self.parts=[];self.headings=[];self.heading=None;self.slugs={};self.blocked=0

    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','iframe','object','svg','math'):self.blocked+=1;return
        if self.blocked or tag not in self.tags:return
        props=dict(attrs);safe={}
        for name in ('title','alt','id','colspan','rowspan','align','start','width','height'):
            if name in props and props[name] is not None:safe[name]=props[name]
        if tag=='a':
            href=props.get('href','') or '';parts=urlsplit(href)
            if href.startswith('#') or parts.scheme in ('http','https','mailto'):
                safe['href']=href
                if not href.startswith('#'):safe['rel']='noopener noreferrer';safe['target']='_blank'
        if tag=='img':
            name=props.get('src','');raw=self.resources.get(name)
            if not raw:return
            if b'<svg' in raw[:2048]:mime='image/svg+xml'
            else:
                from PIL import Image
                try:
                    with Image.open(io.BytesIO(raw)) as image:mime=Image.MIME.get(image.format,'image/png')
                except Exception:return
            safe['src']='data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
            if name.startswith('aster-math:'):safe['class']='math-inline';safe.setdefault('alt',L('公式','Formula'))
            else:safe['loading']='lazy'
        if re.fullmatch('h[1-6]',tag):self.heading=(len(self.parts),int(tag[1]),[],safe)
        self.parts.append('<'+tag+''.join(' '+k+'="'+escape(str(v),quote=True)+'"' for k,v in safe.items())+'>')

    def handle_endtag(self,tag):
        if tag in ('script','style','iframe','object','svg','math'):self.blocked=max(0,self.blocked-1);return
        if self.blocked or tag not in self.tags:return
        if self.heading and tag=='h'+str(self.heading[1]):
            index,level,text,attrs=self.heading;title=''.join(text).strip();self.heading=None
            slug=re.sub(r'[^\w\- ]','',title.casefold()).replace(' ','-') or 'section';count=self.slugs.get(slug,0);self.slugs[slug]=count+1
            attrs['id']=attrs.get('id') or slug+('-'+str(count) if count else '')
            self.parts[index]='<'+tag+''.join(' '+k+'="'+escape(str(v),quote=True)+'"' for k,v in attrs.items())+'>'
            self.headings.append((level,title,attrs['id']))
        if tag not in ('img','hr','br'):self.parts.append('</'+tag+'>')

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in ('img','hr','br'):self.handle_endtag(tag)

    def handle_data(self,data):
        if not self.blocked:
            self.parts.append(escape(data))
            if self.heading:self.heading[2].append(data)


CSS='''
:root{color-scheme:light;--bg:#fff;--ink:#24292f;--soft:#f4f6f8;--line:#d8dee4;--link:#0969da}
:root[data-theme=dark]{color-scheme:dark;--bg:#111923;--ink:#dce4ef;--soft:#1e2a39;--line:#41516a;--link:#80bbff}
:root[data-theme=dark] .math-inline{filter:invert(1)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 22px;display:flex;gap:12px;align-items:center}header strong{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
button{font:inherit;background:var(--soft);color:var(--ink);border:1px solid var(--line);border-radius:5px;padding:3px 10px;cursor:pointer}button:hover{border-color:var(--link)}
.layout{display:flex;max-width:1400px;margin:auto}nav{width:240px;flex-shrink:0;position:sticky;top:64px;align-self:flex-start;max-height:calc(100vh - 80px);overflow:auto;padding:24px 18px;font-size:14px}nav a{display:block;padding:5px 0;text-decoration:none;line-height:1.4}nav .level-2{padding-left:12px}nav .level-3,nav .level-4,nav .level-5,nav .level-6{padding-left:24px}
article{max-width:980px;min-width:0;flex:1;padding:26px 38px 80px}article>:first-child{margin-top:0}h1,h2,h3,h4,h5,h6{line-height:1.3;scroll-margin-top:85px}h1,h2{border-bottom:1px solid var(--line);padding-bottom:.3em}h1{font-size:2em}h2{font-size:1.5em;margin-top:1.5em}p{margin:1em 0}a{color:var(--link)}
pre{background:var(--soft);padding:17px;border-radius:6px;overflow:auto;line-height:1.5}code,kbd,samp{font:14px/1.5 ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace}code{background:var(--soft);padding:.15em .3em;border-radius:3px}pre code{padding:0;white-space:pre;background:none}.code-tools{display:flex;justify-content:flex-end;margin-bottom:-8px;font-size:12px}blockquote{margin-left:0;padding:0 1em;border-left:4px solid var(--line);opacity:.86}table{border-collapse:collapse;max-width:100%;display:block;overflow:auto;margin:1em 0}th,td{border:1px solid var(--line);padding:7px 13px}th{background:var(--soft)}tr:nth-child(even){background:var(--soft)}img{max-width:100%;height:auto}.math-inline{vertical-align:middle;max-width:100%}hr{border:0;border-top:1px solid var(--line);margin:2em 0}li+li{margin-top:.25em}.source-note{font-size:13px;opacity:.65;margin-top:38px}
@media(max-width:850px){nav{display:none}article{padding:22px}header{padding:9px 15px}header strong{font-size:14px}}
@media print{header,nav,.code-tools,.source-note{display:none}article{max-width:none;padding:0}pre{white-space:pre-wrap}pre code{white-space:pre-wrap;overflow-wrap:anywhere}body{color:#111;background:white}a{color:inherit}}
'''


def build_html(filename,prepared,dark=False):
    parser=PreviewHTML(prepared[1]);parser.feed(prepared[0]);parser.close();nonce=secrets.token_urlsafe(18)
    toc=''.join('<a class="level-'+str(level)+'" href="#'+escape(anchor,quote=True)+'">'+escape(title)+'</a>' for level,title,anchor in parser.headings)
    policy=f"default-src 'none'; img-src data:; style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'; base-uri 'none'; form-action 'none'; connect-src 'none'"
    script='''document.getElementById('theme').onclick=()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'light':'dark'};
document.querySelectorAll('pre').forEach(pre=>{const row=document.createElement('div');row.className='code-tools';const b=document.createElement('button');b.textContent=COPY;row.append(b);pre.before(row);b.onclick=async()=>{const text=pre.textContent;try{await navigator.clipboard.writeText(text)}catch(e){const area=document.createElement('textarea');area.value=text;document.body.append(area);area.select();document.execCommand('copy');area.remove()}b.textContent=COPIED;setTimeout(()=>b.textContent=COPY,1200)}});'''
    import json
    script='const COPY='+json.dumps(L('复制代码','Copy code'))+',COPIED='+json.dumps(L('已复制','Copied'))+';'+script
    title=escape(Path(filename).name)
    return '<!doctype html><html lang="'+L('zh-CN','en')+'" data-theme="'+('dark' if dark else 'light')+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="'+escape(policy,quote=True)+'"><title>'+title+' · AsterPDF</title><style nonce="'+nonce+'">'+CSS+'</style></head><body><header><strong>✦ '+title+'</strong><button id="theme">'+L('浅色 / 深色','Light / Dark')+'</button></header><div class="layout"><nav aria-label="'+L('目录','Outline')+'"><strong>'+L('目录','Outline')+'</strong>'+toc+'</nav><article>'+''.join(parser.parts)+'<p class="source-note">'+L('AsterPDF · 本地 Markdown HTML 预览。此页反映打开时的 Markdown 内容，不包含另行添加的 PDF 编辑或批注。','AsterPDF · Local Markdown HTML preview. This page shows the opened Markdown source, not subsequent PDF edits or annotations.')+'</p></article></div><script nonce="'+nonce+'">'+script+'</script></body></html>'


def write_preview(filename,prepared,folder,dark=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(str(Path(filename).resolve()).encode()).hexdigest()[:24];target=folder/('aster-'+key+'.html');temporary=target.with_suffix('.tmp')
    try:
        temporary.write_text(build_html(filename,prepared,dark),encoding='utf-8');os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)
    # Keep recent previews available after the PDF tab closes, with a bounded cache.
    for old in sorted(folder.glob('aster-*.html'),key=lambda p:p.stat().st_mtime,reverse=True)[20:]:old.unlink(missing_ok=True)
    return target
