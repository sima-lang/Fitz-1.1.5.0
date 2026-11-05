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


# ----------------------------------------------------------------------
# Этап 2: Сторож (Guardian)
# ----------------------------------------------------------------------
GUARDIAN_CPU_LIMIT = 90.0
GUARDIAN_DISK_LIMIT = 95.0
GUARDIAN_INTERVAL_SEC = 300  # 5 минут


def guardian_check(metrics: dict) -> list:
    """Возвращает список предупреждений по метрикам check_system. Чистая функция, без I/O."""
    warnings = []
    cpu = metrics.get("cpu_percent")
    disk = metrics.get("disk_percent")
    if cpu is not None and cpu > GUARDIAN_CPU_LIMIT:
        warnings.append(f"ЦП {cpu:.0f}% (порог {GUARDIAN_CPU_LIMIT:.0f}%)")
    if disk is not None and disk > GUARDIAN_DISK_LIMIT:
        warnings.append(f"диск {disk:.0f}% (порог {GUARDIAN_DISK_LIMIT:.0f}%)")
    return warnings


def run_guardian(notify=None) -> list:
    """
    Один проход Сторожа: проверяет check_system, при превышении пишет в журнал
    и вызывает notify(text) — например, для отправки в чат через add_message_signal.
    Возвращает список предупреждений.
    """
    metrics = run_safe_action("check_system")
    if not metrics:
        return []
    warnings = guardian_check(metrics)
    for w in warnings:
        text = f"⚠️ Сторож: {w}. Могу предложить очистку — скажи «очисти кэш»."
        _journal(f"СТОРОЖ: {w}")
        if notify is not None:
            try:
                notify(text)
            except Exception as e:
                _journal(f"ОШИБКА уведомления: {e!r}")
    return warnings


# ----------------------------------------------------------------------
# Этап 2: опасные действия с подтверждением
# ----------------------------------------------------------------------
DANGEROUS_ACTIONS = {
    "launch_app": "запустить приложение",
    "shutdown": "выключить ПК",
    "reboot": "перезагрузить ПК",
    "delete_outside_project": "удалить файлы вне папки проекта",
    "send_external": "отправить сообщение наружу",
}

# Разрешённые приложения для launch_app. Совпадают с ключами словаря apps в core/tools.open_app.
ALLOWED_APPS = (
    "steam", "firefox", "браузер", "chrome", "код", "vscode",
    "терминал", "telegram", "discord", "spotify", "vlc",
)


def is_allowed_app(name: str) -> bool:
    """Запуск разрешён только для имён из белого списка. Пути, аргументы и пробелы отклоняются."""
    if not name:
        return False
    return name.strip().lower() in ALLOWED_APPS


_pending_confirm = {}  # action / arg -> ожидает ответа «да/нет»


def request_dangerous_action(action: str, arg: str = "") -> dict:
    """
    Не выполняет действие. Запоминает его как ожидающее подтверждения
    и возвращает {"needs_confirm": True, "action": action, ...}.
    Для безопасных действий возвращает {"needs_confirm": False}.
    """
    if action not in DANGEROUS_ACTIONS:
        return {"needs_confirm": False, "action": action}
    _pending_confirm.clear()
    _pending_confirm["action"] = action
    _pending_confirm["arg"] = arg
    _journal(f"ЗАПРОС ПОДТВЕРЖДЕНИЯ: {action} {arg}".rstrip())
    what = DANGEROUS_ACTIONS[action] + (f" «{arg}»" if arg else "")
    return {
        "needs_confirm": True,
        "action": action,
        "arg": arg,
        "question": f"Создатель, я хочу выполнить: {what}. Подтверждаешь? (да/нет)",
    }


def has_pending_confirm() -> bool:
    return "action" in _pending_confirm


def resolve_confirm(answer: str) -> str | None:
    """
    Обрабатывает ответ «да»/«нет» на ожидающее подтверждение.
    Возвращает текст ответа Фитца или None, если ожидания нет.
    Действие выполняется ТОЛЬКО после явного «да».
    """
    if not has_pending_confirm():
        return None
    action = _pending_confirm.pop("action")
    arg = _pending_confirm.pop("arg", "")
    low = answer.lower().strip()
    if low in ("да", "подтверждаю", "yes", "ок", "давай"):
        _journal(f"ПОДТВЕРЖДЕНО: {action} {arg}".rstrip())
        return execute_confirmed(action, arg)
    if low in ("нет", "отмена", "не надо", "no"):
        _journal(f"ОТМЕНЕНО: {action} {arg}".rstrip())
        return "Хорошо, не выполняю."
    # Любой другой ответ — отменяем, чтобы не выполнить по неясному сообщению
    _journal(f"ОТМЕНЕНО (неясный ответ): {action} {arg}".rstrip())
    return "Не поняла ответ, действие отменено. Скажи «да» или «нет», если хочешь повторить."


def execute_confirmed(action: str, arg: str = "") -> str:
    """
    Исполнитель ПОДТВЕРЖДЁННОГО действия. Вызывается только из resolve_confirm
    после ответа «да». Каждое действие пишет результат в журнал.
    """
    if action == "shutdown":
        from core.tools import shutdown_pc
        result = shutdown_pc()
    elif action == "reboot":
        from core.tools import reboot_pc
        result = reboot_pc()
    elif action == "launch_app":
        if not is_allowed_app(arg):
            _journal(f"ОТКЛОНЕНО (не в списке): запуск «{arg}»")
            return f"Приложение «{arg}» не в списке разрешённых. Не запускаю."
        from core.tools import open_app
        result = open_app(arg)
    else:
        _journal(f"НЕ ВЫПОЛНЕНО: исполнитель для «{action}» не подключён")
        return f"Исполнитель для «{DANGEROUS_ACTIONS.get(action, action)}» ещё не подключён."
    _journal(f"ВЫПОЛНЕНО «{action}» {arg}: {result}".rstrip())
    return result
