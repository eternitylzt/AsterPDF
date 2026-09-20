"""One settings store; applying preferences synchronizes open documents without editing PDFs."""
from pathlib import Path
from PySide6.QtCore import Qt,QSignalBlocker,QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QTabWidget,QDialogButtonBox,QScrollArea,QPushButton,QFileDialog
from PySide6.QtGui import QColor
from .dialogs import FormDialog
from .i18n import L,tr

def remember_annotation(tab):
    if tab._sync_annotation:return
    for key in ANNOT:
        value=getattr(tab,key);tab.window.settings.setValue('annotation/'+key,value.name() if isinstance(value,QColor) else value)
    tab.window.settings.setValue('annotation_author',tab.annot_author)


ANNOT={'annot_color':('#efb43d',str),'annot_width':(2.,float),'annot_opacity':(.7,float),'annot_font':('china-s',str),'annot_size':(12.,float),'annot_end':(5,int),'annot_dashed':(False,bool),'annot_head_size':(10.,float),'annot_text_border':(0.,float),'annot_border_color':('#243249',str)}

def annotation_defaults(tab):
    for key,(default,kind) in ANNOT.items():
        value=tab.window.settings.value('annotation/'+key,default,type=kind)
        setattr(tab,key,QColor(value) if 'color' in key else value)
    tab.annot_author=tab.window.settings.value('annotation_author','AsterPDF')
    if hasattr(tab,'annot_width_widget'):
        with QSignalBlocker(tab.annot_width_widget):tab.annot_width_widget.setValue(tab.annot_width)
        with QSignalBlocker(tab.annot_opacity_widget):tab.annot_opacity_widget.setValue(round(tab.annot_opacity*100))
        tab.color_action.setText('● '+tr('color'))

class Preferences(QDialog):
    def __init__(self,window):
        super().__init__(window);self.host=window;self.forms=[];self.setWindowTitle(L('设置 / 首选项','Settings / Preferences'));self.resize(660,620)
        root=QVBoxLayout(self);self.tabs=QTabWidget();root.addWidget(self.tabs)
        def page(label):
            form=FormDialog('',self);form.setWindowFlags(Qt.Widget);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(form);self.tabs.addTab(scroll,label);self.forms.append(form);return form
        def field(form,key,label,default,limits=None,choices=None):
            value=window.settings.value(key,default,type=type(default))
            if 'color' in key and key.startswith('annotation/'):
                from .tool_widgets import ColorButton
                w=ColorButton(QColor(value));form.inputs[key]=w;form.form.addRow(label,w)
            elif choices:
                w=form.choice(key,label,choices);w.setCurrentIndex(max(0,w.findData(value)))
            elif isinstance(default,bool):w=form.check(key,label,value)
            elif limits:w=form.number(key,label,value,*limits)
            else:w=form.text(key,label,value)
            return w
        f=page(L('常规','General'))
        field(f,'window/confirm_close',L('退出时询问关闭当前或所有标签页','Ask whether to close current or all tabs'),True)
        field(f,'home/recent',L('首页显示最近文件','Recent files on Home'),True)
        field(f,'ui/font_size',L('界面字体','Interface text'),'medium',choices=[(L('小','Small'),'small'),(L('中','Medium'),'medium'),(L('大','Large'),'large')])
        field(f,'language','语言/Language','zh',choices=[('中文','zh'),('English','en')]);field(f,'dark',tr('dark'),True)
        f=page(L('阅读 / 工具栏','Reading / Toolbar'))
        field(f,'reader/columns',L('并排页数','Columns'),1,choices=[('1',1),('2',2)])
        field(f,'reader/continuous',tr('continuous'),True);field(f,'reader/night',tr('night'),False)
        field(f,'toolbar/opacity',L('工具栏不透明度（%）','Toolbar opacity (%)'),100,(35,100))
        field(f,'toolbar/hidden',L('隐藏工具栏','Hide toolbar'),False);field(f,'toolbar/autohide',L('自动隐藏工具栏','Auto-hide toolbar'),False)
        field(f,'sidebar/hidden',L('收起导航','Collapse navigation'),False);field(f,'sidebar/autohide',L('自动隐藏导航','Auto-hide navigation'),False)
        button=QPushButton(L('自定义工具栏按钮…','Customize toolbar buttons…'));button.clicked.connect(lambda:window.customize_toolbar(self));f.form.addRow(button)
        f=page(L('速览窗','Overview'))
        field(f,'minimap/enabled',L('显示速览窗','Show overview'),True);field(f,'minimap/opacity',L('不透明度（%）','Opacity (%)'),80,(20,100))
        field(f,'minimap/auto_scale',L('按页数自动缩放','Automatic scale by page count'),True)
        field(f,'minimap/scale',L('缩略比例（%）','Preview scale (%)'),10.,(.5,20,1))
        field(f,'minimap/auto_size',L('自动适应尺寸','Automatic dimensions'),True)
        field(f,'minimap/width',L('自定义宽度','Custom width'),148,(100,1500));field(f,'minimap/height',L('自定义高度','Custom height'),370,(100,1500))
        field(f,'minimap/corner',L('位置','Position'),'top-right',choices=[(L('右上','Top right'),'top-right'),(L('左上','Top left'),'top-left'),(L('右下','Bottom right'),'bottom-right'),(L('左下','Bottom left'),'bottom-left')])
        f=page(L('批注','Annotations'));field(f,'annotation/show',L('显示所有批注','Show all annotations'),True);field(f,'annotation/sort',L('列表排序','List order'),'position',choices=[(L('文档位置','Position'),'position'),(L('时间','Time'),'time')]);field(f,'annotation_author',L('批注人','Author'),'AsterPDF')
        names={'annot_color':L('颜色','Color'),'annot_width':L('线宽','Line width'),'annot_opacity':L('不透明度（0–1）','Opacity (0–1)'),'annot_size':L('字号','Font size'),'annot_head_size':L('箭头大小','Arrowhead size'),'annot_text_border':L('文本边框宽度','Text border width'),'annot_border_color':L('文本边框颜色','Text border color'),'annot_dashed':L('虚线','Dashed')}
        for key,(default,kind) in ANNOT.items():
            choices=[(L('中文','CJK'),'china-s'),('Helvetica','helv'),('Times','tiro'),('Courier','cour')] if key=='annot_font' else [(L('实心箭头','Closed arrow'),5),(L('空心箭头','Open arrow'),4),(L('圆','Circle'),2),(L('菱形','Diamond'),3),(L('无','None'),0)] if key=='annot_end' else None
            field(f,'annotation/'+key,names.get(key,L('字体','Font') if key=='annot_font' else L('箭头端点','Arrow ending')),default,(.05,1,2) if key=='annot_opacity' else (4 if key=='annot_size' else 3 if key=='annot_head_size' else .2 if key=='annot_width' else 0,150,1) if kind==float else None,choices)
        f=page(L('对象 / 页面','Objects / Pages'))
        field(f,'image/ratio',L('图片保持宽高比','Keep image aspect ratio'),True)
        field(f,'shape/width',L('图形线宽','Shape line width'),1.5,(.1,50,1));field(f,'shape/fill',L('填充图形','Fill shapes'),False)
        field(f,'color/images',L('换色包含栅格图片','Recolor raster images'),True)
        field(f,'page/angle',L('默认旋转角度','Default rotation'),90,choices=[('90°',90),('-90°',-90),('180°',180)]);field(f,'page/separate',L('提取每页为单独 PDF','Extract one PDF per page'),False)
        field(f,'color/invert',L('默认使用反色','Invert by default'),False)
        field(f,'color/tolerance',L('换色容差（%）','Recolor tolerance (%)'),8.,(0,100,1))
        field(f,'crop/keep',L('裁剪保留框外内容','Keep outside crop'),False)
        f.note(L('设置只调整工具默认值，不会修改现有内容。页码范围、所选对象与裁剪框属于当前文档的操作选区。','Preferences change tool defaults, not existing content. Page ranges, selected objects and crop rectangles remain document-specific.'))
        f=page(L('导出 / 播放','Export / Playback'))
        field(f,'export/dpi','DPI',300,(36,1200));field(f,'export/width',L('输出宽度（0 使用 DPI）','Output width (0 uses DPI)'),0,(0,16000));field(f,'export/quality',L('JPG 质量','JPG quality'),95,(1,100));field(f,'export/format',L('格式','Format'),'png',choices=[('PNG','png'),('JPG','jpg')])
        field(f,'animation/quality',L('动画画质','Animation quality'),'auto',choices=[(L('自动','Auto'),'auto'),(L('原像素','Native'),'native'),(L('流畅','Smooth'),'smooth')])
        field(f,'animation/loop',L('循环播放','Loop playback'),True);field(f,'animation/speed',L('默认播放倍速','Default speed'),1.,(.125,8,3))
        f=page(L('恢复','Recovery'));folder=field(f,'recovery/folder',L('恢复副本目录','Recovery folder'),str(window.recovery_root))
        button=QPushButton(L('选择目录…','Choose folder…'));button.clicked.connect(lambda:folder.setText(QFileDialog.getExistingDirectory(self,tr('open'),folder.text()) or folder.text()));f.form.addRow(button)
        f.note(L('新打开的文档使用该目录。已有文档继续使用原恢复目录直到关闭。恢复副本不会覆盖原文件。','New documents use this folder. Existing sessions retain their recovery directory until closed. Recovery never overwrites the original.'))
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.apply);buttons.rejected.connect(self.reject);root.addWidget(buttons)
    def apply(self):
        values={k:v for form in self.forms for k,v in form.values().items()}
        from PySide6.QtWidgets import QMessageBox
        for key in ('annotation/annot_color','annotation/annot_border_color','shape/stroke','shape/color','color/target'):
            if key in values and not QColor(values[key]).isValid():QMessageBox.warning(self,'AsterPDF',L('请输入有效颜色：','Invalid color: ')+values[key]);return
        try:root=Path(values['recovery/folder']);root.mkdir(parents=True,exist_ok=True)
        except OSError as error:QMessageBox.warning(self,'AsterPDF',str(error));return
        changed={key for key,value in values.items() if self.host.settings.value(key,value,type=type(value))!=value}
        for key,value in values.items():self.host.settings.setValue(key,value)
        mapping={'annot_color':'color','annot_width':'width','annot_opacity':'opacity','annot_size':'size','annot_font':'font','annot_end':'end','annot_head_size':'head','annot_text_border':'border'}
        import json
        from .annotation_tools import KINDS
        for kind in KINDS:
            name='annotation/tools/'+kind
            try:preset=json.loads(self.host.settings.value(name,'{}'))
            except (ValueError,TypeError):preset={}
            for source,target in mapping.items():
                if 'annotation/'+source in changed:preset[target]=values['annotation/'+source]
            if 'annotation/annot_dashed' in changed:preset['dash']='dash' if values['annotation/annot_dashed'] else 'solid'
            if preset:self.host.settings.setValue(name,json.dumps(preset))
        self.host.recovery_root=root;self.accept();QTimer.singleShot(0,lambda:apply_preferences(self.host,changed))

def apply_preferences(window,changed=None):
    if changed==set():return
    s=window.settings
    from . import i18n
    if window.dark!=s.value('dark',True,type=bool) or getattr(window,'applied_font_size',None)!=s.value('ui/font_size','medium'):window.dark=s.value('dark',True,type=bool);window.apply_theme()
    if i18n.LANGUAGE!=s.value('language','zh'):window.change_language(s.value('language','zh'))
    window.refresh_recent()
    for tab in window.document_tabs():
        if changed is None or any(key.startswith('annotation') for key in changed):
            annotation_defaults(tab)
            if tab.active_panel=='annotate':tab.show_annotation_properties(tab.canvas.mode)
        tab.configure_chrome();tab.sidebar.setVisible(not s.value('sidebar/hidden',False,type=bool))
        restore=bool(tab.inline_editor)
        if restore:tab.suspend_inline()
        if (tab.canvas.columns,tab.canvas.continuous)!=(s.value('reader/columns',1,type=int),s.value('reader/continuous',True,type=bool)):tab.set_view(s.value('reader/columns',1,type=int),s.value('reader/continuous',True,type=bool))
        if restore:tab.restore_inline()
        tab.show_annotations.setChecked(s.value('annotation/show',True,type=bool));tab.annotation_sort.setCurrentIndex(max(0,tab.annotation_sort.findData(s.value('annotation/sort','position'))))
        tab.loop.setChecked(s.value('animation/loop',True,type=bool))
        for player in tab.players.values():player.speed=s.value('animation/speed',1.,type=float);player.loop=s.value('animation/loop',True,type=bool)
        tab.rebuild_media_controls()
        if tab.night!=s.value('reader/night',False,type=bool):tab.night=s.value('reader/night',False,type=bool);tab.canvas.invalidate(False)
        m=tab.minimap;m.enabled=s.value('minimap/enabled',True,type=bool);m.auto_scale=s.value('minimap/auto_scale',True,type=bool);m.auto_size=s.value('minimap/auto_size',True,type=bool)
        m.percent=(5. if len(tab.canvas.sizes)>20 else 10.) if m.auto_scale else s.value('minimap/scale',10.,type=float);m.corner=s.value('minimap/corner','top-right');m.opacity=s.value('minimap/opacity',80,type=int);m.graphicsEffect().setOpacity(m.opacity/100)
        if not m.auto_size:m.resize(s.value('minimap/width',148,type=int),s.value('minimap/height',370,type=int))
        m.sync();tab.keep_image_ratio.setChecked(s.value('image/ratio',True,type=bool))
        if not tab.inline_editor:
            tab._sync_text=True;tab.object_size.setValue(s.value('text/size',12.,type=float));tab.object_font.setCurrentText(s.value('text/family','Microsoft YaHei'));tab._sync_text=False
        # Refresh open tool defaults without running a PDF mutation.
        pane=getattr(tab,'shape_properties',None)
        if pane:
            pane.inputs['width'].setValue(s.value('shape/width',1.5,type=float));pane.inputs['fill'].setChecked(s.value('shape/fill',False,type=bool))
            for widget,key in [(tab.shape_stroke,'shape/stroke'),(tab.shape_fill,'shape/color')]:widget.color=QColor(s.value(key,widget.color.name()));widget.setText(widget.color.name())
        pane=getattr(tab,'image_properties',None)
        if pane:pane.inputs['ratio'].setChecked(s.value('image/ratio',True,type=bool))
        pane=getattr(tab,'page_properties',None)
        if pane:
            if 'keep' in pane.inputs:pane.inputs['keep'].setChecked(s.value('crop/keep',False,type=bool))
            if 'angle' in pane.inputs:pane.inputs['angle'].setCurrentIndex(pane.inputs['angle'].findData(s.value('page/angle',90,type=int)))
            if 'separate' in pane.inputs:pane.inputs['separate'].setChecked(s.value('page/separate',False,type=bool))
        pane=getattr(tab,'color_properties',None)
        if pane:
            pane.inputs['images'].setChecked(s.value('color/images',True,type=bool));tab.color_target.color=QColor(s.value('color/target','#3366cc'));tab.color_target.setText(tab.color_target.color.name())
        if pane:
            pane.inputs['invert'].setChecked(s.value('color/invert',False,type=bool))
            pane.inputs['tolerance'].setValue(s.value('color/tolerance',8.,type=float))
    if changed is None or 'animation/quality' in changed:window.animation_quality(s.value('animation/quality','auto'))
    window.update_title()
