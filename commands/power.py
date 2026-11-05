"""
power.py — Блокировка / перезагрузка / выключение.
Кроссплатформенно: через os_layer.
"""
from core import os_layer


def _full_access_enabled() -> bool:
    try:
        from ui.settings_dialog import load_settings
        return bool(load_settings().get("full_access", False))
    except Exception as e:
        print(f"⚠️ Не удалось прочитать настройки full_access: {e}")
        return False


def handle(text, memory, core):
    low = text.lower().strip()

    if low in ("заблокируй пк", "заблокировать пк", "блокировка", "заблокируй"):
        return os_layer.lock_pc()

    if low in ("перезагрузи пк", "перезагрузка", "ребут", "reboot", "перезагрузи"):
        if not _full_access_enabled():
            return "⛔ Полный доступ выключен. Включи в настройках (вкладка «Права»)."
        from core import autonomy
        return autonomy.request_dangerous_action("reboot")["question"]

    if low in ("выключи пк", "выключить пк", "выключение", "shutdown", "выключи"):
        if not _full_access_enabled():
            return "⛔ Полный доступ выключен. Включи в настройках (вкладка «Права»)."
        from core import autonomy
        return autonomy.request_dangerous_action("shutdown")["question"]

    if low in ("отмена", "отменить", "не надо", "отмени выключение"):
        return os_layer.cancel_shutdown()

    return None