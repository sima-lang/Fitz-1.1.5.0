"""
sounds.py — Звуки Фитца 1.5.0 (живость).
Кроссплатформенный: использует pygame или playsound как fallback.
Функции:
  play_start()   — звук приветствия при запуске
  play_error()   — звук ошибки
  play_open()    — звук открытия файла/приложения
  play_click()   — звук клика (для UI)
  play_wake()    — звук пробуждения (wake-word)
"""
import os
from core.logger import get_logger
_log = get_logger("sounds")

_SOUND_ENGINE = None

def _init_pygame():
    """Инициализирует pygame-микшер."""
    global _SOUND_ENGINE
    if _SOUND_ENGINE is not None:
        return _SOUND_ENGINE
    try:
        import pygame
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        _SOUND_ENGINE = "pygame"
        return "pygame"
    except Exception:
        _log.debug("пропущено в core/sounds.py (строка 29)")

    # Fallback: playsound
    try:
        import playsound  # noqa: F401
        _SOUND_ENGINE = "playsound"
        return "playsound"
    except Exception:
        _log.debug("пропущено в core/sounds.py (строка 37)")

    _SOUND_ENGINE = "none"
    return "none"


def _generate_tone(freq: float, duration: float, volume: float = 0.3):
    """Генерирует простой тон через pygame (fallback если нет файлов)."""
    import pygame
    import numpy as np
    import io
    import wave

    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # Простой затухающий синус
    envelope = np.exp(-t * 3)
    wave_data = (np.sin(2 * np.pi * freq * t) * envelope * volume * 32767).astype(np.int16)

    # Пишем в буфер
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(wave_data.tobytes())
    buf.seek(0)

    sound = pygame.mixer.Sound(buf)
    sound.play()
    return sound


def play_start():
    """Звук при старте Фитца."""
    engine = _init_pygame()
    if engine == "pygame":
        import pygame
        # Три восходящих тона
        _generate_tone(523, 0.10, 0.25)  # C5
        import time
        time.sleep(0.08)
        _generate_tone(659, 0.10, 0.25)  # E5
        time.sleep(0.08)
        _generate_tone(784, 0.15, 0.30)  # G5
    elif engine == "playsound":
        try:
            import playsound
            # Пытаемся найти wav-файл, если нет — тихо пропускаем
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "startup.wav")
            if os.path.exists(path):
                playsound.playsound(path, block=False)
        except Exception:
            _log.debug("пропущено в core/sounds.py (строка 93)")


def play_error():
    """Звук ошибки."""
    engine = _init_pygame()
    if engine == "pygame":
        import time
        _generate_tone(200, 0.15, 0.3)
        time.sleep(0.12)
        _generate_tone(150, 0.2, 0.3)
    elif engine == "playsound":
        try:
            import playsound
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "error.wav")
            if os.path.exists(path):
                playsound.playsound(path, block=False)
        except Exception:
            _log.debug("пропущено в core/sounds.py (строка 111)")


def play_open():
    """Звук открытия файла/приложения."""
    engine = _init_pygame()
    if engine == "pygame":
        import time
        _generate_tone(800, 0.05, 0.2)
        time.sleep(0.04)
        _generate_tone(1000, 0.08, 0.2)
    elif engine == "playsound":
        try:
            import playsound
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "open.wav")
            if os.path.exists(path):
                playsound.playsound(path, block=False)
        except Exception:
            _log.debug("пропущено в core/sounds.py (строка 129)")


def play_click():
    """Звук клика UI."""
    engine = _init_pygame()
    if engine == "pygame":
        _generate_tone(1200, 0.03, 0.15)
    elif engine == "playsound":
        try:
            import playsound
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "click.wav")
            if os.path.exists(path):
                playsound.playsound(path, block=False)
        except Exception:
            _log.debug("пропущено в core/sounds.py (строка 144)")


def play_wake():
    """Звук пробуждения (wake-word обнаружен)."""
    engine = _init_pygame()
    if engine == "pygame":
        import time
        _generate_tone(440, 0.08, 0.2)
        time.sleep(0.06)
        _generate_tone(660, 0.12, 0.25)
    elif engine == "playsound":
        try:
            import playsound
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "wake.wav")
            if os.path.exists(path):
                playsound.playsound(path, block=False)
        except Exception:
            _log.debug("пропущено в core/sounds.py (строка 162)")


def play_think():
    """Звук размышления: тихий задумчивый тон."""
    engine = _init_pygame()
    if engine == "pygame":
        _generate_tone(300, 0.20, 0.12)
        import time
        time.sleep(0.25)
        _generate_tone(350, 0.30, 0.10)
    elif engine == "playsound":
        try:
            import playsound
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "think.wav")
            if os.path.exists(path):
                playsound.playsound(path, block=False)
        except Exception:
            _log.debug("пропущено в core/sounds.py (строка 180)")


def play_success():
    """Звук успешного выполнения задачи: восходящие тоны."""
    engine = _init_pygame()
    if engine == "pygame":
        import time
        _generate_tone(523, 0.08, 0.20)
        time.sleep(0.06)
        _generate_tone(659, 0.08, 0.20)
        time.sleep(0.06)
        _generate_tone(784, 0.12, 0.25)
    elif engine == "playsound":
        try:
            import playsound
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "success.wav")
            if os.path.exists(path):
                playsound.playsound(path, block=False)
        except Exception:
            _log.debug("пропущено в core/sounds.py (строка 200)")
