"""
ui/logs_dialog.py — Окно просмотра логов.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
)

LOG_FILE = Path(__file__).parent.parent / "logs" / "debug.log"

class LogsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📜 Логи Фитца")
        self.resize(700, 500)
        self.setStyleSheet("background-color: #0a0a0f; color: #e0e0e0;")
        
        layout = QVBoxLayout(self)
        
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a2e; color: #00ff88;
                font-family: monospace; font-size: 12px;
                border: 1px solid #2a2a4e; border-radius: 8px;
            }
        """)
        layout.addWidget(self.text)
        
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.setStyleSheet("background: #00d4ff; color: #0a0a0f; padding: 8px;")
        refresh_btn.clicked.connect(self._load_logs)
        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet("background: #1a1a2e; color: #e0e0e0; padding: 8px;")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        self._load_logs()

    def _load_logs(self):
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    self.text.setText(f.read())
                # Прокрутка вниз
                self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
            except Exception as e:
                self.text.setText(f"Ошибка чтения логов: {e}")
        else:
            self.text.setText("Логи пока пусты.")