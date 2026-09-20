"""Readable display of TeX metadata, retaining the exact source for inspection."""
import re
def readable(value):
    text=str(value).strip()
    # Some xdvipdfmx titles contain TeX expansion debris after the title's
    # first explicit line break. Only strip this recognizable malformed tail.
    text=re.sub(r'\[[-+\d.]+(?:pt|em|ex)\]\s*`\s*`%%%.*$','',text,flags=re.S)
    text=re.sub(r'\[[-+\d.]+(?:pt|em|ex)\]', '\n',text)
    return text.strip()
