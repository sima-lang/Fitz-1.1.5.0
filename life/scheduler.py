"""
life/scheduler.py — фоновый планировщик автономного режима (версия 1.2.0.1).

Работает отдельным демон-потоком и раз в интервал проверяет расписание
(data/autonomy.json). Задачи выполняются только если режим включён.
Остановка: флаг enabled=false (кнопка / «стоп автономность») или завершение процесса.

Этап 2: Сторож (Guardian) — отдельный поток, раз в 5 минут вызывает
core.autonomy.run_guardian(notify). notify передаёт GUI (add_message_signal).
"""
import threading

from core import autonomy
from core.logger import get_logger

_log = get_logger("scheduler", file="autonomy.log")

DEFAULT_INTERVAL_SEC = 60

_stop_event = threading.Event()
_thread = None

_guardian_stop = threading.Event()
_guardian_thread = None

_idle_stop = threading.Event()
_idle_thread = None
IDLE_POLL_SEC = 30


def _loop(interval: int) -> None:
    _log.info("планировщик запущен, интервал %s с", interval)
    while not _stop_event.is_set():
        try:
            autonomy.run_due_tasks()
        except Exception as e:
            _log.error("ошибка цикла планировщика: %r", e)
        _stop_event.wait(interval)
    _log.info("планировщик остановлен")


def start(interval: int = DEFAULT_INTERVAL_SEC) -> bool:
    """Запускает фоновый поток. Возвращает False, если уже запущен."""
    global _thread
    if _thread and _thread.is_alive():
        return False
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, args=(interval,), name="autonomy-scheduler", daemon=True)
    _thread.start()
    return True


def stop() -> None:
    """Останавливает поток (режим при этом остаётся выключенным в autonomy.json)."""
    _stop_event.set()


def is_running() -> bool:
    return bool(_thread and _thread.is_alive())


# ----------------------------------------------------------------------
# Сторож (Guardian), этап 2
# ----------------------------------------------------------------------
def _guardian_loop(interval: int, notify) -> None:
    _log.info("сторож запущен, интервал %s с", interval)
    while not _guardian_stop.is_set():
        try:
            # Сторож работает только при включённом автономном режиме
            if autonomy.is_enabled():
                autonomy.run_guardian(notify=notify)
        except Exception as e:
            _log.error("ошибка сторожа: %r", e)
        _guardian_stop.wait(interval)
    _log.info("сторож остановлен")


def start_guardian(notify=None, interval: int = autonomy.GUARDIAN_INTERVAL_SEC) -> bool:
    """Запускает Сторожа в фоне. Возвращает False, если уже запущен."""
    global _guardian_thread
    if _guardian_thread and _guardian_thread.is_alive():
        return False
    _guardian_stop.clear()
    _guardian_thread = threading.Thread(
        target=_guardian_loop, args=(interval, notify),
        name="autonomy-guardian", daemon=True,
    )
    _guardian_thread.start()
    return True


def stop_guardian() -> None:
    _guardian_stop.set()


def is_guardian_running() -> bool:
    return bool(_guardian_thread and _guardian_thread.is_alive())


# ----------------------------------------------------------------------
# Триггер простоя для Task Runner (этап 4)
# ----------------------------------------------------------------------
def _idle_loop(poll_sec: int) -> None:
    from core import idle
    _log.info("детектор простоя запущен, порог %s с", idle.IDLE_THRESHOLD_SEC)
    ran_this_idle = False
    while not _idle_stop.is_set():
        try:
            if autonomy.is_enabled() and idle.detect_idle():
                if not ran_this_idle:
                    ran_this_idle = True
                    autonomy.run_task()
            else:
                ran_this_idle = False
        except Exception as e:
            _log.error("ошибка детектора простоя: %r", e)
        _idle_stop.wait(poll_sec)
    _log.info("детектор простоя остановлен")


def start_idle(poll_sec: int = IDLE_POLL_SEC) -> bool:
    """Запускает детектор простоя в фоне. Возвращает False, если уже запущен."""
    global _idle_thread
    if _idle_thread and _idle_thread.is_alive():
        return False
    _idle_stop.clear()
    _idle_thread = threading.Thread(
        target=_idle_loop, args=(poll_sec,), name="autonomy-idle", daemon=True,
    )
    _idle_thread.start()
    return True


def stop_idle() -> None:
    _idle_stop.set()


def is_idle_running() -> bool:
    return bool(_idle_thread and _idle_thread.is_alive())
