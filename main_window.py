from __future__ import annotations

import traceback
from io import BytesIO

import keyboard
from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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

PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "custom": {
        "label": "自定义 / OpenAI 兼容",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4.1-mini",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-v4-flash",
    },
    "gemini": {
        "label": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-2.5-flash",
    },
    "kimi": {
        "label": "Kimi",
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "model": "kimi-k2.6",
    },
    "doubao": {
        "label": "豆包",
        "base_url": "https://operator.las.cn-beijing.volces.com/api/v1/chat/completions",
        "model": "doubao-seed-1-6-251015",
    },
}

DEEPSEEK_MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]

KIMI_MODELS = [
    "kimi-k2.6",
    "kimi-k2.6-thinking",
]

DOUBAO_MODELS = [
    "doubao-seed-1-6-251015",
    "doubao-1-5-pro-32k-250115",
]


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


class ConnectionTestWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            client = AIClient(self.config)
            result = client.test_connection()
        except AIClientError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(traceback.format_exc())
        else:
            self.succeeded.emit(result)


class HotkeyManager(QObject):
    show_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._show_hotkey_ref: int | None = None

    def register(self, show_hotkey: str) -> None:
        self.unregister()
        try:
            self._show_hotkey_ref = keyboard.add_hotkey(
                show_hotkey,
                lambda: self.show_requested.emit(),
            )
        except Exception as exc:
            raise RuntimeError(f"注册显示窗口热键失败: {exc}") from exc

    def unregister(self) -> None:
        if self._show_hotkey_ref is not None:
            keyboard.remove_hotkey(self._show_hotkey_ref)
            self._show_hotkey_ref = None


class MainWindow(QMainWindow):
    def __init__(self, config_store: ConfigStore) -> None:
        super().__init__()
        self.config_store = config_store
        self.config = self._normalize_config(config_store.config)
        self.worker: RequestWorker | None = None
        self.connection_test_worker: ConnectionTestWorker | None = None
        self.pending_payload: ClipboardPayload | None = None
        self._should_exit = False
        self.startup_error_message: str | None = None
        self._updating_provider_fields = False
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(700)

        self.setWindowTitle("Clipboard AI Assistant")
        self.resize(1000, 780)

        self.status_label = QLabel("后台监听中")
        self.preview_label = QLabel("尚未捕获内容")
        self.preview_label.setWordWrap(True)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.image_label = QLabel("当前内容不是图片")
        self.image_label.setMinimumHeight(240)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #d0d0d0; background: #fafafa;")

        self.answer_box = QPlainTextEdit()
        self.answer_box.setReadOnly(True)

        self.provider_input = QComboBox()
        for provider_key, provider_info in PROVIDER_PRESETS.items():
            self.provider_input.addItem(provider_info["label"], provider_key)
        self.provider_input.setCurrentIndex(
            max(0, self.provider_input.findData(self.config.provider))
        )

        self.base_url_input = QLineEdit(self.config.base_url)
        self.api_key_input = QLineEdit(self.config.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.show_window_hotkey_input = QLineEdit(self.config.show_window_hotkey)
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
            "程序默认后台静默启动。\n"
            "复制文本或图片到剪贴板后会自动发送请求。\n"
            "服务商支持自定义 OpenAI 兼容接口、DeepSeek、Gemini、Kimi 和豆包。\n"
            "可在设置页修改显示窗口热键，并点击“测试 API 连接”验证当前配置。"
        )
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet(
            "padding: 10px; border: 1px solid #d8d8d8; background: #f7f7f7;"
        )

        self.save_button = QPushButton("保存设置")
        self.test_connection_button = QPushButton("测试 API 连接")
        self.apply_provider_button = QPushButton("应用服务商预设")
        self.reset_hotkey_button = QPushButton("恢复默认快捷键")
        self.exit_button = QPushButton("退出程序")

        self.clipboard_service = ClipboardService(application_clipboard())
        self.hotkey_manager = HotkeyManager()

        self._build_ui()
        self._populate_model_options(self.config.provider, self.config.model)
        self._bind_events()

        try:
            self._register_hotkeys(self.config)
        except RuntimeError:
            pass

        if self.startup_error_message:
            QTimer.singleShot(0, self._show_startup_error)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._should_exit:
            self._persist_form_settings(apply_hotkey=False)
            self.hotkey_manager.unregister()
            super().closeEvent(event)
            return

        event.ignore()
        self.hide_to_background()

    def _build_ui(self) -> None:
        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.addWidget(QLabel("状态:"))
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.exit_button)

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
        form.addRow("服务商", self.provider_input)
        form.addRow("Base URL", self.base_url_input)
        form.addRow("API Key", self.api_key_input)
        form.addRow("Model", self.model_input)
        form.addRow("显示窗口热键", self.show_window_hotkey_input)
        form.addRow("Temperature", self.temperature_input)
        form.addRow("Timeout (s)", self.timeout_input)
        form.addRow("System Prompt", self.system_prompt_input)
        form.addRow("关键词", self.keywords_input)

        action_row = QWidget()
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addWidget(self.save_button)
        action_layout.addWidget(self.test_connection_button)
        action_layout.addWidget(self.apply_provider_button)
        action_layout.addWidget(self.reset_hotkey_button)
        action_layout.addStretch(1)

        settings_layout.addWidget(self.help_label)
        settings_layout.addLayout(form)
        settings_layout.addWidget(action_row)

        tabs = QTabWidget()
        tabs.addTab(content_tab, "监听")
        tabs.addTab(settings_tab, "设置")
        self.setCentralWidget(tabs)

    def _bind_events(self) -> None:
        self.clipboard_service.payload_captured.connect(self._handle_payload_captured)
        self.clipboard_service.status_changed.connect(self.status_label.setText)
        self.save_button.clicked.connect(self._save_settings)
        self.test_connection_button.clicked.connect(self._test_connection)
        self.apply_provider_button.clicked.connect(self._apply_selected_provider_preset)
        self.reset_hotkey_button.clicked.connect(self._reset_default_hotkey)
        self.exit_button.clicked.connect(self.quit_application)
        self.hotkey_manager.show_requested.connect(self.show_window)
        self.provider_input.currentIndexChanged.connect(self._handle_provider_changed)
        self._auto_save_timer.timeout.connect(self._auto_save_settings)

        self.provider_input.currentIndexChanged.connect(self._schedule_auto_save)
        self.base_url_input.textChanged.connect(self._schedule_auto_save)
        self.api_key_input.textChanged.connect(self._schedule_auto_save)
        self.model_input.currentTextChanged.connect(self._schedule_auto_save)
        self.show_window_hotkey_input.textChanged.connect(self._schedule_auto_save)
        self.temperature_input.valueChanged.connect(self._schedule_auto_save)
        self.timeout_input.valueChanged.connect(self._schedule_auto_save)
        self.system_prompt_input.textChanged.connect(self._schedule_auto_save)
        self.keywords_input.textChanged.connect(self._schedule_auto_save)

    def _normalize_config(self, config: AppConfig) -> AppConfig:
        provider = config.provider if config.provider in PROVIDER_PRESETS else "custom"
        return AppConfig(
            provider=provider,
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            show_window_hotkey=config.show_window_hotkey or "ctrl+shift+s",
            system_prompt=config.system_prompt,
            request_timeout=config.request_timeout,
            temperature=config.temperature,
            keywords=config.keywords,
        )

    def _current_provider(self) -> str:
        provider = self.provider_input.currentData()
        if not isinstance(provider, str):
            return "custom"
        return provider

    def _populate_model_options(self, provider: str, selected_model: str) -> None:
        current_text = selected_model.strip()
        self.model_input.blockSignals(True)
        self.model_input.clear()
        if provider == "deepseek":
            self.model_input.addItems(DEEPSEEK_MODELS)
        elif provider == "gemini":
            self.model_input.addItems(GEMINI_MODELS)
        elif provider == "kimi":
            self.model_input.addItems(KIMI_MODELS)
        elif provider == "doubao":
            self.model_input.addItems(DOUBAO_MODELS)
        if current_text and self.model_input.findText(current_text) == -1:
            self.model_input.addItem(current_text)
        self.model_input.setCurrentText(current_text)
        self.model_input.blockSignals(False)

    def _handle_provider_changed(self) -> None:
        if self._updating_provider_fields:
            return
        provider = self._current_provider()
        self._populate_model_options(provider, self.model_input.currentText())

    def _apply_selected_provider_preset(self) -> None:
        provider = self._current_provider()
        preset = PROVIDER_PRESETS.get(provider)
        if preset is None:
            return

        self._updating_provider_fields = True
        self.base_url_input.setText(preset["base_url"])
        self._populate_model_options(provider, preset["model"])
        self._updating_provider_fields = False
        self.status_label.setText("已应用服务商预设")
        self._schedule_auto_save()

    def _reset_default_hotkey(self) -> None:
        self.show_window_hotkey_input.setText("ctrl+shift+s")
        self.status_label.setText("已恢复默认快捷键")
        self._schedule_auto_save()

    def _build_config_from_form(self) -> AppConfig:
        return AppConfig(
            provider=self._current_provider(),
            base_url=self.base_url_input.text().strip(),
            api_key=self.api_key_input.text().strip(),
            model=self.model_input.currentText().strip(),
            show_window_hotkey=self.show_window_hotkey_input.text().strip().lower(),
            system_prompt=self.system_prompt_input.toPlainText().strip(),
            request_timeout=self.timeout_input.value(),
            temperature=self.temperature_input.value(),
            keywords=self._parse_keywords(),
        )

    def _save_settings(self) -> None:
        config = self._build_config_from_form()
        error_message = self._validate_hotkeys(config)
        if error_message:
            self.status_label.setText("失败")
            QMessageBox.warning(self, "热键配置错误", error_message)
            return

        try:
            self._register_hotkeys(config)
        except RuntimeError as exc:
            self.status_label.setText("失败")
            QMessageBox.critical(self, "热键错误", str(exc))
            return

        self.config_store.save(config)
        self.config = config
        self._auto_save_timer.stop()
        self.status_label.setText("后台监听中")
        QMessageBox.information(self, "设置已保存", "配置已保存并重新加载。")

        latest_payload = self.clipboard_service.current_payload
        if latest_payload is not None:
            self._schedule_payload(latest_payload)

    def _test_connection(self) -> None:
        if self.connection_test_worker and self.connection_test_worker.isRunning():
            return

        config = self._build_config_from_form()
        error_message = self._validate_hotkeys(config)
        if error_message:
            self.status_label.setText("失败")
            QMessageBox.warning(self, "热键配置错误", error_message)
            return

        if not config.base_url:
            self.status_label.setText("失败")
            QMessageBox.warning(self, "配置不完整", "请先填写 Base URL。")
            return
        if not config.api_key:
            self.status_label.setText("失败")
            QMessageBox.warning(self, "配置不完整", "请先填写 API Key。")
            return
        if not config.model:
            self.status_label.setText("失败")
            QMessageBox.warning(self, "配置不完整", "请先填写 Model。")
            return

        self.status_label.setText("正在测试 API 连接")
        self.test_connection_button.setEnabled(False)
        self.connection_test_worker = ConnectionTestWorker(config)
        self.connection_test_worker.succeeded.connect(self._handle_test_success)
        self.connection_test_worker.failed.connect(self._handle_test_failure)
        self.connection_test_worker.finished.connect(self._cleanup_connection_test_worker)
        self.connection_test_worker.start()

    def _handle_test_success(self, message: str) -> None:
        self.status_label.setText("API 连接成功")
        QMessageBox.information(self, "连接成功", f"API 可用。\n\n返回内容：\n{message}")

    def _handle_test_failure(self, message: str) -> None:
        self.status_label.setText("API 连接失败")
        QMessageBox.critical(self, "连接失败", message)

    def _cleanup_connection_test_worker(self) -> None:
        self.test_connection_button.setEnabled(True)
        self.connection_test_worker = None

    def _schedule_auto_save(self) -> None:
        self._auto_save_timer.start()

    def _auto_save_settings(self) -> None:
        self._persist_form_settings(apply_hotkey=False)

    def _persist_form_settings(self, apply_hotkey: bool) -> None:
        config = self._build_config_from_form()

        if self._validate_hotkeys(config):
            config = AppConfig(
                provider=config.provider,
                base_url=config.base_url,
                api_key=config.api_key,
                model=config.model,
                show_window_hotkey=self.config.show_window_hotkey,
                system_prompt=config.system_prompt,
                request_timeout=config.request_timeout,
                temperature=config.temperature,
                keywords=config.keywords,
            )
        elif apply_hotkey:
            self._register_hotkeys(config)

        self.config_store.save(config)
        self.config = config

    def _validate_hotkeys(self, config: AppConfig) -> str | None:
        if not config.show_window_hotkey:
            return "显示窗口热键不能为空。"
        return None

    def _register_hotkeys(self, config: AppConfig) -> None:
        error_message = self._validate_hotkeys(config)
        if error_message:
            raise RuntimeError(error_message)

        try:
            self.hotkey_manager.register(show_hotkey=config.show_window_hotkey)
        except RuntimeError as exc:
            self.startup_error_message = str(exc)
            self.show_window()
            raise
        else:
            self.startup_error_message = None

    def _show_startup_error(self) -> None:
        self.show_window()
        QMessageBox.critical(self, "启动失败", self.startup_error_message or "热键注册失败。")

    def show_window(self) -> None:
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.status_label.setText("窗口已显示")

    def hide_to_background(self) -> None:
        self._persist_form_settings(apply_hotkey=False)
        self.hide()
        self.status_label.setText("后台监听中")

    def quit_application(self) -> None:
        self._should_exit = True
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _handle_payload_captured(self, payload: ClipboardPayload) -> None:
        self._update_preview(payload)
        self._schedule_payload(payload)

    def _schedule_payload(self, payload: ClipboardPayload) -> None:
        self.pending_payload = payload
        if self.worker and self.worker.isRunning():
            self.status_label.setText("检测到新内容，当前请求完成后自动发送")
            return
        self._trigger_next_payload()

    def _trigger_next_payload(self) -> None:
        payload = self.pending_payload
        self.pending_payload = None
        if payload is None:
            return

        if not self.config.api_key:
            self.status_label.setText("已捕获内容，但 API Key 未配置")
            return

        if not self._can_send_payload(payload):
            self.status_label.setText("已捕获内容，但未命中关键词，未发送")
            return

        self.status_label.setText("请求中")
        self.worker = RequestWorker(self.config, payload)
        self.worker.succeeded.connect(self._handle_success)
        self.worker.failed.connect(self._handle_failure)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

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

    def _handle_success(self, answer: str) -> None:
        self.answer_box.setPlainText(answer)
        self.clipboard_service.write_answer_to_clipboard(answer)
        self.status_label.setText("成功")

    def _handle_failure(self, message: str) -> None:
        self.answer_box.setPlainText(message)
        self.status_label.setText("失败")
        if self.isVisible():
            QMessageBox.critical(self, "请求失败", message)

    def _cleanup_worker(self) -> None:
        self.worker = None
        if self.pending_payload is not None:
            QTimer.singleShot(0, self._trigger_next_payload)

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
