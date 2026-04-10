from __future__ import annotations

import traceback
from io import BytesIO

import keyboard
from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai_client import AIClient, AIClientError
from clipboard_service import ClipboardService, application_clipboard
from config import ConfigStore
from models import AppConfig, ClipboardPayload


class RequestWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, config: AppConfig, payload: ClipboardPayload) -> None:
        super().__init__()
        self.config = config
        self.payload = payload

    def run(self) -> None:
        try:
            client = AIClient(self.config)
            if self.payload.kind == "text":
                answer = client.ask_text(self.payload)
            else:
                answer = client.ask_image(self.payload)
        except AIClientError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(traceback.format_exc())
        else:
            self.succeeded.emit(answer)


class HotkeyManager(QObject):
    activated = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._registered_hotkey: str | None = None

    def register(self, hotkey: str) -> None:
        self.unregister()
        try:
            keyboard.add_hotkey(hotkey, self.activated.emit)
        except Exception as exc:
            raise RuntimeError(f"注册全局热键失败: {exc}") from exc
        self._registered_hotkey = hotkey

    def unregister(self) -> None:
        if self._registered_hotkey:
            keyboard.remove_hotkey(self._registered_hotkey)
            self._registered_hotkey = None


class MainWindow(QMainWindow):
    def __init__(self, config_store: ConfigStore) -> None:
        super().__init__()
        self.config_store = config_store
        self.config = config_store.config
        self.worker: RequestWorker | None = None

        self.setWindowTitle("Clipboard AI Assistant")
        self.resize(980, 760)

        self.status_label = QLabel("监听中")
        self.preview_label = QLabel("尚未捕获内容")
        self.preview_label.setWordWrap(True)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.image_label = QLabel("当前内容不是图片")
        self.image_label.setMinimumHeight(240)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #d0d0d0; background: #fafafa;")

        self.answer_box = QPlainTextEdit()
        self.answer_box.setReadOnly(True)

        self.base_url_input = QLineEdit(self.config.base_url)
        self.api_key_input = QLineEdit(self.config.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.model_input = QLineEdit(self.config.model)
        self.hotkey_input = QLineEdit(self.config.global_hotkey)
        self.system_prompt_input = QPlainTextEdit(self.config.system_prompt)

        self.temperature_input = QDoubleSpinBox()
        self.temperature_input.setRange(0.0, 2.0)
        self.temperature_input.setDecimals(1)
        self.temperature_input.setSingleStep(0.1)
        self.temperature_input.setValue(self.config.temperature)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 600)
        self.timeout_input.setValue(self.config.request_timeout)

        self.keywords_input = QPlainTextEdit("\n".join(self.config.keywords))
        self.keywords_input.setPlaceholderText("每行输入一个关键词")

        self.help_label = QLabel(
            "URL：AI 接口地址\n"
            "Hotkey：全局快捷键\n"
            "Temperature：回答随机度\n"
            "关键词：每行一个，同时用于本地过滤和提示词增强"
        )
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet(
            "padding: 10px; border: 1px solid #d8d8d8; background: #f7f7f7;"
        )

        self.save_button = QPushButton("保存设置")
        self.send_button = QPushButton("立即发送")

        self.clipboard_service = ClipboardService(application_clipboard())
        self.hotkey_manager = HotkeyManager()

        self._build_ui()
        self._bind_events()
        self._register_hotkey(self.config.global_hotkey)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.hotkey_manager.unregister()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.addWidget(QLabel("状态:"))
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.send_button)

        preview_box = QGroupBox("最近捕获内容")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.image_label)

        answer_box = QGroupBox("最近答案")
        answer_layout = QVBoxLayout(answer_box)
        answer_layout.addWidget(self.answer_box)

        content_tab = QWidget()
        content_layout = QVBoxLayout(content_tab)
        content_layout.addWidget(status_row)
        content_layout.addWidget(preview_box)
        content_layout.addWidget(answer_box)

        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        form = QFormLayout()
        form.addRow("Base URL", self.base_url_input)
        form.addRow("API Key", self.api_key_input)
        form.addRow("Model", self.model_input)
        form.addRow("Global Hotkey", self.hotkey_input)
        form.addRow("Temperature", self.temperature_input)
        form.addRow("Timeout (s)", self.timeout_input)
        form.addRow("System Prompt", self.system_prompt_input)
        form.addRow("关键词", self.keywords_input)

        settings_layout.addWidget(self.help_label)
        settings_layout.addLayout(form)
        settings_layout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignLeft)

        tabs = QTabWidget()
        tabs.addTab(content_tab, "监听")
        tabs.addTab(settings_tab, "设置")
        self.setCentralWidget(tabs)

    def _bind_events(self) -> None:
        self.clipboard_service.payload_captured.connect(self._update_preview)
        self.clipboard_service.status_changed.connect(self.status_label.setText)
        self.save_button.clicked.connect(self._save_settings)
        self.send_button.clicked.connect(self._trigger_request)
        self.hotkey_manager.activated.connect(self._trigger_request)

    def _save_settings(self) -> None:
        config = AppConfig(
            base_url=self.base_url_input.text().strip(),
            api_key=self.api_key_input.text().strip(),
            model=self.model_input.text().strip(),
            global_hotkey=self.hotkey_input.text().strip().lower(),
            system_prompt=self.system_prompt_input.toPlainText().strip(),
            request_timeout=self.timeout_input.value(),
            temperature=self.temperature_input.value(),
            keywords=self._parse_keywords(),
        )

        try:
            self._register_hotkey(config.global_hotkey)
        except RuntimeError as exc:
            self.status_label.setText("失败")
            QMessageBox.critical(self, "热键错误", str(exc))
            return

        self.config_store.save(config)
        self.config = config
        self.status_label.setText("监听中")
        QMessageBox.information(self, "设置已保存", "配置已保存并重新加载。")

    def _register_hotkey(self, hotkey: str) -> None:
        self.hotkey_manager.register(hotkey)

    def _update_preview(self, payload: ClipboardPayload) -> None:
        timestamp = payload.captured_at.strftime("%H:%M:%S")
        if payload.kind == "text":
            preview = payload.text or ""
            self.preview_label.setText(f"[{timestamp}] 文本\n\n{preview[:2000]}")
            self.image_label.clear()
            self.image_label.setText("当前内容不是图片")
            return

        self.preview_label.setText(f"[{timestamp}] 图片\n\n已捕获图片，发送时会直接走视觉接口。")
        self.image_label.setPixmap(QPixmap())
        if payload.image_bytes:
            pixmap = self._pixmap_from_bytes(payload.image_bytes)
            scaled = pixmap.scaled(
                480,
                280,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)

    def _trigger_request(self) -> None:
        if self.worker and self.worker.isRunning():
            return

        payload = self.clipboard_service.current_payload
        if payload is None:
            self.status_label.setText("失败")
            QMessageBox.warning(self, "无法发送", "当前没有可发送的剪贴板内容。")
            return

        if not self.config.api_key:
            self.status_label.setText("失败")
            QMessageBox.warning(self, "配置不完整", "请先在设置中填写 API Key。")
            return

        if not self._can_send_payload(payload):
            self.status_label.setText("失败")
            QMessageBox.warning(
                self,
                "关键词未命中",
                "当前文本未命中任一关键词，因此不会发送请求。",
            )
            return

        self.status_label.setText("请求中")
        self.worker = RequestWorker(self.config, payload)
        self.worker.succeeded.connect(self._handle_success)
        self.worker.failed.connect(self._handle_failure)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

    def _handle_success(self, answer: str) -> None:
        self.answer_box.setPlainText(answer)
        self.clipboard_service.write_answer_to_clipboard(answer)
        self.status_label.setText("成功")

    def _handle_failure(self, message: str) -> None:
        self.answer_box.setPlainText(message)
        self.status_label.setText("失败")
        QMessageBox.critical(self, "请求失败", message)

    def _cleanup_worker(self) -> None:
        self.worker = None

    def _parse_keywords(self) -> list[str]:
        keywords: list[str] = []
        seen: set[str] = set()
        for raw_line in self.keywords_input.toPlainText().splitlines():
            item = raw_line.strip()
            if not item:
                continue
            lowered = item.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            keywords.append(item)
        return keywords

    def _can_send_payload(self, payload: ClipboardPayload) -> bool:
        if payload.kind != "text":
            return True
        if not self.config.keywords:
            return True
        if not payload.text:
            return False

        text = payload.text.casefold()
        return any(keyword.casefold() in text for keyword in self.config.keywords)

    @staticmethod
    def _pixmap_from_bytes(image_bytes: bytes) -> QPixmap:
        image = Image.open(BytesIO(image_bytes))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue(), "PNG")
        return pixmap
