"""
commands/autonomy_cmd.py — команды управления автономным режимом (этап 3).

Тонкая обёртка над core.autonomy.handle_stop_command: «стоп автономность»,
«включи автономность». Логика остановки живёт в core/autonomy.py.
"""
from core import autonomy


def handle(text, memory, core):
    return autonomy.handle_stop_command(text)
