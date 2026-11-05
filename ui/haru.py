"""
ui/haru.py — Виджет Live2D (Haru).
"""

from PyQt6.QtCore import Qt, QUrl, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from core.logger import get_logger
_log = get_logger("haru")


class DebugPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        pass


class HaruWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setFixedWidth(450)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.view = QWebEngineView()
        self.view.setPage(DebugPage(self.view))
        self.view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.view.setStyleSheet("background: transparent;")
        
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        self.view.load(QUrl("http://127.0.0.1:8000/live2d_viewer.html"))
        layout.addWidget(self.view)
        
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.effect.setOpacity(0.0)
        
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(800)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.start()

    def apply_settings(self, settings=None):
        if settings:
            size = settings.get("haru_size", 450)
            self.setFixedWidth(size)
            visible = settings.get("haru_enabled", True)
            self.setVisible(visible)
            # 1.6.0: модель и масштаб
            model = settings.get("haru_model", "default")
            scale = settings.get("haru_scale", 100)
            self.set_model(model)
            self.set_scale(scale)

    def set_model(self, name: str = "default"):
        """Загружает спрайты из assets/haru/<name>/."""
        import os as _os
        model_dir = _os.path.join(_os.path.dirname(__file__), "..",
                                  "assets", "haru", name)
        if _os.path.isdir(model_dir):
            self._current_model = name
        else:
            self._current_model = "default"

    def set_scale(self, factor: int = 100):
        """Масштабирует Haru: 50–150%."""
        factor = max(50, min(150, factor))
        w = int(450 * factor / 100)
        self.setFixedWidth(w)
        self._scale = factor

    def set_emotion(self, response_text: str):
        if not self.view:
            return
        # Проверяем настройку: если эмоции Haru выключены — не меняем
        try:
            from ui.settings_dialog import load_settings
            if not load_settings().get("haru_emotions", True):
                return
        except Exception:
            _log.debug("пропущено в ui/haru.py (строка 90)")
        resp_lower = response_text.lower()
        expression_index = 0
        if any(w in resp_lower for w in ("ухмыл", "хитр", "сарказ", "ирони", "коварн")):
            expression_index = 5
        elif any(w in resp_lower for w in ("смех", "смешн", "ха-ха", "хех", "ржу", "весел", "забавн", "прикол")):
            expression_index = 6
        elif any(w in resp_lower for w in ("улыб", "рад", "отличн", "здорово", "класс", "привет", "добро пожал")):
            expression_index = 4
        elif any(w in resp_lower for w in ("груст", "жаль", "печаль", "плохо", "тоск", "скуч", "уныл")):
            expression_index = 2
        elif any(w in resp_lower for w in ("зл", "раздраж", "бесит", "ненавиж", "достал", "надоел")):
            expression_index = 3
        elif any(w in resp_lower for w in ("думаю", "интересн", "хм", "возможно", "наверное", "удив", "вот это да")):
            expression_index = 1
        elif any(w in resp_lower for w in ("устал", "спать", "сон", "отдых", "выспат", "зева")):
            expression_index = 7
        elif any(w in resp_lower for w in ("страшн", "боюсь", "испуг", "ужас", "кошмар")):
            expression_index = 8
        self.view.page().runJavaScript(f"window.setHaruExpression({expression_index});")

    # ------------------------------------------------------------
    # ЭМОЦИИ (1.6.2)
    # ------------------------------------------------------------
    def blink(self):
        """Моргание: прячем на 150ms."""
        try:
            self.setVisible(False)
            QTimer.singleShot(150, lambda: self.setVisible(True))
        except Exception:
            _log.debug("пропущено в ui/haru.py (строка 120)")

    # ------------------------------------------------------------
    # СОСТОЯНИЯ ЖИВОСТИ (1.6.3): думает / слушает / не активен
    # ------------------------------------------------------------
    def think(self):
        """Думает: задумчивое выражение, пока идёт запрос к API."""
        self._set_state("thinking", expression=1)

    def listen(self):
        """Слушает: внимательное выражение, пока пользователь говорит/печатает."""
        self._set_state("listening", expression=0)

    def sleep(self):
        """Не активен: выражение «устал», без реакций."""
        self._set_state("sleeping", expression=7)

    def _set_state(self, state: str, expression: int):
        if not self.view:
            return
        self._state = state
        try:
            self.view.page().runJavaScript(f"window.setHaruExpression({expression});")
        except Exception:
            _log.debug("пропущено в ui/haru.py (строка 144)")

    def play_motion(self, group: str):
        """Проигрывает motion-группу модели (Idle, Flick, Tap, FlickLeft, Shake и т.д.)."""
        if not self.view:
            return
        try:
            self.view.page().runJavaScript(f"window.playMotion && window.playMotion({group!r});")
        except Exception:
            _log.debug("пропущено в ui/haru.py (play_motion)")

    def set_gesture(self, name: str):
        """Жест: neutral, angry, joy, sad, alarm — см. GESTURES в live2d_viewer.html."""
        if not self.view:
            return
        try:
            self.view.page().runJavaScript(f"window.setGesture && window.setGesture({name!r});")
        except Exception:
            _log.debug("пропущено в ui/haru.py (set_gesture)")

    def smile(self):
        """Улыбка: happy на 3 секунды."""
        self._emote_to("happy", 3000)

    def sad(self):
        """Грусть: sad на 3 секунды."""
        self._emote_to("sad", 3000)

    def angry(self):
        """Гнев: angry на 3 секунды."""
        self._emote_to("angry", 3000)

    def surprised(self):
        """Удивление: surprised на 2 секунды."""
        self._emote_to("surprised", 2000)

    def _emote_to(self, name: str, duration_ms: int):
        """Временная смена эмоции через JS с возвратом."""
        if not self.view:
            return
        emote_map = {"happy": 4, "sad": 2, "angry": 3, "surprised": 1, "neutral": 0}
        idx = emote_map.get(name, 0)
        try:
            self.view.page().runJavaScript(f"window.setHaruExpression({idx});")
            QTimer.singleShot(duration_ms, lambda: self.view.page().runJavaScript(
                "window.setHaruExpression(0);"))
        except Exception:
            _log.debug("пропущено в ui/haru.py (строка 173)")
