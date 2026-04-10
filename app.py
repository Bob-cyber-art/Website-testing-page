from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from config import ConfigStore
from main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Clipboard AI Assistant")

    config_store = ConfigStore()
    window = MainWindow(config_store)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
