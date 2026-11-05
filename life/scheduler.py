"""
life/scheduler.py — фоновый планировщик автономного режима (версия 1.2.0.1).

Работает отдельным демон-потоком и раз в интервал проверяет расписание
(data/autonomy.json). Задачи выполняются только если режим включён.
Остановка: флаг enabled=false (кнопка / «стоп автономность») или завершение процесса.
"""
import threading

from core import autonomy
from core.logger import get_logger

_log = get_logger("scheduler", file="autonomy.log")

DEFAULT_INTERVAL_SEC = 60

_stop_event = threading.Event()
_thread = None


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
