from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app.main_window import MainWindow


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_EXCEL = PROJECT_ROOT / "sample_data" / "input_global_3.75deg.xlsx"


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_window_loads_sample_columns_and_methods(self) -> None:
        window = MainWindow()
        try:
            window.input_path.setText(str(SAMPLE_EXCEL))
            window._load_columns(str(SAMPLE_EXCEL))
            self.assertEqual(window.latitude_column.currentText(), "latitude")
            self.assertEqual(window.longitude_column.currentText(), "longitude")
            self.assertEqual(window.method.count(), 2)
            self.assertEqual(window.variable_rows[0].source.currentText(), "temperature_c")
            self.assertTrue(window.output_path.text().endswith("_coarse.nc"))
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
