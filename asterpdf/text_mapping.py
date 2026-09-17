"""Bounded matching for long journal text objects."""
import difflib

def opcodes(a,b):
    start=0;limit=min(len(a),len(b))
    while start<limit and a[start]==b[start]:start+=1
    end=0
    while end<limit-start and a[len(a)-end-1]==b[len(b)-end-1]:end+=1
    out=[('equal',0,start,0,start)] if start else []
    aa=a[start:len(a)-end if end else len(a)];bb=b[start:len(b)-end if end else len(b)]
    out.extend((tag,x+start,y+start,u+start,v+start) for tag,x,y,u,v in difflib.SequenceMatcher(None,aa,bb,autojunk=False).get_opcodes())
    if end:out.append(('equal',len(a)-end,len(a),len(b)-end,len(b)))
    return out

def glyph_mapping(text,painted,strict=True):
    # Extraction inserts whitespace between lines/positioned words. Match in
    # linear time when those are the only differences; ambiguity is never guessed.
    result={};a=b=0
    while a<len(text) and b<len(painted):
        if text[a].casefold()==painted[b].casefold() or (text[a]=='\xad' and painted[b]=='-') or (text[a] not in '\n\r' and (text[a].isspace() or text[a]=='\xad') and (painted[b].isspace() or painted[b]=='\xad')):result[a]=b;a+=1;b+=1
        elif text[a].isspace():a+=1
        else:break
    if b==len(painted) and not text[a:].strip():return result
    result={}
    for tag,a,b,c,d in opcodes(text,painted):
        if tag=='equal':result.update((a+i,c+i) for i in range(b-a))
        elif (tag!='delete' or text[a:b].strip()) and strict:return None
    return result
