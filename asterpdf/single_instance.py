"""Per-user, per-profile local file-open forwarding. No network listener."""
from pathlib import Path
import hashlib
import json
import os
import stat
import time

from PySide6.QtCore import QObject, QLockFile, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


MAX_REQUEST = 1024 * 1024


class DesktopInstance(QObject):
    requested = Signal(object)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        profile = Path(profile).resolve()
        key = hashlib.sha256(os.path.normcase(str(profile)).encode()).hexdigest()[:24]
        if os.name == 'nt':
            directory = profile / 'ipc'
            self.address = 'AsterPDF-' + key
        else:
            # macOS ignores socket mode bits. Protect the containing directory;
            # keep its path short enough for sockaddr_un on both Unix platforms.
            directory = Path('/tmp') / f'asterpdf-{os.getuid()}'
            self.address = str(directory / (key + '.sock'))
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        status = directory.lstat()
        if not stat.S_ISDIR(status.st_mode) or (os.name != 'nt' and status.st_uid != os.getuid()):
            raise OSError('AsterPDF command directory is not owned by this user.')
        if os.name != 'nt':
            directory.chmod(0o700)
        self.lock = QLockFile(str(directory / (key + '.lock')))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self.accept_connections)
        self.pending = []
        self.receiver = None
        self.owner = False

    def acquire(self, filenames, timeout=15):
        """Return True for the owner; False only after an existing owner ACKs."""
        request = json.dumps({'version': 1, 'files': filenames}, ensure_ascii=False).encode() + b'\n'
        if len(request) > MAX_REQUEST:
            raise ValueError('Too many filenames in one command.')
        deadline = time.monotonic() + timeout
        while True:
            if self.lock.tryLock(0):
                # Only the lock owner may remove a socket left by a crashed app.
                QLocalServer.removeServer(self.address)
                if not self.server.listen(self.address):
                    self.lock.unlock()
                    raise OSError(self.server.errorString())
                self.owner = True
                return True
            socket = QLocalSocket()
            socket.connectToServer(self.address)
            if socket.waitForConnected(150):
                socket.write(request)
                if socket.bytesToWrite():
                    socket.waitForBytesWritten(1000)
                reply = bytearray()
                while time.monotonic() < deadline:
                    if socket.bytesAvailable() or socket.waitForReadyRead(200):
                        reply.extend(bytes(socket.readAll()))
                        if b'\n' in reply:
                            socket.disconnectFromServer()
                            if reply == b'OK\n':
                                return False
                            raise OSError('The open AsterPDF window rejected this request.')
                    if socket.state() == QLocalSocket.UnconnectedState:
                        break
                socket.abort()
            if time.monotonic() >= deadline:
                raise OSError('The existing AsterPDF window is busy. Please retry in a moment.')
            time.sleep(.05)

    def accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.setReadBufferSize(MAX_REQUEST + 1)
            buffer = bytearray()
            timer = QTimer(socket)
            timer.setSingleShot(True)
            timer.timeout.connect(socket.abort)
            timer.start(15000)

            def receive(socket=socket, buffer=buffer, timer=timer):
                buffer.extend(bytes(socket.readAll()))
                if len(buffer) > MAX_REQUEST:
                    socket.abort()
                    return
                if b'\n' not in buffer:
                    return
                timer.stop()
                try:
                    message = json.loads(buffer)
                    filenames = message['files']
                    if message.get('version') != 1 or not isinstance(filenames, list) or len(filenames) > 512:
                        raise ValueError('Invalid request')
                    if any(not isinstance(p, str) or not Path(p).is_absolute() or '\0' in p for p in filenames):
                        raise ValueError('Invalid filename')
                except (ValueError, KeyError, TypeError):
                    socket.write(b'ERROR\n')
                else:
                    self.pending.append(filenames)
                    socket.write(b'OK\n')
                    QTimer.singleShot(0, self.deliver)
                socket.disconnectFromServer()

            socket.readyRead.connect(receive)
            socket.disconnected.connect(socket.deleteLater)
            receive()

    def bind(self, receiver):
        self.receiver = receiver
        self.deliver()

    def deliver(self):
        if self.receiver:
            pending, self.pending = self.pending, []
            for filenames in pending:
                self.receiver(filenames)
                self.requested.emit(filenames)

    def close(self):
        if self.owner:
            self.server.close()
            self.lock.unlock()
            self.owner = False
