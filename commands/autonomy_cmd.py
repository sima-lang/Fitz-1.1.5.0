"""
commands/autonomy_cmd.py — команды управления автономным режимом (этап 3).

Тонкая обёртка над core.autonomy.handle_stop_command: «стоп автономность»,
«включи автономность». Логика остановки живёт в core/autonomy.py.
"""
from core import autonomy

_TASK_PREFIXES = ("задача на ночь:", "задача на ночь ", "задача:")


def handle(text, memory, core):
    low = text.lower().strip()
    if low in ("включи эмуляцию", "выключи эмуляцию"):
        on = low.startswith("включи")
        autonomy.set_emulation(on)
        return ("Эмуляция ввода включена. Каждое нажатие будет требовать подтверждения «да»."
                if on else "Эмуляция ввода выключена.")
    for prefix in _TASK_PREFIXES:
        if low.startswith(prefix):
            goal = text.strip()[len(prefix):].strip()
            return autonomy.enqueue_task(goal)
    return autonomy.handle_stop_command(text)
