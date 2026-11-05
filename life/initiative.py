"""
initiative.py — Фитц сам предлагает действия и развлечения.
Блок 1.5.0: _suggest_entertainment() с музыкой/видео/фильмами/играми/перерывами.
Защита от спама: не чаще раза в 30 минут.
"""
import time
import random
import threading
from datetime import datetime

from core.logger import get_logger as _gl
_ilog = _gl("initiative")


def _journal(decision: str, activity: str = "", minutes: float = 0.0, reason: str = "") -> None:
    """Пишет причину решения инициативы в data/actions.log. Ошибки не ломают работу."""
    try:
        from core import action_journal
        action_journal.record(
            "initiative",
            {"activity": activity, "minutes": round(minutes, 1), "hour": datetime.now().hour},
            decision,
            reason,
        )
    except Exception as e:
        _ilog.debug("журнал инициативы не записан: %s", e)

try:
    import psutil
except Exception:
    _ilog.warning("psutil not available — system monitoring disabled")
    psutil = None


class Initiative:
    def __init__(self, voice, awareness, soul, min_interval: int = 600):
        self.voice = voice
        self.awareness = awareness
        self.soul = soul
        self.min_interval = min_interval       # секунд между предложениями
        self.entertain_cooldown = 1800          # 30 минут между развлечениями
        self.running = False
        self._last_suggest = 0
        self._last_suggest_time = 0             # антиспам для развлечений
        self._refused_until = 0.0               # отказ пользователя: молчим до этого времени
        self._awaiting_until = 0.0              # окно, в котором «нет» относится к последнему предложению
        self._thread = None
        self._epoch = 0

        # Ожидание ответа пользователя на предложение развлечения
        self._pending_url = None
        self._pending_name = None

        # Колбэк для вывода в чат (подключается из ui_pyqt): fn(text)
        self.on_message = None

    def start(self):
        if self.running:
            return "🧠 Инициатива уже активна"
        self.running = True
        self._epoch += 1
        self._thread = threading.Thread(target=self._loop, args=(self._epoch,), daemon=True)
        self._thread.start()
        return "🧠 Инициатива активна — Фитц сам предложит что-нибудь"

    def stop(self):
        self.running = False
        return "⏹️ Инициатива выключена"

    def suggest_now(self) -> str:
        """Публичный метод — предложить развлечение вручную (из команд).
        Возвращает текст, НЕ говорит голосом (это сделает ui_pyqt)."""
        now = time.time()
        if now - self._last_suggest_time < 120:
            # Не чаще раза в 2 минуты при ручном вызове
            return "⏳ Подожди пару минут перед новым развлечением."
        ent = self._suggest_entertainment()
        if not ent:
            return "🤔 Не могу подобрать развлечение. Скажи, что хочешь: музыка, видео, игра?"
        self._last_suggest_time = now

        ent_type = ent.get("type", "")
        name = ent.get("name", "")
        url = ent.get("url")
        action = ent.get("action")

        if ent_type in ("rest", "game"):
            return action or f"💡 Предлагаю: {name}"

        if ent_type in ("music", "video", "film") and url:
            mood = "нейтральное"
            if self.soul:
                try:
                    mood = self.soul.get_status().get("mood", "нейтральное")
                except Exception:
                    _ilog.debug("psutil check failed — skipping monitoring")
            self._pending_url = url
            self._pending_name = name
            return f"Создатель, я вижу, ты {mood}. Включить {name}? Скажи «да» или «нет»."

        return f"💡 Предлагаю: {name}"

    # ============================================================
    # РАЗВЛЕЧЕНИЯ ПО НАСТРОЕНИЮ + АКТИВНОСТИ
    # ============================================================
    def _suggest_entertainment(self) -> dict | None:
        """
        Возвращает словарь с предложением развлечения или None.
        Формат: {"type": str, "name": str, "url": str|None, "action": str|None}
        """
        mood = "нейтральное"
        if self.soul:
            try:
                mood = self.soul.get_status().get("mood", "нейтральное")
            except Exception:
                _ilog.debug("soul/awareness check skipped")

        activity = "unknown"
        if self.awareness:
            try:
                activity = self.awareness.get_last_activity()
            except Exception:
                _ilog.debug("soul/awareness check skipped")

        # ---- усталое ----
        if mood == "усталое":
            if activity == "coding":
                return {
                    "type": "rest", "name": "перерыв",
                    "url": None,
                    "action": "Создатель, ты долго кодишь. Сделай перерыв на 5 минут?"
                }
            if activity in ("browsing", "video"):
                return {
                    "type": "video", "name": "смешное видео",
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "action": None
                }
            return {
                "type": "rest", "name": "отдых",
                "url": None,
                "action": "Создатель, ты выглядишь уставшим. Отдохни немного."
            }

        # ---- весёлое ----
        if mood == "весёлое":
            if activity == "music":
                return {
                    "type": "music", "name": "весёлый плейлист",
                    "url": "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
                    "action": None
                }
            return {
                "type": "music", "name": "зажигательная музыка",
                "url": "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
                "action": None
            }

        # ---- грустное ----
        if mood == "грустное":
            return {
                "type": "film", "name": "добрая комедия",
                "url": "https://www.youtube.com/watch?v=5qap5aO4i9A",
                "action": None
            }

        # ---- сердитое ----
        if mood == "сердитое":
            return {
                "type": "game", "name": "расслабляющая игра",
                "url": None,
                "action": "Создатель, может, сыграем в что-нибудь спокойное? Это поможет остыть."
            }

        # ---- нейтральное ----
        if mood == "нейтральное":
            if activity == "work":
                return {
                    "type": "rest", "name": "разминка",
                    "url": None,
                    "action": "Создатель, ты долго работаешь. Разомнись?"
                }
            if activity == "coding":
                return {
                    "type": "music", "name": "фокус-музыка для кода",
                    "url": "https://music.youtube.com/watch?v=jfKfPfyJRdk",
                    "action": None
                }

        return None

    # ============================================================
    # ОСНОВНОЙ ЦИКЛ ПРЕДЛОЖЕНИЙ
    # ============================================================
    def _loop(self, epoch):
        time.sleep(60)  # первое предложение через 60 сек
        while self.running and epoch == self._epoch:
            try:
                now = time.time()
                if now < self._refused_until:
                    time.sleep(30)
                    continue
                if now - self._last_suggest > self.min_interval:
                    suggestion = self._generate()
                    if suggestion and self.voice and self.running and epoch == self._epoch:
                        self._say(suggestion)
                        self._last_suggest = now
                        self._awaiting_until = now + 120  # 2 минуты ждём ответа «нет»
                time.sleep(30)
            except Exception:
                _ilog.debug("soul/awareness check skipped")
                time.sleep(60)

    def _say(self, text: str) -> None:
        """Говорит вслух и дублирует в чат, если подключён on_message."""
        if self.voice:
            self.voice.speak(text)
        if self.on_message:
            try:
                self.on_message(text)
            except Exception:
                _ilog.debug("initiative: вывод в чат не удался")

    def awaiting_answer(self) -> bool:
        """True, если недавно было предложение и пользователь мог ответить «нет»."""
        return time.time() < self._awaiting_until

    def refuse(self, minutes: int = 30) -> None:
        """Пользователь сказал «нет»: не предлагаем ничего minutes минут."""
        self._refused_until = time.time() + minutes * 60
        self._awaiting_until = 0.0
        self._pending_url = None
        self._pending_name = None
        _journal("refused", reason=f"отказ на {minutes} мин")

    # ============================================================
    # ГЕНЕРАЦИЯ ПРЕДЛОЖЕНИЙ
    # ============================================================
    def _generate(self) -> str:
        """Генерирует обычное предложение ИЛИ развлечение (если кд позволяет)."""
        # Развлечения — с проверкой антиспама
        now = time.time()
        if now - self._last_suggest_time >= self.entertain_cooldown:
            ent = self._suggest_entertainment()
            if ent:
                self._last_suggest_time = now
                return self._suggest(ent)

        # Обычные предложения
        suggestions = []
        activity = self.awareness.get_last_activity() if self.awareness else "unknown"
        minutes = self.awareness.get_activity_minutes() if self.awareness else 0.0

        if activity == "coding" and minutes >= 30:
            suggestions.append(f"💻 Ты уже {int(minutes)} мин в коде. Может, перерыв на 5 минут?")
        elif activity == "game" and minutes >= 60:
            suggestions.append(f"🎮 Ты в игре {int(minutes)} мин. Не забывай отдыхать.")
        elif activity == "browsing" and minutes >= 45:
            suggestions.append(f"🌐 Ты в браузере уже {int(minutes)} мин. Глазам нужен отдых.")

        hour = datetime.now().hour
        if hour >= 23 or hour < 6:
            suggestions.append("🌙 Уже поздно. Может, спать? Я посторожу.")
        elif hour in (12, 18):
            suggestions.append("🍽️ Время еды. Не забудь поесть.")

        if psutil:
            try:
                cpu = psutil.cpu_percent(interval=0.3)
                ram = psutil.virtual_memory().percent
                if cpu > 85:
                    suggestions.append(f"⚠️ ЦП загружен на {cpu}%. Может, закрыть что-то?")
                if ram > 85:
                    suggestions.append(f"⚠️ ОЗУ занята на {ram}%. Перезагрузка не помешает.")
            except Exception:
                _ilog.debug("soul/awareness check skipped")

        if self.soul:
            try:
                mood = self.soul.get_status().get("mood", "нейтральное")
                if mood == "грустное":
                    suggestions.append("🫂 Ты сегодня грустный. Может, поговорим?")
                elif mood == "усталое":
                    suggestions.append("😴 Ты устал. Отдохни немного.")
            except Exception:
                _ilog.debug("soul/awareness check skipped")

        if not suggestions:
            # Нет реального сигнала — молчим (раньше тут были случайные фразы)
            _journal("silent", activity=activity, minutes=minutes, reason="нет сигнала")
            return None

        text = random.choice(suggestions)
        _journal("suggest", activity=activity, minutes=minutes, reason=text[:80])
        return text

    # ============================================================
    # ПРЕДЛОЖЕНИЕ РАЗВЛЕЧЕНИЯ (с pending URL)
    # ============================================================
    def _suggest(self, ent: dict) -> str:
        """
        Обрабатывает предложение развлечения.
        - rest/game (без URL): просто говорит действие.
        - music/video/film (с URL): сохраняет _pending_url и ждёт ответа.
        Возвращает ПУСТУЮ строку, потому что речь происходит здесь,
        иначе _loop проговорит текст повторно.
        """
        ent_type = ent.get("type", "")
        name = ent.get("name", "")
        url = ent.get("url")
        action = ent.get("action", "")

        if ent_type in ("rest", "game"):
            # Просто говорим и всё
            if action and self.voice:
                self._say(action)
            return ""

        if ent_type in ("music", "video", "film") and url:
            # Сохраняем ожидание и спрашиваем
            mood = "нейтральное"
            if self.soul:
                try:
                    mood = self.soul.get_status().get("mood", "нейтральное")
                except Exception:
                    _ilog.debug("psutil check failed — skipping monitoring")
            self._pending_url = url
            self._pending_name = name
            msg = f"Создатель, я вижу, ты {mood}. Включить {name}? Скажи «да» или «нет»."
            if self.voice:
                self._say(msg)
            return ""

        return ""

    def get_status(self) -> str:
        if not self.running:
            return "🧠 Инициатива выключена"
        elapsed = int(time.time() - self._last_suggest)
        return f"🧠 Инициатива активна (прошло {elapsed} сек с последнего предложения)"

    # ------------------------------------------------------------
    # АВТОНОМНОСТЬ (1.6.0)
    # ------------------------------------------------------------
    _silence_counter = 0

    def _check_silence(self):
        """Если ответа нет 5+ минут — напоминает о себе."""
        type(self)._silence_counter += 1
        if type(self)._silence_counter >= 10 and self.voice:
            try:
                self._say("Создатель, ты тут? Я на посту.")
            except Exception:
                _ilog.debug("voice unavailable for silence check")
            type(self)._silence_counter = 0

    def _check_context(self):
        """Если awareness видит игру — предлагает бота (раз в ~7 минут)."""
        if self.awareness and random.random() < 0.03:
            try:
                activity = self.awareness.get_last_activity()
                if activity == "game" and self.voice:
                    self._say("Создатель, вижу, ты играешь. Запустить бота?")
            except Exception:
                _ilog.debug("context check skipped")