from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit

class AboutDialog(QDialog):
    def __init__(self, theme_colors):
        super().__init__()
        self.theme_colors = theme_colors
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("About NetCDF Converter")
        self.setFixedSize(500, 500)
        layout = QVBoxLayout()
        text = QTextEdit()
        text.setReadOnly(True)
        content = f"""
        <h2 style="color: {self.theme_colors['primary']};">
            🌐 NetCDF Generator
        </h2>
        <p style="color: {self.theme_colors['text']};">
            <b>Version:</b> 1.0.0<br>
            <b>Developed by:</b> Vikas Kumar Meena<br>
            <b>Contact:</b> ce22resch01004@iith.ac.in
        </p>
        <hr style="border-color: {self.theme_colors['divider']};">
        <p style="color: {self.theme_colors['text']};">
            A python based GUI application for converting tabular data (CSV/Excel) to NetCDF format with multi-dimensional support and theme customization.
        </p>
        """
        text.setHtml(content)
        # text.setStyleSheet(f"background-color: {self.theme_colors['background']};")
        text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.theme_colors['background']};
                font-size: 14px;
                border: none;
            }}
        """)
        layout.addWidget(text)
        self.setLayout(layout)