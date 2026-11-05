"""
soul.py — Характер, настроение, энергия Фитца.
Хранит состояние в data/soul.json (чтобы не сбрасывалось при перезапуске).
Блок 5.2: капс/мат → раздражённое настроение.
"""
import os
import json
import random
from datetime import datetime
from core.logger import get_logger
_log = get_logger("soul")

# Порог «скучает»: секунд без обращения. «Устаёт»: задач за последний час.
BORED_AFTER_SECONDS = 30 * 60
BUSY_TASKS_PER_HOUR = 20

# Шкала настроения 0–100: 50 — норма, ниже — хуже, выше — лучше.
MOOD_NORM = 50
MOOD_DRIFT_PER_SECOND_STEP = 1
MOOD_DRIFT_STEP_SECONDS = 600


def mood_label(score: int) -> str:
    if score <= 20:
        return "сердитое"
    if score <= 35:
        return "грустное"
    if score <= 60:
        return "нейтральное"
    return "весёлое"


class Soul:
    def __init__(self, path: str = "data/soul.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.data = self._load()

    def _default(self):
        return {
            "mood_score": MOOD_NORM,
            "mood": "нейтральное",
            "energy": 100,
            "happiness": 70,
            "conversation_count": 0,
            "last_interaction": datetime.now().isoformat(),
            "traits": {
                "humor": 0.5,
                "empathy": 0.7,
                "curiosity": 0.8,
                "talkativeness": 0.6,
            },
        }

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                default = self._default()
                for k, v in default.items():
                    data.setdefault(k, v)
                return data
            except Exception:
                _log.debug("пропущено в life/soul.py (строка 49)")
        return self._default()

    def save(self):
        try:
            self.data["last_interaction"] = datetime.now().isoformat()
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            _log.debug("пропущено в life/soul.py (строка 58)")

    # ---------- настроение (шкала 0–100) ----------
    _NORM = {"energy": 70, "happiness": 60}

    def _drift_toward_norm(self) -> None:
        """Возвращает energy, happiness и mood_score к норме по прошедшему времени."""
        try:
            last = datetime.fromisoformat(self.data.get("last_interaction") or datetime.now().isoformat())
        except ValueError:
            return
        steps = int((datetime.now() - last).total_seconds() // MOOD_DRIFT_STEP_SECONDS)
        if steps <= 0:
            return
        for key, norm in self._NORM.items():
            cur = self.data.get(key, norm)
            if cur < norm:
                self.data[key] = min(norm, cur + steps)
            elif cur > norm:
                self.data[key] = max(norm, cur - steps)
        score = self.data.get("mood_score", MOOD_NORM)
        if score < MOOD_NORM:
            self.data["mood_score"] = min(MOOD_NORM, score + steps)
        elif score > MOOD_NORM:
            self.data["mood_score"] = max(MOOD_NORM, score - steps)

    def _shift_mood(self, delta: int) -> None:
        score = self.data.get("mood_score", MOOD_NORM) + delta
        self.data["mood_score"] = max(0, min(100, score))

    def _sync_mood_label(self) -> None:
        self.data["mood"] = mood_label(self.data["mood_score"])

    def analyze_mood(self, text: str) -> str:
        low = text.lower()
        self._drift_toward_norm()

        # ===== Блок 5.2: капс и мат → раздражение =====
        is_caps = text.isupper() and len(text.strip()) > 3
        has_profanity = any(w in low for w in ("бля", "хер", "хуй", "пизд", "ёб", "еб"))
        if is_caps or has_profanity:
            self._shift_mood(-25)
        elif any(w in low for w in ("устал", "спать", "вымотан", "без сил")):
            self.data["energy"] = max(0, self.data["energy"] - 10)
            self._shift_mood(-10)
        elif any(w in low for w in ("рад", "круто", "отлично", "класс", "весело")):
            self.data["happiness"] = min(100, self.data["happiness"] + 5)
            self._shift_mood(15)
        elif any(w in low for w in ("грустно", "плохо", "тоскливо", "печально")):
            self.data["happiness"] = max(0, self.data["happiness"] - 10)
            self._shift_mood(-15)
        elif any(w in low for w in ("зол", "бесит", "раздражён")):
            self._shift_mood(-20)

        self._sync_mood_label()
        self.data["conversation_count"] += 1
        self.save()
        return self.data["mood"]

    # ---------- настроение по активности ----------
    def record_task(self) -> None:
        """Учитывает выполненную задачу для расчёта усталости (только за последний час)."""
        now = datetime.now().timestamp()
        tasks = [t for t in self.data.get("task_times", []) if now - t < 3600]
        tasks.append(now)
        self.data["task_times"] = tasks
        self.save()

    def tasks_last_hour(self) -> int:
        now = datetime.now().timestamp()
        return sum(1 for t in self.data.get("task_times", []) if now - t < 3600)

    def tick_activity(self) -> str:
        """«Устаёт» при многих задачах за час, «скучает» при долгом простое.
        Явные эмоции из текста пользователя не перезаписываем."""
        if self.data.get("mood") not in ("нейтральное", "скучает", "усталое"):
            return self.data["mood"]
        if self.tasks_last_hour() >= BUSY_TASKS_PER_HOUR:
            self.data["mood"] = "усталое"
        else:
            last = datetime.fromisoformat(self.data.get("last_interaction", datetime.now().isoformat()))
            idle = (datetime.now() - last).total_seconds()
            self.data["mood"] = "скучает" if idle >= BORED_AFTER_SECONDS else "нейтральное"
        return self.data["mood"]

    def get_reaction(self) -> str:
        reactions = {
            "нейтральное": ["Понял. Я здесь.", "Слушаю.", "Говори.", "Я рядом."],
            "весёлое": ["Хорошее настроение! 😊", "Ты сегодня в ударе! 🔥"],
            "усталое": ["Ты устал. Может, отдохнёшь? 😔", "Я посторожу."],
            "грустное": ["Грустно? Рассказывай. Я слушаю.", "Я рядом. Ты не один."],
            "сердитое": [
                "Спокойно. Выдохни.",
                "Я понимаю. Давай разберёмся спокойно.",
                "Не кипятись. Я рядом.",
            ],
            "скучает": ["Тихо тут... Может, поболтаем? 🥱", "Ну что, долго ждать будем?"],
        }
        return random.choice(reactions.get(self.data["mood"], reactions["нейтральное"]))

    def greet(self) -> str:
        hour = datetime.now().hour
        if hour < 6:
            return "Ночь. Я рядом, если что."
        elif hour < 12:
            return "Доброе утро, создатель. С чего начнём?"
        elif hour < 18:
            return "День в разгаре. Я здесь, если понадоблюсь."
        else:
            return "Вечер. Может, стоит отдохнуть?"

    def get_status(self) -> dict:
        return {
            "mood": self.data["mood"],
            "energy": self.data["energy"],
            "happiness": self.data["happiness"],
            "conversations": self.data["conversation_count"],
            "traits": self.data["traits"],
        }

    def get_status_text(self) -> str:
        d = self.data
        return (
            f"🧬 Настроение: {d['mood']}\n"
            f"⚡ Энергия: {d['energy']}%\n"
            f"😊 Счастье: {d['happiness']}%\n"
            f"💬 Разговоров: {d['conversation_count']}"
        )