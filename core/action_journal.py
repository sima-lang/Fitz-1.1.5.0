"""
action_journal.py — журнал действий Фитца с ПК.

Пишет по одной JSON-строке на событие в data/actions.log:
  время, инструмент, аргументы (обрезанные), решение и результат.
Нужен, чтобы после случайного или неожиданного действия было видно, что именно запускалось.
Запись никогда не бросает исключений наружу: журнал не должен ломать работу.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from core.logger import get_logger

_log = get_logger("action_journal")

JOURNAL_PATH = Path(__file__).resolve().parent.parent / "data" / "actions.log"
MAX_ARG_CHARS = 200
MAX_RESULT_CHARS = 300
_lock = threading.Lock()


def _trim(value, limit: int) -> str:
    s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"


def record(tool: str, args: dict, decision: str, result: str = "") -> None:
    """decision: allowed | denied_no_access | cancelled | confirmed | confirmed_typed | error.
    Аргументы обрезаются; значения вроде password/token/key заменяются маской."""
    try:
        safe_args = {}
        for k, v in (args or {}).items():
            if any(s in str(k).lower() for s in ("password", "token", "key", "secret")):
                safe_args[k] = "***"
            else:
                safe_args[k] = _trim(v, MAX_ARG_CHARS)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "args": safe_args,
            "decision": decision,
            "result": _trim(result, MAX_RESULT_CHARS),
        }
        JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        _log.warning("журнал действий не записан: %s", e)


def recent(limit: int = 20) -> list:
    """Последние записи (для показа пользователю)."""
    try:
        lines = JOURNAL_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except Exception as e:
        _log.warning("журнал действий не прочитан: %s", e)
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
