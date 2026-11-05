"""
music.py — Управление музыкой и громкостью.
Кроссплатформенно: через os_layer (Windows: keybd_event, Linux: playerctl/pactl).
"""
from core import os_layer


def handle(text, memory, core):
    low = text.lower().strip()

    if "переключи" in low or "следующий трек" in low or "дальше" in low:
        if os_layer.media_next():
            return "⏭️ Переключаю трек"
        return "⚠️ Не удалось переключить трек"

    if "останови музыку" in low or "стоп музыка" in low or "пауза" in low:
        if os_layer.media_play_pause():
            return "⏸️ Музыка на паузе"
        return "⚠️ Не удалось поставить на паузу"

    if "продолжи" in low or "включи музыку" in low or "играй" in low:
        if os_layer.media_play_pause():
            return "▶️ Музыка продолжена"
        return "⚠️ Не удалось продолжить"

    if "громче" in low:
        if os_layer.volume_up():
            return "🔊 Громче"
        return "⚠️ Не удалось увеличить громкость"

    if "тише" in low:
        if os_layer.volume_down():
            return "🔉 Тише"
        return "⚠️ Не удалось уменьшить громкость"

    if "открой музыку" in low or "открой плеер" in low:
        os_layer.open_url("https://music.yandex.ru")
        return "🌐 Открываю Яндекс.Музыку"

    return None