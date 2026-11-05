"""
utils.py — Общие утилиты для Фитца 1.6.2.
Вынесено из commands/files.py для устранения дублирования.
"""
import os


# ===== ЗАЩИТА ОТ PATH TRAVERSAL =====
_ALLOWED_ROOTS = [
    os.path.expanduser("~"),
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