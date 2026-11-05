"""
build.py — Сборка Фитца (версия в core/version.py) в .exe (Windows) / .bin (Linux).
Запуск: python build.py
"""
import os
import sys
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.version import __version__


def build():
    print("=" * 60)
    print(f"🛡️  СБОРКА ФИТЦА {__version__}")
    print("=" * 60)

    # Очистка
    for folder in ("build", "dist"):
        if os.path.exists(folder):
            shutil.rmtree(folder)

    # Данные, которые надо включить в exe
    add_data = [
        "core", "commands", "life", "vision", "security",
        "dlc", "data", ".env",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "Fitz",
    ]

    for d in add_data:
        if os.path.exists(d):
            cmd.extend(["--add-data", f"{d}{os.pathsep}{d}"])

    # Скрытые импорты (чтобы PyInstaller их не пропустил)
    hidden = [
        "core.voice", "core.brain", "core.memory", "core.config",
        "core.intelligence", "core.wake_word", "core.os_layer",
        "commands", "life", "vision", "security",
        "vosk", "onnx_asr", "sounddevice", "speech_recognition",
        "torch", "pytesseract", "PIL", "mss", "cv2", "psutil",
        "requests", "dotenv", "jeepney",
    ]
    for h in hidden:
        cmd.extend(["--hidden-import", h])

    cmd.append("ui_pyqt.py")  # точка входа — GUI (PyQt6)

    print("⏳ Сборка... (2–5 минут)")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n✅ ГОТОВО!")
        if os_layer_windows():
            print("📁 Файл: dist/Fitz.exe")
        else:
            print("📁 Файл: dist/Fitz")
    else:
        print("\n❌ Ошибка сборки")


def os_layer_windows():
    import platform
    return platform.system() == "Windows"


if __name__ == "__main__":
    build()