"""Scope-aware recoloring side panel; presets are independent of documents."""
import json
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QPixmap,QIcon
from PySide6.QtWidgets import QPushButton,QListWidget,QListWidgetItem,QLabel,QHBoxLayout,QWidget,QComboBox,QCheckBox,QSizePolicy,QAbstractItemView,QButtonGroup
from .i18n import L,tr
from .core import pages_from_text
from . import colors


def build(tab):
    pane=tab.property_pane(tr('colors'));tab.color_properties=pane;tab.edit_tool='colors';tab.set_mode('objects')
    pane.form.setVerticalSpacing(5)
    settings=tab.window.settings
    pane.choice('scope',L('范围','Scope'),[(L('本页','Current page'),'page'),(L('全部页面','All pages'),'all'),(L('指定页面','Page range'),'range'),(L('选定区域','Selected region'),'region')])
    border=QCheckBox(L('展示换色区域边界','Show recolor boundary'));border.setChecked(True);pane.inputs['boundary']=border;pane.form.addRow(border)
    pane.text('pages',L('页码','Pages'),str(tab.canvas.page+1))
    pane.form.addRow(QLabel(L('源颜色','Source colors')))
    from .color_grid import ColorGrid
    source=ColorGrid();pane.inputs['source']=source;pane.form.addRow(source)
    chosen=QLabel();source.colorChanged.connect(lambda rgb:chosen.setText(QColor.fromRgbF(*rgb).name() if rgb else ''));pane.form.addRow(chosen)
    target=tab.color_button(pane,L('目标颜色','Target color'),QColor(settings.value('color/target','#3366cc')));tab.color_target=target
    pane.number('tolerance',L('容差（%）','Tolerance (%)'),settings.value('color/tolerance',8.,type=float),0,100,1)
    pane.check('invert',L('反转颜色','Invert colors'),settings.value('color/invert',False,type=bool))
    images=QCheckBox(L('同时修改图片中的颜色','Also recolor image pixels'));images.setChecked(settings.value('color/images',True,type=bool));pane.inputs['images']=images;pane.form.addRow(images)
    images.setToolTip(L('勾选后，照片、扫描图等内嵌图片的像素也参与换色；取消后只修改文字和矢量图形。仍遵循所选页面或区域及颜色容差。','Include pixels in embedded photos and scanned images. When disabled, recolor only text and vector graphics. Page/region scope and color tolerance still apply.'))
    status=QLabel();status.setWordWrap(True);pane.form.addRow(status)
    pairs=[];listing=QListWidget();listing.setFixedHeight(90);listing.setSelectionMode(QAbstractItemView.ExtendedSelection);pane.pair_list=listing;pane.form.addRow(QLabel(L('换色对 · 从上到下依次换色','Pairs · apply in listed order')));pane.form.addRow(listing)
    def pair_values():
        source=pane.inputs['source'].currentData()
        return [source,target.color.getRgbF()[:3]] if source is not None else None
    def show_pairs():
        listing.clear()
        for source,dest in pairs:
            a,b=QColor.fromRgbF(*source),QColor.fromRgbF(*dest)
            item=QListWidgetItem();item.setToolTip(a.name()+' → '+b.name());item.setData(Qt.AccessibleTextRole,item.toolTip());listing.addItem(item)
            row=QLabel();row.setAttribute(Qt.WA_TransparentForMouseEvents)
            def chip(c):
                background='#172131' if c.lightnessF()>.48 else '#ffffff'
                return f'<span style="color:{c.name()};background-color:{background};">&#9632; {c.name()}</span>'
            row.setText(chip(a)+' &nbsp;→&nbsp; '+chip(b));row.setMargin(5)
            item.setSizeHint(row.sizeHint());listing.setItemWidget(item,row)
    def add():
        pair=pair_values()
        if pair:pairs.append(pair);show_pairs()
    def update():
        row=listing.currentRow();pair=pair_values()
        if row>=0 and pair:pairs[row]=pair;show_pairs();listing.setCurrentRow(row)
    def remove():
        for row in sorted((listing.row(i) for i in listing.selectedItems()),reverse=True):pairs.pop(row)
        show_pairs()
    def set_source(rgb):
        combo=pane.inputs['source'];color=QColor.fromRgbF(*rgb);pix=QPixmap(18,18);pix.fill(color)
        combo.set_color(rgb)
    tab.set_color_source=set_source
    def select_pair(row):
        if 0<=row<len(pairs):
            source,dest=pairs[row];set_source(source);target.color=QColor.fromRgbF(*dest);target.setText(target.color.name())
    listing.currentRowChanged.connect(select_pair)
    def buttons(items,footer=False):
        host=QWidget();layout=QHBoxLayout(host);layout.setContentsMargins(0,0,0,0)
        for label,callback in items:
            button=QPushButton(label);button.clicked.connect(callback);layout.addWidget(button)
        if footer:tab.property_container.layout().addWidget(host)
        else:pane.form.addRow(host)
    buttons([(L('添加对','Add pair'),add),(L('更新对','Update'),update),(L('移除','Remove'),remove)])
    def region_mode():pane.inputs['scope'].setCurrentIndex(3);tab.set_mode('region')
    def scope_changed():
        region=pane.inputs['scope'].currentData()=='region'
        border.setVisible(region);tab.canvas.show_color_boundary=region and border.isChecked()
        if not region:tab.canvas.region=None;tab.canvas.color_boundary=None
        tab.set_mode('region' if region else 'objects');tab.canvas.update()
    pane.inputs['scope'].currentIndexChanged.connect(scope_changed)
    border.toggled.connect(lambda value:(setattr(tab.canvas,'show_color_boundary',value),tab.canvas.update()))
    if tab.canvas.region:pane.inputs['scope'].setCurrentIndex(3)
    scope_changed()
    pane.text('scheme_name',L('方案名称','Scheme name'),'')
    saved=pane.choice('scheme',L('已保存方案','Saved schemes'),[])
    def schemes():
        try:return json.loads(settings.value('color/schemes','{}'))
        except (ValueError,TypeError):return {}
    def load_names():
        saved.clear()
        for name in schemes():saved.addItem(name,name)
    def save_scheme():
        name=pane.inputs['scheme_name'].text().strip()
        if not name:status.setText(L('请填写方案名称。','Enter a scheme name.'));return
        value=pane.values();data=schemes();data[name]={'pairs':pairs or ([pair_values()] if pair_values() else []),'invert':value['invert'],'images':value['images'],'tolerance':value['tolerance']}
        settings.setValue('color/schemes',json.dumps(data));load_names();saved.setCurrentText(name)
    def load_scheme():
        value=schemes().get(saved.currentData())
        if not value:return
        pairs[:]=value['pairs'];show_pairs();pane.inputs['scheme_name'].setText(saved.currentText())
        for key in ('invert','images'):pane.inputs[key].setChecked(value[key])
        pane.inputs['tolerance'].setValue(value['tolerance'])
    def delete_scheme():
        data=schemes();data.pop(saved.currentData(),None);settings.setValue('color/schemes',json.dumps(data));load_names()
    buttons([(tr('save'),save_scheme),(L('载入','Load'),load_scheme),(L('删除','Delete'),delete_scheme)]);load_names()
    def scope():
        value=pane.values();page=tab.canvas.page
        indices=pages_from_text('all' if value['scope']=='all' else value['pages'],tab.info['count']) if value['scope'] in ('all','range') else [page]
        region=tab.canvas.region or getattr(tab.canvas,'color_boundary',None)
        if value['scope']=='region':
            if not region or region[0]!=page:raise ValueError(L('请框选换色区域。','Select a recolor region.'))
            return indices,region[1]
        return indices,None
    state={'signature':None,'pending':False}
    def refresh_palette():
        if tab.closed or getattr(tab,'color_properties',None) is not pane:timer.stop();return
        if not pane.isVisible() or state['pending'] or tab.busy:return
        try:indices,region=scope()
        except ValueError as error:pane.inputs['source'].clear();state['signature']=None;status.setText(str(error));return
        tolerance=pane.inputs['tolerance'].value()/100
        signature=(tab.document.revision,tuple(indices),tuple(region) if region else None,tolerance)
        if signature==state['signature']:return
        state['pending']=True;state['signature']=signature
        def done(data):
            if tab.closed or getattr(tab,'color_properties',None) is not pane or tab.document.revision!=signature[0]:return
            combo=pane.inputs['source'];old=combo.currentData();combo.clear()
            for rgb,count in data['colors'].most_common():
                color=QColor.fromRgbF(*rgb);pix=QPixmap(18,18);pix.fill(color);combo.addItem(QIcon(pix),color.name(),rgb)
            if old is not None and any(tuple(old)==tuple(rgb) for rgb in data['colors']):set_source(old)
            status.setText(L(f'范围内 {len(indices)} 页 · {data["images"]} 个图片资源',f'{len(indices)} pages in scope · {data["images"]} image resources'))
        tab.queue.submit(lambda j:colors.inventory(tab.document,indices,region,tolerance),done,lambda e:status.setText(e) if getattr(tab,'color_properties',None) is pane and not tab.closed else None,lambda:state.update(pending=False),priority=-1)
    timer=QTimer(pane);timer.setInterval(350);timer.timeout.connect(refresh_palette);timer.start();QTimer.singleShot(0,refresh_palette)
    def apply():
        try:indices,region=scope()
        except ValueError as error:status.setText(str(error));return
        values=pane.values();selected=[pair for n,pair in enumerate(pairs) if apply_all.isChecked() or listing.item(n).isSelected()]
        if not values['invert'] and not selected:status.setText(L('需至少添加一对','Add at least one pair'));return
        for key in ('images','invert','tolerance'):settings.setValue('color/'+key,values[key])
        boundary=(indices[0],tuple(region)) if region else None
        def done(_):
            if getattr(tab,'color_properties',None) is not pane:return
            tab.canvas.color_boundary=boundary;tab.canvas.show_color_boundary=border.isChecked();tab.canvas.update();state['signature']=None
        tab.run(tr('colors'),lambda j:colors.replace(tab.document,indices,invert=values['invert'],images=values['images'],tolerance=values['tolerance']/100,region=region,progress=j.signals.progress.emit,pairs=selected),done,editing=True,local_edit=len(indices)==1)
    options=QWidget();layout=QHBoxLayout(options);layout.setContentsMargins(0,0,0,0);layout.setSpacing(5)
    apply_all=QCheckBox(L('对所有对生效','All pairs'));apply_selected=QCheckBox(L('对已选对生效','Selected pairs'));apply_all.setChecked(True)
    group=QButtonGroup(pane);group.addButton(apply_all);group.addButton(apply_selected);layout.addWidget(apply_all);layout.addWidget(apply_selected)
    tab.property_container.layout().addWidget(options);pane.apply_all_pairs=apply_all;pane.apply_selected_pairs=apply_selected
    buttons([(tr('apply'),apply),(tr('cancel'),tab.close_properties)],footer=True)
    for label in pane.findChildren(QLabel):
        if label.wordWrap():label.setMinimumHeight(label.heightForWidth(180)+8);label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Minimum)
    pane.apply_colors=apply;pane.add_pair=add;pane.save_scheme=save_scheme;pane.load_scheme=load_scheme;pane.pairs=pairs
