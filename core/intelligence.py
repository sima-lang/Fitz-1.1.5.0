"""
intelligence.py — Долгосрочная память Фитца (SQLite).
Хранит факты, контекст диалогов, воспоминания.
Блок 4.5: дневник событий (таблица events).
Поиск по ключевым словам (без тяжёлых векторов, кроссплатформенно).
"""
import os
import re
import json
import sqlite3
from datetime import datetime
from core.logger import get_logger
_log = get_logger("intelligence")

# Долгосрочная память: максимум фактов, старые удаляются
LONG_TERM_LIMIT = 100


class Intelligence:
    def __init__(self, db_path: str = "data/intelligence.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                content TEXT,
                importance INTEGER DEFAULT 1,
                created TEXT,
                last_used TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_input TEXT,
                response TEXT,
                mood TEXT,
                topic TEXT,
                timestamp TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                value TEXT,
                created TEXT,
                last_accessed TEXT,
                access_count INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity TEXT,
                window TEXT,
                process TEXT,
                timestamp TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT,
                value TEXT,
                embedding TEXT,
                ts TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT,
                date TEXT,
                activity TEXT,
                ts TEXT
            )
        """)
        conn.commit()
        conn.close()

    # ============================================================
    # ЗНАНИЯ
    # ============================================================
    def add_knowledge(self, topic: str, content: str, importance: int = 1) -> bool:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT id FROM knowledge WHERE topic = ? AND content = ?",
            (topic, content),
        )
        if c.fetchone():
            conn.close()
            return False
        now = datetime.now().isoformat()
        c.execute(
            "INSERT INTO knowledge (topic, content, importance, created, last_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (topic, content, importance, now, now),
        )
        conn.commit()
        conn.close()
        return True

    def search_knowledge(self, query: str, limit: int = 5) -> list:
        """Поиск по ключевым словам (без учёта регистра)."""
        if not query:
            return []
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
        if not words:
            return []

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        results = []
        for w in words:
            like = f"%{w}%"
            c.execute(
                "SELECT topic, content, importance FROM knowledge "
                "WHERE LOWER(topic) LIKE ? OR LOWER(content) LIKE ? "
                "ORDER BY importance DESC LIMIT ?",
                (like, like, limit),
            )
            for row in c.fetchall():
                if row not in results:
                    results.append(row)

        if results:
            now = datetime.now().isoformat()
            for topic, content, _ in results:
                c.execute(
                    "UPDATE knowledge SET last_used = ? "
                    "WHERE topic = ? AND content = ?",
                    (now, topic, content),
                )
            conn.commit()
        conn.close()

        return [
            {"topic": t, "content": c, "importance": imp}
            for t, c, imp in results[:limit]
        ]

    # ============================================================
    # КОНТЕКСТ ДИАЛОГОВ
    # ============================================================
    def add_context(self, user_input: str, response: str,
                    mood: str = "нейтральное", topic: str = "general"):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO context (user_input, response, mood, topic, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_input, response, mood, topic, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_context(self, limit: int = 10) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT user_input, response, timestamp, mood FROM context "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = c.fetchall()
        conn.close()
        return [
            {"user": u, "response": r, "time": ts, "mood": m}
            for u, r, ts, m in reversed(rows)
        ]

    def search_context(self, query: str, limit: int = 5) -> list:
        """
        RAG — поиск по истории диалогов по ключевым словам.
        Возвращает записи, где user_input или response содержат слова из query.
        """
        if not query:
            return []
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
        if not words:
            return []

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        results = []
        for w in words:
            like = f"%{w}%"
            c.execute(
                "SELECT user_input, response, timestamp, mood FROM context "
                "WHERE LOWER(user_input) LIKE ? OR LOWER(response) LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (like, like, limit),
            )
            for row in c.fetchall():
                if row not in results:
                    results.append(row)
        conn.close()

        return [
            {"user": u, "response": r, "time": ts, "mood": m}
            for u, r, ts, m in results[:limit]
        ]

    # ============================================================
    # ДОЛГОСРОЧНАЯ ПАМЯТЬ (RAG) — 1.6.0
    # ============================================================
    def remember_long_term(self, key: str, value: str) -> bool:
        """Сохраняет факт в long_term_memory. Возвращает True если добавлено."""
        if not key or not value:
            return False
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT id FROM long_term_memory WHERE key = ?",
            (key,),
        )
        if c.fetchone():
            conn.close()
            return False
        c.execute(
            "INSERT INTO long_term_memory (key, value, embedding, ts) "
            "VALUES (?, ?, ?, ?)",
            (key, value, "", datetime.now().isoformat()),
        )
        # Сжатие: держим не более LONG_TERM_LIMIT фактов, старые удаляем
        c.execute(
            "DELETE FROM long_term_memory WHERE id NOT IN ("
            "SELECT id FROM long_term_memory ORDER BY id DESC LIMIT ?)",
            (LONG_TERM_LIMIT,),
        )
        conn.commit()
        conn.close()
        return True

    def recall_long_term(self, query: str, limit: int = 3) -> list:
        """Поиск по long_term_memory по ключевым словам (RAG без векторов)."""
        if not query:
            return []
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
        if not words:
            return []

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        results = []
        for w in words:
            like = f"%{w}%"
            c.execute(
                "SELECT key, value, ts FROM long_term_memory "
                "WHERE LOWER(key) LIKE ? OR LOWER(value) LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (like, like, limit),
            )
            for row in c.fetchall():
                if row not in results:
                    results.append(row)
        conn.close()
        return [
            {"key": k, "value": v, "ts": ts}
            for k, v, ts in results[:limit]
        ]

    def get_last_long_term(self, limit: int = 1) -> list:
        """Последние записи долгосрочной памяти."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT key, value, ts FROM long_term_memory "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = c.fetchall()
        conn.close()
        return [
            {"key": k, "value": v, "ts": ts}
            for k, v, ts in rows
        ]

    # ============================================================
    # ДОЛГОСРОЧНЫЕ ВОСПОМИНАНИЯ
    # ============================================================
    def remember(self, key: str, value: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute(
            "INSERT OR REPLACE INTO memories (key, value, created, last_accessed, access_count) "
            "VALUES (?, ?, ?, ?, 0)",
            (key, value, now, now),
        )
        conn.commit()
        conn.close()

    def recall(self, key: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT value, access_count FROM memories WHERE key = ?",
            (key,),
        )
        row = c.fetchone()
        if row:
            value, count = row
            c.execute(
                "UPDATE memories SET last_accessed = ?, access_count = ? WHERE key = ?",
                (datetime.now().isoformat(), count + 1, key),
            )
            conn.commit()
            conn.close()
            return value
        conn.close()
        return None

    def get_all_memories(self, limit: int = 50) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT key, value, created, access_count FROM memories "
            "ORDER BY access_count DESC LIMIT ?",
            (limit,),
        )
        rows = c.fetchall()
        conn.close()
        return [
            {"key": k, "value": v, "created": cr, "access": ac}
            for k, v, cr, ac in rows
        ]

    def forget(self, key: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM memories WHERE key = ?", (key,))
        conn.commit()
        conn.close()

    # ============================================================
    # ФАКТЫ О ПОЛЬЗОВАТЕЛЕ (через API)
    # ============================================================
    def extract_facts(self, text: str, api) -> list:
        """Выделяет факты о пользователе (имя, работа, привычки). Пустой список, если API молчит."""
        if not text or not api or not getattr(api, "enabled", False):
            return []
        prompt = (
            "Выдели факты о пользователе: имя, работа, привычки. "
            "Каждый факт — короткая фраза на русском. "
            "Если фактов нет, верни пустой массив. "
            'Ответь ТОЛЬКО JSON-массивом строк, например ["зовут Андрей", "работает программистом"].\n\n'
            f"Текст: {text}"
        )
        try:
            raw = api.ask(prompt, max_tokens=200, temperature=0.2) or ""
        except Exception as e:
            _log.debug(f"extract_facts: ошибка API: {e!r}")
            return []
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group(0))
        except (ValueError, TypeError):
            return []
        return [str(x).strip() for x in items if isinstance(x, str) and str(x).strip()][:5]

    # ============================================================
    # ДНЕВНИК СОБЫТИЙ (Блок 4.5)
    # ============================================================
    def add_episode(self, activity: str, when: datetime = None) -> None:
        """Эпизодическая память: что Фитц делал в конкретный час (14:00, 15:00...)."""
        when = when or datetime.now()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO episodes (hour, date, activity, ts) VALUES (?, ?, ?, ?)",
            (when.strftime("%H:00"), when.strftime("%Y-%m-%d"),
             activity, when.isoformat()),
        )
        # Храним последние 1000 эпизодов
        c.execute(
            "DELETE FROM episodes WHERE id NOT IN ("
            "SELECT id FROM episodes ORDER BY id DESC LIMIT 1000)"
        )
        conn.commit()
        conn.close()

    def get_episodes(self, date_str: str = None) -> list:
        """Возвращает эпизоды за дату: [(час, активность), ...] по времени."""
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT hour, activity FROM episodes WHERE date = ? ORDER BY ts",
            (date_str,),
        )
        rows = c.fetchall()
        conn.close()
        return rows

    def add_event(self, activity: str, window: str = "", process: str = ""):
        """Пишет смену активности в дневник."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "INSERT INTO events (activity, window, process, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (activity, window or "", process or "", datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()
        except Exception:
            _log.debug("пропущено в core/intelligence.py (строка 390)")

    def get_events_for_date(self, date_str: str = None, limit: int = 50) -> list:
        """
        Возвращает события за дату (YYYY-MM-DD). Если date_str None — за сегодня.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "SELECT activity, window, process, timestamp FROM events "
                "WHERE timestamp LIKE ? ORDER BY id DESC LIMIT ?",
                (f"{date_str}%", limit),
            )
            rows = c.fetchall()
            conn.close()
            return [
                {"activity": a, "window": w, "process": p, "time": ts}
                for a, w, p, ts in reversed(rows)
            ]
        except Exception:
            return []

    def get_events_summary(self, date_str: str = None) -> str:
        """
        Краткая сводка: сколько времени в какой активности за дату.
        """
        events = self.get_events_for_date(date_str, limit=500)
        if not events:
            return "📭 Нет записей за этот день"

        from datetime import datetime as _dt
        durations = {}
        for i, ev in enumerate(events):
            try:
                t_start = _dt.fromisoformat(ev["time"])
                if i + 1 < len(events):
                    t_end = _dt.fromisoformat(events[i + 1]["time"])
                else:
                    t_end = _dt.now()
                delta = (t_end - t_start).total_seconds()
                act = ev["activity"] or "unknown"
                durations[act] = durations.get(act, 0) + delta
            except Exception:
                _log.debug("пропущено в core/intelligence.py (строка 436)")
                continue

        ru = {
            "coding": "💻 код",
            "game": "🎮 игра",
            "music": "🎵 музыка",
            "video": "📺 видео",
            "browsing": "🌐 браузер",
            "chatting": "💬 общение",
            "work": "📄 работа",
            "terminal": "⌨️ терминал",
            "unknown": "❔ прочее",
        }

        lines = [f"📔 ДНЕВНИК за {date_str or 'сегодня'}:"]
        for act, sec in sorted(durations.items(), key=lambda x: -x[1]):
            if sec < 60:
                continue
            mins = int(sec // 60)
            name = ru.get(act, act)
            lines.append(f"  • {name}: ~{mins} мин")
        return "\n".join(lines) if len(lines) > 1 else "📭 Мало данных за этот день"

    # ============================================================
    # СТАТИСТИКА
    # ============================================================
    def get_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM knowledge")
        knowledge_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM context")
        context_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM memories")
        memory_count = c.fetchone()[0]
        conn.close()
        return {
            "knowledge": knowledge_count,
            "context": context_count,
            "memories": memory_count,
        }


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_intelligence = None


def get_intelligence() -> Intelligence:
    global _intelligence
    if _intelligence is None:
        _intelligence = Intelligence()
    return _intelligence