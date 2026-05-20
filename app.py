from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from config import ConfigStore
from main_window import MainWindow
from single_instance import AcquireResult, SingleInstanceController


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Clipboard AI Assistant")
    app.setQuitOnLastWindowClosed(False)

    instance_controller = SingleInstanceController("ClipboardAIAssistantSingleton")
    acquire_result = instance_controller.acquire()
    if acquire_result is AcquireResult.NOTIFIED_EXISTING:
        return 0
    if acquire_result is AcquireResult.ERROR:
        QMessageBox.critical(
            None,
            "启动失败",
            f"无法创建单实例服务：{instance_controller.error_message or '未知错误'}",
        )
        return 1

    config_store = ConfigStore()
    window = MainWindow(config_store)
    instance_controller.show_requested.connect(window.show_window)

    if window.startup_error_message:
        window.show_window()
    else:
        QTimer.singleShot(0, window.hide_to_background)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
