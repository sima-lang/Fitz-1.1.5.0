"""
screen.py — Зрение Фитца через dsh SDK (скриншоты + описание экрана).
"""
import threading
from core.vision_sdk import describe_screen


def handle(text, memory, core):
    low = text.lower().strip()

    # ===== ОПИСАНИЕ ЭКРАНА =====
    if low in ("что на экране", "посмотри на экран", "опиши экран",
               "что видишь", "что видно на экране", "покажи экран"):
        def worker():
            result = describe_screen("Сделай скриншот и опиши, что на экране. Что открыто, какие окна, что происходит.")
            if hasattr(core, "add_message_signal"):
                core.add_message_signal.emit("🛡️ Фитц", result, False)
            if hasattr(core, "voice") and core.voice:
                core.voice.speak(result)
        
        threading.Thread(target=worker, daemon=True).start()
        return "👁️ Смотрю на экран..."

    # ===== КОНКРЕТНОЕ ОКНО =====
    if low.startswith("что в окне ") or low.startswith("посмотри на окно "):
        target = text.split(" ", 3)[-1].strip() if " " in text else text
        def worker():
            result = describe_screen(
                f"Сделай скриншот и опиши, что в окне '{target}'. Что там написано, какие элементы."
            )
            if hasattr(core, "add_message_signal"):
                core.add_message_signal.emit("🛡️ Фитц", result, False)
            if hasattr(core, "voice") and core.voice:
                core.voice.speak(result)
        threading.Thread(target=worker, daemon=True).start()
        return f"👁️ Смотрю на окно '{target}'..."

    # ===== ПОИСК НА ЭКРАНЕ =====
    if low.startswith("найди на экране "):
        query = text[17:].strip()
        if not query:
            return "Что искать на экране?"
        def worker():
            result = describe_screen(
                f"Сделай скриншот и найди на экране: '{query}'. Опиши, где это находится."
            )
            if hasattr(core, "add_message_signal"):
                core.add_message_signal.emit("🛡️ Фитц", result, False)
        threading.Thread(target=worker, daemon=True).start()
        return f"🔍 Ищу '{query}' на экране..."

    # ===== КЛИК ПО ЭЛЕМЕНТУ =====
    if low.startswith("кликни по ") or low.startswith("нажми на "):
        target = text.split(" ", 2)[-1].strip() if " " in text else text
        def worker():
            result = describe_screen(
                f"Сделай скриншот и кликни на элементе: '{target}'. Используй computer_click."
            )
            if hasattr(core, "add_message_signal"):
                core.add_message_signal.emit("🛡️ Фитц", result, False)
        threading.Thread(target=worker, daemon=True).start()
        return f"🖱️ Кликаю по '{target}'..."

    # ===== СТАТУС =====
    if low in ("статус зрения", "статус ocr", "статус супер зрения"):
        return "👁️ Зрение через dsh SDK: активно (WinRects + Provod)"

    return None