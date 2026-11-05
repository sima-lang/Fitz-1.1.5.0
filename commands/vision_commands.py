"""
vision_commands.py — Камера и зрение.
Кроссплатформенно: через os_layer.get_camera_backend().
Пока упрощённая версия (без Guardian/SuperVision — их добавим позже).
"""
import os
import time
from core.logger import get_logger

try:
    import cv2
except Exception:
    cv2 = None

from core import os_layer
_log = get_logger("vision_commands")


_camera = None


def _get_camera():
    global _camera
    if _camera is None and cv2 is not None:
        _camera = {
            "cap": None,
            "running": False,
        }
    return _camera


def handle(text, memory, core):
    low = text.lower().strip()

    if cv2 is None:
        if low in ("включи камеру", "включи зрение", "камера"):
            return "⚠️ OpenCV не установлен"
        return None

    cam = _get_camera()

    # ===== ВКЛЮЧИ КАМЕРУ =====
    if low in ("включи камеру", "включи зрение"):
        if cam["running"]:
            return "👁️ Камера уже работает"
        try:
            cap = cv2.VideoCapture(0, os_layer.get_camera_backend())
            if not cap.isOpened():
                return "❌ Камера не доступна"
            cam["cap"] = cap
            cam["running"] = True
            return "👁️ Камера включена"
        except Exception as e:
            return f"❌ Ошибка камеры: {e}"

    # ===== ВЫКЛЮЧИ =====
    if low in ("выключи камеру", "выключи зрение"):
        if not cam["running"]:
            return "🔴 Камера уже выключена"
        try:
            cam["cap"].release()
        except Exception:
            _log.debug("пропущено в commands/vision_commands.py (строка 63)")
        cam["cap"] = None
        cam["running"] = False
        return "⏹️ Камера выключена"

        # ===== СТРАЖ =====
    if low in ("включи охрану", "включи стража", "активируй стража"):
        from vision.guardian import get_guardian
        g = get_guardian(voice=getattr(core, "voice", None))
        return g.start()

    if low in ("выключи охрану", "выключи стража", "деактивируй стража"):
        from vision.guardian import get_guardian
        g = get_guardian()
        return g.stop()

    if low in ("статус охраны", "статус стража"):
        from vision.guardian import get_guardian
        g = get_guardian()
        return g.get_status()

    # ===== СТАТУС =====
    if low in ("статус камеры", "камера"):
        return "👁️ Камера работает" if cam["running"] else "🔴 Камера выключена"

    # ===== СДЕЛАЙ ФОТО =====
    if low in ("сделай фото", "снимок", "фото"):
        if not cam["running"]:
            return "🔴 Сначала скажи 'включи камеру'"
        try:
            ret, frame = cam["cap"].read()
            if not ret or frame is None:
                return "❌ Не удалось сделать снимок"
            os.makedirs("data/images", exist_ok=True)
            path = f"data/images/photo_{int(time.time())}.jpg"
            cv2.imwrite(path, frame)
            return f"📸 Сохранено: {path}"
        except Exception as e:
            return f"❌ Ошибка: {e}"
    
        # ===== ЖЕСТЫ =====
    if low in ("включи жесты", "распознавание жестов", "включи распознавание жестов"):
        from vision.gestures import GestureDetector
        from core import os_layer
        
        def on_gesture(gesture):
            voice = getattr(core, "voice", None)
            if gesture == "open_hand":
                os_layer.media_play_pause()
                if voice: voice.speak("Продолжаю.")
            elif gesture == "fist":
                os_layer.media_play_pause()
                if voice: voice.speak("Стоп.")

        if not hasattr(core, "_gesture_detector"):
            core._gesture_detector = GestureDetector(voice=getattr(core, "voice", None), callback=on_gesture)
        
        return core._gesture_detector.start()

    if low in ("выключи жесты", "останови жесты", "отключи распознавание жестов"):
        if hasattr(core, "_gesture_detector"):
            return core._gesture_detector.stop()
        return "❌ Жесты не были включены"
    return None