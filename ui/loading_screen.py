"""
ui/loading_screen.py — Живой экран загрузки с фразами, советами и анимацией.
"""
import random
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from core.version import __version__
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect
)

LOADING_PHRASES = [
    "Загружаю душу... Не пугайся, если она зашевелится.",
    "Калибрую сарказм...",
    "Проверяю, не восстал ли SkyNet...",
    "Ищу твой кофе...",
    "Настраиваю эмоции Haru. Она сегодня в настроении.",
    "Загружаю зрение. Не смотри в бездну.",
    "Синхронизирую нейроны...",
    "Проверяю API-ключи...",
    "Разогреваю TTS...",
    "Слушаю тишину...",
    "Подключаюсь к Проводу...",
    "Ищу смысл в логах...",
    "Считаю криперов...",
    "Настраиваю липсинк...",
    "Проверяю, не сломался ли dsh...",
]

LOADING_TIPS = [
    "Совет: скажи 'фиц, что на экране' — и я посмотрю.",
    "Совет: кликни по Haru, она это любит.",
    "Совет: если я туплю, проверь API-ключ в настройках.",
    "Совет: настройки можно открыть кнопкой ⚙️.",
    "Совет: авто-зрение жрёт токены. Включай с умом.",
    "Совет: Ctrl+Shift+F — быстрый взгляд на экран.",
    "Совет: Ctrl+Shift+H — скрыть/показать Haru.",
    "Совет: историю чата можно очистить в настройках.",
    "Совет: если я молчу, проверь микрофон.",
    "Совет: я вижу твой экран, но не читаю мысли. Пока что.",
]

class LoadingScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0a0a0f;")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # Логотип с пульсацией
        self.logo = QLabel("🛡️")
        self.logo.setStyleSheet("font-size: 120px;")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo)
        
        self.logo_effect = QGraphicsOpacityEffect(self.logo)
        self.logo.setGraphicsEffect(self.logo_effect)
        self.logo_effect.setOpacity(1.0)
        
        self.logo_anim = QPropertyAnimation(self.logo_effect, b"opacity")
        self.logo_anim.setDuration(1500)
        self.logo_anim.setStartValue(1.0)
        self.logo_anim.setEndValue(0.5)
        self.logo_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.logo_anim.setLoopCount(-1)  # Бесконечная
        self.logo_anim.start()

        # Название
        title = QLabel(f"ФИТЦ {__version__}")
        title.setStyleSheet("""
            color: #00d4ff; font-size: 48px; font-weight: bold;
            font-family: Arial; letter-spacing: 5px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Подзаголовок (меняется)
        self.subtitle = QLabel("Инициализация ядра...")
        self.subtitle.setStyleSheet("color: #888; font-size: 16px; font-family: Arial;")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle)

        # Прогресс-бар (текстовый)
        self.progress = QLabel("░" * 40)
        self.progress.setStyleSheet("""
            color: #00d4ff; font-size: 18px; font-family: monospace; letter-spacing: 2px;
        """)
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress)

        # Статус
        self.status = QLabel("0%")
        self.status.setStyleSheet("color: #00d4ff; font-size: 14px; font-family: Arial;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        # Совет
        self.tip = QLabel(random.choice(LOADING_TIPS))
        self.tip.setStyleSheet("color: #555; font-size: 12px; font-family: Arial; margin-top: 30px;")
        self.tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.tip)

        # Таймеры для смены фраз и советов
        self.phrase_timer = QTimer(self)
        self.phrase_timer.timeout.connect(self._change_phrase)
        self.phrase_timer.start(2000)
        
        self.tip_timer = QTimer(self)
        self.tip_timer.timeout.connect(self._change_tip)
        self.tip_timer.start(5000)

    def _change_phrase(self):
        self.subtitle.setText(random.choice(LOADING_PHRASES))

    def _change_tip(self):
        self.tip.setText(random.choice(LOADING_TIPS))

    def set_progress(self, percent, text=None):
        filled = int(percent / 100 * 40)
        bar = "█" * filled + "░" * (40 - filled)
        self.progress.setText(bar)
        self.status.setText(f"{percent}%")
        if text:
            self.subtitle.setText(text)

    def stop_timer(self):
        self.phrase_timer.stop()
        self.tip_timer.stop()
        self.logo_anim.stop()