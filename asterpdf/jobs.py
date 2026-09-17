from __future__ import annotations
import traceback
from contextlib import nullcontext
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from .core import ENGINE_LOCK


class Signals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, int)
    finished = Signal()


class Job(QRunnable):
    def __init__(self, function, engine=True):
        super().__init__()
        self.function = function
        self.engine = engine
        self.signals = Signals()
        self.cancelled = False

    @Slot()
    def run(self):
        try:
            with ENGINE_LOCK if self.engine else nullcontext():
                if not self.cancelled:
                    result = self.function(self)
                    self.signals.result.emit(result)
        except Exception as e:
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class Queue(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.jobs = set()

    def submit(self, function, result=None, error=None, finished=None, progress=None, priority=0, engine=True):
        job = Job(function,engine)
        self.jobs.add(job)
        job.connections=[]
        if result:
            job.signals.result.connect(result);job.connections.append('result')
        if error:
            job.signals.error.connect(error);job.connections.append('error')
        if finished:
            job.signals.finished.connect(finished);job.connections.append('finished')
        if progress:
            job.signals.progress.connect(progress);job.connections.append('progress')
        job.signals.finished.connect(lambda:self.retire(job))
        self.pool.start(job, priority)
        return job

    def retire(self,job):
        self.jobs.discard(job)
        job.function=None
        for name in set(job.connections+['finished']):
            try:getattr(job.signals,name).disconnect()
            except RuntimeError:pass
        job.signals.deleteLater()
