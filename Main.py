"""Application entry point."""

from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("NetCDF Grid Interpolator")
    application.setOrganizationName("Open Science Tools")
    window = MainWindow()
    window.show()
    return application.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
