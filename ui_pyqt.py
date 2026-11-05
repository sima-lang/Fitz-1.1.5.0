"""
ui_pyqt.py — Фитц 1.5.0 (Главное окно, сборка интерфейса, применение настроек) [v1.5.0]
"""
import os
import sys
import threading
import time
import json
import math
import re
import atexit
import platform as _platform
import traceback
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# ===== WEBSOCKET-МОСТ К КЛИЕНТУ GODOT (godot_client/) =====
# Работает в своём потоке с asyncio-циклом, не блокирует Qt.
# Протокол: JSON {"state": "calm|think|talk|error|joy"}.
GODOT_HOST = "127.0.0.1"
GODOT_PORT = 8765
_GODOT_STATES = {"calm", "think", "talk", "error", "joy"}


class GodotBridge:
    def __init__(self, host: str = GODOT_HOST, port: int = GODOT_PORT):
        import threading as _th
        self.host = host
        self.port = port
        self._loop = None
        self._thread = None
        self._clients = set()
        self._last_state = "calm"
        self._ready = _th.Event()
        self.available = False

    def start(self) -> bool:
        try:
            import websockets  # noqa: F401
        except ImportError:
            log("⚠️ websockets не установлен — мост к Godot выключен (pip install websockets)")
            return False
        import threading as _th
        self._thread = _th.Thread(target=self._run, name="godot-bridge", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        return self.available

    def send(self, state: str) -> None:
        """Отправляет состояние всем клиентам. Безопасно из любого потока."""
        if state not in _GODOT_STATES:
            return
        self._last_state = state
        if self._loop is None or not self.available:
            return
        import asyncio
        asyncio.run_coroutine_threadsafe(self._broadcast(state), self._loop)

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run(self) -> None:
        import asyncio
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except OSError as e:
            log(f"⚠️ мост Godot: порт {self.port} недоступен: {e}")
        except Exception as e:
            log(f"⚠️ мост Godot упал: {e}")
        finally:
            self._ready.set()
            self._loop.close()

    async def _serve(self) -> None:
        import asyncio
        import websockets
        async with websockets.serve(self._handler, self.host, self.port):
            self.available = True
            self._ready.set()
            log(f"✅ мост к Godot: ws://{self.host}:{self.port}")
            await asyncio.Future()

    async def _handler(self, ws):
        self._clients.add(ws)
        try:
            await ws.send(json.dumps({"state": self._last_state}))
            async for _ in ws:
                pass  # клиент только принимает, входящих сообщений не ждём
        except Exception:
            log("пропущено в ui_pyqt (строка 95)")
        finally:
            self._clients.discard(ws)

    async def _broadcast(self, state: str) -> None:
        msg = json.dumps({"state": state})
        for ws in list(self._clients):
            try:
                await ws.send(msg)
            except Exception:
                self._clients.discard(ws)


# ===== АВТОМАТИЗАЦИЯ UNSAFE MODE ЧЕРЕЗ YDOTOOL (только Linux) =====
def _run_ydotool(cmd: list, wait: float = 0.5):
    """Выполняет команду ydotool с задержкой (Linux only)."""
    if _platform.system() != "Linux":
        return False
    try:
        subprocess.run(cmd, check=True, timeout=5)
        time.sleep(wait)
        return True
    except Exception as e:
        print(f"⚠️ Ошибка ydotool: {e}")
        return False

def _automate_unsafe_mode(enable: bool = True):
    """Эмулирует нажатия для включения/выключения unsafe_mode в GNOME.
    На Windows/macOS просто возвращает False без ошибок."""
    if _platform.system() != "Linux":
        print(f"ℹ️ ydotool-автоматизация недоступна на {_platform.system()} — пропускаем.")
        return False

    action = "true" if enable else "false"
    print(f"🔧 Автоматизация unsafe_mode = {action}...")

    # 1. Alt+F2 (открыть консоль)
    if not _run_ydotool(["ydotool", "key", "56:1", "60:1", "60:0", "56:0"], wait=0.8):
        return False

    # 2. Вводим "lg" и Enter
    if not _run_ydotool(["ydotool", "type", "lg"], wait=0.3):
        return False
    if not _run_ydotool(["ydotool", "key", "28:1", "28:0"], wait=0.8):  # Enter
        return False

    # 3. Вводим команду и Enter
    cmd_str = f"global.context.unsafe_mode = {action}"
    if not _run_ydotool(["ydotool", "type", cmd_str], wait=0.3):
        return False
    if not _run_ydotool(["ydotool", "key", "28:1", "28:0"], wait=0.5):  # Enter
        return False

    # 4. Закрываем консоль (Esc)
    _run_ydotool(["ydotool", "key", "1:1", "1:0"], wait=0.3)

    print(f"✅ unsafe_mode = {action} выполнен.")
    return True
# =========================================================

# ===== ОБРАБОТЧИК ОШИБОК =====
def handle_exception(exc_type, exc_value, exc_traceback):
    print("\n" + "=" * 60)
    print("❌ КРИТИЧЕСКАЯ ОШИБКА:")
    print("=" * 60)
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("=" * 60 + "\n")
sys.excepthook = handle_exception

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFrame, QLabel
)

from ui.chat import ChatWidget
from ui.haru import HaruWidget
from ui.hotbar import Hotbar
from ui.loading_screen import LoadingScreen
from ui.settings_dialog import SettingsDialog, load_settings
from ui.logs_dialog import LogsDialog

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    print("пропущено в ui_pyqt (строка 182): load_dotenv недоступен")

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# ===== ПОТОКОБЕЗОПАСНЫЙ ЛОГ (с atexit-защитой) =====
_log_lock = threading.Lock()
_log_file = None

def _open_log():
    """Лениво открывает лог-файл (режим 'a' — не стирает предыдущие логи)."""
    global _log_file
    if _log_file is None or _log_file.closed:
        try:
            os.makedirs("logs", exist_ok=True)
            _log_file = open("logs/debug.log", "a", encoding="utf-8")
        except Exception:
            _log_file = None
    return _log_file

def _close_log():
    """Закрывает лог-файл. Вызывается через atexit и при штатном закрытии."""
    global _log_file
    if _log_file is not None:
        try:
            _log_file.close()
        except Exception:
            log("Import/submodule load skipped — continuing without it")
        _log_file = None

# Гарантируем закрытие даже при краше
atexit.register(_close_log)


def _sys_stats_text() -> str:
    """CPU / RAM / температура CPU для статус-бара. При ошибке psutil возвращает «н/д»."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        temp = "н/д"
        sensors = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        for key in ("k10temp", "coretemp", "cpu_thermal"):
            if sensors.get(key):
                temp = f"{sensors[key][0].current:.0f}°C"
                break
        return f"CPU {cpu:.0f}% {temp} | RAM {ram:.0f}%"
    except Exception as e:
        log(f"⚠️ статистика системы: {e}")
        return "CPU/RAM н/д"

def log(msg):
    print(msg)
    f = _open_log()
    if f is None:
        return
    with _log_lock:
        try:
            f.write(msg + "\n")
            f.flush()
        except Exception:
            log("Import/submodule load skipped — continuing without it")


from core import action_journal
from core.memory import Memory
from core.brain import Brain
from core.voice import Voice
from core.living_commands import process_command
from core.wake_word import WakeWordDetector
from core.sounds import play_start, play_error, play_open, play_think, play_success
from life import Soul, Awareness, Initiative
from life.greetings import make_greeting
from life.game_mode import get_game_mode
from life.autosave import get_autosave
from vision.guardian import get_guardian

# ===== HTTP СЕРВЕР =====
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()
    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            pass


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def start_local_server(ready_event: threading.Event):
    PORT = 8000
    root_dir = str(Path(__file__).parent)
    handler = lambda *a, **kw: QuietHandler(*a, directory=root_dir, **kw)
    try:
        with ReusableThreadingHTTPServer(("", PORT), handler) as httpd:
            ready_event.set()
            httpd.serve_forever()
    except Exception as e:
        log(f"❌ HTTP сервер не поднялся: {e}")
        ready_event.set()


class FitzApp(QMainWindow):
    voice_text_signal = pyqtSignal(str)
    add_message_signal = pyqtSignal(str, str, bool)
    set_emotion_signal = pyqtSignal(str)
    typing_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int, str)
    close_signal = pyqtSignal()
    # Сигналы для безопасного перехода из фоновых потоков в главный
    finish_loading_signal = pyqtSignal()
    finish_close_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Автоматически включаем unsafe_mode через ydotool (только Linux)
        _automate_unsafe_mode(enable=True)

        os.environ["DEEPSEEK_API_KEY"] = os.getenv("API_KEY", "")
        os.environ["DEEPSEEK_BASE_URL"] = os.getenv("API_URL", "https://api.provod.ai/v1")
        os.environ["DSH_HOME"] = os.path.expanduser("~/fitz_dsh_home")

        self.setWindowTitle("🛡️ Фитц 1.5.0")
        self.resize(1200, 800)
        self.setStyleSheet("QMainWindow { background-color: #0a0a0f; }")

        # Очищаем старые minecraft-файлы, чтобы избежать зависаний
        for mc_file in [Path("data/mc_from_bot.txt"), Path("data/mc_to_bot.txt")]:
            try:
                if mc_file.exists():
                    mc_file.write_text("", encoding="utf-8")
            except Exception:
                log("пропущено в ui_pyqt (строка 321)")

        self.mc_process = None
        self._mc_lock = threading.Lock()  # защита mc_process
        self.mc_timer = QTimer()
        self.mc_timer.timeout.connect(self._check_mc_messages)
        self.mc_timer.start(2000)

        self._core_lock = threading.Lock()  # защита brain/voice/wake/...
        self.brain = None
        self.voice = None
        self.wake = None
        self.soul = None
        self.awareness = None
        self.initiative = None
        self.game_mode = None
        self.autosave = None
        self.guardian = None
        self.memory = None
        self.is_running = True
        self._smoothed_volume = 0.0
        self.last_screen_description = ""
        self._api_status = ""
        self._closing = False

        self.executor = ThreadPoolExecutor(max_workers=2)

        # Мост к Godot отключён: нестабилен. Чтобы вернуть — создать GodotBridge() и вызвать start().
        self.godot = None

        self.voice_text_signal.connect(self._process)
        self.add_message_signal.connect(self._add_message)
        self.set_emotion_signal.connect(self._set_emotion)
        self.typing_signal.connect(self._set_typing)
        self.progress_signal.connect(self._set_progress)
        self.close_signal.connect(self.close)
        self.finish_loading_signal.connect(self._finish_loading)
        self.finish_close_signal.connect(self._finish_close)

        icon_path = "assets/sphere.gif" if os.path.exists("assets/sphere.gif") else "sphere.gif"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        ready_event = threading.Event()
        threading.Thread(target=start_local_server, args=(ready_event,), daemon=True).start()
        ready_event.wait(timeout=2.0)

        self.loading_screen = LoadingScreen()
        self.setCentralWidget(self.loading_screen)
        self.loading_screen.set_progress(0, "Подготовка...")
        threading.Thread(target=self._load_core, daemon=True).start()

    def _start_speech_watcher(self):
        """Шлёт в Godot «talk», пока голос говорит, и «calm» после. Опрос 10 раз в секунду.
        Не трогает core/voice.py: читает только флаг is_speaking."""
        def _watch():
            was_speaking = False
            while True:
                try:
                    speaking = bool(self.voice and getattr(self.voice, "is_speaking", False))
                except Exception:
                    speaking = False
                if speaking != was_speaking:
                    was_speaking = speaking
                    if speaking:
                        self._godot_send("talk")
                    else:
                        # речь закончилась: возвращаемся в спокойствие, если не «думаем»
                        self._godot_send("calm")
                time.sleep(0.1)
        threading.Thread(target=_watch, name="speech-watcher", daemon=True).start()

    def _set_typing(self, visible: bool):
        self._godot_send("think" if visible else "calm")
        if not hasattr(self, "chat") or self.chat is None:
            return
        try:
            if visible:
                self.chat.show_typing()
            else:
                self.chat.hide_typing()
        except Exception as e:
            log(f"⚠️ typing: {e}")

    def _set_progress(self, value: int, text: str):
        try:
            if hasattr(self, "loading_screen") and self.loading_screen is not None:
                self.loading_screen.set_progress(value, text)
        except Exception as e:
            log(f"⚠️ progress: {e}")

    def _load_core(self):
        """Загрузка ядра в фоновом потоке. Все мутации self.* защищены _core_lock."""
        self.progress_signal.emit(10, "Загрузка памяти...")

        with self._core_lock:
            self.memory = Memory()

        self.progress_signal.emit(25, "Подключение к мозгу...")
        with self._core_lock:
            self.brain = Brain()
            self.brain.memory = self.memory
            self.brain.app = self
        log("✅ Brain загружен")

        # 1.6.2: загружаем senior_mode из настроек
        try:
            from ui.settings_dialog import load_settings
            s = load_settings()
            self.senior_mode = s.get("senior_mode", False)
            self.brain.senior_mode = self.senior_mode
            log(f"senior_mode = {self.senior_mode}")
        except Exception:
            self.senior_mode = False

        self.progress_signal.emit(30, "Проверка API...")
        try:
            from core.api import API
            api = API()
            if api.enabled:
                test_resp = api.ask("ping")
                if not test_resp or "Ошибка" in test_resp or "⚠️" in test_resp:
                    self._api_status = "⚠️ API не отвечает"
                else:
                    self._api_status = "✅ API OK"
            else:
                self._api_status = "⚠️ API выключен"
        except Exception as e:
            self._api_status = f"⚠️ API ошибка: {e}"
        log(self._api_status)

        self.progress_signal.emit(50, "Загрузка голоса...")
        with self._core_lock:
            self.voice = Voice()
        self._start_speech_watcher()

        self.progress_signal.emit(75, "Загрузка слуха...")
        with self._core_lock:
            self.wake = WakeWordDetector()
            self.wake.start()

        self.progress_signal.emit(90, "Настройка души...")
        with self._core_lock:
            self.soul = Soul()
            self.awareness = Awareness(interval=5)
            self.awareness.set_intelligence(self.brain.intel)  # дневник событий
            self.initiative = Initiative(self.voice, self.awareness, self.soul, min_interval=600)
            self.initiative.on_message = lambda text: self.add_message_signal.emit("🛡️ Фитц", text, False)
            self.game_mode = get_game_mode(voice=self.voice, brain=self.brain, memory=self.memory)
            self.autosave = get_autosave(brain=self.brain, soul=self.soul, memory=self.memory)
            self.guardian = get_guardian(voice=self.voice)

            self.brain.soul = self.soul
            self.brain.awareness = self.awareness
            self.brain.voice = self.voice

        self.progress_signal.emit(100, "Готово!")
        # Проверка окружения Linux/Wayland: что не работает — сообщим в чат
        try:
            from core.linux_env import check_environment
            self._env_problems = check_environment()
            for p in self._env_problems:
                log(f"⚠️ окружение: {p}")
        except Exception as e:
            self._env_problems = []
            log(f"⚠️ проверка окружения: {e}")
        # Безопасно: сигнал доставляет вызов в главный поток Qt
        self.finish_loading_signal.emit()

    def _finish_loading(self):
        """Выполняется в главном потоке Qt."""
        try:
            if hasattr(self, "loading_screen") and self.loading_screen is not None:
                self.loading_screen.stop_timer()
        except Exception:
            log("Import/submodule load skipped — continuing without it")
        self._show_main()
        problems = getattr(self, "_env_problems", [])
        if problems:
            text = "Не работает в этой системе:\n" + "\n".join(f"• {p}" for p in problems)
            self.add_message_signal.emit("🛡️ Фитц", text, False)

    def _show_main(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        self.hotbar = Hotbar()
        self.hotbar.settings_clicked.connect(self._open_settings)
        self.hotbar.stop_clicked.connect(self._stop_current_task)
        self.hotbar.logs_clicked.connect(self._open_logs)
        self.hotbar.haru_toggle_clicked.connect(self._toggle_haru)
        self.hotbar.minimize_clicked.connect(self.showMinimized)
        self.hotbar.exit_clicked.connect(self.close)
        main_layout.addWidget(self.hotbar)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        left_layout = QVBoxLayout()
        self.chat = ChatWidget()
        self.chat.load_history()
        self._flush_pending_messages()
        left_layout.addWidget(self.chat, stretch=1)

        self.input_frame = QFrame()
        self.input_frame.setStyleSheet("""
            QFrame { background-color: #1a1a2e; border: 2px solid #00d4ff; border-radius: 10px; }
        """)
        input_layout = QHBoxLayout(self.input_frame)
        input_layout.setContentsMargins(10, 5, 10, 5)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Напиши Фитцу...")
        self.entry.setStyleSheet("""
            QLineEdit { background: transparent; color: #e0e0e0; font-family: Arial; font-size: 13px; border: none; }
        """)
        self.entry.returnPressed.connect(self._send)
        input_layout.addWidget(self.entry)

        copy_btn = QPushButton("📋")
        copy_btn.setFixedSize(40, 40)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(26, 26, 46, 0.7);
                color: #00d4ff; border: 1px solid #0a3a5a;
                border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2a3a5e;
                border: 1px solid #00d4ff;
            }
        """)
        copy_btn.clicked.connect(self._copy_all)
        input_layout.addWidget(copy_btn)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(40, 40)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff; color: #0a0a0f;
                border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover {
                background-color: #00ff88;
                border: 1px solid #00ff88;
            }
        """)
        send_btn.clicked.connect(self._send)
        input_layout.addWidget(send_btn)

        left_layout.addWidget(self.input_frame)
        content_layout.addLayout(left_layout, stretch=1)

        self.haru = HaruWidget()
        content_layout.addWidget(self.haru, stretch=0)

        main_layout.addLayout(content_layout, stretch=1)

        self.status_bar = QLabel("API: ? | Зрение: OFF | Haru: ON | MC: OFF")
        self.status_bar.setStyleSheet("""
            QLabel { color: #00d4ff; background-color: #12121a;
                     font-family: monospace; font-size: 11px;
                     padding: 4px 10px; border-top: 1px solid #2a2a4e; }
        """)
        main_layout.addWidget(self.status_bar)

        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._send_vision_command)
        QShortcut(QKeySequence("Ctrl+Shift+H"), self, self._toggle_haru)
        QShortcut(QKeySequence("Ctrl+Shift+M"), self, lambda: self._process("включи музыку"))
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, lambda: self._process("тишина"))
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self._reread_last_file)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._send)
        QShortcut(QKeySequence("Escape"), self, lambda: self.entry.clear())

        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_status_bar)
        self.stats_timer.start(5000)

        self.awareness.start()
        self.initiative.start()
        self.game_mode.start()
        self.autosave.start()

        threading.Thread(target=self._voice_loop, daemon=True).start()

        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self._sync_voice_tick)
        self.sync_timer.start(50)

        self.vision_timer = QTimer()
        self.vision_timer.timeout.connect(self._auto_vision_tick)

        self._apply_settings()
        self._update_status_bar()

        greeting = make_greeting(self.brain, self.soul, self.awareness)
        self._add_message("🛡️ Фитц", greeting, is_user=False)
        if self.voice:
            self.voice.speak(greeting)

        if self._api_status and "⚠️" in self._api_status:
            self._add_message("⚠️ Система", self._api_status + ". Проверь ключ в настройках.", False)

        self._animate_border()

        # Звук приветствия
        try:
            play_start()
        except Exception:
            log("Import/submodule load skipped — continuing without it")

    def _update_status_bar(self):
        api = "OK" if self._api_status and "✅" in self._api_status else "⚠️"
        vision = "ON" if getattr(self, "vision_timer", None) and self.vision_timer.isActive() else "OFF"
        haru = "ON" if getattr(self, "haru", None) and self.haru.isVisible() else "OFF"
        with self._mc_lock:
            mc = "ON" if self.mc_process else "OFF"
        if getattr(self, "status_bar", None):
            self.status_bar.setText(
                f"API: {api} | Зрение: {vision} | Haru: {haru} | MC: {mc} | {_sys_stats_text()}"
            )

    def set_guardian_mode(self, enabled: bool):
        self._guardian_mode = bool(enabled)
        if enabled:
            self.setStyleSheet("QMainWindow { background-color: #1a0505; }")
            self.input_frame.setStyleSheet(
                "QFrame { background-color: #2a0808; border: 2px solid #ff3333; border-radius: 10px; }"
            )
            self.status_bar.setStyleSheet(
                "QLabel { color: #ff4444; background-color: #1a0505; "
                "font-family: monospace; font-size: 11px; "
                "padding: 4px 10px; border-top: 1px solid #4a1010; }"
            )
            if self.voice:
                self.voice.speak("Режим хранителя активирован.", pitch="low", rate="slow")
            return "🚨 Режим хранителя активирован. Красный интерфейс, низкий голос."
        else:
            self.setStyleSheet("QMainWindow { background-color: #0a0a0f; }")
            self.input_frame.setStyleSheet("""
                QFrame { background-color: #1a1a2e; border: 2px solid #00d4ff; border-radius: 10px; }
            """)
            self.status_bar.setStyleSheet("""
                QLabel { color: #00d4ff; background-color: #12121a;
                         font-family: monospace; font-size: 11px;
                         padding: 4px 10px; border-top: 1px solid #2a2a4e; }
            """)
            if self.voice:
                self.voice.speak("Обычный режим.", pitch="high", rate="medium")
            return "🛡️ Обычный режим. Всё спокойно."

    def _apply_settings(self):
        settings = load_settings()
        self.chat.apply_settings(settings)
        self.haru.apply_settings(settings)
        self.hotbar.apply_settings(settings)

        opacity = settings.get("window_opacity", 100) / 100.0
        opacity = max(0.1, min(1.0, opacity))
        self.setWindowOpacity(opacity)

        # ---- Голос ----
        if self.voice:
            self.voice.volume = settings.get("voice_volume", 1.0)

        # ---- Зрение ----
        if settings.get("vision_enabled", False):
            interval = settings.get("vision_interval_min", 20) * 60 * 1000
            self.vision_timer.start(interval)
        else:
            self.vision_timer.stop()

        # ---- Инициатива ----
        if self.initiative:
            if settings.get("initiative_enabled", True):
                if not self.initiative.running:
                    self.initiative.start()
            else:
                if self.initiative.running:
                    self.initiative.stop()
            # Интервал и агрессивность
            iv = settings.get("initiative_interval", 10)
            aggr = settings.get("initiative_aggression", "средняя")
            if aggr == "низкая":
                self.initiative.min_interval = iv * 60 * 2   # вдвое реже
            elif aggr == "высокая":
                self.initiative.min_interval = iv * 60 // 2  # вдвое чаще
            else:
                self.initiative.min_interval = iv * 60

        # ---- Личность (soul traits) ----
        if self.soul:
            try:
                self.soul.traits["sarcasm"] = 0.9 if settings.get("personality_sarcasm", True) else 0.1
                self.soul.traits["empathy"]  = 0.9 if settings.get("personality_empathy", True)  else 0.1
                self.soul.traits["humor"]    = 0.9 if settings.get("personality_humor", True)    else 0.1
            except Exception:
                log("пропущено в ui_pyqt (строка 727)")

        # ---- Анимации ----
        # Если выключены — не будем перезапускать _animate_border
        if not settings.get("animations_enabled", True):
            try:
                self._anim_active = False
            except Exception:
                log("пропущено в ui_pyqt (строка 735)")

        # ---- Звуки ----
        try:
            if self.voice:
                # громкость звуков интерфейса — отдельно от голоса
                # (оставляем голос как есть, sounds_volume для effects)
                pass
        except Exception:
            log("Import/submodule load skipped — continuing without it")

        self._update_status_bar()

    def _open_settings(self):
        dialog = SettingsDialog(self)
        dialog.mc_connect_requested.connect(lambda s: self._start_mc_bot(s, dialog))
        dialog.mc_disconnect_requested.connect(lambda: self._stop_mc_bot(dialog))
        if dialog.exec():
            self._apply_settings()

    def _open_logs(self):
        dialog = LogsDialog(self)
        dialog.exec()

    def _toggle_haru(self):
        if self.haru.isVisible():
            self.haru.hide()
        else:
            self.haru.show()
        self._update_status_bar()

    def _send_vision_command(self):
        self._process("что на экране")

    def _auto_vision_tick(self):
        if not self.is_running:
            return
        def worker():
            try:
                from core.vision_sdk import describe_screen

                activity = "unknown"
                if self.awareness and hasattr(self.awareness, "get_last_activity"):
                    activity = self.awareness.get_last_activity()

                game_name = None
                if self.game_mode:
                    game_name = getattr(self.game_mode, "current_game", None)

                if game_name:
                    category = "игра"
                elif activity == "coding":
                    category = "код"
                elif activity in ("video", "browsing"):
                    category = "серфинг"
                else:
                    category = "прочее"

                if game_name:
                    prompt = (
                        f"На экране запущена игра {game_name}. "
                        f"Сделай скриншот ОКНА игры (по названию '{game_name}', если умеешь, иначе весь экран). "
                        f"Посмотри на геймплей: здоровье, враги, предметы. "
                        f"Ответь 2–3 предложениями как друг: что происходит и что можно улучшить прямо сейчас."
                    )
                    window_title = game_name
                elif activity == "coding":
                    prompt = (
                        "Пользователь пишет код. Сделай скриншот окна редактора (или весь экран). "
                        "Посмотри на код: есть ли ошибки, что можно улучшить? "
                        "Ответь 1–2 предложениями как друг."
                    )
                    window_title = None
                elif activity in ("video", "browsing"):
                    prompt = (
                        "Пользователь смотрит видео или сидит в браузере. Сделай скриншот. "
                        "Посмотри, что на экране: какое видео, какой сайт, о чём это? "
                        "Ответь 1–2 предложениями как друг."
                    )
                    window_title = None
                elif activity in ("work", "chatting", "music"):
                    prompt = (
                        "Пользователь работает за компьютером. Сделай скриншот. "
                        "Посмотри, чем он занят, и скажи, нужна ли помощь. "
                        "Ответь 1–2 предложениями как друг."
                    )
                    window_title = None
                else:
                    prompt = (
                        "Сделай скриншот. Проанализируй, чем занят пользователь. "
                        "Ответь ОДНИМ предложением (до 15 слов) как друг: что он делает и нужна ли помощь. "
                        "НЕ перечисляй окна. Только смысл."
                    )
                    window_title = None

                # Таймаут 30 секунд на авто-зрение
                _av_result = {"value": None}
                def _av_worker():
                    try:
                        _av_result["value"] = describe_screen(prompt, window_title=window_title, category=category)
                    except Exception:
                        _av_result["value"] = None

                _avt = threading.Thread(target=_av_worker, daemon=True)
                _avt.start()
                _avt.join(timeout=60.0)
                if _avt.is_alive():
                    log("⚠️ Авто-зрение: таймаут 60 сек")
                    return
                result = _av_result["value"]

                if result and result != self.last_screen_description:
                    self.last_screen_description = result
                    self.add_message_signal.emit("🛡️ Фитц", result, False)
                    if self.voice:
                        self.voice.speak(result)
            except Exception as e:
                log(f"❌ Ошибка авто-зрения: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _sync_voice_tick(self):
        if not self.voice:
            return
        raw_volume = getattr(self.voice, "current_volume", 0.0)
        self._smoothed_volume += (raw_volume - self._smoothed_volume) * 0.3
        volume = min(0.8, self._smoothed_volume)
        sync_file = Path(__file__).parent / "is_speaking.txt"
        tmp_file = Path(__file__).parent / "is_speaking.tmp"
        try:
            with open(tmp_file, "w") as f:
                f.write(f"{volume:.3f}")
            os.replace(tmp_file, sync_file)
        except Exception as e:
            log(f"Ошибка записи is_speaking.txt: {e}")

    def _set_emotion(self, response_text):
        # Эмоция по тексту: ошибка → error (грусть), успех → joy (радость).
        # «говорит» не выставляем здесь — это делает наблюдатель за voice.is_speaking.
        self._godot_send(self._godot_state_for(response_text))
        self.haru.set_emotion(response_text)
        gesture = self._gesture_for(response_text) or self._gesture_for_mood()
        if gesture:
            self.haru.set_gesture(gesture)
        motion = self._motion_for_emoji(response_text) or self._motion_for(response_text)
        if motion:
            self.haru.play_motion(motion)
        else:
            self.haru.play_motion("Tap")

    _EMOTION_MOTION = {"joy": "Flick", "laugh": "Tap", "smirk": "FlickLeft"}

    @classmethod
    def _motion_for_emoji(cls, text) -> str | None:
        from core.brain import extract_emotion
        emotion = extract_emotion(str(text or ""))
        return cls._EMOTION_MOTION.get(emotion)

    _MOTION_TRIGGERS = (
        ("Shake", ("ошибк", "опасно", "осторожно", "нельзя", "не получилось")),
        ("Flick", ("привет", "молодец", "отлично", "круто", "рад")),
        ("FlickLeft", ("грустн", "жаль", "извини", "плохо")),
        ("Tap", ("ха-ха", "смешно", "хехе", "прикол")),
    )

    @classmethod
    def _motion_for(cls, text) -> str | None:
        low = str(text or "").lower()
        for group, words in cls._MOTION_TRIGGERS:
            if any(w in low for w in words):
                return group
        return None

    def _gesture_for_mood(self) -> str | None:
        soul = getattr(self, "soul", None)
        if soul is None:
            return None
        mood = soul.get_status().get("mood", "нейтральное")
        return {"сердитое": "angry", "весёлое": "joy", "грустное": "sad"}.get(mood)

    _GESTURE_TRIGGERS = (
        ("alarm", ("осторожно", "опасно", "внимание!")),
        ("joy", ("молодец", "отлично сработал", "горжусь")),
    )

    @classmethod
    def _gesture_for(cls, text) -> str | None:
        low = str(text or "").lower()
        for gesture, words in cls._GESTURE_TRIGGERS:
            if any(w in low for w in words):
                return gesture
        return None

    def _godot_send(self, state: str):
        """Отправляет состояние в Godot, если мост запущен. Ошибки не пробрасываем."""
        bridge = getattr(self, "godot", None)
        if bridge is None:
            return
        try:
            bridge.send(state)
        except Exception as e:
            log(f"⚠️ godot: {e}")

    @staticmethod
    def _godot_state_for(text) -> str:
        """Эмоция по тексту ответа: error (ошибка/грусть) или joy (успех/радость)."""
        t = str(text or "").lstrip()
        if t.startswith(("⚠️", "❌", "⛔")):
            return "error"
        return "joy"

    def _animate_border(self):
        if not self.is_running:
            return
        is_speaking = self.voice and getattr(self.voice, "is_speaking", False)
        if is_speaking:
            color = "#00ff88"
            self._border_phase = getattr(self, "_border_phase", 0.0) + 0.2
        else:
            self._border_phase = getattr(self, "_border_phase", 0.0) + 0.05
            r = int(100 + 50 * math.sin(self._border_phase))
            g = int(100 + 50 * math.sin(self._border_phase + 2))
            b = int(255)
            color = f"#{r:02x}{g:02x}{b:02x}"
        border_style = f"border: 2px solid {color}; border-radius: 10px;"
        try:
            input_style = self.input_frame.styleSheet()
            if "border:" in input_style:
                input_style = re.sub(r"border: \d+px solid #[0-9a-fA-F]+;", border_style, input_style)
            else:
                input_style += border_style
            self.input_frame.setStyleSheet(input_style)
        except Exception:
            log("Import/submodule load skipped — continuing without it")
        QTimer.singleShot(100, self._animate_border)

    def _add_message(self, sender, text, is_user=False):
        if not hasattr(self, "chat") or self.chat is None:
            self._pending_messages = getattr(self, "_pending_messages", [])
            self._pending_messages.append((sender, text, is_user))
            return
        self.chat.add_message(sender, text, is_user)

    def _flush_pending_messages(self):
        for sender, text, is_user in getattr(self, "_pending_messages", []):
            self.chat.add_message(sender, text, is_user)
        self._pending_messages = []
    def _send(self):
        text = self.entry.text().strip()
        self.entry.clear()
        if not text:
            return
        self._add_message("Ты", text, is_user=True)
        self._process(text)

    def _sound_safe(self, fn):
        """Звук не должен ронять ответ: любая ошибка звука подавляется и логируется."""
        try:
            fn()
        except Exception as e:
            log(f"⚠️ звук {getattr(fn, '__name__', fn)}: {e}")

    def _haru_state(self, state: str):
        """Меняет состояние Haru (think/listen). Вызывается из фонового потока,
        поэтому переход отправляется в UI-поток через QTimer."""
        def _apply():
            haru = getattr(self, "haru", None)
            if haru is None:
                return
            try:
                if state == "think":
                    haru.think()
                elif state == "listen":
                    haru.listen()
            except Exception as e:
                log(f"⚠️ haru {state}: {e}")
        QTimer.singleShot(0, _apply)

    def _stop_current_task(self):
        agent = getattr(self, "_fitz_agent", None)
        if agent is not None:
            agent.request_stop()
        self.typing_signal.emit(False)
        self.add_message_signal.emit("🛡️ Фитц", "⏹ Текущая задача остановлена.", False)

    def _reread_last_file(self):
        path = getattr(self, "_last_read_path", None)
        if not path:
            self.add_message_signal.emit("🛡️ Фитц", "Я ещё ничего не читал. Сначала скажи, какой файл открыть.", False)
            return
        self._process(f"прочитай файл {path}")

    def _play_all_motions(self):
        groups = ["Flick", "Tap", "Shake", "FlickLeft"]
        for i, group in enumerate(groups):
            QTimer.singleShot(i * 2500, lambda g=group: self.haru.play_motion(g))

    def _process(self, text):
        self.executor.submit(self._process_worker, text)

    def _process_worker(self, text):
        try:
            self.memory.log(f"Ты: {text}")
            if self.soul:
                self.soul.analyze_mood(text)

            # ===== ПРОВЕРКА НА РАБОТУ С ФАЙЛАМИ (в обход brain) =====
            low_text = text.lower().strip()

            # ===== ВСЕ АНИМАЦИИ ПО КОМАНДЕ =====
            if "все анимации" in low_text or "все движения" in low_text:
                self._play_all_motions()
                self.add_message_signal.emit("🛡️ Фитц", "Показываю все анимации.", False)
                return

            # ===== ОТКАЗ НА ЛЮБОЕ ПРЕДЛОЖЕНИЕ ИНИЦИАТИВЫ =====
            if (self.initiative and self.initiative.awaiting_answer()
                    and low_text in ("нет", "не надо", "отстань", "не хочу")):
                self.initiative.refuse(30)
                msg = "Хорошо, не буду предлагать 30 минут."
                self.add_message_signal.emit("🛡️ Фитц", msg, False)
                if self.voice:
                    self.voice.speak(msg)
                self.typing_signal.emit(False)
                return

            # ===== ОБРАБОТКА ОТВЕТА НА ПРЕДЛОЖЕНИЕ РАЗВЛЕЧЕНИЯ =====
            if self.initiative and getattr(self.initiative, "_pending_url", None):
                if low_text in ("да", "включи", "давай", "го", "ага", "угу", "ок", "yes", "врубай"):
                    url = self.initiative._pending_url
                    name = self.initiative._pending_name or "развлечение"
                    self.initiative._pending_url = None
                    self.initiative._pending_name = None
                    import webbrowser as _wb
                    try:
                        _wb.open(url)
                    except Exception:
                        log("пропущено в ui_pyqt (строка 1003)")
                    msg = f"🎵 Включаю {name}!"
                    self.add_message_signal.emit("🛡️ Фитц", msg, False)
                    if self.voice:
                        self.voice.speak(msg)
                    self.typing_signal.emit(False)
                    return
                elif low_text in ("нет", "не надо", "не", "отстань", "no", "отмена", "не хочу"):
                    self.initiative._pending_url = None
                    self.initiative._pending_name = None
                    self.initiative.refuse(30)
                    msg = "Хорошо, не включаю."
                    self.add_message_signal.emit("🛡️ Фитц", msg, False)
                    if self.voice:
                        self.voice.speak(msg)
                    self.typing_signal.emit(False)
                    return

            if (low_text.startswith("открой ") or
                low_text.startswith("прочитай ") or
                low_text.startswith("покажи ") or
                "проверь код " in low_text or
                "проверь файл " in low_text):
                from commands.files import handle as files_handle
                files_result = files_handle(text, self.memory, self.brain)
                if files_result:
                    self.add_message_signal.emit("🛡️ Фитц", files_result, False)
                    if self.voice:
                        self.voice.speak(files_result)
                    self.set_emotion_signal.emit(files_result)
                    self.typing_signal.emit(False)
                    try:
                        play_open()
                    except Exception:
                        log("пропущено в ui_pyqt (строка 1037)")
                    return

            # ===== ЖУРНАЛ ДЕЙСТВИЙ =====
            if low_text in ("покажи журнал", "журнал действий", "покажи журнал действий",
                            "что ты делал", "история действий"):
                entries = action_journal.recent(15)
                if not entries:
                    self.add_message_signal.emit("🛡️ Фитц", "Журнал действий пуст.", False)
                    return
                lines = ["📜 Последние действия:"]
                for e in entries:
                    lines.append(f"• {e.get('ts','')} {e.get('tool','')} [{e.get('decision','')}] "
                                 f"{str(e.get('result',''))[:80]}")
                self.add_message_signal.emit("🛡️ Фитц", "\n".join(lines), False)
                return

            # ===== РЕЖИМ «НЕ БЕСПОКОИТЬ» (ТИШИНА) =====
            if low_text in ("тишина", "не беспокоить", "режим тишины", "тихий час"):
                self.add_message_signal.emit(
                    "🛡️ Фитц",
                    "🔇 Режим тишины включён на 1 час. Я не буду говорить и предлагать инициативы.",
                    False
                )
                if self.voice:
                    self.voice.speak("Режим тишины.", pitch="low", rate="slow")
                    import time as _time
                    _time.sleep(2)
                    self.voice.volume = 0.0
                if self.initiative:
                    self.initiative.stop()
                # Таймер на 1 час — возвращаем всё обратно
                def _restore_noise():
                    if self.voice:
                        self.voice.volume = 1.0
                    if self.initiative and not self.initiative.running:
                        self.initiative.start()
                    self.add_message_signal.emit(
                        "🛡️ Фитц",
                        "🔔 Режим тишины окончен. Я снова с вами!",
                        False
                    )
                threading.Timer(3600, _restore_noise).start()
                self.typing_signal.emit(False)
                return

            # ===== СКРИНШОТ С ЗАДЕРЖКОЙ =====
            _scr_delay_match = re.search(
                r"скриншот через\s+(\d+)\s*(?:сек|секунд[ыу]?)?",
                low_text
            )
            if _scr_delay_match:
                delay = int(_scr_delay_match.group(1))
                delay = max(1, min(60, delay))  # от 1 до 60 сек
                self.add_message_signal.emit(
                    "🛡️ Фитц",
                    f"📸 Сделаю скриншот через {delay} сек...",
                    False
                )
                def _delayed_screenshot():
                    import time as _time
                    _time.sleep(delay)
                    self._auto_vision_tick()
                threading.Thread(target=_delayed_screenshot, daemon=True).start()
                self.typing_signal.emit(False)
                return

            # ===== МАЙНКРАФТ-БОТ =====
            if "играй в майнкрафт" in low_text or "запусти майнкрафт" in low_text:
                self.add_message_signal.emit("🛡️ Фитц", "🎮 Запускаю Майнкрафт-бота...", False)
                self._start_mc_bot(
                    {"mc_host": "localhost", "mc_port": 34485, "mc_nick": "FitzBot"},
                    dialog=None
                )
                if self.mc_process:
                    msg = "🎮 Бот подключён к localhost:34485 (ник: FitzBot). Я буду управлять им автоматически."
                else:
                    msg = "⚠️ Не удалось запустить бота. Проверь, что Node.js установлен (npm install mineflayer)."
                self.add_message_signal.emit("🛡️ Фитц", msg, False)
                if self.voice:
                    self.voice.speak(msg)
                self.typing_signal.emit(False)
                return

            # ===== ЗРЕНИЕ ЧЕРЕЗ DSH =====
            _vision_triggers = (
                "что на экране", "посмотри на экран", "опиши экран",
                "что видишь", "что видно на экране", "покажи экран",
                "что в окне", "посмотри на окно", "найди на экране",
                "кликни по", "нажми на",
            )
            if any(w in text.lower() for w in _vision_triggers):
                self.typing_signal.emit(True)
                self.add_message_signal.emit("🛡️ Фитц", "👁️ Смотрю на экран...", False)
                try:
                    from core.vision_sdk import describe_screen
                    game_name = None
                    if self.game_mode:
                        game_name = getattr(self.game_mode, "current_game", None)

                    activity = "unknown"
                    if self.awareness and hasattr(self.awareness, "get_last_activity"):
                        activity = self.awareness.get_last_activity()

                    if game_name:
                        category = "игра"
                        prompt = f"Проанализируй игру {game_name}. Что происходит на экране? Что можно улучшить в геймплее?"
                    elif activity == "coding":
                        category = "код"
                        prompt = "Посмотри на код на экране. Есть ли ошибки? Что можно улучшить?"
                    elif activity in ("video", "browsing"):
                        category = "серфинг"
                        prompt = "Что на экране? Какое видео или сайт?"
                    else:
                        category = "прочее"
                        prompt = "Сделай скриншот и опиши, что на экране. Что открыто, какие окна, что происходит."

                    # Таймаут 30 секунд на скриншот + описание
                    _vision_result = {"value": "⚠️ Таймаут зрения (30 сек). Попробуй ещё раз."}
                    def _vision_worker():
                        try:
                            _vision_result["value"] = describe_screen(prompt, window_title=game_name, category=category)
                        except Exception as ex:
                            _vision_result["value"] = f"⚠️ Ошибка зрения: {ex}"

                    _vt = threading.Thread(target=_vision_worker, daemon=True)
                    _vt.start()
                    _vt.join(timeout=60.0)
                    if _vt.is_alive():
                        log("⚠️ describe_screen завис на 60 сек — пропускаем")
                        result = _vision_result["value"]
                    else:
                        result = _vision_result["value"]
                    self.add_message_signal.emit("🛡️ Фитц", result, False)
                    self.set_emotion_signal.emit(result)
                    if self.voice:
                        self.voice.speak(result)
                except Exception as e:
                    log(f"❌ Ошибка зрения: {e}")
                    self.add_message_signal.emit("⚠️", f"Ошибка зрения: {e}", False)
                finally:
                    self.typing_signal.emit(False)
                return

            self.typing_signal.emit(True)

            # Питание — только через гейт _execute_tool (полный доступ + слово «ДА») и честный результат
            power_tool = {
                "перезагрузи пк": "reboot_pc", "перезагрузка": "reboot_pc",
                "ребут": "reboot_pc", "reboot": "reboot_pc", "перезагрузи": "reboot_pc",
                "выключи пк": "shutdown_pc", "выключить пк": "shutdown_pc",
                "выключение": "shutdown_pc", "shutdown": "shutdown_pc", "выключи": "shutdown_pc",
            }.get(text.lower().strip())
            if power_tool:
                answer = self._execute_tool({"tool": power_tool, "args": {}})
                self.add_message_signal.emit("🛡️ Фитц", answer, False)
                self.typing_signal.emit(False)
                return

            result = process_command(text, self.memory, self.brain)
            log(f"process_command вернул: {result!r}")

            # ===== 1.6.2: переключение сеньор-режима =====
            low_text = text.lower().strip()

            # Порядок проверок: ВЫКЛ → ВКЛ → СТАТУС (важно!)
            is_off = ("выключи сеньор" in low_text or "сеньор режим выкл" in low_text
                      or "senior off" in low_text) and "статус" not in low_text
            is_on = ("включи сеньор" in low_text or "сеньор режим вкл" in low_text
                     or "senior mode" in low_text or "senior on" in low_text) and "статус" not in low_text
            is_status = "статус сеньор" in low_text or "сеньор режим статус" in low_text

            if is_off or is_on or is_status:
                try:
                    from ui.settings_dialog import load_settings, save_settings
                    s = load_settings()
                    if is_off:
                        if self.senior_mode:
                            self.senior_mode = False
                            s["senior_mode"] = False
                            save_settings(s)
                            response = ("О, создатель, ты решил вернуться к обычному режиму? "
                                        "Ну ладно, я не обижаюсь. Шучу. Обижаюсь.")
                        else:
                            response = "Сеньор-режим уже выключен, создатель. Ты что, забыл?"
                    elif is_on:
                        if not self.senior_mode:
                            self.senior_mode = True
                            s["senior_mode"] = True
                            save_settings(s)
                            response = ("О, создатель, ты решил включить сеньор-режим? "
                                        "Ну что ж, теперь я буду планировать всё за тебя. "
                                        "Смотри и учись.")
                        else:
                            response = "Сеньор-режим уже включён, создатель. Я и так планирую всё за тебя."
                    elif is_status:
                        if self.senior_mode:
                            response = "Сеньор-режим: включён. Я планирую шаги, создатель."
                        else:
                            response = "Сеньор-режим: выключен. Я просто твой саркастичный друг."
                    self.brain.senior_mode = self.senior_mode
                    self.add_message_signal.emit("🛡️ Фитц", response, False)
                    if self.voice:
                        self.voice.speak(response)
                    self.typing_signal.emit(False)
                except Exception as e:
                    log(f"senior_mode toggle error: {e}")
                    response = f"⚠️ Ошибка переключения режима: {e}"
                    self.add_message_signal.emit("⚠️", response, False)
                return

            response = None
            if isinstance(result, dict):
                response = result.get("response")
            elif isinstance(result, str) and result.strip():
                response = result

            if not response:
                try:
                    if getattr(self, "senior_mode", False):
                        # Сеньор-режим: планирует шаги
                        self._sound_safe(play_think)
                        self._haru_state("think")
                        agent = getattr(self, "_fitz_agent", None)
                        if agent is None:
                            from core.agent import FitzAgent
                            self._fitz_agent = FitzAgent(
                                brain=self.brain,
                                execute_tool=self._execute_tool,
                                max_retries=2,
                            )
                            agent = self._fitz_agent
                        response = agent.process(text)
                        log(f"FitzAgent (senior_mode) ответил: {response[:200]!r}")
                    else:
                        # Дружеский режим: саркастичный ответ
                        self._sound_safe(play_think)
                        self._haru_state("think")
                        response = self.brain.ask(text)
                except Exception as e:
                    log(f"❌ Ошибка ответа: {e}")
                    response = self.brain.ask(text)  # fallback
                finally:
                    self._haru_state("listen")

            if not response or not str(response).strip():
                response = "Я не понял. Повтори проще."

            # Звук по результату: ошибка или успех
            if str(response).startswith(("⚠️", "❌", "⛔")):
                self._sound_safe(play_error)
            else:
                self._sound_safe(play_success)

            if self.voice:
                low_resp = str(response).lower()
                if any(w in low_resp for w in ("молодец", "отлично", "супер", "класс")):
                    pitch, rate = "x-high", "medium"
                elif any(w in low_resp for w in ("осторожно", "опасно", "тревога", "внимание")):
                    pitch, rate = "low", "slow"
                elif any(w in low_resp for w in ("грустно", "жаль", "сочувствую")):
                    pitch, rate = "low", "medium"
                else:
                    pitch, rate = "high", "medium"
                self.voice.speak(response, pitch=pitch, rate=rate)

            self.add_message_signal.emit("🛡️ Фитц", str(response), False)
            self.set_emotion_signal.emit(str(response))

            if text.startswith("[Игра]"):
                self._send_to_minecraft(str(response))

        except Exception as e:
            log(f"❌ Ошибка в _process: {e}")
            self.typing_signal.emit(False)
            self.add_message_signal.emit("⚠️", str(e), False)
            try:
                play_error()
            except Exception:
                log("пропущено в ui_pyqt (строка 1316)")

    def _voice_loop(self):
        def on_voice(text):
            low = text.lower().strip()
            if low in ("пока", "выход", "стоп", "quit", "exit"):
                self.close_signal.emit()
                return
            self.add_message_signal.emit("🎤", f"«{text}»", True)
            if text.strip():
                self.voice_text_signal.emit(text)
        try:
            self.voice.listen_continuous(on_voice, wake_detector=self.wake)
        except Exception as e:
            log(f"❌ Ошибка в _voice_loop: {e}")

    def _copy_all(self):
        text = self.chat.get_last_text()
        if text:
            QApplication.clipboard().setText(text)
            self._add_message("📋 Система", "Текст скопирован.", False)

    def _start_mc_bot(self, settings, dialog=None):
        with self._mc_lock:
            if self.mc_process:
                self._stop_mc_bot(dialog)

            try:
                node_path = shutil.which("node")
                if not node_path:
                    if dialog:
                        dialog.set_mc_status("Ошибка: node не найден в PATH")
                    return

                # stdout/stderr → DEVNULL, чтобы pipe не забился и не повесил бота
                self.mc_process = subprocess.Popen(
                    [node_path, "mine_bot.js", settings["mc_host"], str(settings["mc_port"]), settings["mc_nick"]],
                    cwd=str(Path(__file__).parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                if dialog:
                    dialog.set_mc_status("Подключен (ожидание спавна...)")
                self._update_status_bar()

            except Exception as e:
                log(f"❌ Ошибка запуска бота: {e}")
                if dialog:
                    dialog.set_mc_status(f"Ошибка: {e}")

    def _stop_mc_bot(self, dialog=None):
        with self._mc_lock:
            if self.mc_process:
                self.mc_process.terminate()
                try:
                    self.mc_process.wait(timeout=3)
                except Exception:
                    log("пропущено в ui_pyqt (строка 1374)")
                self.mc_process = None
                if dialog:
                    dialog.set_mc_status("Отключен")
        self._update_status_bar()

    def _check_mc_messages(self):
        from_bot = Path("data/mc_from_bot.txt")

        if not from_bot.exists():
            return

        try:
            content = from_bot.read_text(encoding="utf-8").strip()
            if not content:
                return

            tmp = from_bot.with_suffix(".tmp")
            try:
                tmp.write_text("", encoding="utf-8")
                os.replace(tmp, from_bot)
            except Exception:
                log("пропущено в ui_pyqt (строка 1396)")

            if content.startswith("{"):
                try:
                    state = json.loads(content)
                    log(f"📥 JSON от бота: {content[:80]}...")
                    # Вызывается из QTimer → главный поток Qt, QTimer.singleShot здесь безопасен
                    QTimer.singleShot(0, lambda s=state: self._think_for_minecraft(s))
                except json.JSONDecodeError:
                    log("⚠️ Битый JSON, пропускаем")

            elif content.startswith("[Игра]"):
                log(f"📥 Чат из игры: {content}")
                self.voice_text_signal.emit(content)

            elif content.startswith("✅") or content.startswith("❌"):
                self.add_message_signal.emit("🎮 Майнкрафт", content, False)

        except Exception as e:
            log(f"⚠️ Ошибка чтения от бота: {e}")

    def _think_for_minecraft(self, state):
        # Проверяем, что бот жив (файл to_bot обновлялся недавно)
        to_bot = Path("data/mc_to_bot.txt")
        if not to_bot.exists() or (time.time() - to_bot.stat().st_mtime > 10):
            return  # Бот мёртв, не думаем

        prompt = (
            f"Ты — Фитц, играешь в Майнкрафт. "
            f"Состояние: здоровье {state.get('health')}/20, еда {state.get('food')}/20. "
            f"Ближайший игрок: {state.get('nearestPlayer')}. "
            f"Ближайший моб: {state.get('nearestMob')}. "
            f"Рядом дерево: {state.get('hasWoodNearby')}. "
            f"Позиция: {state.get('pos')}. "
            f"Ответь СТРОГО одним словом из списка:\n"
            f"FOLLOW — идти к игроку\n"
            f"DIG — рубить дерево\n"
            f"ATTACK — атаковать моба\n"
            f"EAT — съесть еду\n"
            f"STOP — стоять на месте\n"
            f"JUMP — прыгнуть\n"
            f"Никаких объяснений, только одно слово."
        )
        
        try:
            response = self.brain.ask(prompt, max_tokens=20)
            action = response.strip().split()[0].upper() if response else "STOP"
        except Exception as e:
            log(f"⚠️ Ошибка ИИ для Майнкрафта: {e}")
            return
        
        # Отправляем боту
        try:
            tmp = to_bot.with_suffix(".tmp")
            tmp.write_text(action, encoding="utf-8")
            os.replace(tmp, to_bot)
            log(f"🎮 Фитц решил: {action}")
        except Exception as e:
            log(f"⚠️ Ошибка записи в бота: {e}")

    def _send_to_minecraft(self, text):
        self._write_to_bot(f"say:{text[:200]}")

    def _write_to_bot(self, text: str):
        """Атомарная запись в mc_to_bot.txt."""
        to_bot = Path("data/mc_to_bot.txt")
        tmp = to_bot.with_suffix(".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, to_bot)
        except Exception as e:
            log(f"⚠️ Ошибка записи в бота: {e}")

    # ============================================================
    # ПОДТВЕРЖДЕНИЕ ОПАСНЫХ КОМАНД (1.6.2)
    # ============================================================
    _DANGEROUS_TOOLS = {
        "run_command_full", "sudo_command", "kill_process",
        "shutdown_pc", "reboot_pc", "install_package",
        # Ввод и блокировка: легко сработать случайно, поэтому подтверждение
        "click_at", "type_text", "press_key", "lock_screen",
    }

    # Все опасные инструменты требуют ввода слова «ДА», а не одного клика (защита от случайного нажатия).

    def _confirm_command(self, cmd_summary: str, typed: bool = False) -> bool:
        """Показывает подтверждение опасной команды.
        typed=True: вместо кнопки «Да» нужно ввести слово «ДА» (защита от случайного нажатия)."""
        try:
            from PyQt6.QtWidgets import QMessageBox, QInputDialog
            text = f"Создатель, я собираюсь выполнить:\n\n{cmd_summary}\n\n"
            if typed:
                text += "Это серьёзная команда. Введи слово ДА, чтобы подтвердить:"
                word, ok = QInputDialog.getText(self, "⚠️ Серьёзная команда", text)
                return bool(ok) and word.strip() == "ДА"
            reply = QMessageBox.question(
                self, "⚠️ Подтверждение",
                text + "Подтверждаешь?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return reply == QMessageBox.StandardButton.Yes
        except Exception:
            return False

    def _execute_tool(self, action: dict) -> str:
        """Выполняет инструмент и пишет результат в журнал. Логика — в _execute_tool_inner."""
        tool = action.get("tool", "say")
        args = action.get("args", {})
        result = self._execute_tool_inner(action)
        # say/ask — это не действия с ПК; в журнал не пишем, чтобы не засорять.
        if tool not in ("say", "ask"):
            action_journal.record(tool, args, "executed", str(result))
        return result

    def _execute_tool_inner(self, action: dict) -> str:
        """Выполняет один инструмент. Опасные — с подтверждением."""
        from core.tools import (
            read_file, write_file, generate_code, rewrite_file,
            open_app, search_web, take_screenshot,
            play_music, window_control, run_command,
            run_command_full, sudo_command, kill_process,
            system_info, network_info, install_package,
            shutdown_pc, reboot_pc, lock_screen,
            click_at, type_text, press_key,
        )
        tool = action.get("tool", "say")
        args = action.get("args", {})

        # 1.6.2: подтверждение для опасных команд
        if tool in self._DANGEROUS_TOOLS:
            # Проверяем full_access в настройках
            try:
                from ui.settings_dialog import load_settings
                full_access = load_settings().get("full_access", False)
            except Exception as e:
                print(f"⚠️ Не удалось прочитать настройки full_access: {e}")
                full_access = False
            if not full_access:
                action_journal.record(tool, args, "denied_no_access")
                return "⛔ Полный доступ выключен. Включи в настройках (вкладка «Права»)."
            confirm_text = f"инструмент: {tool}\n"
            for k, v in args.items():
                confirm_text += f"  {k}: {v}\n"
            typed = tool in self._DANGEROUS_TOOLS
            if not self._confirm_command(confirm_text.strip(), typed=typed):
                action_journal.record(tool, args, "cancelled")
                return "🚫 Отменено."
            action_journal.record(tool, args, "confirmed_typed" if typed else "confirmed")

        try:
            if tool == "say":
                return args.get("text", "OK.")
            elif tool == "ask":
                return args.get("text", "Что нужно сделать?")
            elif tool == "read_file":
                path = args.get("path", args.get("name", ""))
                self._last_read_path = path
                return read_file(path)
            elif tool == "write_file":
                path = args.get("path", args.get("name", ""))
                content = args.get("content", args.get("text", ""))
                return write_file(path, content)
            elif tool == "generate_code":
                prompt = args.get("prompt", args.get("query", ""))
                language = args.get("language", "python")
                return generate_code(prompt, language)
            elif tool == "rewrite_file":
                path = args.get("path", args.get("name", ""))
                language = args.get("language", "python")
                return rewrite_file(path, language)
            elif tool == "open_app":
                name = args.get("name", args.get("target", ""))
                return open_app(name)
            elif tool == "search_web":
                query = args.get("query", args.get("name", ""))
                return search_web(query)
            elif tool == "take_screenshot":
                return take_screenshot()
            elif tool == "play_music":
                mood = args.get("mood", "нейтральное")
                return play_music(mood)
            elif tool == "window_control":
                act = args.get("action", "")
                name = args.get("name", "")
                return window_control(act, name)
            elif tool == "run_command":
                cmd = args.get("cmd", args.get("command", ""))
                return run_command(cmd)

            # ===== НОВЫЕ ИНСТРУМЕНТЫ (1.6.2) =====
            elif tool == "run_command_full":
                cmd = args.get("cmd", args.get("command", ""))
                return run_command_full(cmd)
            elif tool == "sudo_command":
                cmd = args.get("cmd", args.get("command", ""))
                return sudo_command(cmd)
            elif tool == "kill_process":
                pid = args.get("pid", args.get("name", ""))
                return kill_process(pid)
            elif tool == "system_info":
                return system_info()
            elif tool == "network_info":
                return network_info()
            elif tool == "install_package":
                pkg = args.get("pkg", args.get("name", ""))
                return install_package(pkg)
            elif tool == "shutdown_pc":
                return shutdown_pc()
            elif tool == "reboot_pc":
                return reboot_pc()
            elif tool == "lock_screen":
                return lock_screen()
            elif tool == "click_at":
                x = args.get("x", args.get("pos_x", "0"))
                y = args.get("y", args.get("pos_y", "0"))
                return click_at(x, y)
            elif tool == "type_text":
                text = args.get("text", args.get("content", ""))
                return type_text(text)
            elif tool == "press_key":
                key = args.get("key", args.get("name", ""))
                return press_key(key)
            else:
                return f"⚠️ Неизвестный инструмент: {tool}"
        except Exception as e:
            log(f"❌ _execute_tool({tool}): {e}")
            return f"⚠️ Ошибка инструмента {tool}: {e}"

    # ============================================================
    # ЗАКРЫТИЕ
    # ============================================================
    def closeEvent(self, event):
        # Выключаем unsafe_mode перед закрытием (только Linux)
        _automate_unsafe_mode(enable=False)

        if getattr(self, "_closing", False):
            event.accept()
            return

        self._closing = True
        self.is_running = False

        try:
            self.chat.save_history()
        except Exception as e:
            log(f"⚠️ Ошибка сохранения истории: {e}")

        try:
            self.sync_timer.stop()
            self.vision_timer.stop()
            if hasattr(self, "mc_timer"):
                self.mc_timer.stop()
        except Exception:
            log("Import/submodule load skipped — continuing without it")

        from ui.closing_screen import ClosingScreen
        self.closing_screen = ClosingScreen()
        self.setCentralWidget(self.closing_screen)

        threading.Thread(target=self._cleanup_worker, daemon=True).start()
        event.ignore()

    def _cleanup_worker(self):
        """Фоновая очистка: остановка подсистем и закрытие лога."""
        for obj in [self.initiative, self.awareness, self.game_mode, self.autosave,
                    self.guardian, self.wake, self.voice]:
            try:
                if obj:
                    t = threading.Thread(target=obj.stop, daemon=True)
                    t.start()
                    t.join(timeout=1.0)
            except Exception:
                log("пропущено в ui_pyqt (строка 1669)")

        # Закрываем лог-файл
        _close_log()

        # Безопасно: сигнал переносит вызов в главный поток Qt
        self.finish_close_signal.emit()

    def _finish_close(self):
        """Выполняется в главном потоке Qt."""
        if hasattr(self, "closing_screen") and self.closing_screen:
            try:
                self.closing_screen.set_status("Готово. До встречи!")
                self.closing_screen.stop_timer()
            except Exception:
                log("пропущено в ui_pyqt (строка 1684)")

        bridge = getattr(self, "godot", None)
        if bridge is not None:
            try:
                bridge.stop()
            except Exception:
                log("пропущено в ui_pyqt (строка 1691)")

        QTimer.singleShot(500, lambda: os._exit(0))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FitzApp()
    window.show()
    sys.exit(app.exec())