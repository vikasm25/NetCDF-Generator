from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_launcher_checks_installs_and_reports_missing_python(self) -> None:
        launcher = (PROJECT_ROOT / "Run App.bat").read_text(encoding="utf-8")
        self.assertIn("where python", launcher)
        self.assertIn("import PyQt5, numpy, pandas, xarray, netCDF4, openpyxl, xlrd", launcher)
        self.assertIn('python -m pip install -r "%~dp0Requirements.txt"', launcher)
        self.assertIn("Python is not installed", launcher)
        self.assertIn("pause", launcher)
        self.assertNotIn(".venv\\Scripts", launcher)


if __name__ == "__main__":
    unittest.main()
