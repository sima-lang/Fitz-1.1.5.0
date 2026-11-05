"""
build_exe.py — Сборка Фитца (версия в core/version.py) в fitz.exe (Windows).

Зависимости: PyInstaller (pip install pyinstaller).
Запуск:   python build_exe.py
Результат: dist/Fitz.exe (одиночный .exe, без консоли).

Важно: перед сборкой установи зависимости:
    pip install -r requirements-windows.txt
"""

import sys
import os

# Убеждаемся, что мы в корне проекта
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

# ------------------------------------------------------------
# Скрытые импорты (PyInstaller не всегда находит их автоматически)
# ------------------------------------------------------------
HIDDEN_IMPORTS = [
    # PyQt6
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    # core
    "core.brain", "core.agent", "core.api", "core.memory",
    "core.voice", "core.voice_processor", "core.intelligence",
    "core.tools", "core.vision_sdk", "core.sounds",
    "core.os_layer", "core.logger", "core.utils",
    # life
    "life.soul", "life.awareness", "life.initiative",
    # commands
    "commands.system", "commands.files", "commands.ai",
    "commands.power", "commands.music", "commands.security",
    "commands.internet", "commands.apps", "commands.media",
    "commands.dj", "commands.screen", "commands.tasks",
    "commands.extra", "commands.vision_commands",
    # ui
    "ui.hotbar", "ui.haru", "ui.loading_screen",
    "ui.settings_dialog",
    # security
    "security.safe_links",
    # Windows-specific
    "PIL", "PIL.ImageGrab",
    "mss",
    "sounddevice", "soundfile",
    "numpy",
    "torch",
    "pygame",
    "speech_recognition",
    "pyttsx3",
]

# ------------------------------------------------------------
# PyInstaller
# ------------------------------------------------------------
try:
    import PyInstaller.__main__ as pyi
except ImportError:
    print("❌ PyInstaller не установлен. Выполни: pip install pyinstaller")
    sys.exit(1)

args = [
    "ui_pyqt.py",
    "--name=Fitz",
    "--onefile",
    "--windowed",
    "--clean",
    "--noconfirm",
]

# Скрытые импорты
for imp in HIDDEN_IMPORTS:
    args.append(f"--hidden-import={imp}")

# Данные (если есть)
if os.path.isdir("data"):
    args.append("--add-data=data:data")
if os.path.isdir("assets"):
    args.append("--add-data=assets:assets")

print("🚀 Запуск PyInstaller...")
pyi.run(args)

print(f"\n✅ Сборка завершена! EXE: dist{os.sep}Fitz.exe")