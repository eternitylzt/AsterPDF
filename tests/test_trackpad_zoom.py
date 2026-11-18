"""Qt input streams: trackpad magnification, pointer anchoring, and two-finger scrolling."""
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QNativeGestureEvent, QPointingDevice, QWheelEvent
from PySide6.QtWidgets import QApplication, QGestureEvent, QPinchGesture
from test_practical_ui import ui


def native(target, kind, global_pos, value=0):
    event = QNativeGestureEvent(kind, QPointingDevice.primaryPointingDevice(), 2,
        QPointF(target.mapFromGlobal(global_pos.toPoint())), global_pos, global_pos,
        value, QPointF())
    QApplication.sendEvent(target, event)
    return event


def wheel(target, global_pos, angle=0, pixels=0, modifiers=Qt.ControlModifier,
          phase=Qt.ScrollUpdate):
    event = QWheelEvent(QPointF(target.mapFromGlobal(global_pos.toPoint())), global_pos,
        QPoint(0, pixels), QPoint(0, angle), Qt.NoButton, modifiers, phase, False)
    QApplication.sendEvent(target, event)
    return event


def test_native_pinch_keeps_the_document_point_under_the_fingers(ui):
    app, window, tab, pump = ui
    tab.set_view(1, True); tab.set_zoom(2); tab.goto(0)
    viewport = tab.scroll.viewport()
    anchor = QPointF(viewport.mapToGlobal(QPoint(330, 280)))
    before = tab.canvas.locate(QPointF(tab.canvas.mapFromGlobal(anchor.toPoint())))
    start = tab.canvas.scale
    assert native(viewport, Qt.BeginNativeGesture, anchor).isAccepted()
    for target, delta in ((tab.canvas, .1), (viewport, .05), (tab.canvas, -.04)):
        assert native(target, Qt.ZoomNativeGesture, anchor, delta).isAccepted()
    native(tab.canvas, Qt.RotateNativeGesture, anchor, 15)
    native(viewport, Qt.EndNativeGesture, anchor)
    assert tab.canvas.scale == pytest.approx(start * 1.1 * 1.05 * .96)
    after = tab.canvas.locate(QPointF(tab.canvas.mapFromGlobal(anchor.toPoint())))
    assert after[0] == before[0]
    assert (after[1] - before[1]).manhattanLength() < 2
    assert tab.fit_mode is None


def test_precision_wheel_zoom_is_proportional_and_plain_scroll_stays_scroll(ui):
    app, window, tab, pump = ui
    tab.set_view(1, True); tab.set_zoom(2); tab.goto(0)
    viewport = tab.scroll.viewport()
    anchor = QPointF(viewport.mapToGlobal(QPoint(330, 280)))
    start = tab.canvas.scale
    wheel(viewport, anchor, phase=Qt.ScrollBegin)
    for target in (tab.canvas, viewport, tab.canvas, viewport):
        wheel(target, anchor, angle=30)
    wheel(viewport, anchor, phase=Qt.ScrollEnd)
    assert tab.canvas.scale == pytest.approx(start * 1.12)
    wheel(viewport, anchor, pixels=6)
    assert tab.canvas.scale == pytest.approx(start * 1.12 ** 1.05)
    scale = tab.canvas.scale
    bar = tab.scroll.verticalScrollBar(); bar.setValue(100)
    wheel(viewport, anchor, pixels=-40, modifiers=Qt.NoModifier)
    assert bar.value() > 100
    assert tab.canvas.scale == scale


def test_qt_touch_pinch_uses_incremental_scale_without_repeating_on_release(ui):
    app, window, tab, pump = ui
    tab.set_view(1, True); tab.set_zoom(2); tab.goto(0)
    canvas = tab.canvas
    anchor = QPointF(canvas.mapToGlobal(QPoint(330, 280)))
    before = tab.canvas.locate(QPointF(tab.canvas.mapFromGlobal(anchor.toPoint())))
    start = tab.canvas.scale
    class Pinch(QPinchGesture):
        current_state = Qt.GestureUpdated

        def state(self):
            return self.current_state

    pinch = Pinch()
    pinch.setChangeFlags(QPinchGesture.ScaleFactorChanged)
    pinch.setCenterPoint(anchor)
    pinch.setScaleFactor(1.04)
    pinch.setTotalScaleFactor(1.7)
    # Qt's dispatcher drops manually constructed gestures without its private
    # recognizer state, so exercise the widget's handler with a real QGestureEvent.
    assert canvas.event(QGestureEvent([pinch]))
    assert tab.canvas.scale == pytest.approx(start * 1.04)
    scale = tab.canvas.scale
    pinch.current_state = Qt.GestureFinished
    assert tab.scroll.viewportEvent(QGestureEvent([pinch]))
    assert tab.canvas.scale == scale
    after = tab.canvas.locate(QPointF(tab.canvas.mapFromGlobal(anchor.toPoint())))
    assert after[0] == before[0]
    assert (after[1] - before[1]).manhattanLength() < 1.5
