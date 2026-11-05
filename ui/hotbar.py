"""
ui/hotbar.py — Верхняя панель с кнопками.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from ui.theme import get_theme


class Hotbar(QWidget):
    settings_clicked = pyqtSignal()
    logs_clicked = pyqtSignal()
    haru_toggle_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    minimize_clicked = pyqtSignal()
    exit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        self.title = QLabel("🛡️ ФИТЦ 1.1.5.0")
        self.layout.addWidget(self.title)
        self.layout.addStretch()

        self.buttons = []
        buttons_data = [
            ("⏹", self.stop_clicked),
            ("⚙️", self.settings_clicked),
            ("📜", self.logs_clicked),
            ("👁️", self.haru_toggle_clicked),
            ("➖", self.minimize_clicked),
            ("✖", self.exit_clicked),
        ]

        for text, signal in buttons_data:
            btn = QPushButton(text)
            btn.setFixedSize(35, 35)
            btn.clicked.connect(signal.emit)
            self.layout.addWidget(btn)
            self.buttons.append(btn)
        
        self.apply_settings()

    def apply_settings(self, settings=None):
        theme = get_theme(settings.get("theme", "cyberpunk") if settings else "cyberpunk",
                          settings.get("accent_color") if settings else None)
        
        self.title.setStyleSheet(f"color: {theme['accent']}; font-size: 18px; font-weight: bold; font-family: Arial;")
        
        for btn in self.buttons:
            color = "#ff4444" if btn.text() == "✖" else theme['accent']
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme['bubble_fitz']}; color: {color};
                    border-radius: 17px; font-size: 16px;
                }}
                QPushButton:hover {{ background-color: {theme['border']}; }}
            """)