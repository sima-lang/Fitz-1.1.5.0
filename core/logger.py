"""
core/logger.py — Единый логгер Фитца 1.1.5.0.

Ротация раз в сутки, макс 5 файлов. Формат: [Время] [Уровень] [Имя] Сообщение.

Логи по модулям: имена из _MODULE_FILES пишут в свой файл (data/voice.log,
data/brain.log, data/ui.log), остальные — в общий data/fitz.log.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "data"
_LOG_FILE = _LOG_DIR / "fitz.log"

# Модули, у которых отдельный лог-файл
_MODULE_FILES = {
    "voice": "voice.log",
    "brain": "brain.log",
    "ui": "ui.log",
}

_FORMAT = logging.Formatter(
    "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_handlers: dict[str, TimedRotatingFileHandler] = {}


def _make_handler(path: Path) -> TimedRotatingFileHandler:
    """Создаёт ротирующий хендлер на конкретный файл."""
    handler = TimedRotatingFileHandler(
        str(path),
        when="midnight",
        interval=1,
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(_FORMAT)
    return handler


def get_logger(name: str, file: str | None = None) -> logging.Logger:
    """Возвращает логгер с ротацией.

    file — имя файла внутри data/ (например "voice.log"). Если не передан,
    берётся из _MODULE_FILES по имени логгера, иначе общий data/fitz.log.
    Повторные вызовы не добавляют дублирующиеся хендлеры.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    target = _LOG_DIR / (file or _MODULE_FILES.get(name, "fitz.log"))
    key = str(target)

    if any(getattr(h, "_fitz_path", None) == key for h in logger.handlers):
        return logger

    handler = _handlers.get(key)
    if handler is None:
        handler = _make_handler(target)
        handler._fitz_path = key
        _handlers[key] = handler

    logger.addHandler(handler)
    return logger
