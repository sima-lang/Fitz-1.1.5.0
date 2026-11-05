"""
core/logger.py — Единый логгер Фитца 1.1.5.0.
Ротация раз в сутки, макс 5 файлов. Формат: [Время] [Уровень] [Имя] Сообщение.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "data"
_LOG_FILE = _LOG_DIR / "fitz.log"

# Ротация раз в сутки, храним 5 файлов
_handler = TimedRotatingFileHandler(
    str(_LOG_FILE),
    when="midnight",
    interval=1,
    backupCount=5,
    encoding="utf-8",
    delay=True,
)
_handler.setLevel(logging.DEBUG)
_handler.setFormatter(logging.Formatter(
    "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))


def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер с ротацией. Не добавляет дублирующиеся хендлеры."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not any(isinstance(h, TimedRotatingFileHandler) for h in logger.handlers):
        logger.addHandler(_handler)
    return logger