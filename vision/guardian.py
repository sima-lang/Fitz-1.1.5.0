"""
guardian.py — Страж Фитца (охрана камеры) на YuNet.
Кроссплатформенно: cv2.FaceDetectorYN + os_layer.
Если камера сломана/чёрный экран — НЕ блокирует ПК (защита от ложных срабатываний).
"""
import os
import time
import threading
from core.logger import get_logger

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

from core import os_layer
_log = get_logger("guardian")


class Guardian:
    def __init__(self, voice=None, camera_index: int = 0):
        self.voice = voice
        self.camera_index = camera_index
        self.running = False
        self.locked = False
        self.absent_counter = 0
        self.max_absent = 60  # секунд без лица → блокировка (увеличили)
        self._thread = None
        self._cap = None
        self._detector = None
        self._model_path = "data/models/face_detection_yunet_2023mar.onnx"

    def _init_detector(self):
        if cv2 is None:
            return False
        if not os.path.exists(self._model_path):
            print(f"⚠️ Guardian: модель YuNet не найдена: {self._model_path}")
            return False
        try:
            # Создаём детектор. Размер входа будет обновляться динамически.
            self._detector = cv2.FaceDetectorYN.create(
                self._model_path,
                "",
                (320, 320),
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5000,
            )
            return True
        except Exception as e:
            print(f"⚠️ Guardian: ошибка YuNet: {e}")
            return False

    def _open_camera(self):
        if cv2 is None:
            return False
        try:
            cap = cv2.VideoCapture(self.camera_index, os_layer.get_camera_backend())
            if not cap.isOpened():
                return False
            self._cap = cap
            return True
        except Exception:
            return False

    def _close_camera(self):
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            _log.debug("пропущено в vision/guardian.py (строка 73)")
        self._cap = None

    def _face_present(self) -> bool:
        if self._cap is None or self._detector is None:
            return True  # защита: если что-то не так, не блокируем

        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return True  # камера не даёт кадры → не блокируем

            # Проверка на чёрный экран
            if np is not None and np.array(frame).mean() < 5:
                return True

            h, w = frame.shape[:2]
            self._detector.setInputSize((w, h))
            _, faces = self._detector.detect(frame)

            if faces is None:
                return False  # камера работает, но лиц нет
            return len(faces) > 0

        except Exception:
            return True  # при любой ошибке — не блокируем

    def start(self) -> str:
        if cv2 is None:
            return "❌ OpenCV не установлен — страж недоступен"
        if self.running:
            return "🛡️ Страж уже работает"
        if not self._init_detector():
            return "❌ Не удалось загрузить модель YuNet"
        if not self._open_camera():
            return "❌ Камера не доступна"
        self.running = True
        self.locked = False
        self.absent_counter = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return "🛡️ Страж активирован (слежу за камерой, YuNet)"

    def stop(self) -> str:
        self.running = False
        time.sleep(0.3)
        self._close_camera()
        return "🛡️ Страж выключен"

    def _loop(self):
        while self.running:
            try:
                present = self._face_present()
                if present:
                    if self.absent_counter > 10 and self.voice:
                        self.voice.speak("С возвращением, создатель.")
                    self.absent_counter = 0
                    self.locked = False
                else:
                    self.absent_counter += 1
                    if self.absent_counter >= self.max_absent and not self.locked:
                        self._lock_pc()
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Guardian: {e}")
                time.sleep(2)

    def _lock_pc(self):
        try:
            os_layer.lock_pc()
            self.locked = True
            if self.voice:
                self.voice.speak("Пользователь не обнаружен. ПК заблокирован.")
        except Exception:
            _log.debug("пропущено в vision/guardian.py (строка 147)")

    def get_status(self) -> str:
        if not self.running:
            return "🛡️ Страж выключен"
        if self.locked:
            return "🛡️ Страж активен — ПК заблокирован"
        return f"🛡️ Страж активен (нет в кадре: {self.absent_counter}/{self.max_absent})"


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_guardian = None


def get_guardian(voice=None) -> Guardian:
    global _guardian
    if _guardian is None:
        _guardian = Guardian(voice=voice)
    return _guardian