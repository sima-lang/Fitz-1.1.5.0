"""
ui/minecraft_dialog.py — Настройки подключения к Майнкрафту.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QPushButton, QCheckBox, QLabel
)

class MinecraftDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("🎮 Майнкрафт — Подключение")
        self.resize(400, 250)
        self.setStyleSheet("background-color: #0a0a0f; color: #e0e0e0;")
        
        self.settings = settings or {}
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.host_input = QLineEdit(self.settings.get("mc_host", "localhost"))
        form.addRow("Хост:", self.host_input)
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(self.settings.get("mc_port", 34485))
        form.addRow("Порт:", self.port_input)
        
        self.nick_input = QLineEdit(self.settings.get("mc_nick", "FitzBot"))
        form.addRow("Ник бота:", self.nick_input)
        
        self.enabled_check = QCheckBox("Включить бота при старте")
        self.enabled_check.setChecked(self.settings.get("mc_enabled", False))
        form.addRow(self.enabled_check)
        
        layout.addLayout(form)
        
        self.status_label = QLabel("Статус: не подключен")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)
        
        btn_layout = QVBoxLayout()
        self.connect_btn = QPushButton("Подключить")
        self.connect_btn.setStyleSheet("background: #00d4ff; color: #0a0a0f; padding: 8px;")
        self.disconnect_btn = QPushButton("Отключить")
        self.disconnect_btn.setStyleSheet("background: #3a1a1a; color: #ff4444; padding: 8px;")
        
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)

    def get_settings(self):
        return {
            "mc_host": self.host_input.text(),
            "mc_port": self.port_input.value(),
            "mc_nick": self.nick_input.text(),
            "mc_enabled": self.enabled_check.isChecked(),
        }
    
    def set_status(self, text):
        self.status_label.setText(f"Статус: {text}")