"""
media.py — Музыка и видео (веб-версия).
"""
import subprocess
from core import os_layer

MY_WAVE_URL = "https://music.yandex.ru/my/wave"

def _spawn(cmd):
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def _open_url(url: str) -> str:
    import webbrowser
    try:
        webbrowser.open(url)
        return f"🌐 Открываю: {url}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

def handle(text, memory, core):
    low = text.lower().strip()

    # ===== МУЗЫКА (В БРАУЗЕРЕ) =====
    if low in ("включи музыку", "открой музыку", "яндекс музыка", "моя волна"):
        return _open_url(MY_WAVE_URL)

    # ===== ПЕРЕКЛЮЧЕНИЕ ТРЕКОВ (МЕДИА-КЛАВИШИ) =====
    if low in ("следующий трек", "переключи трек", "дальше", "next"):
        if os_layer.media_next():
            return "⏭️ Следующий трек"
        return "⚠️ Не удалось переключить трек"

    if low in ("предыдущий трек", "назад", "previous"):
        if os_layer.media_prev():
            return "⏮️ Предыдущий трек"
        return "⚠️ Не удалось переключить трек"

    if low in ("пауза", "стоп музыка", "останови музыку"):
        if os_layer.media_play_pause():
            return "⏸️ Пауза"
        return "⚠️ Не удалось поставить на паузу"

    if low in ("продолжи", "играй"):
        if os_layer.media_play_pause():
            return "▶️ Продолжаю"
        return "⚠️ Не удалось продолжить"

    # ===== ВИДЕО =====
    if low in ("включи видео", "открой ютуб", "ютуб", "youtube"):
        return _open_url("https://youtube.com")

    return None