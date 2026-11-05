"""
ui/closing_screen.py — Экран сохранения при выходе.
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

CLOSING_PHRASES = [
    "Сохраняю историю...",
    "Записываю воспоминания...",
    "Убираю за собой...",
    "Прощаюсь с Haru...",
    "Выключаю свет...",
    "До встречи, создатель.",
]

class ClosingScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0a0a0f;")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        logo = QLabel("🌙")
        logo.setStyleSheet("font-size: 100px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        self.subtitle = QLabel(CLOSING_PHRASES[0])
        self.subtitle.setStyleSheet("color: #00d4ff; font-size: 20px; font-family: Arial;")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle)

        self.status = QLabel("Сохранение...")
        self.status.setStyleSheet("color: #888; font-size: 14px; font-family: Arial;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        self.phrase_idx = 0
        self.phrase_timer = QTimer(self)
        self.phrase_timer.timeout.connect(self._next_phrase)
        self.phrase_timer.start(800)

    def _next_phrase(self):
        self.phrase_idx = (self.phrase_idx + 1) % len(CLOSING_PHRASES)
        self.subtitle.setText(CLOSING_PHRASES[self.phrase_idx])

    def set_status(self, text):
        self.status.setText(text)

    def stop_timer(self):
        self.phrase_timer.stop()