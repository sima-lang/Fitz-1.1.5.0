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
        # Атомарно: загружаем актуальное состояние, сливаем и пишем.
        # Так цепочка/очередь не теряются при конкурентных вызовах из разных потоков.
        current = load_state()
        current.update(state)
        atomic_write_json(str(SCHEDULE_FILE), current)


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
# Очередь задач Task Runner (этап 3)
# ----------------------------------------------------------------------
MAX_QUEUE = 10


def enqueue_task(goal: str) -> str:
    """Ставит цель в очередь. Выполнится при простое, если режим включён."""
    goal = (goal or "").strip()
    if not goal:
        return "Не понял, какую задачу поставить."
    state = load_state()
    queue = state.get("queue", [])
    if len(queue) >= MAX_QUEUE:
        return f"Очередь полна ({MAX_QUEUE}). Дождись выполнения задач."
    queue.append({"goal": goal[:500], "status": "queued"})
    state["queue"] = queue
    save_state(state)
    _journal(f"задача в очереди: {goal[:120]}")
    return "Задача поставлена в очередь. Выполню, когда ты будешь неактивен, и автономность включена."


def run_task(goal: str | None = None, api=None) -> dict | None:
    """
    Точка входа Task Runner. Берёт задачу из очереди (или goal), выполняет по шагам.
    Работает только при включённой автономности. Возвращает сводку или None.
    Эмуляционные шаги (type_text, click_at, press_key) ставятся на паузу и ждут «да».
    """
    if not is_enabled():
        return None
    state = load_state()
    if goal is None:
        queue = state.get("queue", [])
        item = next((q for q in queue if q.get("status") == "queued"), None)
        if item is None:
            return None
        goal = item["goal"]
        item["status"] = "running"
        save_state(state)
    from core import task_runner
    try:
        summary = task_runner.run_cycle(goal, api=api)
    except Exception as e:
        _log.error("задача упала: %r", e)
        summary = {"goal": goal, "steps": 0, "ok": 0, "error": repr(e)}
    if goal is not None:
        state = load_state()
        for q in state.get("queue", []):
            if q.get("goal") == goal and q.get("status") == "running":
                # Если задача ждёт подтверждения — не помечаем как failed
                if summary.get("pending"):
                    q["status"] = "awaiting_confirm"
                else:
                    q["status"] = "done" if summary.get("ok") else "failed"
        save_state(state)
    _journal(f"задача выполнена: {goal[:80]} — шагов ok {summary.get('ok', 0)}/{summary.get('steps', 0)}"
             + (" (ожидает подтверждения)" if summary.get("pending") else ""))
    return summary


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
    "sleep_pc": "усыпить ПК",
}


# ----------------------------------------------------------------------
# Эмуляция ввода: флаг по умолчанию выключен
# ----------------------------------------------------------------------
def is_emulation_enabled() -> bool:
    return bool(load_state().get("emulation_enabled", False))


def set_emulation(value: bool) -> None:
    state = load_state()
    state["emulation_enabled"] = bool(value)
    save_state(state)
    _journal("эмуляция " + ("включена" if value else "выключена"))


def sleep_pc() -> str:
    """Усыпление ПК: только через подтверждение, и только при включённой автономности и пустой очереди."""
    if not is_enabled():
        return "Автономность выключена — усыпление не выполняю."
    if any(q.get("status") == "queued" for q in load_state().get("queue", [])):
        return "В очереди есть задачи — усыпление отложено."
    return request_dangerous_action("sleep_pc")["question"]

# Разрешённые приложения для launch_app. Совпадают с ключами словаря apps в core/tools.open_app.
ALLOWED_APPS = (
    "steam", "firefox", "браузер", "chrome", "код", "vscode",
    "терминал", "блокнот", "telegram", "discord", "spotify", "vlc",
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
    with _lock:
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
    with _lock:
        return "action" in _pending_confirm


def get_pending_question() -> str | None:
    """Возвращает текст вопроса для GUI или None, если ожидания нет."""
    with _lock:
        action = _pending_confirm.get("action")
        arg = _pending_confirm.get("arg", "")
    if action is None:
        return None
    what = DANGEROUS_ACTIONS.get(action, action)
    what += (f" «{arg}»" if arg else "")
    return f"⚠️ Создатель, я хочу выполнить: {what}. Подтверждаешь? Напиши «да» или «нет»."


def resolve_confirm(answer: str) -> str | None:
    """
    Обрабатывает ответ «да»/«нет» на ожидающее подтверждение.
    Возвращает текст ответа Фитца или None, если ожидания нет.
    Действие выполняется ТОЛЬКО после явного «да».
    """
    with _lock:
        if "action" not in _pending_confirm:
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
    elif action == "sleep_pc":
        import subprocess
        try:
            r = subprocess.run(["systemctl", "suspend"], capture_output=True, text=True, timeout=15)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            result = f"⚠️ Не удалось усыпить ПК: {e}"
        else:
            result = "💤 Усыпляю ПК." if r.returncode == 0 else f"⚠️ Не удалось: {(r.stderr or r.stdout).strip()[:200]}"
    elif action in ("click_at", "type_text", "press_key"):
        from core import agent_tools
        res = agent_tools.emulate(action, arg)
        if not res.get("ok"):
            _journal(f"ЭМУЛЯЦИЯ ОТКЛОНЕНА «{action}»: {res.get('error') or res.get('result')}")
            return f"Эмуляция не выполнена: {res.get('error') or res.get('result')}"
        result = res["result"]
    else:
        _journal(f"НЕ ВЫПОЛНЕНО: исполнитель для «{action}» не подключён")
        return f"Исполнитель для «{DANGEROUS_ACTIONS.get(action, action)}» ещё не подключён."
    _journal(f"ВЫПОЛНЕНО «{action}» {arg}: {result}".rstrip())
    # Цепочка: после подтверждённого шага выполняем оставшиеся шаги задачи.
    if action in ("click_at", "type_text", "press_key"):
        from core import task_runner
        # Текущий подтверждённый шаг уже выполнен — снимаем его с начала цепочки, иначе он повторится.
        chain = load_chain()
        if chain and chain[0].get("tool") == action:
            save_chain(chain[1:])
        cont = task_runner.continue_chain()
        if cont:
            result = f"{result}\n{cont}"
        elif not load_chain():
            # Цепочка была и исчерпана этим подтверждением — задача завершена.
            _journal("Задача выполнена полностью")
            result = f"{result}\nЗадача выполнена полностью."
    return result


# ----------------------------------------------------------------------
# Цепочка шагов: остаток задачи, который ждёт подтверждения эмуляции.
# Хранится в data/autonomy.json (ключ "chain"), чтобы пережить перезапуск.
# ----------------------------------------------------------------------
def save_chain(steps: list) -> None:
    save_state({"chain": list(steps)})
    _journal(f"ЦЕПОЧКА сохранена: {len(steps)} шагов ждут продолжения")


def load_chain() -> list:
    return list(load_state().get("chain", []))


def clear_chain() -> None:
    state = load_state()
    if state.get("chain"):
        save_state({"chain": []})
        _journal("ЦЕПОЧКА очищена")


def cancel_tasks() -> str:
    """
    Команда «отмени задачу»: снимает остаток цепочки и всю очередь задач.
    Само действие не выполняется — только отмена запланированного.
    """
    save_state({"chain": [], "queue": []})
    _journal("ОТМЕНА: цепочка и очередь очищены")
    return "Задача отменена."
