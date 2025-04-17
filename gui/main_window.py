import numpy as np
import pandas as pd
import xarray as xr
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QSpinBox,
    QVBoxLayout, QHBoxLayout, QLineEdit, QFormLayout, QComboBox,
    QMessageBox, QGroupBox, QGridLayout, QMenuBar, 
    QAction, QDialog, QTextEdit, QScrollArea)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from gui.about_dialog import AboutDialog
from utils.themes import THEMES

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.df = None
        self.extra_dim_widgets = []
        self.variable_widgets = []
        self.current_theme = "oceanic"
        self.themes = THEMES
        self.init_ui()
        self.apply_theme(self.themes[self.current_theme])

    def init_ui(self):
        self.setWindowTitle("NetCDF Generator Pro")
        self.setFixedSize(1100, 850)

        # Menu bar with theme switching
        menubar = QMenuBar()
        theme_menu = menubar.addMenu("🎨 Theme")
        
        self.light_action = QAction("Light Theme", self)
        self.light_action.triggered.connect(lambda: self.toggle_theme("light"))
        theme_menu.addAction(self.light_action)
        
        self.dark_action = QAction("Dark Theme", self)
        self.dark_action.triggered.connect(lambda: self.toggle_theme("dark"))
        theme_menu.addAction(self.dark_action)

        self.oceanic_action = QAction("Oceanic Theme", self)
        self.oceanic_action.triggered.connect(lambda: self.toggle_theme("oceanic"))
        theme_menu.addAction(self.oceanic_action)

        main_layout = QVBoxLayout()
        main_layout.setMenuBar(menubar)

        # File selection section
        file_btn = QPushButton("📂 Open Data File")
        file_btn.clicked.connect(self.load_file)
        self.file_label = QLabel("No file selected")
        self.file_label.setWordWrap(True)

        # Dimensions controls
        dim_layout = QHBoxLayout()
        dim_layout.addWidget(QLabel("📏 Total Dimensions:"))
        self.dim_spin = QSpinBox()
        self.dim_spin.setMinimum(2)
        self.dim_spin.setMaximum(10)
        self.dim_spin.valueChanged.connect(self.update_dimensions)
        dim_layout.addWidget(self.dim_spin)

        # Coordinate selection
        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("🌐 Latitude Column:"))
        self.lat_dropdown = QComboBox()
        coord_layout.addWidget(self.lat_dropdown)
        coord_layout.addWidget(QLabel("🌐 Longitude Column:"))
        self.lon_dropdown = QComboBox()
        coord_layout.addWidget(self.lon_dropdown)

        # Extra dimensions group
        self.extra_dim_group = QGroupBox("➕ Additional Dimensions")
        scroll_dim = QScrollArea()
        scroll_dim.setWidgetResizable(True)
        dim_container = QWidget()
        self.extra_dim_layout = QGridLayout(dim_container)
        scroll_dim.setWidget(dim_container)
        self.extra_dim_group.setLayout(QVBoxLayout())
        self.extra_dim_group.layout().addWidget(scroll_dim)

        # Variables section
        var_layout = QHBoxLayout()
        var_layout.addWidget(QLabel("📊 Number of Variables:"))
        self.var_spin = QSpinBox()
        self.var_spin.setMinimum(1)
        self.var_spin.setMaximum(15)
        self.var_spin.valueChanged.connect(self.update_variables)
        var_layout.addWidget(self.var_spin)

        self.var_group = QGroupBox("📈 Variables")
        scroll_var = QScrollArea()
        scroll_var.setWidgetResizable(True)
        var_container = QWidget()
        self.var_layout = QGridLayout(var_container)
        scroll_var.setWidget(var_container)
        self.var_group.setLayout(QVBoxLayout())
        self.var_group.layout().addWidget(scroll_var)

        # Metadata section
        meta_layout = QHBoxLayout()
        meta_layout.addWidget(QLabel("🔧 Fill Value:"))
        self.fill_value_combo = QComboBox()
        self.fill_value_combo.addItems(["NaN", "0"])
        meta_layout.addWidget(self.fill_value_combo)
        meta_layout.addWidget(QLabel("📝 Description:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Dataset description")
        meta_layout.addWidget(self.desc_input)

        # Grid resolution
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("📐 Grid Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "0.25 x 0.25", "0.5 x 0.5", "1 x 1", 
            "3.75 x 3.75", "15 x 15", "Custom"
        ])
        self.resolution_combo.currentTextChanged.connect(self.toggle_custom_res)
        res_layout.addWidget(self.resolution_combo)
        
        self.custom_lat = QLineEdit()
        self.custom_lat.setPlaceholderText("Latitude Step")
        self.custom_lon = QLineEdit()
        self.custom_lon.setPlaceholderText("Longitude Step")
        res_layout.addWidget(self.custom_lat)
        res_layout.addWidget(self.custom_lon)
        self.custom_lat.hide()
        self.custom_lon.hide()

        # Output section
        output_btn = QPushButton("📁 Select Output Folder")
        output_btn.clicked.connect(self.select_output)
        self.out_label = QLabel("No folder selected")
        self.out_label.setWordWrap(True)
        self.out_file = QLineEdit()
        self.out_file.setPlaceholderText("Output filename")

        # Generate button
        generate_btn = QPushButton("🚀 Generate NetCDF")
        generate_btn.clicked.connect(self.generate_netcdf)

        # About button
        about_btn = QPushButton("ℹ About")
        about_btn.clicked.connect(self.show_about)

        # Layout assembly
        main_layout.addWidget(file_btn)
        main_layout.addWidget(self.file_label)
        main_layout.addLayout(dim_layout)
        main_layout.addLayout(coord_layout)
        main_layout.addWidget(self.extra_dim_group)
        main_layout.addLayout(var_layout)
        main_layout.addWidget(self.var_group)
        main_layout.addLayout(meta_layout)
        main_layout.addLayout(res_layout)
        main_layout.addWidget(output_btn)
        main_layout.addWidget(self.out_label)
        main_layout.addWidget(self.out_file)
        main_layout.addWidget(generate_btn)
        main_layout.addWidget(about_btn)

        self.setLayout(main_layout)


    def apply_theme(self, colors):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {colors['background']};
                color: {colors['text']};
                font-family: 'Segoe UI';
                font-size: 13px;
            }}

            QMenuBar {{
            background-color: {colors['surface']};
            border-bottom: 1px solid {colors['divider']};
            }}

            QGroupBox {{
            background-color: {colors['surface']};
            }}

            QScrollArea {{
                background-color: {colors['surface']};
            }}


            QGroupBox {{
                border: 2px solid {colors['divider']};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 18px;
            }}
            QGroupBox::title {{
                color: {colors['primary']};
                subcontrol-origin: margin;
                left: 10px;
            }}
            QPushButton {{
                background-color: {colors['primary']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {colors['secondary']};
            }}
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {colors['surface']};
                color: {colors['text']};
                border: 1px solid {colors['divider']};
                padding: 6px;
                border-radius: 4px;
            }}
            QScrollArea {{
                border: none;
                background: {colors['surface']};
            }}
            QMenuBar {{
                background-color: {colors['surface']};
                color: {colors['text']};
            }}
            QMenuBar::item:selected {{
                background-color: {colors['divider']};
            }}
        """)
        
        # Update palette for better disabled state visibility
        palette = self.palette()
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(colors['disabled']))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(colors['disabled']))
        self.setPalette(palette)

    def toggle_theme(self, theme_name):
        self.current_theme = theme_name
        self.apply_theme(self.themes[theme_name])

    def show_about(self):
        dialog = AboutDialog(self.themes[self.current_theme])
        dialog.exec_()

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "Data Files (*.xlsx *.xls *.csv)")
        if file_path:
            try:
                self.df = pd.read_csv(file_path) if file_path.endswith(".csv") else pd.read_excel(file_path)
                self.file_label.setText(file_path)
                self.lat_dropdown.clear()
                self.lon_dropdown.clear()
                self.lat_dropdown.addItems(self.df.columns)
                self.lon_dropdown.addItems(self.df.columns)
                self.update_dimensions()
                self.update_variables()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error loading file:\n{str(e)}")

    def update_dimensions(self):
        for i in reversed(range(self.extra_dim_layout.count())):
            self.extra_dim_layout.itemAt(i).widget().deleteLater()
        self.extra_dim_widgets = []

        num_extra_dims = max(0, self.dim_spin.value() - 2)
        for i in range(num_extra_dims):
            name_input = QLineEdit(placeholderText=f"Dim {i+1} Name")
            col_dropdown = QComboBox()
            if self.df is not None:
                col_dropdown.addItems(self.df.columns)
            self.extra_dim_layout.addWidget(QLabel(f"Dimension {i+3}:"), i, 0)
            self.extra_dim_layout.addWidget(name_input, i, 1)
            self.extra_dim_layout.addWidget(col_dropdown, i, 2)
            self.extra_dim_widgets.append((name_input, col_dropdown))

    def update_variables(self):
        for i in reversed(range(self.var_layout.count())):
            self.var_layout.itemAt(i).widget().deleteLater()
        self.variable_widgets = []

        for i in range(self.var_spin.value()):
            name_input = QLineEdit(placeholderText=f"Variable {i+1}")
            col_dropdown = QComboBox()
            unit_input = QLineEdit(placeholderText="Units")
            if self.df is not None:
                col_dropdown.addItems(self.df.columns)
            self.var_layout.addWidget(QLabel(f"Var {i+1}:"), i, 0)
            self.var_layout.addWidget(name_input, i, 1)
            self.var_layout.addWidget(col_dropdown, i, 2)
            self.var_layout.addWidget(unit_input, i, 3)
            self.variable_widgets.append((name_input, col_dropdown, unit_input))

    def toggle_custom_res(self, text):
        show_custom = text == "Custom"
        self.custom_lat.setVisible(show_custom)
        self.custom_lon.setVisible(show_custom)

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.out_label.setText(folder)

    def get_target_grid(self):
        res_map = {
            "0.25 x 0.25": (0.25, 0.25),
            "0.5 x 0.5": (0.5, 0.5),
            "1 x 1": (1.0, 1.0),
            "3.75 x 3.75": (3.75, 3.75),
            "15 x 15": (15.0, 15.0)
        }
        if self.resolution_combo.currentText() == "Custom":
            try:
                dlat = float(self.custom_lat.text())
                dlon = float(self.custom_lon.text())
            except ValueError:
                raise ValueError("Invalid resolution values")
        else:
            dlat, dlon = res_map[self.resolution_combo.currentText()]
        
        lats = np.arange(90 - dlat/2, -90, -dlat)
        lons = np.arange(-180 + dlon/2, 180, dlon)
        return lats, lons

    def generate_netcdf(self):
        try:
            if self.df is None or self.df.empty:
                raise ValueError("No data loaded")
            
            # Get fill value selection
            fill_value = 0 if self.fill_value_combo.currentText() == "0" else np.nan
            
            # Get dimensions and variables
            dims = []
            coord_cols = []
            for name_input, col_dropdown in self.extra_dim_widgets:
                dim_name = name_input.text().strip()
                if not dim_name:
                    raise ValueError("Dimension name required")
                dims.append(dim_name)
                coord_cols.append(col_dropdown.currentText())
            
            lat_col = self.lat_dropdown.currentText()
            lon_col = self.lon_dropdown.currentText()
            dims += ['lat', 'lon']
            coord_cols += [lat_col, lon_col]

            # Create xarray dataset
            target_lats, target_lons = self.get_target_grid()
            coords = {
                'lat': target_lats,
                'lon': target_lons
            }
            
            # Add extra dimensions
            for dim, col in zip(dims[:-2], coord_cols[:-2]):
                unique_vals = self.df[col].unique()
                coords[dim] = xr.DataArray(sorted(unique_vals), dims=dim)

            # Create variables
            ds = xr.Dataset()
            for var_name_input, col_dropdown, unit_input in self.variable_widgets:
                var_name = var_name_input.text().strip() or col_dropdown.currentText()
                da = xr.DataArray(
                    dims=dims,
                    coords=coords,
                    attrs={'units': unit_input.text()}
                )
                # Initialize with NaNs
                da.values = np.full(da.shape, np.nan)
                ds[var_name] = da

            # Populate data
            for _, row in self.df.iterrows():
                sel_args = {}
                for dim, col in zip(dims, coord_cols):
                    val = row[col]
                    if dim in ['lat', 'lon']:
                        # Find nearest grid point
                        idx = np.abs(coords[dim] - val).argmin()
                        val = coords[dim][idx].item()
                    sel_args[dim] = val
                
                for var_name in ds.data_vars:
                    var_col = next(v[1].currentText() for v in self.variable_widgets 
                                 if v[0].text().strip() == var_name)
                    ds[var_name].loc[sel_args] = row[var_col]

            # Handle fill value
            if fill_value == 0:
                ds = ds.fillna(0)

            # Save to file
            output_path = f"{self.out_label.text()}/{self.out_file.text().strip()}.nc"
            ds.to_netcdf(output_path)
            
            QMessageBox.information(self, "Success", f"File saved:\n{output_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed:\n{str(e)}")
