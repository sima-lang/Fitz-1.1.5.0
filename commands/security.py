"""
security.py — Безопасность: IP, статус защиты, анти-вор.
"""
import requests
from core import os_layer


def handle(text, memory, core):
    low = text.lower().strip()

    # ===== МОЙ IP =====
    if low in ("мой ip", "ip", "какой у меня ip"):
        try:
            ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
            return f"🌍 Твой IP: {ip}"
        except Exception:
            return "⚠️ Не удалось получить IP"

    # ===== СТАТУС ЗАЩИТЫ (общий) =====
    if low in ("статус безопасности", "статус защиты"):
        return (
            "🔒 СТАТУС БЕЗОПАСНОСТИ:\n"
            f"🖥️ ОС: {os_layer.SYSTEM}\n"
            f"👑 Права админа: {'✅' if os_layer.is_admin() else '❌'}\n"
            "🌍 Проверка IP: ✅\n"
        )

    # ===== АНТИ-ВОР: функция удалена (не было детектора вторжений) =====
    if low in ("статус антивора", "анти-вор", "анти вор", "отчёт защиты", "кто стучался", "кто пытался"):
        return "⚠️ Анти-вор отключён: модуль не обнаруживал вторжений и удалён."

    # ===== БЛОКИРОВКА ПК =====
    if low in ("заблокируй пк", "блокировка"):
        return os_layer.lock_pc()

        # ===== ПРОВЕРКА ССЫЛОК =====
    if low.startswith("проверь ссылку "):
        url = text[14:].strip()
        from security.safe_links import get_safe_links
        sl = get_safe_links()
        return sl.check_url(url)

    if low.startswith("безопасно "):
        url = text[10:].strip()
        from security.safe_links import get_safe_links
        sl = get_safe_links()
        is_safe, msg = sl.is_safe_url(url)
        return "✅ Безопасно" if is_safe else f"⚠️ {msg}"

    return None