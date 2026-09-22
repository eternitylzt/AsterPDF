"""Offline, bounded TeX-to-SVG. Document text never becomes JavaScript code."""
from pathlib import Path
import re
import json


class MathRenderer:
    def __init__(self):
        self.context=None
        self.cache={}

    def svg(self,tex,display=False):
        key=(tex,display)
        if key in self.cache:return self.cache[key]
        if len(tex)>16384:raise ValueError('Formula is too long')
        if self.context is None:
            import quickjs
            self.context=quickjs.Context()
            self.context.set_memory_limit(64*1024*1024)
            self.context.set_max_stack_size(2*1024*1024)
            self.context.set_time_limit(5)
            self.context.eval((Path(__file__).parent/'resources'/'mathjax-svg.js').read_text(encoding='utf8'))
        self.context.set_time_limit(2)
        self.context.set('asterTex',tex);self.context.set('asterDisplay',bool(display))
        raw=json.loads(self.context.eval('JSON.stringify(asterMath(asterTex,asterDisplay))'))
        # Qt SVG does not resolve CSS currentColor. MathJax emits self-contained paths.
        raw=raw.replace('currentColor','#111111')
        width=float(re.search(r'width="([\d.]+)ex"',raw).group(1))*7.33
        height=float(re.search(r'height="([\d.]+)ex"',raw).group(1))*7.33
        scale=min(1,640/max(1,width))
        raw=re.sub(r'width="[\d.]+ex"',f'width="{width*scale:.3f}"',raw,count=1)
        raw=re.sub(r'height="[\d.]+ex"',f'height="{height*scale:.3f}"',raw,count=1)
        result=raw.encode('utf8')
        if len(self.cache)<1000:self.cache[key]=result
        return result
