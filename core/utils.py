"""
utils.py — Общие утилиты для Фитца 1.1.5.0.
Вынесено из commands/files.py для устранения дублирования.
"""
import json
import os


def atomic_write_json(path: str, data, indent: int = 2) -> None:
    """Пишет JSON атомарно: при сбое старый файл остаётся целым."""
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ===== ЗАЩИТА ОТ PATH TRAVERSAL =====
# Только пользовательские каталоги и корень проекта. ~/.ssh, ~/.gnupg и прочие
# скрытые каталоги домашней папки в список не входят.
_HOME = os.path.expanduser("~")
_ALLOWED_ROOTS = [
    os.path.join(_HOME, "Рабочий стол"),
    os.path.join(_HOME, "Документы"),
    os.path.join(_HOME, "Загрузки"),
    os.path.join(_HOME, "Изображения"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
]


def _is_safe_path(path: str) -> bool:
    """Проверяет, что реальный путь не выходит за пределы разрешённых директорий."""
    if not path:
        return False
    try:
        real = os.path.realpath(path)
        for root in _ALLOWED_ROOTS:
            root_real = os.path.realpath(root)
            if os.path.commonpath([real, root_real]) == root_real:
                return True
        return False
    except (ValueError, OSError):
        return False