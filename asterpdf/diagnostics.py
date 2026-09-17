"""Opt-in native desktop diagnostic run; never enabled in ordinary sessions."""
from pathlib import Path
import json
import sys
import time
from PySide6.QtCore import QTimer, QEvent, Qt, QPoint, QPointF, QRect
from PySide6.QtGui import QKeyEvent,QWheelEvent
from PySide6.QtWidgets import QApplication


def start(window, directory, expected_files):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();activated=set();samples={};errors=[];navigation=set();checks=[]
    edit_check={'done':False,'passed':False};validated=set();play_started={};print_check={'started':False,'done':False,'passed':False}
    from .fonts import font_bytes
    from PySide6.QtGui import QFont
    try:buffer=font_bytes(QFont().defaultFamily())
    except Exception as e:buffer=None;edit_check.update(done=True,error=str(e))
    def edit_work(job):
        import pymupdf as fitz
        from .core import Document
        from .objects import discover
        from .text_patch import apply
        original=directory/'diagnostic-input.pdf'
        with fitz.open() as pdf:
            page=pdf.new_page();page.insert_text((50,60),'Original label',fontsize=16);pdf.save(original)
        doc=Document(original,directory/'recovery')
        try:
            obj=next(o for o in discover(doc,0) if o.kind=='text')
            old=[[{'text':'Original label','family':obj.details['family'],'size':16,'color':(0,0,0),'bold':False,'italic':False}]]
            new=[[dict(old[0][0],text='Edited label',fontbuffer=buffer)]]
            apply(doc,0,obj,old,new)
            doc.add_annotation(0,'arrow',[(50,100),(150,130)],author_name='Diagnostic',line_end=5)
            target=directory/'diagnostic-edited.pdf';doc.save(target)
            with fitz.open(target) as pdf:
                page=pdf[0];text=page.get_text()
                passed='Edited label' in text and 'Original label' not in text and len(list(page.annots()))==1
            return {'done':True,'passed':passed,'system_font_edit_save_reopen':passed}
        finally:doc.close()
    if buffer:
        window.queue.submit(edit_work,lambda result:edit_check.update(result),lambda message:edit_check.update(done=True,error=message),priority=2)
    timer=QTimer(window);timer.setInterval(60)
    def tick():
        elapsed=time.monotonic()-started
        tabs=[window.tabs.widget(i) for i in range(window.tabs.count()) if hasattr(window.tabs.widget(i),'document')]
        pending=[tab for tab in tabs if tab.document.original not in validated]
        for tab in pending[:1]:
            key=tab.document.original
            window.tabs.setCurrentWidget(tab)
            if key not in navigation:
                window.tabs.setCurrentWidget(tab);tab.set_view(1,False);tab.goto(0)
                QApplication.sendEvent(tab.canvas,QKeyEvent(QEvent.KeyPress,Qt.Key_Right,Qt.NoModifier))
                checks.append({'check':'single-page Right key','passed':tab.canvas.page==min(1,tab.info['count']-1)})
                window.toggle_presentation()
                QApplication.sendEvent(tab.canvas,QKeyEvent(QEvent.KeyPress,Qt.Key_Left,Qt.NoModifier))
                checks.append({'check':'presentation Left key','passed':tab.canvas.page==0})
                QApplication.sendEvent(tab.canvas,QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
                checks.append({'check':'presentation Escape','passed':not window.presentation})
                navigation.add(key)
            if tab.animations and key not in activated:
                tab.goto(tab.animations[0].page);tab.fit(False);tab.set_panel('media')
                tab.players[(tab.animations[0].page,tab.animations[0].key)].start();activated.add(key);play_started[key]=time.monotonic()
            elif tab.assets and key not in activated:
                tab.open_media(tab.assets[0]);activated.add(key);play_started[key]=time.monotonic()
            # Windows hidden-start validation may receive no native paint
            # events. Ask Qt to paint the real viewport so the ordinary tile
            # pipeline is exercised; do not treat open/decode as page success.
            if not tab.canvas.cache and not tab.canvas.pending:
                viewport=tab.scroll.viewport()
                tab.canvas.grab(QRect(tab.scroll.horizontalScrollBar().value(),tab.scroll.verticalScrollBar().value(),viewport.width(),viewport.height()))
            sample=samples.setdefault(key,{'pages':tab.info['count'],'rendered_pages':0,'animation_frames':0,'video_frames':0,'media_position_ms':0})
            sample['rendered_pages']=max(sample['rendered_pages'],len(tab.canvas.cache))
            sample['animation_frames']=sum(p.rendered_frames for p in tab.players.values())
            sample['video_frames']=sum(p.actual_video_frames for p in tab.video_players)
            sample['media_position_ms']=max([p.player.position() for p in tab.video_players] or [0])
            for p in tab.video_players:
                if p.player.errorString():errors.append(p.player.errorString())
            playback=bool(tab.canvas.cache) and (not tab.animations or sample['animation_frames']>=8) and (not tab.assets or sample['video_frames']>=8 or sample['media_position_ms']>=700)
            if playback and time.monotonic()-play_started.get(key,started)>=3:
                validated.add(key);tab.pause_media();window.grab().save(str(directory/f'desktop-{len(validated)}.png'))
        ready=edit_check['done'] and len(tabs)==expected_files and len(validated)==expected_files
        if ready and not print_check['started']:
            from PySide6.QtPrintSupport import QPrinter
            from .printing import print_document
            printer=QPrinter(QPrinter.HighResolution);printer.setResolution(100);printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(str(directory/'diagnostic-print.pdf'))
            print_check['started']=True
            def verify_print(ok):
                import pymupdf as fitz
                from .core import ENGINE_LOCK
                try:
                    with ENGINE_LOCK,fitz.open(directory/'diagnostic-print.pdf') as pdf:count=len(pdf)
                    print_check.update(done=True,passed=ok and count==tabs[0].info['count'],pages=count)
                except Exception as error:print_check.update(done=True,passed=False,error=str(error))
            print_document(tabs[0],printer,verify_print)
        if (ready and print_check['done']) or elapsed>60:
            timer.stop()
            report={'frozen':bool(getattr(sys,'frozen',False)),'elapsed_seconds':round(elapsed,2),
                    'print':print_check,'passed':ready and print_check['passed'] and edit_check['passed'] and not errors and all(c['passed'] for c in checks),'navigation':checks,'text_edit':edit_check,'documents':list(samples.values()),'errors':list(set(errors))}
            (directory/'desktop-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            window.close();QApplication.instance().exit(0 if report['passed'] else 1)
    timer.timeout.connect(tick);timer.start()
    window._diagnostic_timer=timer
