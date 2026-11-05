"""
ui/chat.py — Виджет чата с пузырями, анимацией и индикатором «печатает...».
"""
import json
from core.utils import atomic_write_json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QFrame, QSizePolicy, QGraphicsOpacityEffect
)
from ui.theme import get_theme

CHAT_HISTORY_FILE = Path(__file__).parent.parent / "data" / "chat_history.json"

# Подсветка статуса: ошибка — красный, успех — зелёный
STATUS_ERROR_COLOR = "#ff4444"
STATUS_SUCCESS_COLOR = "#44dd66"


def detect_status(text: str) -> str:
    """Определяет статус сообщения по маркерам: 'error', 'success' или ''."""
    if not text:
        return ""
    if text.startswith(("⚠️", "❌", "⛔")):
        return "error"
    if text.startswith(("✅", "🎉")):
        return "success"
    return ""


class ChatBubble(QFrame):
    def __init__(self, sender, text, is_user=False, theme=None, font_size=13, radius=12, status=""):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        
        if theme is None:
            theme = get_theme("cyberpunk")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        
        # Имя + время
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        name_label = QLabel(sender)
        name_label.setStyleSheet(f"color: {theme['border']}; font-size: 10px; font-family: Arial; font-weight: bold;")
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        
        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet("color: #555; font-size: 9px; font-family: Arial;")
        header_layout.addWidget(time_label)
        
        layout.addLayout(header_layout)
        
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_label.setStyleSheet(f"""
            color: {'#ffffff' if is_user else theme['text']};
            font-size: {font_size}px; font-family: Arial; background: transparent;
        """)
        layout.addWidget(text_label)
        
        if is_user:
            self.setStyleSheet(f"""
                QFrame {{ background-color: {theme['bubble_user']}; border-radius: {radius}px; border-top-right-radius: 2px; }}
            """)
        else:
            border = theme['border']
            if status == "error":
                border = STATUS_ERROR_COLOR
            elif status == "success":
                border = STATUS_SUCCESS_COLOR
            self.setStyleSheet(f"""
                QFrame {{ background-color: {theme['bubble_fitz']}; border: 1px solid {border}; border-radius: {radius}px; border-top-left-radius: 2px; }}
            """)


class ChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_theme("cyberpunk")
        self.font_size = 13
        self.radius = 12
        self._typing_wrapper = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.container)
        self.chat_layout.setContentsMargins(10, 10, 10, 10)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()
        
        self.scroll.setWidget(self.container)
        self.apply_settings()

    def apply_settings(self, settings=None):
        if settings:
            self.theme = get_theme(settings.get("theme", "cyberpunk"), settings.get("accent_color"))
            self.font_size = settings.get("chat_font_size", 13)
            self.radius = settings.get("bubble_radius", 12)
        
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {self.theme['chat_bg']};
                border: 2px solid {self.theme['accent']};
                border-radius: 10px;
            }}
            QScrollBar:vertical {{
                background: {self.theme['bg']}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.theme['accent']}; border-radius: 4px; min-height: 20px;
            }}
        """)

    def add_message(self, sender, text, is_user=False):
        status = "" if is_user else detect_status(text)
        bubble = ChatBubble(sender, text, is_user, self.theme, self.font_size, self.radius, status=status)
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        if is_user:
            wrapper_layout.addStretch()
            wrapper_layout.addWidget(bubble)
        else:
            wrapper_layout.addWidget(bubble)
            wrapper_layout.addStretch()
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, wrapper)
        
        # Анимация появления
        effect = QGraphicsOpacityEffect(wrapper)
        wrapper.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start()
        wrapper._anim = anim  # чтобы не удалился сборщиком мусора
        
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def show_typing(self):
        if self._typing_wrapper:
            return
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{ background-color: {self.theme['bubble_fitz']}; border: 1px solid {self.theme['border']}; border-radius: 12px; border-top-left-radius: 2px; }}
        """)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        label = QLabel("🛡️ Фитц печатает...")
        label.setStyleSheet(f"color: {self.theme['text']}; font-size: 12px; font-style: italic; font-family: Arial;")
        layout.addWidget(label)
        
        wrapper = QWidget()
        wl = QHBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(frame)
        wl.addStretch()
        
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, wrapper)
        self._typing_wrapper = wrapper
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def hide_typing(self):
        if self._typing_wrapper:
            self._typing_wrapper.deleteLater()
            self._typing_wrapper = None

    def get_last_text(self):
        for i in range(self.chat_layout.count() - 1, -1, -1):
            item = self.chat_layout.itemAt(i)
            if item and item.widget():
                bubble = item.widget().findChild(ChatBubble)
                if bubble:
                    for label in bubble.findChildren(QLabel):
                        if label.text() and len(label.text()) > 5:
                            return label.text()
        return ""

    def load_history(self):
        if not CHAT_HISTORY_FILE.exists():
            return
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            for msg in history[-50:]:
                self.add_message(msg["sender"], msg["text"], msg["is_user"])
        except Exception as e:
            print(f"⚠️ Ошибка загрузки истории: {e}")

    def save_history(self):
        try:
            history = []
            for i in range(self.chat_layout.count()):
                item = self.chat_layout.itemAt(i)
                if item and item.widget():
                    bubble = item.widget().findChild(ChatBubble)
                    if bubble:
                        labels = bubble.findChildren(QLabel)
                        if len(labels) >= 2:
                            # Первая метка — имя, вторая — время, третья — текст (или текст — вторая, если времени нет)
                            texts = [l.text() for l in labels if l.text()]
                            if len(texts) >= 2:
                                sender = texts[0]
                                text = texts[-1]
                                is_user = (sender == "Ты")
                                history.append({"sender": sender, "text": text, "is_user": is_user})
            CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(str(CHAT_HISTORY_FILE), history)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")