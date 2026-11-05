"""
user_profile.py — Долгосрочный профиль пользователя.
Хранит факты о создателе (имя, предпочтения, привычки).
"""
import os
import json
from core.logger import get_logger
_log = get_logger("user_profile")


class UserProfile:
    def __init__(self, path: str = "data/user_profile.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                _log.debug("пропущено в core/user_profile.py (строка 23)")
        return {
            "name": None,
            "likes": [],
            "dislikes": [],
            "habits": [],
            "facts": [],
        }

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            _log.debug("пропущено в core/user_profile.py (строка 37)")

    def set_name(self, name: str):
        self.data["name"] = name
        self.save()
        return f"✅ Запомнил имя: {name}"

    def add_fact(self, fact: str):
        if fact not in self.data["facts"]:
            self.data["facts"].append(fact)
            self.save()
            return f"🧠 Запомнил факт: {fact}"
        return "Я это уже знаю."

    def add_like(self, item: str):
        if item not in self.data["likes"]:
            self.data["likes"].append(item)
            self.save()
            return f"👍 Запомнил, что ты любишь: {item}"
        return "Я это уже знаю."

    def list_facts(self) -> list:
        return list(self.data["facts"])

    def remove_fact(self, key: str) -> str:
        """Удаляет факт по номеру (из list_facts) или по подстроке. Неоднозначное не трогает."""
        facts = self.data["facts"]
        key = (key or "").strip()
        if not key:
            return "⚠️ Укажи номер или текст факта."
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(facts):
                removed = facts.pop(idx)
                self.save()
                return f"🗑️ Забыл факт: {removed}"
            return f"⚠️ Нет факта с номером {key}."
        matches = [i for i, f in enumerate(facts) if key.lower() in f.lower()]
        if not matches:
            return f"⚠️ Не нашёл факт, похожий на «{key}»."
        if len(matches) > 1:
            return "⚠️ Подходит несколько фактов, назови номер:\n" + "\n".join(
                f"{i + 1}. {facts[i]}" for i in matches)
        removed = facts.pop(matches[0])
        self.save()
        return f"🗑️ Забыл факт: {removed}"

    def get_context(self) -> str:
        """Формирует строку для системного промпта ИИ."""
        parts = []
        if self.data.get("name"):
            parts.append(f"Пользователя зовут {self.data['name']}.")
        if self.data.get("likes"):
            parts.append(f"Он любит: {', '.join(self.data['likes'])}.")
        if self.data.get("dislikes"):
            parts.append(f"Он не любит: {', '.join(self.data['dislikes'])}.")
        if self.data.get("facts"):
            parts.append(f"Известные факты: {'; '.join(self.data['facts'])}.")
        
        if parts:
            return " ".join(parts)
        return ""


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_profile = None

def get_profile() -> UserProfile:
    global _profile
    if _profile is None:
        _profile = UserProfile()
    return _profile