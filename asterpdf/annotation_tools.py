"""Inline annotation properties with independent, persistent tool presets."""
import json
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton,QTextEdit,QLabel
from .i18n import L,tr

KINDS=('select_annot','highlight','underline','strikeout','replace_text','squiggly','note','freetext','ink','line','arrow','rectangle','ellipse')

def build(tab,kind,selected=None,author=False):
    if selected and len(selected)==1:
        ann=selected[0];kind={'Text':'note','FreeText':'freetext','Square':'rectangle','Circle':'ellipse','StrikeOut':'strikeout','ReplaceText':'replace_text'}.get(ann['type'],ann['type'].lower())
        if ann['type']=='Line':kind='arrow' if ann.get('line_end') else 'line'
    pane=tab.property_pane(L('批注人信息','Annotation author') if author else tr(kind));tab.annotation_properties=pane
    if author:
        name=pane.text('author',L('姓名','Name'),tab.annot_author if tab.annot_author!='AsterPDF' else '')
        name.setPlaceholderText('AsterPDF')
        def save(text):
            tab.annot_author=text.strip() or 'AsterPDF';tab.window.settings.setValue('annotation_author',tab.annot_author)
            for opened in tab.window.document_tabs():opened.annot_author=tab.annot_author
        name.textChanged.connect(save);return
    key='annotation/tools/'+kind
    try:values=json.loads(tab.window.settings.value(key,'{}'))
    except (ValueError,TypeError):values={}
    values={'color':'#efb43d' if kind=='highlight' else '#d02d39','width':2.,'opacity':.7 if kind=='highlight' else 1.,'size':12.,'font':'china-s','end':5,'head':10.,'dash':'solid','border':0.,'fill':False,'fill_color':'#f7d577',**values}
    if selected:
        ann=selected[0];values.update(color=QColor.fromRgbF(*(ann.get('color') or (0,0,0))).name(),width=ann.get('width',2),opacity=ann.get('opacity',1),size=ann.get('fontsize',12),font=ann.get('fontname','china-s'),end=ann.get('line_end') or 5,head=ann.get('head_size',10),dash=ann.get('dash','dash' if ann.get('dashed') else 'solid'),fill=bool(ann.get('fill')),fill_color=QColor.fromRgbF(*(ann.get('fill') or (1,1,1))).name(),border=ann.get('width',0))
    color=tab.color_button(pane,tr('color'),QColor(values['color']))
    pane.number('width',tr('width'),max(0,values['width']),0,30,1)
    pane.number('opacity',L('不透明度（%）','Opacity (%)'),values['opacity']*100,5,100,0)
    dash=pane.choice('dash',L('线型','Line style'),[(L('实线','Solid'),'solid'),(L('虚线','Dashed'),'dash'),(L('点线','Dotted'),'dot'),(L('点划线','Dash-dot'),'dashdot')]+([(L('波浪线','Wave'),'wave')] if kind in ('underline','squiggly') else []));dash.setCurrentIndex(max(0,dash.findData(values['dash'])))
    if (selected and len(selected)>1) or kind in ('highlight','note'):
        dash.hide();pane.form.labelForField(dash).hide()
    text_kind=kind in ('note','freetext','replace_text') or bool(selected and len(selected)==1)
    fill=None
    if kind in ('rectangle','ellipse'):
        pane.check('fill',L('填充','Fill'),values['fill']);fill=tab.color_button(pane,L('填充颜色','Fill color'),QColor(values['fill_color']))
    if kind=='arrow' or (selected and len(selected)==1 and selected[0]['type']=='Line'):
        end=pane.choice('end',L('箭头端点','Arrow ending'),[(L('实心','Closed'),5),(L('空心','Open'),4),(L('圆形','Circle'),2),(L('无','None'),0)]);end.setCurrentIndex(max(0,end.findData(values['end'])))
        pane.number('head',L('箭头大小','Arrowhead size'),values['head'],3,80,1)
    if kind in ('freetext','note') or (selected and len(selected)==1 and selected[0]['type']=='FreeText'):
        pane.number('size',L('字号','Font size'),values['size'],4,150,1)
        font=pane.choice('font',L('字体','Font'),[(L('中文','CJK'),'china-s'),('Helvetica','helv'),('Times','tiro'),('Courier','cour')]);font.setCurrentIndex(max(0,font.findData(values['font'])))
        pane.number('border',L('文本框边框','Text border'),values['border'],0,20,1)
    editor=None
    if text_kind:
        editor=QTextEdit();editor.setAcceptRichText(False);editor.setMinimumHeight(85);editor.setMaximumHeight(150);editor.setPlaceholderText(L('批注内容 / 替换文字','Comment / replacement text'));pane.form.addRow(editor)
        if selected:editor.setPlainText(selected[0]['text'])
    tab.annotation_text_input=editor
    def current():
        result={**values,**pane.values(),'color':color.color.name()};result['opacity']/=100
        if fill:result['fill_color']=fill.color.name()
        return result
    def sync(*_):
        if selected:return
        v=current();tab.window.settings.setValue(key,json.dumps(v));tab.annot_color=color.color;tab.annot_width=v['width'];tab.annot_opacity=v['opacity'];tab.annot_size=v['size'];tab.annot_font=v['font'];tab.annot_end=v['end'];tab.annot_head_size=v['head'];tab.annot_dashed=v['dash']!='solid';tab.annot_dash=v['dash'];tab.annot_text_border=v['border'];tab.annot_fill=QColor(v['fill_color']).getRgbF()[:3] if v['fill'] else None
    for widget in pane.inputs.values():
        signal=getattr(widget,'valueChanged',None) or getattr(widget,'currentIndexChanged',None) or getattr(widget,'toggled',None)
        if signal is not None:signal.connect(sync)
    color.changed.connect(sync)
    if fill:fill.changed.connect(sync)
    if not selected:sync()
    def apply():
        chosen=[it.data(Qt.UserRole) for it in tab.annotation_list.selectedItems()]
        if not chosen or tab.busy:return
        v=current();changes=[]
        for ann in chosen:
            options=dict(color=color.color.getRgbF()[:3],width=v['width'],opacity=v['opacity'],dashed=v['dash']!='solid' if len(chosen)==1 else ann.get('dashed',False),dash=v['dash'] if len(chosen)==1 else ann.get('dash','solid'),line_end=v['end'] if len(chosen)==1 else ann.get('line_end'),head_size=v['head'] if len(chosen)==1 else ann.get('head_size'))
            if editor is not None and len(chosen)==1:options['text']=editor.toPlainText()
            if ann['type'] in ('FreeText','Text') and len(chosen)==1:options.update(fontsize=v['size'],fontname=v['font'],width=v['border'])
            if fill:options['fill']=QColor(v['fill_color']).getRgbF()[:3] if v['fill'] else ()
            changes.append((ann,options))
        tab.run(tr('annotate'),lambda j:tab.document.change_annotations(changes),editing=True,local_edit=len({a['page'] for a in chosen})==1)
    if selected or kind=='select_annot':
        button=QPushButton(tr('apply'));button.clicked.connect(apply);pane.form.addRow(button)
    pane.apply_annotations=apply
    if kind in ('note','freetext','replace_text') and not selected:pane.note(L('先填写内容，再点击页面或选择文字放置。','Enter text, then click the page or select text to place it.'))

def content(tab):
    editor=getattr(tab,'annotation_text_input',None)
    return editor.toPlainText() if editor is not None else ''
