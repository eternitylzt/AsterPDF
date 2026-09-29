"""System-browser Markdown, fullscreen fitting, and video click regressions."""
from pathlib import Path
import time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest,QSignalSpy
from asterpdf.markdown_html import build_html,write_preview
from asterpdf.markdown_import import prepare
from test_practical_ui import ui


def test_local_html_math_images_outline_and_browser_setting(ui,tmp_path,monkeypatch):
    from PIL import Image
    from html.parser import HTMLParser
    app,w,t,pump=ui;Image.new('RGB',(30,20),'red').save(tmp_path/'plot.png')
    path=tmp_path/'notes.md';path.write_text('# Document\n\nInline $x^2$\n\n## Code\n\n```python\nprint("hello")\n```\n\n![plot](plot.png)\n\n| X | Y |\n|---|---|\n| 1 | 2 |\n\n## Code\n\n<script>alert(1)</script><a href="javascript:alert(1)" onclick="alert(2)">bad</a>\n',encoding='utf-8')
    prepared=prepare(path);html=build_html(path,prepared)
    assert '<table' in html and 'data:image/png;base64,' in html and 'data:image/svg+xml;base64,' in html
    assert 'href="#code"' in html and 'href="#code-1"' in html and '<pre><code' in html
    assert 'javascript:' not in html and ' onclick=' not in html and 'alert(' not in html
    assert 'Content-Security-Policy' in html and "connect-src &#x27;none&#x27;" in html
    assert 'font:14px/1.5' in html and 'navigator.clipboard.writeText' in html
    launched=[];monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:(launched.append(url),True)[1])
    w.settings.setValue('markdown/browser_mode','always')
    w.open_file(path);pump(lambda:not w.opening and not w.queue.jobs and len(launched)==1)
    assert len(launched)==1 and launched[0].isLocalFile();target=Path(launched[0].toLocalFile());assert target.exists()
    tab=w.current();assert tab.info['count']==1 and len(tab.info['toc'])==3 and w.markdown_preview_action.isEnabled()
    path.write_text('# Replaced on disk',encoding='utf-8');w.show_markdown_preview();pump(lambda:not w.queue.jobs)
    assert len(launched)==2 and 'Replaced on disk' not in target.read_text(encoding='utf-8')
    w.settings.setValue('markdown/browser_mode','never')
    other=tmp_path/'other.md';other.write_text('# Other document',encoding='utf-8');w.open_file(other);pump(lambda:not w.opening and not w.queue.jobs)
    assert len(launched)==2;w.show_markdown_preview();pump(lambda:not w.queue.jobs);assert len(launched)==3


def test_fullscreen_width_controls_manual_zoom_restore_and_keep(ui):
    app,w,t,pump=ui;t.set_zoom(.73);before=t.canvas.scale
    w.fullscreen();pump(lambda:hasattr(w,'fullscreen_controls') and w.fullscreen_controls.isVisible() and t.fit_mode=='width_fit')
    expected=(t.scroll.viewport().width()-32)/t.info['sizes'][t.canvas.page][0]
    assert t.canvas.scale==pytest.approx(expected,rel=.005)
    controls=w.fullscreen_controls;QTest.mouseClick(controls.page,Qt.LeftButton);pump();assert t.fit_mode=='page_fit'
    controls.zoom.setValue(140);pump();assert t.zoom_factor==pytest.approx(1.4) and t.fit_mode is None
    QTest.keyClick(controls.zoom,Qt.Key_Escape);pump(lambda:not w.document_fullscreen and abs(t.canvas.scale-before)<.001)
    assert not controls.isVisible()
    w.settings.setValue('reader/fullscreen_fit','keep');w.fullscreen();pump(lambda:controls.isVisible());assert t.canvas.scale==pytest.approx(before)
    w.escape();pump(lambda:not w.document_fullscreen and not controls.isVisible())
    t.fit(False);kept=t.canvas.scale;w.fullscreen();pump(lambda:controls.isVisible())
    assert t.canvas.scale==pytest.approx(kept) and t.fit_mode is None
    w.escape();pump()


@pytest.mark.parametrize('widget_surface',[False,True])
def test_video_one_click_pause_resume_and_no_canvas_bubbling(ui,monkeypatch,widget_surface):
    from asterpdf import player as module
    from PySide6.QtMultimedia import QMediaPlayer
    app,w,t,pump=ui;monkeypatch.setattr(module,'use_widget_video_surface',lambda:widget_surface)
    w.open_file(Path(__file__).parents[1]/'examples/AsterPDF-media.pdf');pump(lambda:not w.opening and not w.queue.jobs)
    tab=w.current();pump(lambda:bool(tab.assets));asset=next(a for a in tab.assets if a.kind=='video');tab.open_media(asset)
    pump(lambda:bool(tab.video_players));v=tab.video_players[0];v.audio.setMuted(True);v.player.setLoops(QMediaPlayer.Infinite)
    pump(lambda:v.actual_video_frames>=2 and v.player.playbackState()==QMediaPlayer.PlayingState)
    spy=QSignalSpy(tab.canvas.mediaClick)
    for _ in range(3):
        QTest.mouseClick(v.video,Qt.LeftButton);pump(lambda:v.player.playbackState()==QMediaPlayer.PausedState)
        assert not v.want_playing
        count=v.actual_video_frames;QTest.mouseClick(v.video,Qt.LeftButton);pump(lambda:v.player.playbackState()==QMediaPlayer.PlayingState and v.actual_video_frames>count)
        assert v.want_playing
    assert spy.count()==0
    QTest.mouseClick(v.play_button,Qt.LeftButton);pump(lambda:v.player.playbackState()==QMediaPlayer.PausedState)
    assert not v.want_playing
    if widget_surface:assert not v.video.image.isNull()
    v.shutdown()
    if widget_surface:assert v.video.image.isNull()
