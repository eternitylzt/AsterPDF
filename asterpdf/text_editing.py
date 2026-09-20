"""Selection-based rich text editing with safe draft suspension."""
from PySide6.QtCore import Qt,Signal,QTimer,QPointF,QRectF
from PySide6.QtGui import QFont,QFontDatabase,QTextCharFormat,QTextCursor,QColor,QFontMetricsF,QRawFont,QPainter
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QDoubleSpinBox,
    QPushButton,QToolButton,QTextEdit,QColorDialog,QMessageBox,QDialog)
from .i18n import L,tr
from .fonts import matched_family,font_bytes
from .core import Unsupported,ENGINE_LOCK
from . import objects,text_patch

FAMILY=QTextCharFormat.UserProperty+1
SIZE=QTextCharFormat.UserProperty+2

class InlineEditor(QTextEdit):
    def createMimeDataFromSelection(self):
        import json,base64
        mime=super().createMimeDataFromSelection();cursor=self.textCursor();start,end=cursor.selectionStart(),cursor.selectionEnd();runs=[];fonts={}
        block=self.document().begin()
        while block.isValid():
            if runs and start<=block.position()<end:runs.append({'text':'\n'})
            it=block.begin()
            while not it.atEnd():
                fragment=it.fragment()
                if fragment.isValid():
                    a=max(start,fragment.position());b=min(end,fragment.position()+fragment.length())
                    if a<b:
                        fmt=fragment.charFormat();raw=fragment.text().encode('utf-16-le');text=raw[(a-fragment.position())*2:(b-fragment.position())*2].decode('utf-16-le')
                        family=fmt.property(FAMILY) or fmt.font().family();bold=fmt.fontWeight()>=QFont.Bold;italic=fmt.fontItalic()
                        runs.append(dict(text=text,family=family,size=float(fmt.property(SIZE) or self.owner.inline_object.size),bold=bold,italic=italic,color=fmt.foreground().color().getRgbF()[:3]))
                        if family not in fonts:
                            found=embedded_font(self.owner.document,self.owner.inline_page,family,text,bold,italic,self.owner.inline_object)
                            if found:fonts[family]=base64.b64encode(found[0]).decode('ascii')
                it+=1
            block=block.next()
        mime.setData('application/x-asterpdf-text',json.dumps({'runs':runs,'fonts':fonts}).encode('utf-8'));return mime

    def insertFromMimeData(self,mime):
        if not mime.hasFormat('application/x-asterpdf-text'):super().insertFromMimeData(mime);return
        import json,base64
        data=json.loads(bytes(mime.data('application/x-asterpdf-text')));self.owner.clipboard_fonts={k:base64.b64decode(v) for k,v in data.get('fonts',{}).items()}
        cursor=self.textCursor();cursor.beginEditBlock()
        for run in data['runs']:
            if 'family' in run:cursor.insertText(run['text'],self.owner.format_for(run['family'],run['size'],run['color'],run['bold'],run['italic']))
            else:cursor.insertText(run['text'])
        cursor.endEditBlock();self.setTextCursor(cursor)

    def inputMethodEvent(self,event):
        self.preedit_text=event.preeditString();super().inputMethodEvent(event);self.viewport().update()

    def inputMethodQuery(self,query):
        if query==Qt.ImCursorRectangle and hasattr(self,'owner') and hasattr(self.owner,'inline_original_runs'):
            boxes,total=self.glyph_rects();position=self.textCursor().position()
            if boxes:
                box=QRectF(boxes.get(position) or boxes[max(boxes)])
                if position not in boxes:box.moveLeft(box.right())
                box.setWidth(1);box.translate(self.viewport().pos());return box
        return super().inputMethodQuery(query)

    def glyph_rects(self):
        from .text_mapping import glyph_mapping
        tab=self.owner;glyphs=getattr(self,'preview_glyphs',tab.inline_object.details.get('glyphs',[]))
        text=getattr(self,'preview_text',self.original_text)
        key=(id(glyphs),text,self.x(),self.y(),self.viewport().x(),self.viewport().y(),tab.canvas.scale,tab.canvas.rects[tab.inline_page].x(),tab.canvas.rects[tab.inline_page].y())
        if getattr(self,'_glyph_key',None)==key:return self._glyph_boxes
        offsets=[0]
        for ch in text:offsets.append(offsets[-1]+len(ch.encode('utf-16-le'))//2)
        mapping=glyph_mapping(text,''.join(chr(g[0]) for g in glyphs),strict=False) or {}
        origin=QPointF(self.pos()+self.viewport().pos());boxes={}
        for position,index in mapping.items():
            import pymupdf as fitz
            visual=tuple(fitz.Rect(glyphs[index][3])*fitz.Matrix(tab.inline_object.details.get('page_rotation_matrix',(1,0,0,1,0,0))))
            box=tab.canvas.page_rect(tab.inline_page,visual);box.translate(-origin);boxes[offsets[position]]=box
        self._glyph_key=key;self._glyph_boxes=(boxes,offsets[-1]);return self._glyph_boxes

    def cursor_for_point(self,point):
        boxes,total=self.glyph_rects()
        if not boxes:return self.cursorForPosition(point.toPoint())
        index,box=min(boxes.items(),key=lambda item:abs(item[1].center().y()-point.y())*5+abs(item[1].center().x()-point.x()))
        positions=sorted(boxes);pos=index if point.x()<box.center().x() else next((p for p in positions if p>index),total)
        cursor=self.textCursor();cursor.setPosition(min(pos,self.document().characterCount()-1));return cursor

    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:super().mousePressEvent(event);return
        cursor=self.cursor_for_point(event.position());self._anchor=self.textCursor().anchor() if event.modifiers()&Qt.ShiftModifier else cursor.position()
        if event.modifiers()&Qt.ShiftModifier:
            pos=cursor.position();cursor.setPosition(self._anchor);cursor.setPosition(pos,QTextCursor.KeepAnchor)
        self.setTextCursor(cursor);self.setFocus();event.accept()

    def mouseMoveEvent(self,event):
        if event.buttons()&Qt.LeftButton and hasattr(self,'_anchor'):
            cursor=self.cursor_for_point(event.position());pos=cursor.position();cursor.setPosition(self._anchor);cursor.setPosition(pos,QTextCursor.KeepAnchor);self.setTextCursor(cursor);event.accept()
        else:super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self,event):
        cursor=self.cursor_for_point(event.position());cursor.select(QTextCursor.WordUnderCursor);self.setTextCursor(cursor);self._anchor=cursor.anchor();event.accept()

    def paintEvent(self,event):
        # Both caret and draft are measured by the PDF engine, not a substitute
        # Qt font. QTextDocument remains responsible for clipboard and undo.
        painter=QPainter(self.viewport());cursor=self.textCursor();boxes,total=self.glyph_rects()
        if getattr(self,'preview_image',None) is not None:
            x,y,w,h=self.preview_bounds;box=self.owner.canvas.page_rect(self.owner.inline_page,(x,y,x+w,y+h));box.translate(-QPointF(self.pos()+self.viewport().pos()))
            painter.drawImage(box,self.preview_image)
        if cursor.hasSelection():
            for pos,box in boxes.items():
                if cursor.selectionStart()<=pos<cursor.selectionEnd():painter.fillRect(box,QColor(75,130,230,85))
        elif self.hasFocus():
            position=cursor.position();box=boxes.get(position)
            if box is None and boxes:
                box=QRectF(boxes[max(p for p in boxes if p<=position)] if any(p<=position for p in boxes) else next(iter(boxes.values())));box.moveLeft(box.right())
            if box is None:box=QRectF(self.cursorRect(cursor))
            painter.fillRect(QRectF(box.left(),box.top(),1.2,box.height()),QColor('#6742b8'))
            if getattr(self,'preedit_text',''):
                painter.setFont(self.textCursor().charFormat().font());painter.setPen(QColor('#243249'))
                painter.drawText(QPointF(box.left(),box.bottom()-2),self.preedit_text)
        painter.end()


class FontPicker(QComboBox):
    currentFontChanged=Signal(QFont)
    def __init__(self):
        super().__init__();self.setEditable(True);self.setProperty('font_selector',True);self.addItems(QFontDatabase.families())
        self.activated.connect(lambda _:self.currentFontChanged.emit(QFont(self.currentText())))
        self.lineEdit().editingFinished.connect(lambda:self.currentFontChanged.emit(QFont(self.currentText())))
    def currentFont(self):return QFont(self.currentText())
    def setCurrentFont(self,font):
        previous=self.currentText();self.setCurrentText(font.family())
        if previous!=font.family():self.currentFontChanged.emit(font)


def resolve_font(family,text,bold=False,italic=False):
    import pymupdf as fitz
    installed=QFontDatabase.families();match,exact=matched_family(family)
    choices=[family,match,'Arial','Times New Roman','Microsoft YaHei','SimSun','Cambria Math','Segoe UI Symbol','Noto Sans','Noto Sans CJK SC','DejaVu Sans','PingFang SC']
    for candidate in dict.fromkeys(choices):
        if candidate not in installed:continue
        qfont=QFont(candidate);qfont.setBold(bold);qfont.setItalic(italic);raw=QRawFont.fromFont(qfont)
        if any(not raw.supportsCharacter(ord(c)) for c in text if not c.isspace()):continue
        try:
            data=font_bytes(candidate,bold,italic)
            with ENGINE_LOCK:
                pdf_font=fitz.Font(fontbuffer=data)
                if all(pdf_font.has_glyph(ord(c)) for c in text if not c.isspace()):return data,candidate
        except (ValueError,RuntimeError):continue
    raise Unsupported(L('当前字体无法覆盖输入字形或不允许嵌入。草稿已保留；可撤销、取消，或选择 / 下载其它字体。','No suitable embeddable font covers these characters. The draft is retained: undo, cancel, or choose/download another font.'))


def embedded_font(document,page,family,text,bold,italic,obj):
    """Reuse an embedded face only when it covers the new input and same style."""
    import pymupdf as fitz
    import re
    def normalized(name):
        return re.sub(r'(regular|psmt|mt)$','',re.sub('[^a-z0-9]','',name.split('+')[-1].lower()))
    spans=obj.details.get('spans',[])
    if not any(s['font']==family for s in spans) and not any(style and style[0]==family for _,style in obj.details.get('edit_styles',[])):return None
    with ENGINE_LOCK,fitz.open(document.path) as pdf:
        for xref,ext,kind,base,*_ in pdf[page].get_fonts():
            if normalized(base)!=normalized(family):continue
            try:
                data=pdf.extract_font(xref)[3]
                if not data:
                    try:data=fitz.Font(base).buffer
                    except (ValueError,RuntimeError):continue
                font=fitz.Font(fontbuffer=data)
                if (font.is_bold and not bold) or (font.is_italic and not italic):continue
                if all(font.has_glyph(ord(c)) for c in text if not c.isspace()):return data,family
            except (RuntimeError,ValueError):continue
    return None


class TextEditingMixin:
    def build_text_properties(self):
        self._sync_text=False;self.suspended_inline=None
        panel=QWidget();panel.setMinimumWidth(205);panel.setMaximumWidth(275);root=QVBoxLayout(panel);root.setContentsMargins(10,8,10,8)
        title=QLabel(tr('text_ops'));root.addWidget(title)
        self.text_format_group=QWidget();form=QFormLayout(self.text_format_group);form.setContentsMargins(0,0,0,0)
        self.object_font=FontPicker();self.object_font.setCurrentText(self.window.settings.value('text/family','Microsoft YaHei'));self.object_font.setMinimumWidth(125);self.object_font.setMaximumWidth(235);form.addRow(L('字体','Font'),self.object_font)
        self.object_size=QDoubleSpinBox();self.object_size.setKeyboardTracking(False);self.object_size.setRange(1,300);self.object_size.setDecimals(1);self.object_size.setValue(self.window.settings.value('text/size',12.,type=float));form.addRow(L('字号','Size'),self.object_size)
        row=QHBoxLayout();self.text_bold=QToolButton();self.text_bold.setText('B');self.text_bold.setCheckable(True);self.text_bold.setToolTip(L('加粗','Bold'));self.text_bold.setStyleSheet('font-weight:bold')
        self.text_italic=QToolButton();self.text_italic.setText('I');self.text_italic.setCheckable(True);self.text_italic.setToolTip(L('倾斜','Italic'));self.text_italic.setStyleSheet('font-style:italic')
        self.text_color=QPushButton(L('颜色','Color'));self.text_color.clicked.connect(self.choose_text_color)
        for button in (self.text_bold,self.text_italic,self.text_color):row.addWidget(button)
        form.addRow(row)
        self.font_notice=QLabel();self.font_notice.setWordWrap(True);form.addRow(self.font_notice)
        online=QPushButton(L('在线字体库…','Online fonts…'));online.clicked.connect(self.find_fonts);form.addRow(online)
        self.box_controls=QWidget();boxform=QFormLayout(self.box_controls);boxform.setContentsMargins(0,0,0,0)
        self.box_width=QDoubleSpinBox();self.box_width.setRange(2,10000);self.box_width.setSuffix(' pt');self.box_width.setKeyboardTracking(False);boxform.addRow(L('宽度','Width'),self.box_width)
        self.box_angle=QDoubleSpinBox();self.box_angle.setRange(-180,180);self.box_angle.setSuffix('°');self.box_angle.setKeyboardTracking(False);boxform.addRow(L('旋转','Rotation'),self.box_angle)
        self.box_width.valueChanged.connect(lambda v:self.change_box(width=v));self.box_angle.valueChanged.connect(lambda v:self.change_box(angle=v));self.box_controls.hide()
        root.addWidget(self.text_format_group);root.addWidget(self.box_controls)
        clipboard=QHBoxLayout();root.addLayout(clipboard)
        for label,method in [(L('复制','Copy'),'copy'),(L('粘贴','Paste'),'paste')]:
            button=QPushButton(label);button.setFocusPolicy(Qt.NoFocus);button.clicked.connect(lambda checked=False,m=method:getattr(self.inline_editor,m)() if self.inline_editor else None);clipboard.addWidget(button)
        self.add_layer_controls(root)
        buttons=QHBoxLayout();root.addLayout(buttons)
        for name,callback in [(tr('apply'),lambda:self.commit_inline()),(tr('cancel'),self.exit_text_tools)]:
            button=QPushButton(name);button.clicked.connect(callback);buttons.addWidget(button)
        add=QPushButton(L('插入文本框','Insert text box'));add.setCheckable(True);self.add_text_button=add;add.clicked.connect(lambda:self.set_mode('objects' if self.canvas.mode=='add_text' else 'add_text'));root.addWidget(add)
        self.draft_notice=QLabel(L('双击页面上的文字块后，选择文字以调整样式。','Double-click a text block, then select characters to format.'));self.draft_notice.setWordWrap(True);root.addWidget(self.draft_notice);root.addStretch()
        from .chrome import OffsetPanel
        self.text_format_group.setEnabled(False);self.text_properties=panel;self.text_container=OffsetPanel(panel);self.splitter.insertWidget(1,self.text_container);panel.hide();self.text_container.hide()
        self.object_font.currentFontChanged.connect(lambda _:self.format_selection('family'))
        self.object_size.valueChanged.connect(lambda _:self.format_selection('size'))
        self.text_bold.toggled.connect(lambda _:self.format_selection('bold'));self.text_italic.toggled.connect(lambda _:self.format_selection('italic'))

    def show_text_properties(self):
        if hasattr(self,'property_container'):self.property_container.hide()
        self.text_container.show();self.text_properties.show()
        index=self.splitter.indexOf(self.text_container);self.splitter.setCollapsible(index,False)
        sizes=self.splitter.sizes();sizes[index]=max(225,sizes[index]);sizes[self.splitter.indexOf(self.document_views)]=max(300,self.splitter.width()-sum(s for i,s in enumerate(sizes) if i!=self.splitter.indexOf(self.document_views)))
        self.splitter.setSizes(sizes);self.position_chrome()

    def text_tools(self):
        self.leave_color_tools()
        if hasattr(self,'property_container'):self.property_container.hide()
        self.canvas.vector_edit=False;self.edit_tool='text'
        self.set_mode('objects')
        self.show_text_properties();self.document_views.setCurrentWidget(self.scroll)
        if self.suspended_inline:self.restore_inline()

    def format_for(self,family,size,color,bold=False,italic=False):
        fmt=QTextCharFormat();font=QFont(matched_family(family)[0]);font.setPointSizeF(size*self.canvas.scale*72/self.logicalDpiY());font.setBold(bold);font.setItalic(italic)
        fmt.setFont(font);fmt.setForeground(QColor.fromRgbF(*color));fmt.setProperty(FAMILY,family);fmt.setProperty(SIZE,float(size));return fmt

    def start_inline(self,obj):
        import copy
        obj=copy.deepcopy(obj)
        if self.suspended_inline:
            self.restore_inline()
            if self.inline_object.id==obj.id and self.inline_page==self.canvas.object_page:return
            if QMessageBox.question(self,tr('text_ops'),L('还有未应用的文字草稿。放弃该草稿并编辑另一对象？','Discard the pending text draft and edit another object?'),QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        if hasattr(self,'property_container'):self.property_container.hide()
        self.edit_tool='text';self.canvas.vector_edit=False;self.cancel_inline();self.set_mode('objects');self.inline_object=obj;self.inline_page=self.canvas.object_page;self.inline_color=None;self.inline_source_path=str(self.document.path);self.show_text_properties()
        editor=InlineEditor(self.canvas);editor.owner=self;editor.preview_serial=0;self.inline_editor=editor;editor.viewport().setAutoFillBackground(False);editor.setAcceptRichText(False);editor.setLineWrapMode(QTextEdit.NoWrap);editor.document().setDocumentMargin(0);editor.setUndoRedoEnabled(False)
        editor.recovery_timer=QTimer(editor);editor.recovery_timer.setSingleShot(True);editor.recovery_timer.timeout.connect(self.persist_recovery_draft)
        editor.preview_timer=QTimer(editor);editor.preview_timer.setSingleShot(True);editor.preview_timer.timeout.connect(self.preview_inline)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Apply widget styling once, before rich text. Reapplying QSS on each
        # edit can overwrite QTextDocument's font and foreground properties.
        editor.setStyleSheet('QTextEdit {background:transparent;border:1px solid #8867cc;border-radius:0;padding:0;}')
        editor.ensurePolished()
        spans=obj.details.get('spans',[]);cursor=editor.textCursor()
        if obj.details.get('edit_styles'):
            for ch,style in obj.details['edit_styles']:
                if style:
                    family,size,bold,italic,color=style;cursor.insertText(ch,self.format_for(family,size,color,bold,italic))
                else:cursor.insertText(ch)
        elif spans:
            last_line=spans[0]['line']
            for span in spans:
                if span['line']!=last_line:cursor.insertText('\n');last_line=span['line']
                c=span.get('color',0);rgb=((c>>16&255)/255,(c>>8&255)/255,(c&255)/255)
                cursor.insertText(span['text'],self.format_for(span['font'],span['size'],rgb,bool(span['flags']&16),bool(span['flags']&2)))
        else:
            c=obj.details.get('color',0);rgb=((c>>16&255)/255,(c>>8&255)/255,(c&255)/255)
            cursor.insertText(obj.text,self.format_for(obj.details.get('family','Arial'),obj.size,rgb,bool(obj.details.get('flags',0)&16),bool(obj.details.get('flags',0)&2)))
        self.box_controls.setVisible(bool(obj.details.get('box')))
        if obj.details.get('box'):
            self._sync_text=True;self.box_width.setValue(obj.details['box']['rect'][2]);self.box_angle.setValue(obj.details['box'].get('angle',0));self._sync_text=False
        editor.setUndoRedoEnabled(True);self.inline_original_runs=self.text_runs();self.inline_initial=self.text_signature()
        box=self.canvas.page_rect(self.inline_page,obj.bbox).adjusted(-2,-2,18,4);box.setWidth(max(150,box.width()));box.setHeight(max(20,box.height()));editor.setGeometry(box.toRect())
        editor.original_text="".join(c for c,_ in text_patch.characters(self.inline_original_runs))
        editor.textChanged.connect(self.update_inline_style);editor.cursorPositionChanged.connect(self.sync_text_controls)
        editor.cursorPositionChanged.connect(editor.viewport().update);editor.selectionChanged.connect(editor.viewport().update)
        editor.undoAvailable.connect(lambda _:self.window.update_title());editor.redoAvailable.connect(lambda _:self.window.update_title())
        editor.installEventFilter(self);editor.show();editor.setFocus();editor.selectAll();self.text_format_group.setEnabled(True)
        self.sync_text_controls();self.update_inline_style();QTimer.singleShot(0,self.position_inline)

    def position_inline(self):
        if not self.inline_editor or self.inline_page>=len(self.canvas.rects):return
        if self.inline_object.details.get('box'):
            from .text_handles import position_box
            position_box(self);return
        box=self.canvas.page_rect(self.inline_page,self.inline_object.bbox).adjusted(-4,-4,18,4)
        glyphs=getattr(self.inline_editor,'preview_glyphs',self.inline_object.details.get('glyphs',[]))
        if glyphs:
            bounds=QRectF()
            for g in glyphs:bounds=bounds.united(self.canvas.page_rect(self.inline_page,g[3]))
            box=box.united(bounds.adjusted(-4,-4,18,4))
        if hasattr(self.inline_editor,'preview_bounds'):
            x,y,w,h=self.inline_editor.preview_bounds;box=box.united(self.canvas.page_rect(self.inline_page,(x,y,x+w,y+h)).adjusted(-2,-2,2,2))
        document=self.inline_editor.document();available=self.canvas.rects[self.inline_page].right()-box.left()
        box.setWidth(min(max(150,box.width(),document.idealWidth()+8),available));box.setHeight(max(20,box.height(),document.size().height()+4));self.inline_editor.setGeometry(box.toRect())

    def change_box(self,width=None,angle=None):
        if self._sync_text or not self.inline_editor or not self.inline_object.details.get('box'):return
        box=self.inline_object.details['box']
        if width is not None:box['rect'][2]=width;box['auto']=False
        if angle is not None:box['angle']=angle
        self.inline_editor.box_changed=True;self.update_inline_style()

    def text_runs(self):
        if not self.inline_editor:return []
        lines=[];block=self.inline_editor.document().begin()
        while block.isValid():
            runs=[];iterator=block.begin()
            while not iterator.atEnd():
                fragment=iterator.fragment()
                if fragment.isValid():
                    fmt=fragment.charFormat();c=fmt.foreground().color();runs.append({'text':fragment.text(),'family':fmt.property(FAMILY) or fmt.font().family(),'size':float(fmt.property(SIZE) or self.inline_object.size),'bold':fmt.fontWeight()>=QFont.Bold,'italic':fmt.fontItalic(),'color':c.getRgbF()[:3]})
                iterator+=1
            lines.append(runs);block=block.next()
        return lines

    def text_signature(self):
        return tuple(text_patch.characters(self.text_runs()))

    def inline_dirty(self):return self.inline_editor is not None and (self.text_signature()!=self.inline_initial or getattr(self.inline_editor,'box_changed',False))

    def sync_text_controls(self):
        if not self.inline_editor:return
        fmt=self.inline_editor.textCursor().charFormat();family=fmt.property(FAMILY) or fmt.font().family();size=float(fmt.property(SIZE) or self.inline_object.size)
        self._sync_text=True;self.object_font.setCurrentFont(QFont(family));self.object_size.setValue(size);self.text_bold.setChecked(fmt.fontWeight()>=QFont.Bold);self.text_italic.setChecked(fmt.fontItalic());self._sync_text=False
        substitute,found=matched_family(family)
        self.font_notice.setText('' if found else L('PDF 原字体：','PDF font: ')+family+'\n'+L('新输入推荐：','Suggested input: ')+substitute)

    def format_selection(self,kind):
        if self._sync_text or not self.inline_editor:return
        fmt=QTextCharFormat()
        if kind=='family':
            family=self.object_font.currentText();fmt.setFontFamilies([family]);fmt.setProperty(FAMILY,family)
        elif kind=='size':
            size=self.object_size.value();fmt.setFontPointSize(size*self.canvas.scale*72/self.logicalDpiY());fmt.setProperty(SIZE,size)
        elif kind=='bold':fmt.setFontWeight(QFont.Bold if self.text_bold.isChecked() else QFont.Normal)
        elif kind=='italic':fmt.setFontItalic(self.text_italic.isChecked())
        self.inline_editor.mergeCurrentCharFormat(fmt);self.inline_editor.setFocus();self.update_inline_style()

    def choose_text_color(self):
        if not self.inline_editor:return
        color=QColorDialog.getColor(self.inline_editor.textCursor().charFormat().foreground().color(),self)
        if color.isValid():
            fmt=QTextCharFormat();fmt.setForeground(color);self.inline_editor.mergeCurrentCharFormat(fmt);self.update_inline_style()

    def update_inline_style(self):
        if not self.inline_editor or not hasattr(self,'inline_initial'):return
        pristine=not self.inline_dirty() and not self.inline_object.details.get('new')
        self.inline_editor.setProperty('original_preview',pristine)
        self.inline_editor.viewport().setAutoFillBackground(False)
        palette=self.inline_editor.viewport().palette();palette.setColor(palette.ColorRole.Base,QColor('white'));palette.setColor(palette.ColorRole.Text,QColor('#182334'));self.inline_editor.viewport().setPalette(palette)
        self.inline_editor.viewport().update();self.window.update_title()
        self.position_inline()
        self.inline_editor.preview_serial+=1
        if pristine:
            self.inline_editor.preview_image=None
            for name in ('preview_glyphs','preview_text'):
                if hasattr(self.inline_editor,name):delattr(self.inline_editor,name)
            self.inline_editor.preview_timer.stop()
        else:self.inline_editor.preview_timer.start(120)
        self.inline_editor.recovery_timer.start(350)

    def resolve_inline_fonts(self,lines):
        buffers={};substitutes=set()
        runs=[run for line in lines for run in line if run['text']] if self.inline_object.details.get('box') else text_patch.changed_runs(self.inline_original_runs,lines)
        for run in runs:
            if self.inline_object.details.get('box'):run['delta_text']=run['text']
            key=(run['family'],run['bold'],run['italic'],run['delta_text'])
            if key not in buffers:
                found=embedded_font(self.document,self.inline_page,key[0],key[3],key[1],key[2],self.inline_object)
                cached=getattr(self,'clipboard_fonts',{}).get(key[0])
                if not found and cached:
                    import pymupdf as fitz
                    with ENGINE_LOCK:
                        font=fitz.Font(fontbuffer=cached)
                        if all(font.has_glyph(ord(c)) for c in key[3] if not c.isspace()):found=(cached,key[0])
                buffers[key]=found or resolve_font(key[0],key[3],key[1],key[2])
            run['fontbuffer'],actual=buffers[key]
            if actual!=run['family']:substitutes.add(actual)
        return substitutes

    def preview_inline(self):
        from .text_preview import render
        from types import SimpleNamespace
        editor=self.inline_editor
        if not editor:return
        import copy
        serial=editor.preview_serial;lines=self.text_runs();old=self.inline_original_runs;obj=copy.deepcopy(self.inline_object);page=self.inline_page
        try:substitutes=self.resolve_inline_fonts(lines)
        except (ValueError,RuntimeError) as error:self.draft_notice.setText(str(error));return
        def done(result):
            if self.inline_editor is not editor or editor.preview_serial!=serial:return
            editor.preview_image,editor.preview_bounds,editor.preview_glyphs=result;editor.preview_angle=obj.details.get('box',{}).get('angle',0)
            editor.preview_text=''.join(c for c,_ in text_patch.characters(lines));self.position_inline();editor.viewport().update()
            self.draft_notice.setText(L('新输入使用：','New input uses: ')+', '.join(sorted(substitutes)) if substitutes else L('局部 PDF 预览 · 应用后写入文档','Local PDF preview · Apply to commit'))
        def failed(message):
            if self.inline_editor is editor and editor.preview_serial==serial:self.draft_notice.setText(message)
        scale=self.canvas.scale*self.canvas.devicePixelRatioF()
        source=SimpleNamespace(path=self.inline_source_path)
        self.queue.submit(lambda j:render(source,page,obj,old,lines,scale),done,failed,priority=2)

    def exit_text_tools(self):
        self.cancel_inline();self.text_properties.hide();self.text_container.hide();self.set_mode('objects')

    def cancel_inline(self):
        if self.inline_editor:
            editor=self.inline_editor;self.inline_editor=None;
            if hasattr(editor,'handles'):editor.handles.hide();editor.handles.deleteLater()
            editor.preview_timer.stop();editor.recovery_timer.stop();editor.hide();editor.deleteLater()
            (self.document.folder/'draft.json').unlink(missing_ok=True)
            if hasattr(self,'text_format_group'):self.text_format_group.setEnabled(False);self.box_controls.hide()
            self.canvas.setFocus();self.window.update_title()

    def persist_recovery_draft(self):
        if not self.inline_editor:return
        from dataclasses import asdict
        from .core import atomic_json
        path=self.document.folder/'draft.json'
        if not self.inline_dirty():path.unlink(missing_ok=True);return
        atomic_json(path,{'page':self.inline_page,'object':asdict(self.inline_object),'runs':self.text_runs(),'original':self.inline_original_runs,'source':self.inline_source_path})

    def restore_recovery_draft(self,data):
        self.goto(data['page']);self.active_panel='objects';self.editing_objects=True;self.canvas.mode='objects';self.canvas.object_page=data['page']
        self.tool_panels.setCurrentIndex(self.panel_keys['objects']);self.tool_panels.show();self.module_actions['objects'].setChecked(True);self.position_chrome()
        obj=objects.PdfObject(**data['object']);self.start_inline(obj);cursor=self.inline_editor.textCursor();cursor.select(QTextCursor.Document);cursor.removeSelectedText()
        for n,line in enumerate(data['runs']):
            if n:cursor.insertText('\n')
            for run in line:cursor.insertText(run['text'],self.format_for(run['family'],run['size'],run['color'],run['bold'],run['italic']))
        self.inline_editor.setTextCursor(cursor);self.update_inline_style();self.persist_recovery_draft()

    def suspend_inline(self):
        if not self.inline_editor:return
        self.persist_recovery_draft()
        self.inline_editor.hide();
        if hasattr(self.inline_editor,'handles'):self.inline_editor.handles.hide()
        self.suspended_inline=(self.inline_editor,self.inline_object,self.inline_page,self.inline_initial,self.inline_original_runs)
        self.inline_editor=None;self.text_format_group.setEnabled(False);self.window.update_title()

    def restore_inline(self):
        if not self.suspended_inline:return
        self.inline_editor,self.inline_object,self.inline_page,self.inline_initial,self.inline_original_runs=self.suspended_inline;self.suspended_inline=None
        self.show_text_properties();self.inline_editor.show();self.position_inline();self.inline_editor.setFocus();self.text_format_group.setEnabled(True);self.sync_text_controls()

    def leave_inline(self,after):
        if not self.inline_editor:after();return
        self.commit_inline(after,on_failure=lambda:(self.suspend_inline(),after()))

    def commit_inline(self,after=None,on_failure=None):
        if not self.inline_editor or self.busy:return
        if not self.inline_dirty():
            self.cancel_inline()
            if callable(after):QTimer.singleShot(0,after)
            return
        if self.inline_source_path!=str(self.document.path):
            self.draft_notice.setText(L('保留草稿期间 PDF 内容已更改。请复制草稿，取消后重新选择文字块再应用。','The PDF changed while this draft was retained. Copy the draft, cancel, and select the text block again.'))
            if on_failure:on_failure()
            return
        obj=self.inline_object;page=self.inline_page;lines=self.text_runs();buffers={};substitutes=set()
        try:
            substitutes=self.resolve_inline_fonts(lines)
        except (ValueError,RuntimeError) as error:
            self.draft_notice.setText(str(error))
            if on_failure:on_failure()
            return
        self.inline_editor.setReadOnly(True)
        if hasattr(self.inline_editor,'handles'):self.inline_editor.handles.setEnabled(False)
        self.inline_editor.preview_timer.stop()
        def done(_):
            self.cancel_inline();self.draft_notice.setText(L('已应用。输入字体：','Applied. Input fonts: ')+', '.join(sorted(substitutes)) if substitutes else L('已应用局部文字修改。','Local text changes applied.'))
            if callable(after):QTimer.singleShot(0,after)
        def failed(message):
            if self.inline_editor:
                self.inline_editor.setReadOnly(False)
                if hasattr(self.inline_editor,'handles'):self.inline_editor.handles.setEnabled(True)
            self.draft_notice.setText(message)
            if on_failure:on_failure()
        original=self.inline_original_runs
        self.run(tr('modify'),lambda j:text_patch.apply(self.document,page,obj,original,lines),done,editing=True,failure=failed,local_edit=True)
