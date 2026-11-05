"""
core/idle.py — детектор бездействия пользователя (мышь/клавиатура).

Источник: GNOME Mutter IdleMonitor через gdbus. Если источник недоступен —
возвращаем None («неизвестно»), а не «простаивает». Агент при None не запускается.
"""
import re
import subprocess

IDLE_THRESHOLD_SEC = 120  # 2 минуты

_GDBUS_CMD = [
    "gdbus", "call", "--session",
    "--dest", "org.gnome.Mutter.IdleMonitor",
    "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
    "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime",
]


def parse_idletime_ms(output: str):
    """Разбирает вывод gdbus вида '(uint64 40053,)' в миллисекунды. Иначе None."""
    m = re.search(r"uint64\s+(\d+)", output or "")
    return int(m.group(1)) if m else None


def get_idle_ms():
    """Миллисекунды с последнего ввода или None, если узнать нельзя."""
    try:
        r = subprocess.run(_GDBUS_CMD, capture_output=True, text=True, timeout=3)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return parse_idletime_ms(r.stdout)


def detect_idle(threshold_sec: int = IDLE_THRESHOLD_SEC) -> bool:
    """True — пользователь бездействует дольше порога. False — активен или неизвестно."""
    ms = get_idle_ms()
    if ms is None:
        return False
    return ms >= threshold_sec * 1000
