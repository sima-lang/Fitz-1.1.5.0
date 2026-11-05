"""
core/autonomy.py — автономный режим Фитца (версия 1.2.0.1, этап 1: безопасные действия).

Что здесь:
- реестр БЕЗОПАСНЫХ действий, которые Фитц может выполнять сам (без подтверждения);
- расписание в data/autonomy.json (атомарная запись);
- журнал самостоятельных действий в data/autonomy.log;
- кнопка остановки: флаг в data/autonomy.json (enabled=false), команда «стоп автономность».

Опасные действия (запуск приложений, выключение, удаление файлов вне проекта,
отправка наружу) сюда НЕ добавляются: для них нужен отдельный путь с подтверждением.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from core.logger import get_logger
from core.utils import atomic_write_json

_log = get_logger("autonomy", file="autonomy.log")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCHEDULE_FILE = DATA_DIR / "autonomy.json"
JOURNAL_FILE = DATA_DIR / "autonomy.log"

_lock = threading.Lock()

DEFAULT_STATE = {
    "enabled": False,
    "tasks": [],
}


# ----------------------------------------------------------------------
# Безопасные действия (без подтверждения)
# ----------------------------------------------------------------------
def action_check_system() -> dict:
    """Состояние системы: ЦП, ОЗУ, диск. Ничего не меняет."""
    import psutil
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


SAFE_ACTIONS = {
    "check_system": action_check_system,
}


# ----------------------------------------------------------------------
# Состояние (расписание и флаг включения)
# ----------------------------------------------------------------------
def load_state() -> dict:
    try:
        with open(SCHEDULE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_STATE, **data}
    except FileNotFoundError:
        return dict(DEFAULT_STATE)
    except (json.JSONDecodeError, OSError) as e:
        _log.warning("autonomy.json повреждён, режим выключен: %s", e)
        return dict(DEFAULT_STATE)


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        atomic_write_json(str(SCHEDULE_FILE), state)


def is_enabled() -> bool:
    return bool(load_state().get("enabled", False))


def set_enabled(value: bool) -> None:
    state = load_state()
    state["enabled"] = bool(value)
    save_state(state)
    _journal("режим " + ("включён" if value else "выключен"))


def stop() -> str:
    """Кнопка остановки / команда «стоп автономность»."""
    set_enabled(False)
    return "Автономный режим остановлен."


# ----------------------------------------------------------------------
# Журнал
# ----------------------------------------------------------------------
def _journal(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}\n"
    with _lock:
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    _log.info(message)


# ----------------------------------------------------------------------
# Выполнение задач
# ----------------------------------------------------------------------
def run_safe_action(name: str):
    """Выполняет безопасное действие по имени. Опасные имена отклоняются."""
    fn = SAFE_ACTIONS.get(name)
    if fn is None:
        _journal(f"ОТКЛОНЕНО: действие «{name}» не входит в безопасный набор")
        return None
    try:
        result = fn()
        _journal(f"выполнено «{name}»: {result}")
        return result
    except Exception as e:
        _journal(f"ОШИБКА «{name}»: {e!r}")
        return None


def run_due_tasks() -> int:
    """Запускает задачи расписания, если режим включён. Возвращает число выполненных."""
    state = load_state()
    if not state.get("enabled"):
        return 0
    done = 0
    for task in state.get("tasks", []):
        if task.get("kind") != "safe":
            continue
        if run_safe_action(task.get("action", "")) is not None:
            done += 1
    return done


def handle_stop_command(text: str):
    """Возвращает ответ, если фраза — команда управления автономностью, иначе None."""
    low = text.lower().strip()
    if low in ("стоп автономность", "останови автономность", "выключи автономность"):
        return stop()
    if low in ("включи автономность", "запусти автономность"):
        set_enabled(True)
        return "Автономный режим включён (только безопасные действия)."
    return None
