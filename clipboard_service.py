from __future__ import annotations

import hashlib
from datetime import datetime
from io import BytesIO

from PIL import Image
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QClipboard, QGuiApplication, QImage

from models import ClipboardPayload


class ClipboardService(QObject):
    payload_captured = Signal(object)
    status_changed = Signal(str)

    def __init__(self, clipboard: QClipboard) -> None:
        super().__init__()
        self.clipboard = clipboard
        self.current_payload: ClipboardPayload | None = None
        self._ignore_hashes: set[str] = set()
        self._last_seen_hash: str | None = None
        self.clipboard.dataChanged.connect(self._handle_clipboard_change)

    def _handle_clipboard_change(self) -> None:
        payload = self._extract_payload()
        if payload is None:
            return

        if payload.source_hash in self._ignore_hashes:
            self._ignore_hashes.remove(payload.source_hash)
            return

        if payload.source_hash == self._last_seen_hash:
            return

        self._last_seen_hash = payload.source_hash
        self.current_payload = payload
        if payload.kind == "text":
            self.status_changed.emit("已捕获文本")
        else:
            self.status_changed.emit("已捕获图片")
        self.payload_captured.emit(payload)

    def _extract_payload(self) -> ClipboardPayload | None:
        mime_data = self.clipboard.mimeData()
        if mime_data is None:
            return None

        text = self.clipboard.text().strip()
        if text:
            digest = self._hash_bytes(text.encode("utf-8"))
            return ClipboardPayload(
                kind="text",
                text=text,
                source_hash=digest,
                captured_at=datetime.now(),
            )

        image = self.clipboard.image()
        if image.isNull():
            return None

        image_bytes = self._qimage_to_png_bytes(image)
        digest = self._hash_bytes(image_bytes)
        return ClipboardPayload(
            kind="image",
            image_bytes=image_bytes,
            source_hash=digest,
            captured_at=datetime.now(),
        )

    def write_answer_to_clipboard(self, answer: str) -> None:
        digest = self._hash_bytes(answer.encode("utf-8"))
        self._ignore_hashes.add(digest)
        self.clipboard.setText(answer)

    @staticmethod
    def _qimage_to_png_bytes(image: QImage) -> bytes:
        buffer = BytesIO()
        pil_image = Image.fromqimage(image)
        pil_image.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _hash_bytes(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


def application_clipboard() -> QClipboard:
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        raise RuntimeError("无法访问系统剪贴板。")
    return clipboard
