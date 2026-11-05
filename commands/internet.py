"""
internet.py — Погода, IP, проверка сайтов, сокращение ссылок.
Кроссплатформенно (requests).
"""
import requests


def handle(text, memory, core):
    low = text.lower().strip()

    # ===== ПОГОДА =====
    if low == "погода":
        try:
            r = requests.get("https://wttr.in/Moscow?format=%C+%t+%w&lang=ru", timeout=5)
            if r.status_code == 200 and r.text.strip():
                return f"🌤️ Москва: {r.text.strip()}"
            return "🌤️ Погода недоступна"
        except Exception:
            return "⚠️ Ошибка получения погоды"

    if low.startswith("погода"):
        # "погода", "погода погода", "погода в москве"
        if " в " in low:
            city = low.split(" в ", 1)[1].strip()
            try:
                r = requests.get(f"https://wttr.in/{city}?format=%C+%t+%w&lang=ru", timeout=5)
                if r.status_code == 200 and r.text.strip():
                    return f"🌤️ {city}: {r.text.strip()}"
                return f"🌤️ {city}: данные недоступны"
            except Exception:
                return f"⚠️ Ошибка получения погоды для {city}"
        # просто "погода"
        try:
            r = requests.get("https://wttr.in/Moscow?format=%C+%t+%w&lang=ru", timeout=5)
            if r.status_code == 200 and r.text.strip():
                return f"🌤️ Москва: {r.text.strip()}"
            return "🌤️ Погода недоступна"
        except Exception:
            return "⚠️ Ошибка получения погоды"

    # ===== ПРОВЕРЬ САЙТ =====
    if low.startswith("проверь сайт "):
        url = text[13:].strip()
        if not url.startswith("http"):
            url = "https://" + url
        try:
            r = requests.get(url, timeout=10)
            return f"🌐 {url} доступен (код {r.status_code})"
        except Exception:
            return f"🌐 {url} недоступен"

    # ===== СОКРАТИ ССЫЛКУ =====
    if low.startswith("сократи ссылку "):
        url = text[15:].strip()
        try:
            r = requests.post("https://cleanuri.com/api/v1/shorten",
                              json={"url": url}, timeout=10)
            if r.status_code == 200:
                return f"🔗 {r.json().get('result_url', 'Ошибка')}"
            return "❌ Не удалось сократить"
        except Exception:
            return "❌ Ошибка сокращения ссылки"

    return None