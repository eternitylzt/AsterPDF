"""Real AcroForm values, appearances, native input, history and save/reopen."""
import io
import json
from pathlib import Path
import pytest
import pymupdf as fitz
import pikepdf as pp
from PySide6.QtCore import Qt,QDate,QTimer,QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit,QFileDialog,QCalendarWidget,QToolButton,QMessageBox
from asterpdf.core import Document,ENGINE_LOCK
from asterpdf import forms,i18n
from test_practical_ui import ui


def make_form(path):
    with fitz.open() as pdf:
        page=pdf.new_page(width=595,height=842)
        def add(name,kind,rect,flags=0,choices=None,value='',date=False):
            w=fitz.Widget();w.field_name=name;w.field_type=kind;w.rect=fitz.Rect(rect);w.field_flags=flags;w.field_value=value
            w.text_font='Helv';w.text_fontsize=11;w.text_color=(0,0,.7);w.border_color=(.3,.4,.5);w.border_width=1
            if choices:w.choice_values=choices
            if date:w.script_format='AFDate_FormatEx("dd.mm.yyyy");';w.script_stroke='AFDate_KeystrokeEx("dd.mm.yyyy");'
            page.add_widget(w)
        add('Name',fitz.PDF_WIDGET_TYPE_TEXT,(50,50,260,78),value='Original')
        add('Details',fitz.PDF_WIDGET_TYPE_TEXT,(50,100,350,180),flags=4096)
        add('Date',fitz.PDF_WIDGET_TYPE_TEXT,(50,200,240,230),date=True)
        add('Agree',fitz.PDF_WIDGET_TYPE_CHECKBOX,(50,250,70,270))
        add('GroupA',fitz.PDF_WIDGET_TYPE_CHECKBOX,(100,250,120,270))
        add('GroupB',fitz.PDF_WIDGET_TYPE_CHECKBOX,(140,250,160,270))
        add('Choice',fitz.PDF_WIDGET_TYPE_COMBOBOX,(50,300,260,330),choices=['First','Second'])
        add('List',fitz.PDF_WIDGET_TYPE_LISTBOX,(50,360,260,440),flags=1<<21,choices=['Alpha','Beta','Gamma'])
        add('Locked',fitz.PDF_WIDGET_TYPE_TEXT,(50,470,260,500),flags=1,value='Read only')
        page=pdf.new_page(width=595,height=842)
        add('Name',fitz.PDF_WIDGET_TYPE_TEXT,(50,50,260,78),value='Original')
        page.insert_text((50,550),'Unchanged page text')
        pdf.save(path)
    with pp.open(path,allow_overwriting_input=True) as pdf:
        kids=[node for _,_,node in forms.widgets(pdf) if str(node.get('/T','')) in ('GroupA','GroupB')]
        parent=pdf.make_indirect(pp.Dictionary(FT=pp.Name.Btn,T=pp.String('Group'),Ff=32768,V=pp.Name.Off,Kids=pp.Array(kids)))
        ids={node.objgen for node in kids};pdf.Root.AcroForm.Fields=pp.Array([n for n in pdf.Root.AcroForm.Fields if n.objgen not in ids]+[parent])
        for i,node in enumerate(kids):
            for key in ('/T','/FT','/Ff','/V'):
                if key in node:del node[key]
            node.Parent=parent
            normal=node.AP.N;on=next(k for k in normal.keys() if k!='/Off');normal[f'/Choice{i}']=normal[on];del normal[on]
        pdf.save(path)
    return path


def model(document,name):return next(f for f in forms.scan(document.path)['fields'] if f['name']==name)


def test_values_appearances_groups_choices_and_history(tmp_path):
    source=make_form(tmp_path/'form.pdf');original=source.read_bytes();doc=Document(source,tmp_path/'recovery')
    try:
        before=forms.scan(doc.path);byname={f['name']:f for f in before['fields']}
        changes={byname['Name']['key']:'Test user 中文',byname['Details']['key']:'Line one\nSecond line 中文',byname['Date']['key']:'28.09.2026',byname['Agree']['key']:True,byname['Group']['key']:True,byname['Choice']['key']:'Second',byname['List']['key']:['Alpha','Gamma']}
        forms.fill(doc,changes)
        after=forms.scan(doc.path)
        assert all(f['value']=='Test user 中文' for f in after['fields'] if f['name']=='Name')
        assert sum(f['checked'] for f in after['fields'] if f['name']=='Group')==1
        assert model(doc,'List')['value']==['Alpha','Gamma'] and model(doc,'Agree')['checked']
        assert model(doc,'Locked')['value']=='Read only'
        with fitz.open(doc.path) as pdf:
            assert 'Unchanged page text' in pdf[1].get_text()
            assert all(p.get_pixmap().samples for p in pdf)
            # Read text from the newly written appearance independently of /V.
            with pp.open(doc.path) as raw:
                node=next(n for key,_,n in forms.widgets(raw) if key==byname['Name']['key'])
                ap=node.AP.N;assert len(ap.read_bytes())>0 and ap.Resources.Font
                with pp.new() as scratch:
                    page=scratch.add_blank_page(page_size=(210,50));page.Resources=pp.Dictionary(XObject=pp.Dictionary(F=scratch.copy_foreign(ap)));page.Contents=scratch.make_stream(b'q /F Do Q')
                    stream=io.BytesIO();scratch.save(stream)
                    with fitz.open(stream=stream.getvalue(),filetype='pdf') as rendered:assert 'Test user' in rendered[0].get_text() and '中文' in rendered[0].get_text()
        saved=tmp_path/'filled.pdf';doc.save(saved)
        with pp.open(saved) as pdf:
            assert pdf.Root.AcroForm.Fields and not pdf.Root.AcroForm.NeedAppearances
            for key,_,node in forms.widgets(pdf):
                if key in changes:assert '/V' in node or '/V' in node.get('/Parent',{})
        doc.undo();assert model(doc,'Name')['value']=='Original'
        doc.redo();assert model(doc,'Name')['value']=='Test user 中文'
        forms.fill(doc,{byname['Name']['key']:'',byname['Details']['key']:''})
        assert model(doc,'Name')['value']=='' and model(doc,'Details')['value']==''
        doc.undo()
        with pytest.raises(ValueError):forms.fill(doc,{byname['Date']['key']:'31.02.2026'})
        with pytest.raises(ValueError):forms.fill(doc,{byname['Locked']['key']:'not allowed'})
        assert source.read_bytes()==original
    finally:doc.close()


def test_native_input_tab_checkbox_save_and_recovery_draft(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui
    source=make_form(tmp_path/'ui-form.pdf');w.open_file(source);pump(lambda:not w.opening and not w.queue.jobs)
    tab=w.current();pump(lambda:len(tab.forms.fields)==10);tab.fit(True);pump()
    f=next(f for f in tab.forms.fields if f['name']=='Name')
    pos=tab.canvas.page_rect(0,f['rect']).center().toPoint();QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,pos);pump()
    assert isinstance(tab.forms.input,QLineEdit)
    tab.forms.input.selectAll();QTest.keyClicks(tab.forms.input,'User typed')
    assert tab.form_dirty() and '*' in w.tabs.tabText(w.tabs.currentIndex())
    draft=json.loads((tab.document.folder/'form-draft.json').read_text());assert draft['values'][f['key']]=='User typed'
    QTest.keyClick(tab.forms.input,Qt.Key_Tab);pump(lambda:not tab.busy and not tab.forms.writing and tab.forms.active!=f['key'])
    assert tab.forms.find(tab.forms.active)['name']=='Details'
    tab.forms.dismiss();pump()
    check=next(f for f in tab.forms.fields if f['name']=='Agree')
    QTest.mouseClick(tab.canvas,Qt.LeftButton,Qt.NoModifier,tab.canvas.page_rect(0,check['rect']).center().toPoint())
    pump(lambda:not tab.busy and not tab.forms.writing and not tab.forms.dirty)
    assert next(f for f in tab.forms.fields if f['name']=='Agree')['checked']
    saved=tmp_path/'ui-saved.pdf';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**kw:(str(saved),'PDF (*.pdf)'))
    w.save_tab(True);pump(lambda:not tab.busy and saved.exists())
    with fitz.open(saved) as pdf:assert all(widget.field_value=='User typed' for p in pdf for widget in p.widgets() or [] if widget.field_name=='Name')
    tab.forms.dismiss();w.history(False);pump(lambda:not tab.busy and not tab.queue.jobs);assert not model(tab.document,'Agree')['checked']
    for lang,label,hint in [('zh','收藏','添加 / 移除收藏'),('en','Favorites','Add / remove favorite')]:
        w.change_language(lang);pump();assert tab.sidebar.tabText(tab.sidebar.indexOf(tab.bookmarks))==label
        assert tab.quick_actions['bookmark'].toolTip()==hint


def test_calendar_list_navigation_and_close_flush(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui
    source=make_form(tmp_path/'date-list.pdf');w.open_file(source);pump(lambda:not w.opening and not w.queue.jobs)
    tab=w.current();pump(lambda:bool(tab.forms.fields));tab.fit(True)
    field=next(f for f in tab.forms.fields if f['name']=='Date');tab.forms.activate(field)
    def choose():
        calendar=next(widget for widget in app.allWidgets() if isinstance(widget,QCalendarWidget) and widget.isVisible())
        calendar.clicked.emit(QDate(2026,10,5))
    QTimer.singleShot(100,choose)
    button=tab.forms.editor.findChild(QToolButton);QTest.mouseClick(button,Qt.LeftButton)
    assert tab.forms.input.text()=='05.10.2026'
    tab.forms.flush();pump(lambda:not tab.busy and not tab.forms.writing)
    QTest.keyClick(tab.forms.input,Qt.Key_Tab);pump()
    assert tab.forms.find(tab.forms.active)['name']=='Agree' and not tab.forms.dirty and not tab.forms.input.isChecked()
    QTest.keyClick(tab.forms.input,Qt.Key_Backtab);pump();assert tab.forms.find(tab.forms.active)['name']=='Date'
    QTest.keyClick(tab.forms.input,Qt.Key_Tab);pump();assert not tab.forms.input.isChecked()
    QTest.keyClick(tab.forms.input,Qt.Key_Space);tab.forms.flush();pump(lambda:not tab.busy and not tab.forms.writing)
    assert model(tab.document,'Agree')['checked']
    item=next(f for f in tab.forms.fields if f['name']=='List');tab.forms.activate(item);pump()
    listing=tab.forms.input;listing.item(0).setSelected(True);listing.item(2).setSelected(True)
    page=tab.canvas.page;QTest.keyClick(listing,Qt.Key_Down);assert tab.canvas.page==page
    tab.forms.flush(tab.forms.dismiss);pump(lambda:not tab.busy and not tab.forms.writing)
    name=next(f for f in tab.forms.fields if f['name']=='Name');tab.forms.activate(name);tab.forms.input.selectAll();QTest.keyClicks(tab.forms.input,'Saved on close')
    prompts=[]
    monkeypatch.setattr(QMessageBox,'question',lambda *args:(prompts.append(w.current()),QMessageBox.Save)[1])
    w.close_tab(w.tabs.indexOf(tab));pump(lambda:tab.closed and not w.queue.jobs)
    assert prompts==[tab]
    with fitz.open(source) as pdf:assert next(p.field_value for p in pdf[0].widgets() if p.field_name=='Name')=='Saved on close'


def test_restore_uncommitted_form_draft(ui,tmp_path):
    app,w,t,pump=ui
    source=make_form(tmp_path/'recover.pdf');old=Document(source,tmp_path/'old-recovery')
    try:
        key=model(old,'Name')['key'];manifest=old.folder/'recovery.json'
        data=json.loads(manifest.read_text());data['form_draft']={'values':{key:'Recovered input'}}
        (old.folder/'form-draft.json').write_text(json.dumps(data['form_draft']),encoding='utf8')
        w.open_recovery(data,manifest);pump(lambda:w.current() is not t and not w.queue.jobs)
        restored=w.current();pump(lambda:model(restored.document,'Name')['value']=='Recovered input' and not restored.busy and not restored.forms.writing)
        assert restored.document.dirty and not (old.folder/'form-draft.json').exists()
        with fitz.open(source) as pdf:assert next(p.field_value for p in pdf[0].widgets() if p.field_name=='Name')=='Original'
    finally:old.close()


def test_focus_without_edits_is_noop_and_animation_widgets_still_play(ui,tmp_path):
    app,w,t,pump=ui
    # The standard demo includes a LaTeX-style widget animation.
    pump(lambda:bool(t.animations));animation=t.animations[0];t.goto(animation.page);t.pointer();pump()
    center=t.canvas.page_rect(animation.page,animation.rect).center().toPoint()
    assert t.forms.hit(animation.page,QPointF((animation.rect[0]+animation.rect[2])/2,(animation.rect[1]+animation.rect[3])/2)) is None
    QTest.mouseClick(t.canvas,Qt.LeftButton,Qt.NoModifier,center);pump(lambda:any(p.playing for p in t.players.values()))
    t.pause_media()
    source=make_form(tmp_path/'no-edit.pdf');w.open_file(source);pump(lambda:not w.opening and not w.queue.jobs)
    tab=w.current();pump(lambda:bool(tab.forms.fields));revision=tab.document.revision
    tab.forms.activate(next(f for f in tab.forms.fields if f['name']=='Name'));tab.forms.flush(tab.forms.dismiss);pump()
    assert tab.document.revision==revision and not tab.form_dirty()


def test_form_fill_preserves_animation_and_other_page_content(document,tmp_path):
    from asterpdf import media
    from asterpdf.objects import content_bytes
    source=make_form(tmp_path/'field-source.pdf')
    def insert(pdf):
        with pp.open(source) as other:
            widget=next(n for _,_,n in forms.widgets(other) if str(n.get('/T',''))=='Agree')
            copied=pdf.copy_foreign(widget);copied.P=pdf.pages[0].obj;copied.T=pp.String('FormAgree')
            if '/Annots' not in pdf.pages[0].obj:pdf.pages[0].obj.Annots=pp.Array()
            pdf.pages[0].obj.Annots.append(copied);pdf.Root.AcroForm.Fields.append(copied)
    document.edit('test mixed form and animation',insert)
    before=media.scan(document)[0]
    with pp.open(document.path) as pdf:contents=[content_bytes(p) for p in pdf.pages]
    forms.fill(document,{model(document,'FormAgree')['key']:True})
    after=media.scan(document)[0]
    assert [(a.page,a.key,len(a.frames),a.fps) for a in before]==[(a.page,a.key,len(a.frames),a.fps) for a in after]
    with pp.open(document.path) as pdf:assert contents==[content_bytes(p) for p in pdf.pages]
    assert model(document,'FormAgree')['checked']
