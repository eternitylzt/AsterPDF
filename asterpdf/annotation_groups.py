"""Interpret Adobe text-replacement annotation groups without altering source data."""
import re

def group_replacements(pdf,items):
    lookup={a['xref']:a for a in items};groups={};hidden=set()
    for ann in items:
        if ann['type'] not in ('StrikeOut','Caret'):continue
        kind,value=pdf.xref_get_key(ann['xref'],'IRT')
        if kind!='xref':continue
        parent=lookup.get(int(value.split()[0]))
        if not parent or {ann['type'],parent['type']}!={'Caret','StrikeOut'}:continue
        caret=ann if ann['type']=='Caret' else parent
        strike=parent if ann['type']=='Caret' else ann
        group=groups.setdefault(caret['xref'],dict(strike,type='ReplaceText',text=caret['text'] or strike['text'],related=[caret['xref']]))
        if strike['xref']!=group['xref']:group['related'].append(strike['xref'])
        hidden.update((caret['xref'],strike['xref']))
    return [a for a in items if a['xref'] not in hidden]+list(groups.values())
