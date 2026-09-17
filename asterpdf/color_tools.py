"""Scope-aware recoloring side panel; presets are independent of documents."""
import json
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QPixmap,QIcon
from PySide6.QtWidgets import QPushButton,QListWidget,QListWidgetItem,QLabel,QHBoxLayout,QWidget,QComboBox,QCheckBox,QSizePolicy
from .i18n import L,tr
from .core import pages_from_text
from . import colors


def build(tab):
    pane=tab.property_pane(tr('colors'));tab.color_properties=pane;tab.edit_tool='colors';tab.set_mode('region')
    settings=tab.window.settings
    pane.choice('scope',L('范围','Scope'),[(L('本页','Current page'),'page'),(L('全部页面','All pages'),'all'),(L('指定页面','Page range'),'range'),(L('选定区域','Selected region'),'region')])
    pane.text('pages',L('页码','Pages'),str(tab.canvas.page+1))
    pane.form.addRow(QLabel(L('源颜色','Source colors')))
    from .color_grid import ColorGrid
    source=ColorGrid();pane.inputs['source']=source;pane.form.addRow(source)
    chosen=QLabel();source.colorChanged.connect(lambda rgb:chosen.setText(QColor.fromRgbF(*rgb).name() if rgb else ''));pane.form.addRow(chosen)
    target=tab.color_button(pane,L('目标颜色','Target color'),QColor(settings.value('color/target','#3366cc')));tab.color_target=target
    pane.number('tolerance',L('容差（%）','Tolerance (%)'),settings.value('color/tolerance',8.,type=float),0,100,1)
    pane.check('invert',L('反转颜色','Invert colors'),settings.value('color/invert',False,type=bool))
    images=QCheckBox(L('同时修改栅格图片','Also recolor raster images'));images.setChecked(settings.value('color/images',True,type=bool));pane.inputs['images']=images;pane.form.addRow(images)
    status=QLabel();status.setWordWrap(True);pane.form.addRow(status)
    pairs=[];listing=QListWidget();listing.setMaximumHeight(115);pane.form.addRow(QLabel(L('换色对 · 按顺序匹配一次','Pairs · first match wins')));pane.form.addRow(listing)
    def pair_values():
        source=pane.inputs['source'].currentData()
        return [source,target.color.getRgbF()[:3]] if source is not None else None
    def show_pairs():
        listing.clear()
        for source,dest in pairs:listing.addItem(QColor.fromRgbF(*source).name()+' → '+QColor.fromRgbF(*dest).name())
    def add():
        pair=pair_values()
        if pair:pairs.append(pair);show_pairs()
    def update():
        row=listing.currentRow();pair=pair_values()
        if row>=0 and pair:pairs[row]=pair;show_pairs();listing.setCurrentRow(row)
    def remove():
        row=listing.currentRow()
        if row>=0:pairs.pop(row);show_pairs()
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
    pane.note(L('列表为空时应用当前源色与目标色；多对同时匹配原颜色，不级联替换。','With an empty list, apply the current pair. Multiple pairs match original colors without cascading.'))
    def region_mode():pane.inputs['scope'].setCurrentIndex(3);tab.set_mode('region')
    buttons([(L('框选区域','Select region'),region_mode),(L('取源色','Pick source'),lambda:tab.set_mode('color_pick'))])
    border=QCheckBox(L('展示换色区域边界','Show recolor boundary'));border.setChecked(True);pane.inputs['boundary']=border;pane.form.addRow(border)
    border.toggled.connect(lambda value:(setattr(tab.canvas,'show_color_boundary',value),tab.canvas.update()))
    if tab.canvas.region:pane.inputs['scope'].setCurrentIndex(3)
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
    pane.note(L('源色按估计可见面积排序，渐变聚合，最多 32 色；可取色并调容差。渐变矢量、图案、批注和动画帧暂不换色。','Sources are sorted by estimated visible area, clustered to at most 32 colors. Use the picker and tolerance for other shades. Vector gradients, patterns, annotations and animation frames are unchanged.'))
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
        except ValueError as error:status.setText(str(error));return
        tolerance=pane.inputs['tolerance'].value()/100
        signature=(tab.document.revision,tuple(indices),tuple(region) if region else None,tolerance)
        if signature==state['signature']:return
        state['pending']=True;state['signature']=signature
        def done(data):
            if tab.closed or getattr(tab,'color_properties',None) is not pane or tab.document.revision!=signature[0]:return
            combo=pane.inputs['source'];old=combo.currentData();combo.clear()
            for rgb,count in data['colors'].most_common():
                color=QColor.fromRgbF(*rgb);pix=QPixmap(18,18);pix.fill(color);combo.addItem(QIcon(pix),color.name(),rgb)
            if old is not None:set_source(old)
            status.setText(L(f'范围内 {len(indices)} 页 · {data["images"]} 个图片资源',f'{len(indices)} pages in scope · {data["images"]} image resources'))
        tab.queue.submit(lambda j:colors.inventory(tab.document,indices,region,tolerance),done,lambda e:status.setText(e) if getattr(tab,'color_properties',None) is pane and not tab.closed else None,lambda:state.update(pending=False),priority=-1)
    timer=QTimer(pane);timer.setInterval(350);timer.timeout.connect(refresh_palette);timer.start();QTimer.singleShot(0,refresh_palette)
    def apply():
        try:indices,region=scope()
        except ValueError as error:status.setText(str(error));return
        values=pane.values();selected=list(pairs or ([pair_values()] if pair_values() else []))
        if not values['invert'] and not selected:status.setText(L('请选择源颜色。','Choose a source color.'));return
        for key in ('images','invert','tolerance'):settings.setValue('color/'+key,values[key])
        boundary=(indices[0],tuple(region)) if region else None
        def done(_):
            tab.canvas.color_boundary=boundary;tab.canvas.show_color_boundary=border.isChecked();tab.canvas.update();state['signature']=None
        tab.run(tr('colors'),lambda j:colors.replace(tab.document,indices,invert=values['invert'],images=values['images'],tolerance=values['tolerance']/100,region=region,progress=j.signals.progress.emit,pairs=selected),done,editing=True,local_edit=len(indices)==1)
    buttons([(tr('apply'),apply),(tr('cancel'),tab.close_properties)],footer=True)
    for label in pane.findChildren(QLabel):
        if label.wordWrap():label.setMinimumHeight(label.heightForWidth(180)+8);label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Minimum)
    pane.apply_colors=apply;pane.add_pair=add;pane.save_scheme=save_scheme;pane.load_scheme=load_scheme;pane.pairs=pairs
