"""Modern PyQt5 user interface."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QDoubleSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import (
    AREA_WEIGHTED,
    NEAREST_NEIGHBOR,
    ConversionRequest,
    DimensionSpec,
    ValidationError,
    VariableSpec,
    convert_to_netcdf,
    inspect_grid,
    read_column_names,
    safe_netcdf_name,
)


APP_STYLE = """
QMainWindow, QScrollArea, QWidget#page {
    background: #F4F7FB;
    color: #172033;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QFrame#card {
    background: #FFFFFF;
    border: 1px solid #DDE5EF;
    border-radius: 12px;
}
QLabel#title { color: #10213A; font-size: 22pt; font-weight: 700; }
QLabel#subtitle { color: #607089; font-size: 10.5pt; }
QLabel#sectionTitle { color: #16243A; font-size: 12.5pt; font-weight: 650; }
QLabel#hint { color: #718096; font-size: 9pt; }
QLabel#badge {
    background: #E8F2FF;
    color: #1457A6;
    border: 1px solid #C8DFFF;
    border-radius: 10px;
    padding: 4px 9px;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#summary {
    background: #F6F9FC;
    color: #42526A;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 8px 10px;
}
QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit {
    background: #FFFFFF;
    color: #172033;
    border: 1px solid #C9D4E2;
    border-radius: 7px;
    padding: 7px 9px;
    min-height: 20px;
    selection-background-color: #2F76D2;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
    border: 1px solid #2F76D2;
}
QPushButton {
    background: #FFFFFF;
    color: #28415F;
    border: 1px solid #C8D4E2;
    border-radius: 7px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover { background: #F1F6FC; border-color: #9CB3CE; }
QPushButton:pressed { background: #E7EEF7; }
QPushButton#primary {
    background: #2167C5;
    color: #FFFFFF;
    border: 1px solid #2167C5;
    padding: 10px 20px;
}
QPushButton#primary:hover { background: #1859AE; }
QPushButton#danger { color: #B42318; border: 0; padding: 5px; font-size: 13pt; }
QPushButton#danger:hover { background: #FFF0EE; }
QProgressBar {
    border: 0;
    background: #E6EDF6;
    border-radius: 3px;
    max-height: 6px;
    text-align: center;
}
QProgressBar::chunk { background: #2F76D2; border-radius: 3px; }
"""


class ConversionWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, request: ConversionRequest) -> None:
        super().__init__()
        self.request = request

    def run(self) -> None:
        try:
            self.finished.emit(convert_to_netcdf(self.request))
        except Exception as exc:  # The worker must always return control to the GUI.
            self.failed.emit(str(exc))


class CompactDoubleSpinBox(QDoubleSpinBox):
    def textFromValue(self, value: float) -> str:
        return f"{value:.6f}".rstrip("0").rstrip(".")


class Card(QFrame):
    def __init__(self, title: str, hint: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 17, 20, 19)
        self.body.setSpacing(11)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        self.body.addWidget(heading)
        if hint:
            helper = QLabel(hint)
            helper.setObjectName("hint")
            helper.setWordWrap(True)
            self.body.addWidget(helper)


class DimensionRow(QWidget):
    def __init__(self, columns: list[str], remove_callback) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.source = QComboBox()
        self.source.addItems(columns)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Output dimension name")
        remove = QPushButton("×")
        remove.setObjectName("danger")
        remove.setFixedWidth(30)
        remove.setToolTip("Remove dimension")
        remove.clicked.connect(lambda: remove_callback(self))
        self.source.currentTextChanged.connect(self._suggest_name)
        layout.addWidget(self.source, 2)
        layout.addWidget(self.name, 2)
        layout.addWidget(remove)
        self._suggest_name(self.source.currentText())

    def _suggest_name(self, value: str) -> None:
        if not self.name.text().strip():
            self.name.setText(safe_netcdf_name(value, "dimension"))


class VariableRow(QWidget):
    def __init__(self, columns: list[str], remove_callback, initial: str = "") -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.source = QComboBox()
        self.source.addItems(columns)
        if initial in columns:
            self.source.setCurrentText(initial)
        self.name = QLineEdit()
        self.name.setPlaceholderText("NetCDF variable name")
        self.units = QLineEdit()
        self.units.setPlaceholderText("Units (optional)")
        remove = QPushButton("×")
        remove.setObjectName("danger")
        remove.setFixedWidth(30)
        remove.setToolTip("Remove variable")
        remove.clicked.connect(lambda: remove_callback(self))
        self.source.currentTextChanged.connect(self._source_changed)
        layout.addWidget(self.source, 2)
        layout.addWidget(self.name, 2)
        layout.addWidget(self.units, 1)
        layout.addWidget(remove)
        self._source_changed(self.source.currentText())

    def _source_changed(self, value: str) -> None:
        if not self.name.text().strip():
            self.name.setText(safe_netcdf_name(value))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.columns: list[str] = []
        self.dimension_rows: list[DimensionRow] = []
        self.variable_rows: list[VariableRow] = []
        self.worker_thread: QThread | None = None
        self.worker: ConversionWorker | None = None
        self.setWindowTitle("NetCDF Grid Interpolator")
        self.resize(1020, 820)
        self.setMinimumSize(760, 620)
        self.setStyleSheet(APP_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        page = QWidget()
        page.setObjectName("page")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(28, 24, 28, 28)
        page_layout.setSpacing(15)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("NetCDF Grid Interpolator")
        title.setObjectName("title")
        subtitle = QLabel(
            "Convert regular Excel or CSV grids to coarser, georeferenced NetCDF files."
        )
        subtitle.setObjectName("subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        badge = QLabel("CF-1.8   WGS84")
        badge.setObjectName("badge")
        header.addWidget(badge, alignment=Qt.AlignTop)
        page_layout.addLayout(header)

        input_card = Card(
            "1. Input data",
            "Choose a CSV or Excel file with one row per grid cell.",
        )
        file_row = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Select an .xlsx, .xls, .csv, or .tsv file")
        browse_input = QPushButton("Browse")
        browse_input.clicked.connect(self._browse_input)
        file_row.addWidget(self.input_path, 1)
        file_row.addWidget(browse_input)
        input_card.body.addLayout(file_row)
        self.input_summary = QLabel("No file loaded")
        self.input_summary.setObjectName("summary")
        input_card.body.addWidget(self.input_summary)
        page_layout.addWidget(input_card)

        mapping_card = Card(
            "2. Grid and dimensions",
            "Select latitude and longitude. Add time, depth, scenario, or another dimension only when present.",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        grid.addWidget(QLabel("Latitude column"), 0, 0)
        grid.addWidget(QLabel("Longitude column"), 0, 1)
        self.latitude_column = QComboBox()
        self.longitude_column = QComboBox()
        grid.addWidget(self.latitude_column, 1, 0)
        grid.addWidget(self.longitude_column, 1, 1)
        self.analyze_button = QPushButton("Analyze grid")
        self.analyze_button.clicked.connect(self._analyze_grid)
        grid.addWidget(self.analyze_button, 1, 2)
        mapping_card.body.addLayout(grid)
        dimension_header = QHBoxLayout()
        dimension_header.addWidget(QLabel("Additional dimensions"))
        dimension_header.addStretch()
        add_dimension = QPushButton("+ Add dimension")
        add_dimension.clicked.connect(self._add_dimension)
        dimension_header.addWidget(add_dimension)
        mapping_card.body.addLayout(dimension_header)
        self.dimension_layout = QVBoxLayout()
        self.dimension_layout.setSpacing(7)
        mapping_card.body.addLayout(self.dimension_layout)
        page_layout.addWidget(mapping_card)

        variable_card = Card(
            "3. Variables",
            "Choose one or more data columns and define the output names and units.",
        )
        variable_header = QHBoxLayout()
        labels = ["Source column", "Output name", "Units"]
        stretches = [2, 2, 1]
        for text, stretch in zip(labels, stretches):
            label = QLabel(text)
            label.setObjectName("hint")
            variable_header.addWidget(label, stretch)
        variable_header.addSpacing(30)
        variable_card.body.addLayout(variable_header)
        self.variable_layout = QVBoxLayout()
        self.variable_layout.setSpacing(7)
        variable_card.body.addLayout(self.variable_layout)
        add_variable = QPushButton("+ Add variable")
        add_variable.clicked.connect(self._add_variable)
        variable_card.body.addWidget(add_variable, alignment=Qt.AlignLeft)
        page_layout.addWidget(variable_card)

        output_card = Card(
            "4. Regridding and output",
            "The output resolution must be strictly coarser than both input axes.",
        )
        output_grid = QGridLayout()
        output_grid.setHorizontalSpacing(12)
        output_grid.setVerticalSpacing(7)
        output_grid.addWidget(QLabel("Method"), 0, 0)
        output_grid.addWidget(QLabel("Output resolution (degrees)"), 0, 1)
        output_grid.addWidget(QLabel("Input missing marker"), 0, 2)
        output_grid.addWidget(QLabel("NetCDF fill value"), 0, 3)
        self.method = QComboBox()
        self.method.addItem("Nearest Neighbor", NEAREST_NEIGHBOR)
        self.method.addItem("Area-weighted average", AREA_WEIGHTED)
        self.output_resolution = CompactDoubleSpinBox()
        self.output_resolution.setDecimals(6)
        self.output_resolution.setRange(0.000001, 180.0)
        self.output_resolution.setSingleStep(0.25)
        self.output_resolution.setValue(15.0)
        self.output_resolution.setSuffix("°")
        self.input_missing = QLineEdit()
        self.input_missing.setPlaceholderText("Optional, e.g. -9999")
        self.output_fill = QLineEdit("-9999")
        output_grid.addWidget(self.method, 1, 0)
        output_grid.addWidget(self.output_resolution, 1, 1)
        output_grid.addWidget(self.input_missing, 1, 2)
        output_grid.addWidget(self.output_fill, 1, 3)
        output_card.body.addLayout(output_grid)
        output_card.body.addWidget(QLabel("Dataset description"))
        self.description = QTextEdit()
        self.description.setPlaceholderText("Describe the dataset, variable, period, or processing purpose")
        self.description.setMaximumHeight(82)
        output_card.body.addWidget(self.description)
        output_card.body.addWidget(QLabel("Output NetCDF file"))
        output_row = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Choose where to save the .nc file")
        browse_output = QPushButton("Browse")
        browse_output.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_path, 1)
        output_row.addWidget(browse_output)
        output_card.body.addLayout(output_row)
        page_layout.addWidget(output_card)

        footer = QHBoxLayout()
        self.status = QLabel("Ready")
        self.status.setObjectName("subtitle")
        footer.addWidget(self.status)
        footer.addStretch()
        self.generate_button = QPushButton("Generate NetCDF")
        self.generate_button.setObjectName("primary")
        self.generate_button.clicked.connect(self._start_conversion)
        footer.addWidget(self.generate_button)
        page_layout.addLayout(footer)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.hide()
        page_layout.addWidget(self.progress)
        page_layout.addItem(QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding))

        scroll.setWidget(page)
        self.setCentralWidget(scroll)

    def _browse_input(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose gridded input data",
            str(Path.cwd()),
            "Tabular data (*.xlsx *.xls *.csv *.tsv)",
        )
        if not filename:
            return
        self.input_path.setText(filename)
        self._load_columns(filename)

    def _browse_output(self) -> None:
        start = self.output_path.text().strip() or str(Path.cwd() / "interpolated.nc")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save NetCDF",
            start,
            "NetCDF files (*.nc)",
        )
        if filename:
            if not filename.lower().endswith(".nc"):
                filename += ".nc"
            self.output_path.setText(filename)

    @staticmethod
    def _find_column(columns: list[str], candidates: tuple[str, ...]) -> str:
        normalized = {column.lower().replace("_", "").replace(" ", ""): column for column in columns}
        for candidate in candidates:
            key = candidate.lower().replace("_", "").replace(" ", "")
            if key in normalized:
                return normalized[key]
        return ""

    def _load_columns(self, filename: str) -> None:
        try:
            columns = read_column_names(filename)
        except ValidationError as exc:
            self._show_error(str(exc))
            return
        self.columns = columns
        self.latitude_column.clear()
        self.longitude_column.clear()
        self.latitude_column.addItems(columns)
        self.longitude_column.addItems(columns)
        latitude = self._find_column(columns, ("latitude", "lat", "y"))
        longitude = self._find_column(columns, ("longitude", "lon", "long", "x"))
        if latitude:
            self.latitude_column.setCurrentText(latitude)
        if longitude:
            self.longitude_column.setCurrentText(longitude)
        elif len(columns) > 1:
            self.longitude_column.setCurrentIndex(1)

        for row in list(self.dimension_rows):
            self._remove_dimension(row)
        for row in list(self.variable_rows):
            self._remove_variable(row)
        coordinate_choices = {self.latitude_column.currentText(), self.longitude_column.currentText()}
        default_variable = next((column for column in columns if column not in coordinate_choices), columns[0])
        self._add_variable(default_variable)
        self.input_summary.setText(f"Loaded {len(columns)} columns. Click Analyze grid to verify spacing and extent.")
        source = Path(filename)
        self.output_path.setText(str(source.with_name(f"{source.stem}_coarse.nc")))
        self.status.setText("Columns loaded")

    def _add_dimension(self) -> None:
        if not self.columns:
            self._show_error("Choose an input file before adding a dimension.")
            return
        row = DimensionRow(self.columns, self._remove_dimension)
        self.dimension_rows.append(row)
        self.dimension_layout.addWidget(row)

    def _remove_dimension(self, row: DimensionRow) -> None:
        if row in self.dimension_rows:
            self.dimension_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def _add_variable(self, initial: str = "") -> None:
        if not self.columns:
            self._show_error("Choose an input file before adding a variable.")
            return
        row = VariableRow(self.columns, self._remove_variable, initial)
        self.variable_rows.append(row)
        self.variable_layout.addWidget(row)

    def _remove_variable(self, row: VariableRow) -> None:
        if row in self.variable_rows:
            self.variable_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def _analyze_grid(self) -> None:
        if not self.input_path.text().strip():
            self._show_error("Choose an input file first.")
            return
        try:
            info = inspect_grid(
                self.input_path.text().strip(),
                self.latitude_column.currentText(),
                self.longitude_column.currentText(),
            )
        except ValidationError as exc:
            self._show_error(str(exc))
            return
        self.input_summary.setText(
            f"{info.row_count:,} rows   |   {info.shape_text}   |   "
            f"Input resolution {info.resolution_text}   |   "
            f"Extent {info.latitude_bounds[0]:g}° to {info.latitude_bounds[1]:g}° latitude, "
            f"{info.longitude_bounds[0]:g}° to {info.longitude_bounds[1]:g}° longitude"
        )
        self.status.setText("Grid validation passed")

    @staticmethod
    def _optional_float(value: str, label: str) -> float | None:
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValidationError(f"{label} must be numeric.") from exc

    def _request(self) -> ConversionRequest:
        input_path = self.input_path.text().strip()
        output_path = self.output_path.text().strip()
        if not input_path:
            raise ValidationError("Choose an input file.")
        if not output_path:
            raise ValidationError("Choose an output NetCDF file.")
        dimensions = tuple(
            DimensionSpec(row.source.currentText(), row.name.text().strip())
            for row in self.dimension_rows
        )
        variables = tuple(
            VariableSpec(
                row.source.currentText(),
                row.name.text().strip(),
                row.units.text().strip(),
            )
            for row in self.variable_rows
        )
        input_missing = self._optional_float(self.input_missing.text(), "Input missing marker")
        output_fill = self._optional_float(self.output_fill.text(), "NetCDF fill value")
        if output_fill is None:
            output_fill = float("nan")
        return ConversionRequest(
            input_path=input_path,
            output_path=output_path,
            latitude_column=self.latitude_column.currentText(),
            longitude_column=self.longitude_column.currentText(),
            dimensions=dimensions,
            variables=variables,
            output_resolution=self.output_resolution.value(),
            method=self.method.currentData(),
            description=self.description.toPlainText().strip(),
            input_missing_value=input_missing,
            output_fill_value=output_fill,
        )

    def _start_conversion(self) -> None:
        try:
            request = self._request()
        except ValidationError as exc:
            self._show_error(str(exc))
            return
        if Path(request.output_path).exists():
            answer = QMessageBox.question(
                self,
                "Replace existing file?",
                f"The output file already exists:\n\n{request.output_path}\n\nReplace it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self._set_busy(True)
        self.status.setText("Reading, validating, and regridding data…")
        self.worker_thread = QThread(self)
        self.worker = ConversionWorker(request)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._conversion_finished)
        self.worker.failed.connect(self._conversion_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _set_busy(self, busy: bool) -> None:
        self.generate_button.setEnabled(not busy)
        self.analyze_button.setEnabled(not busy)
        if busy:
            self.progress.setRange(0, 0)
            self.progress.show()
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)
            self.progress.hide()

    def _conversion_finished(self, result) -> None:
        self._set_busy(False)
        self.status.setText(f"Saved {result.output_path.name}")
        QMessageBox.information(
            self,
            "NetCDF created",
            f"Saved {len(result.variable_names)} variable(s) on a "
            f"{result.output_latitude_count} × {result.output_longitude_count} grid.\n\n"
            f"{result.output_path}",
        )
        self.worker = None
        self.worker_thread = None

    def _conversion_failed(self, message: str) -> None:
        self._set_busy(False)
        self.status.setText("Conversion failed")
        self._show_error(message)
        self.worker = None
        self.worker_thread = None

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Cannot continue", message)

