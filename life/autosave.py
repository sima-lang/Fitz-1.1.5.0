"""
autosave.py — Автосохранение данных Фитца.
Каждые N секунд сохраняет brain.json, soul.json, tasks.json и создаёт бэкап.
Кроссплатформенно: чистый Python.
"""
import os
import json
import time
import threading
import shutil
from datetime import datetime
from core.logger import get_logger
_log = get_logger("autosave")


class AutoSave:
    def __init__(self, brain=None, soul=None, memory=None, interval: int = 60):
        self.brain = brain
        self.soul = soul
        self.memory = memory
        self.interval = interval  # секунд
        self.running = False
        self._thread = None
        self.backup_dir = "data/autosave"
        os.makedirs(self.backup_dir, exist_ok=True)

    def start(self) -> str:
        if self.running:
            return "💾 Автосохранение уже активно"
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return f"💾 Автосохранение активировано (каждые {self.interval} сек)"

    def stop(self) -> str:
        self.running = False
        return "⏹️ Автосохранение выключено"

    def _loop(self):
        while self.running:
            time.sleep(self.interval)
            try:
                self._save_all()
            except Exception as e:
                print(f"⚠️ AutoSave: {e}")

    def _save_all(self):
        """Сохраняет все данные и создаёт бэкап."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1) сохраняем brain
        if self.brain:
            try:
                self.brain.save()
            except Exception:
                _log.debug("пропущено в life/autosave.py (строка 56)")

        # 2) сохраняем soul
        if self.soul:
            try:
                self.soul.save()
            except Exception:
                _log.debug("пропущено в life/autosave.py (строка 63)")

        # 3) собираем данные для бэкапа
        data = {
            "timestamp": timestamp,
            "brain": self.brain.data if self.brain else {},
            "soul": self.soul.data if self.soul else {},
            "memory": self.memory.get_history(100) if self.memory else [],
        }

        # 4) пишем бэкап
        backup_file = os.path.join(self.backup_dir, f"autosave_{timestamp}.json")
        try:
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            _log.debug("пропущено в life/autosave.py (строка 79)")

        # 5) копируем последний бэкап в latest.json
        try:
            shutil.copy2(backup_file, os.path.join(self.backup_dir, "latest.json"))
        except Exception:
            _log.debug("пропущено в life/autosave.py (строка 85)")

        # 6) чистим старые бэкапы (оставляем 10)
        try:
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if f.endswith(".json") and f != "latest.json"]
            )
            for old in backups[:-10]:
                os.remove(os.path.join(self.backup_dir, old))
        except Exception:
            _log.debug("пропущено в life/autosave.py (строка 95)")

    def restore_latest(self) -> str:
        """Восстанавливает последнее сохранение."""
        latest = os.path.join(self.backup_dir, "latest.json")
        if not os.path.exists(latest):
            return "❌ Нет сохранённых данных"
        try:
            with open(latest, "r", encoding="utf-8") as f:
                data = json.load(f)

            # восстанавливаем brain
            if self.brain and "brain" in data:
                self.brain.data = data["brain"]
                self.brain.save()

            # восстанавливаем soul
            if self.soul and "soul" in data:
                self.soul.data = data["soul"]
                self.soul.save()

            return f"✅ Восстановлено сохранение от {data.get('timestamp', 'неизвестно')}"
        except Exception as e:
            return f"❌ Ошибка восстановления: {e}"

    def get_status(self) -> str:
        try:
            count = len([f for f in os.listdir(self.backup_dir) if f.endswith(".json")])
        except Exception:
            count = 0
        status = "✅ активно" if self.running else "❌ выключено"
        return f"💾 Автосохранение: {status}\n📁 Бэкапов: {count}"


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_autosave = None


def get_autosave(brain=None, soul=None, memory=None, interval: int = 60) -> AutoSave:
    global _autosave
    if _autosave is None:
        _autosave = AutoSave(brain=brain, soul=soul, memory=memory, interval=interval)
    return _autosave