"""Sovelluksen käynnistys."""

from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import APP_NAME, MainWindow
    from .ui.theme import apply_theme

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    apply_theme(app)
    win = MainWindow()
    win.show()
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".xml"):
        win.open_library(sys.argv[1])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
