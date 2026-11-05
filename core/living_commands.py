"""
living_commands.py — Умное оживление команд Фитца.

Логика:
1. Проверяем, команда ли это (commands.handle).
2. Если команда — смотрим, "быстрая" она или "сложная":
   - быстрые (время, дата, статус) — возвращаем как есть (без ИИ);
   - сложные (погода, файлы, музыка) — просим ИИ пересказать живо.
3. Если не команда — main.py идёт в brain.ask.
"""
import os
from datetime import datetime

from commands import handle as handle_command
from core.logger import get_logger
_mod_log = get_logger("living_commands")


# Команды, которые НЕ надо пересказывать через ИИ (быстрые)
FAST_COMMANDS = {
    "время", "дата", "день", "день недели",
    "мониторинг", "диски", "процессы", "инфо о пк",
    "статус", "статус системы", "статус охраны", "статус зрения",
    "мой ip", "ip",
    "статус игрового режима",
    "логи", "логи зрения", "логи ocr",
}



def _log(msg: str):
    """Пишем в logs/commands.log, чтобы видеть, что происходит с командами."""
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/commands.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        _mod_log.debug("пропущено в core/living_commands.py (строка 48)")


def _is_fast(text: str) -> bool:
    low = text.lower().strip()
    for cmd in FAST_COMMANDS:
        if low == cmd or low.startswith(cmd + " "):
            return True
    return False


def _is_fallback_text(text: str) -> bool:
    """Грубая проверка: похоже ли на fallback-ответ Brain."""
    if not text:
        return True
    low = text.lower()
    if "не понял" in low:
        return True
    if "⚠️" in text:
        return True
    if "повтори проще" in low:
        return True
    return False


def process_command(text, memory=None, core=None, verbose=False):
    """
    Возвращает dict {"response": str, "action": str|None, "ok": bool}
    или None, если это не команда.
    """
    try:
        result = handle_command(text, memory, core)
    except Exception as e:
        _log(f"handle_command упал: {e!r} для «{text[:80]}»")
        return {"response": f"⚠️ Ошибка команды: {e}", "action": None, "ok": False}

    if result is None:
        return None

    response = result
    action = result

    # быстрые — без ИИ
    if _is_fast(text) and not verbose:
        _log(f"FAST: «{text[:60]}» → {str(response)[:80]!r}")
        return {"response": response, "action": action, "ok": True}

    # сложные — через ИИ (если API доступен)
    if core is not None and getattr(core, "api", None) and core.api.enabled:
        try:
            prompt = (
                f'Пользователь сказал: "{text}"\n'
                f'Твоя система УЖЕ выполнила: "{result}"\n'
                "ВАЖНО: ты — Фитц, у тебя ЕСТЬ доступ к компьютеру через команды. "
                "Действие уже выполнено успешно. НЕ говори 'я не могу', 'у меня нет доступа', "
                "'я только чат'. Просто живо прокомментируй то, что уже сделано, как друг. "
                "1–2 предложения."
            )
            lived = core.ask(prompt)   # ← ЭТОЙ СТРОКИ НЕ ХВАТАЛО

            was_fallback = getattr(core, "_last_was_fallback", False)
            if was_fallback or _is_fallback_text(lived):
                _log(f"LIVELY: fallback от API, оставляем ответ команды: {str(response)[:80]!r}")
            elif lived and len(lived.strip()) > 3:
                _log(f"LIVELY: «{text[:40]}» → пересказ ИИ: {lived[:80]!r}")
                response = lived
        except Exception as e:
            _log(f"LIVELY: ошибка пересказа: {e!r}")

    return {"response": response, "action": action, "ok": True}