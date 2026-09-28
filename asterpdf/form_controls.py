"""In-place AcroForm interaction with transactional saves and recovery drafts."""
from PySide6.QtCore import Qt,QObject,QTimer,QEvent,QDate,QRectF
from PySide6.QtGui import QColor,QPen,QFont
from PySide6.QtWidgets import (QWidget,QLineEdit,QPlainTextEdit,QComboBox,QListWidget,QListWidgetItem,
    QAbstractItemView,QToolButton,QHBoxLayout,QCalendarWidget,QMenu,QWidgetAction,QLabel,QApplication,QCheckBox,QRadioButton)
from .core import atomic_json
from .i18n import L
from . import forms


class FormControls(QObject):
    def __init__(self,tab):
        super().__init__(tab);self.tab=tab;self.fields=[];self.pending={};self.revision=-1
        self.loading=False;self.writing=False;self.inflight={};self.editor=None;self.input=None;self.active=None;self.callbacks=[];self.restored=None
        self.notice=QLabel(tab.scroll.viewport());self.notice.setWordWrap(True);self.notice.setStyleSheet('background:#fff1cc;color:#33270d;padding:5px;border:1px solid #b99647;');self.notice.hide()
        self.save_timer=QTimer(self);self.save_timer.setSingleShot(True);self.save_timer.setInterval(900);self.save_timer.timeout.connect(self.flush)
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.tick);self.timer.start()
        self.reload()

    @property
    def dirty(self):return bool(self.pending)

    def enabled(self):
        t=self.tab
        return t.active_panel=='read' and t.canvas.mode=='select' and not t.window.presentation

    def reload(self):
        t=self.tab
        if self.loading or self.writing or t.closed or t.busy:return
        if not t.info.get('has_forms'):self.revision=t.document.revision;self.fields=[];return
        self.loading=True;revision=t.document.revision
        def done(data):
            if t.closed:return
            if revision!=t.document.revision:return
            self.fields=data['fields'];self.revision=revision;t.canvas.update()
            if self.restored is not None:
                self.pending=self.restored;self.restored=None;self.persist();t.window.update_title();self.save_timer.start()
            if data['xfa']:self.message(L('此文档含 XFA，首轮仅支持标准 AcroForm。','This document contains XFA; only standard AcroForm filling is supported.'))
            elif data['signed']:self.message(L('已签名文档的表单保持只读，避免使签名失效。','Forms in signed documents are read-only to preserve signatures.'))
        t.queue.submit(lambda j:forms.scan(t.document.path),done,self.message,lambda:setattr(self,'loading',False))

    def tick(self):
        t=self.tab
        if t.closed:self.timer.stop();self.save_timer.stop();return
        if self.revision!=t.document.revision and not self.dirty:self.reload()
        if self.editor:
            field=self.find(self.active)
            if field:
                rect=t.canvas.page_rect(field['page'],field['rect'])
                self.editor.setGeometry(rect.toAlignedRect());self.editor.setVisible(self.enabled() and not t.canvas.rects[field['page']].isEmpty())
                size=max(9,round((field['size'] or 11)*t.canvas.scale));font=self.input.font()
                if font.pixelSize()!=size:font.setPixelSize(size);self.input.setFont(font)
        self.notice.setMaximumWidth(max(180,t.scroll.viewport().width()-40));self.notice.adjustSize();self.notice.move(12,max(4,getattr(t,'reading_inset',0)+4));self.notice.raise_()

    def find(self,key):return next((f for f in self.fields if f['key']==key),None)

    def media_field(self,field):
        return field['kind']=='unsupported' or any(field['page']==a.page and (field['xref'] in a.hide or field['rect']==a.rect or any(field['rect']==b[0] for b in a.buttons)) for a in self.tab.animations)

    def hit(self,page,point):
        if not self.enabled():return None
        return next((f for f in reversed(self.fields) if f['visible'] and not self.media_field(f) and f['page']==page and QRectF(f['rect'][0],f['rect'][1],f['rect'][2]-f['rect'][0],f['rect'][3]-f['rect'][1]).contains(point)),None)

    def paint(self,painter,page):
        if not self.enabled() or not self.tab.window.settings.value('forms/highlight',True,type=bool):return
        painter.save()
        for f in self.fields:
            if f['page']!=page or not f['visible'] or f['readonly'] or f['kind'] in ('unsupported','signature') or self.media_field(f):continue
            painter.setPen(QPen(QColor('#6099dc'),.8));painter.setBrush(QColor(89,155,239,27));painter.drawRect(self.tab.canvas.page_rect(page,f['rect']))
        painter.restore()

    def message(self,text):
        self.notice.setText(str(text));self.notice.show();self.tick()

    def value(self,field):
        return self.pending.get(field['key'],field['checked'] if field['kind'] in ('check','radio') else field['value'])

    def persist(self):
        path=self.tab.document.folder/'form-draft.json'
        if self.pending:atomic_json(path,{'values':self.pending})
        else:path.unlink(missing_ok=True)

    def change(self,value):
        field=self.find(self.active)
        if not field:return
        baseline=self.inflight.get(field['key'],field['checked'] if field['kind'] in ('check','radio') else field['value'])
        if value==baseline:self.pending.pop(field['key'],None)
        else:self.pending[field['key']]=value
        self.persist();self.tab.window.update_title();self.save_timer.start()

    def dismiss(self,cancel=False):
        if cancel and self.active:
            self.pending.pop(self.active,None);self.persist();self.tab.window.update_title()
        if self.editor:self.editor.hide();self.editor.deleteLater()
        self.editor=self.input=None;self.active=None;self.notice.hide();self.tab.canvas.setFocus()

    def activate(self,field,click=True):
        if not field:return
        if self.tab.busy or self.writing:
            self.flush(lambda:self.activate(self.find(field['key']),click));return
        if self.active==field['key'] and self.editor:self.tick();self.editor.show();self.input.setFocus();return
        if self.dirty:
            self.flush(lambda:self.activate(self.find(field['key']),click));return
        self.dismiss()
        if field['readonly'] or field['kind'] in ('unsupported','signature'):
            self.message(L('此字段只读或属于暂不支持的类型（如签名、按钮脚本）。','This field is read-only or unsupported (such as signatures or scripted buttons).'));return
        self.active=field['key'];t=self.tab;t.goto(field['page']);rect=t.canvas.page_rect(field['page'],field['rect']);t.scroll.ensureVisible(int(rect.center().x()),int(rect.center().y()),20,60)
        kind=field['kind'];value=self.value(field)
        if kind in ('check','radio') and click:
            self.change(not value if kind=='check' else True);self.flush();return
        if kind in ('check','radio'):
            widget=QCheckBox(t.canvas) if kind=='check' else QRadioButton(t.canvas);widget.setChecked(bool(value));widget.toggled.connect(self.change)
        elif kind=='text' and field['multiline']:
            widget=QPlainTextEdit(t.canvas);widget.setPlainText(str(value));widget.textChanged.connect(lambda:self.change(widget.toPlainText()))
        elif kind=='text':
            widget=QLineEdit(t.canvas);widget.setText(str(value));widget.setAlignment((Qt.AlignLeft,Qt.AlignHCenter,Qt.AlignRight)[min(2,field['align'])])
            if field['maxlen']:widget.setMaxLength(field['maxlen'])
            if field['password']:widget.setEchoMode(QLineEdit.Password)
            widget.textEdited.connect(self.change)
        elif kind=='combo':
            widget=QComboBox(t.canvas);widget.setEditable(field['editable']);widget.addItem('','')
            for export,label in field['options']:widget.addItem(label,export)
            index=widget.findData(value);widget.setCurrentIndex(max(0,index))
            if field['editable']:
                if index<0:widget.setEditText(value)
                widget.editTextChanged.connect(lambda text:self.change(next((v for v,label in field['options'] if label==text),text)))
            else:widget.currentIndexChanged.connect(lambda _:self.change(widget.currentData()))
        else:
            widget=QListWidget(t.canvas);widget.setSelectionMode(QAbstractItemView.ExtendedSelection if field['multiple'] else QAbstractItemView.SingleSelection)
            selected=value if isinstance(value,list) else [value]
            for export,label in field['options']:
                item=QListWidgetItem(label);item.setData(Qt.UserRole,export);widget.addItem(item);item.setSelected(export in selected)
            widget.itemSelectionChanged.connect(lambda:self.change([item.data(Qt.UserRole) for item in widget.selectedItems()] if field['multiple'] else next((item.data(Qt.UserRole) for item in widget.selectedItems()),'')))
        self.input=widget;self.editor=widget
        name=field['font'] or 'Arial';family=name.split(',')[0]
        if name.lower() in ('helv','hebo','hebi','heit','heob'):family='Arial'
        font=QFont(family);font.setItalic('italic' in name.lower() or name.lower() in ('hebi','heit','heob'));font.setBold('bold' in name.lower() or name.lower() in ('hebo','hebi'));widget.setFont(font)
        if field['date']:
            frame=QWidget(t.canvas);layout=QHBoxLayout(frame);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0);layout.addWidget(widget)
            button=QToolButton();button.setText('▦');button.setToolTip(L('选择日期','Choose date'));button.clicked.connect(lambda:self.calendar(button,field));layout.addWidget(button);self.editor=frame
            widget.setPlaceholderText(field['date'])
        color=QColor.fromRgbF(*forms.rgb(field['color'])).name()
        self.editor.setStyleSheet('QLineEdit,QPlainTextEdit,QComboBox,QListWidget {background:#f7fbff;color:'+color+';border:1px solid #3b87dc;selection-background-color:#a9c9ff;selection-color:#162536;}')
        for child in [widget]+widget.findChildren(QWidget):child.installEventFilter(self)
        hints=[]
        if field['required']:hints.append(L('必填','Required'))
        if field['date']:hints.append(L('日期格式：','Date format: ')+field['date'])
        if field['rich']:hints.append(L('修改后以纯文本保存','Edits are saved as plain text'))
        if field['scripts']:hints.append(L('此字段的自定义脚本不执行，请自行核对计算或验证结果','Custom scripts are not executed; check calculations and validation manually'))
        widget.setToolTip(field['label']+'\n'+' · '.join(hints))
        if hints:self.message(' · '.join(hints))
        self.tick();self.editor.show();self.editor.raise_();widget.setFocus()

    def calendar(self,button,field):
        menu=QMenu(self.editor);calendar=QCalendarWidget();calendar.setGridVisible(True)
        date=QDate.fromString(self.input.text(),field['date'])
        if date.isValid():calendar.setSelectedDate(date)
        action=QWidgetAction(menu);action.setDefaultWidget(calendar);menu.addAction(action)
        def picked(date):self.input.setText(date.toString(field['date']));self.change(self.input.text());menu.close();self.input.setFocus()
        calendar.clicked.connect(picked);menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def eventFilter(self,obj,event):
        if event.type()==QEvent.KeyPress:
            if event.key() in (Qt.Key_Tab,Qt.Key_Backtab):
                self.advance(-1 if event.key()==Qt.Key_Backtab or event.modifiers()&Qt.ShiftModifier else 1);return True
            if event.key()==Qt.Key_Escape:self.dismiss(cancel=True);return True
            if event.key() in (Qt.Key_Return,Qt.Key_Enter) and isinstance(self.input,QLineEdit):self.flush(self.dismiss);return True
        if event.type()==QEvent.FocusOut and self.dirty:self.save_timer.start(100)
        return super().eventFilter(obj,event)

    def advance(self,direction=1):
        eligible=[f for f in self.fields if f['visible'] and not f['readonly'] and f['kind'] not in ('unsupported','signature') and not self.media_field(f)]
        if not eligible:return
        index=next((i for i,f in enumerate(eligible) if f['key']==self.active),-1 if direction>0 else 0)
        target=eligible[(index+direction)%len(eligible)];self.flush(lambda:self.activate(self.find(target['key']),click=False))

    def flush(self,after=None):
        t=self.tab
        if after:self.callbacks.append(after)
        if self.writing:return
        if t.busy:QTimer.singleShot(100,self.flush);return
        if not self.dirty:
            callbacks,self.callbacks=self.callbacks,[]
            for callback in callbacks:callback()
            return
        self.save_timer.stop();batch=dict(self.pending);self.inflight=batch;self.writing=True
        def work(job):
            pages=forms.fill(t.document,batch)
            return pages,forms.scan(t.document.path)
        def done(result):
            pages,data=result;self.fields=data['fields'];self.revision=t.document.revision
            for key,value in batch.items():
                if self.pending.get(key)==value:self.pending.pop(key,None)
            self.persist()
            for page in pages:t.canvas.invalidate_page(page)
            t.minimap.release();t.window.update_title()
            QTimer.singleShot(0,finish)
        def finish():
            self.writing=False;self.inflight={}
            if self.dirty:self.flush()
            else:
                callbacks,self.callbacks=self.callbacks,[]
                for callback in callbacks:callback()
        def failed(message):
            self.writing=False;self.inflight={};self.callbacks=[];t.window._close_pending=False;t.window._closing_all=False;self.message(message)
        t.run(L('填写表单','Fill form'),work,done,editing=True,local_edit=True,failure=failed)
