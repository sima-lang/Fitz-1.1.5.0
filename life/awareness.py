"""
awareness.py — Фитц видит, что происходит на ПК.
Кроссплатформенно: через core.os_layer (Windows: win32gui, Linux: GNOME Shell D-Bus, macOS: osascript).
"""
import time
import threading
from datetime import datetime

from core import os_layer
from core.logger import get_logger
_log = get_logger("awareness")


class Awareness:
    def __init__(self, interval: int = 5):
        self.interval = interval
        self.running = False
        self.last_activity = "неизвестно"
        self.last_window = None
        self.log = []
        self._thread = None
        self._intel = None  # ссылка на Intelligence (для дневника)
        self._last_episode_activity = None
        self._activity_since = None

    def set_intelligence(self, intel):
        """Подключает модуль intelligence для записи событий в дневник."""
        self._intel = intel

    def start(self):
        if self.running:
            return "👂 Восприятие уже активно"
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return "👂 Фитц теперь видит, что ты делаешь"

    def stop(self):
        self.running = False
        return "🔇 Восприятие выключено"

    def _loop(self):
        while self.running:
            try:
                title = os_layer.get_active_window_title()
                process = os_layer.get_active_process_name()
                activity = self._analyze(title, process)

                if title and title != self.last_window:
                    self.last_window = title
                    if activity != self.last_activity or self._activity_since is None:
                        self._activity_since = time.time()
                    self.last_activity = activity
                    self.log.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "window": title,
                        "process": process,
                        "activity": activity,
                    })
                    if len(self.log) > 100:
                        self.log = self.log[-100:]

                    # Пишем в дневник intelligence (если подключён)
                    if self._intel:
                        try:
                            self._intel.add_event(activity, title, process or "")
                        except Exception:
                            _log.debug("пропущено в life/awareness.py (строка 68)")
                        # Эпизод: только при смене типа активности (не на каждое окно)
                        if activity != self._last_episode_activity:
                            self._last_episode_activity = activity
                            try:
                                self._intel.add_episode(activity)
                            except Exception:
                                _log.debug("пропущено в life/awareness.py (строка 75)")

                time.sleep(self.interval)
            except Exception:
                time.sleep(self.interval * 2)

    def _analyze(self, title: str, process: str) -> str:
        t = (title or "").lower()
        p = (process or "").lower()

        # игры
        if any(w in p or w in t for w in
               ("steam", "game", "gta", "cyberpunk", "witcher",
                "minecraft", "dota", "csgo", "cs2", "valorant")):
            return "game"

        # код
        if any(w in p or w in t for w in
               ("code", "vscode", "pycharm", "sublime", "atom",
                "idea", "android studio", "xed", "gedit", "kate")):
            return "coding"

        # терминал
        if any(w in p or w in t for w in
               ("terminal", "konsole", "gnome-terminal", "xterm",
                "kitty", "alacritty", "bash", "zsh")):
            return "terminal"

        # музыка
        if any(w in p or w in t for w in
               ("spotify", "music", "yandexmusic", "rhythmbox", "vlc")):
            return "music"

        # видео
        if "youtube" in t or "twitch" in t:
            return "video"

        # браузер
        if any(w in p or w in t for w in
               ("chrome", "firefox", "chromium", "opera", "edge", "brave")):
            return "browsing"

        # мессенджеры
        if any(w in p or w in t for w in
               ("telegram", "discord", "slack", "whatsapp", "signal")):
            return "chatting"

        # документы
        if any(w in p or w in t for w in
               ("libreoffice", "word", "excel", "powerpoint", "writer")):
            return "work"

        return "unknown"

    def get_last_activity(self) -> str:
        return self.last_activity

    def get_activity_minutes(self) -> float:
        """Сколько минут подряд длится текущая активность (0, если неизвестна)."""
        if self._activity_since is None or self.last_activity in ("unknown", "неизвестно"):
            return 0.0
        return (time.time() - self._activity_since) / 60.0

    def get_log(self, limit: int = 10) -> list:
        return self.log[-limit:]

    def get_status(self) -> str:
        return "👂 Восприятие активно" if self.running else "👂 Восприятие выключено"

    def suggest_by_activity(self) -> str:
        a = self.last_activity
        if a == "game":
            return "🎮 Играешь? Удачи! Если что — я рядом."
        if a == "coding":
            return "💻 Пишешь код? Может, проверим на ошибки?"
        if a == "music":
            return "🎵 Хорошая музыка? Что играет?"
        if a == "video":
            return "📺 Что смотришь? Интересно?"
        if a == "browsing":
            return "🌐 Что ищешь? Могу помочь."
        if a == "chatting":
            return "💬 Общаешься? Напиши, если нужен совет."
        if a == "work":
            return "📄 Работаешь? Успехов! Я рядом."
        return None