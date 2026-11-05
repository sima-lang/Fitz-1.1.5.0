"""
commands/__init__.py — Роутер команд Фитца.
Логирует: сработавшие хендлеры, упавшие хендлеры, нераспознанные сообщения.
"""
import os
from datetime import datetime

from . import (
    system, files, power, music, security,
    internet, ai, extra, tasks, vision_commands,
    apps, media, dj,
)
from core.logger import get_logger
_mod_log = get_logger("__init__")


def _log(msg: str):
    """Пишем в logs/commands.log — видно, что происходит с командами."""
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/commands.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        _mod_log.debug("пропущено в commands/__init__.py (строка 24)")


HANDLERS = [
    system.handle, apps.handle, media.handle,
    files.handle, power.handle, music.handle, security.handle,
    internet.handle, ai.handle, extra.handle, tasks.handle,
    vision_commands.handle, dj.handle,
    # screen.handle УБРАН — зрение работает через ui_pyqt._process_worker,
    # чтобы не терять результат (у Brain нет add_message_signal)
]


def handle(text, memory, core):
    for h in HANDLERS:
        try:
            r = h(text, memory, core)
            if r is not None:
                _log(f"HIT {h.__module__}: «{text[:60]}» → {str(r)[:80]!r}")
                return r
        except Exception as e:
            _log(f"ERR {h.__module__}: {e!r} | текст: «{text[:80]}»")
            continue

    # DLC-хендлеры
    try:
        from dlc_loader import load_dlcs
        if not hasattr(handle, "_dlc_handlers"):
            handle._dlc_handlers = load_dlcs()
        for h in handle._dlc_handlers:
            try:
                r = h(text, memory, core)
                if r is not None:
                    _log(f"HIT DLC {getattr(h, '__module__', '?')}: «{text[:60]}»")
                    return r
            except Exception as e:
                _log(f"ERR DLC: {e!r}")
    except Exception:
        _mod_log.debug("пропущено в commands/__init__.py (строка 62)")

    _log(f"MISS: «{text[:80]}»")
    return None