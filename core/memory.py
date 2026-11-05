"""
memory.py — краткосрочная память и логи Фитца 1.5.0
Совместим со старым data/session.log (строки вида "[YYYY-MM-DD HH:MM:SS] текст").
Добавлен get_recent_pairs() — структурированное чтение для контекста ИИ.
"""
import os
import re
from datetime import datetime
from core.logger import get_logger
_log = get_logger("memory")


# Регулярка для разбора строк вида "[2026-10-30 20:06:00] Ты: привет"
_LINE_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(?P<body>.*)$"
)


class Memory:
    def __init__(self, path: str = "data/session.log"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    # ---------- запись ----------
    def log(self, text: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {text}\n")
        except Exception as e:
            print(f"⚠️ Ошибка записи лога: {e}")

    # ---------- чтение (сырое) ----------
    def get_history(self, limit: int = 30) -> list:
        """Последние N строк из лога (как раньше — для отладки)."""
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [l.rstrip("\n") for l in lines[-limit:]]
        except Exception:
            return []

    # ---------- чтение (структурированное) ----------
    def get_recent_pairs(self, limit: int = 10) -> list:
        """
        Возвращает последние N пар (user, assistant) из session.log.

        Формат записей, который мы пишем в _process_worker:
          [ts] Ты: <текст>
        А ответы Фитца в session.log сейчас НЕ пишутся (только через brain.learn
        в brain.json). Поэтому здесь восстанавливаем только user-сторону,
        а assistant подтянет brain.get_context. Метод нужен, чтобы:
          • показать в контексте, что пользователь писал, даже если brain.json
            почему-то пуст;
          • не терять сообщения, которые упали до brain.learn.
        """
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return []

        pairs = []
        for raw in lines[-limit * 4:]:  # с запасом, чтобы набрать limit пар
            m = _LINE_RE.match(raw.rstrip("\n"))
            if not m:
                continue
            body = m.group("body").strip()
            if body.startswith("Ты:"):
                user_text = body[3:].strip()
                if user_text:
                    pairs.append({"user": user_text, "response": None})
            elif body.startswith("🛡️ Фитц:") or body.startswith("Фитц:"):
                resp = body.split(":", 1)[1].strip()
                if pairs and pairs[-1]["response"] is None:
                    pairs[-1]["response"] = resp
        return pairs[-limit:]

    def search(self, keyword: str) -> list:
        if not os.path.exists(self.path):
            return []
        keyword = keyword.lower()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return [l.rstrip("\n") for l in f if keyword in l.lower()]
        except Exception:
            return []

    # ---------- служебное ----------
    def clear(self):
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
                return True
        except Exception:
            _log.debug("пропущено в core/memory.py (строка 100)")
        return False

    def size(self) -> int:
        try:
            return os.path.getsize(self.path) if os.path.exists(self.path) else 0
        except Exception:
            return 0