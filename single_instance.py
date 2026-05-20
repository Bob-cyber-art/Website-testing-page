from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class AcquireResult(str, Enum):
    PRIMARY = "primary"
    NOTIFIED_EXISTING = "notified_existing"
    ERROR = "error"


class SingleInstanceController(QObject):
    show_requested = Signal()

    def __init__(self, server_name: str) -> None:
        super().__init__()
        self.server_name = server_name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._handle_new_connection)
        self.error_message: str | None = None

    def acquire(self) -> AcquireResult:
        if self._notify_existing_instance():
            return AcquireResult.NOTIFIED_EXISTING

        QLocalServer.removeServer(self.server_name)
        if self.server.listen(self.server_name):
            return AcquireResult.PRIMARY

        self.error_message = self.server.errorString()
        return AcquireResult.ERROR

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket(self)
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(300):
            return False

        socket.write(b"SHOW")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True

    def _handle_new_connection(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None:
            return

        socket.waitForReadyRead(300)
        message = bytes(socket.readAll()).decode("utf-8", errors="ignore").strip()
        socket.disconnectFromServer()
        socket.deleteLater()

        if message == "SHOW":
            self.show_requested.emit()
