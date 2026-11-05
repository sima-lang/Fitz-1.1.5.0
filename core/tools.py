"""
tools.py — Инструменты Senior-режима Фитца 1.5.0.
read_file, open_app, search_web, take_screenshot, play_music, window_control,
write_file, generate_code, rewrite_file, run_command.
"""
import os
import re
import shlex
import shutil
import subprocess
import webbrowser
import platform as _platform

from core.logger import get_logger as _gl
_tlog = _gl("tools")

_SYSTEM = _platform.system()

# ===== ВНУТРЕННИЕ =====
def _safe_run(cmd: list, timeout: float = 8) -> str:
    """Безопасный subprocess.run, возвращает stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or ""
    except Exception as e:
        return str(e)


def _ydotool(args: list, timeout: float = 5) -> tuple:
    """Запускает ydotool и проверяет код возврата. Возвращает (ok, текст_ошибки)."""
    try:
        r = subprocess.run(["ydotool", *args], capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return False, str(e)
    if r.returncode == 0:
        return True, ""
    return False, (r.stderr.strip() or f"код {r.returncode}")


# ===== 1. READ FILE =====
def read_file(path: str) -> str:
    """Читает файл с защитой от Path Traversal. Возвращает содержимое или ошибку."""
    if not path or not path.strip():
        return "⚠️ Укажи путь к файлу."

    path = path.strip().strip('"').strip("'")

    from commands.files import _find_path
    from commands.files import _read_file_content as _read
    from core.utils import _is_safe_path

    if os.path.isabs(path) and os.path.exists(path):
        if not _is_safe_path(path):
            return "⛔ Доступ запрещён (Path Traversal)."
        return _read(path)

    found = _find_path(path)
    if not found:
        return f"⚠️ Файл '{path}' не найден."

    if not _is_safe_path(found):
        return "⛔ Доступ запрещён."

    return _read(found)


# ===== 2. OPEN APP =====
def open_app(name: str) -> str:
    """Запускает приложение. Пробует which, snap, flatpak."""
    name = name.strip().lower()

    apps = {
        "steam": ["steam", "/snap/bin/steam", "flatpak run com.valvesoftware.Steam"],
        "firefox": ["firefox", "/snap/bin/firefox"],
        "браузер": ["firefox", "google-chrome", "chromium-browser"],
        "chrome": ["google-chrome", "google-chrome-stable", "/snap/bin/chromium"],
        "код": ["code", "codium", "code-insiders"],
        "vscode": ["code", "codium", "code-insiders"],
        "терминал": ["gnome-terminal", "konsole", "xterm", "alacritty"],
        "telegram": ["telegram-desktop", "/snap/bin/telegram-desktop"],
        "discord": ["discord", "/snap/bin/discord"],
        "spotify": ["spotify", "/snap/bin/spotify"],
        "vlc": ["vlc", "/snap/bin/vlc"],
    }

    candidates = apps.get(name, [name])

    for cmd in candidates:
        if " " in cmd:
            try:
                subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"🚀 Запустил: {name} ({cmd})"
            except Exception:
                _tlog.debug("пропущено в core/tools.py (строка 94)")
                continue
        else:
            found = shutil.which(cmd)
            if found:
                try:
                    subprocess.Popen([found], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return f"🚀 Запустил: {name}"
                except Exception as e:
                    return f"⚠️ Не удалось запустить {name}: {e}"

    return f"⚠️ Приложение '{name}' не найдено. Проверь название."


# ===== 3. SEARCH WEB =====
def search_web(query: str) -> str:
    """Открывает браузер с Google-поиском."""
    if not query or not query.strip():
        return "⚠️ Что искать?"
    from urllib.parse import quote
    url = f"https://www.google.com/search?q={quote(query)}"
    try:
        webbrowser.open(url)
        return f"🔍 Ищу: {query}"
    except Exception as e:
        return f"⚠️ Ошибка поиска: {e}"


# ===== 4. TAKE SCREENSHOT =====
def take_screenshot() -> str:
    """Делает скриншот (кроссплатформенно). Возвращает путь к файлу."""
    import time as _time
    ts = _time.strftime("%Y%m%d_%H%M%S")
    dest_dir = os.path.join("data", "screenshots", "senior")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"senior_{ts}.png")

    if _SYSTEM == "Linux":
        try:
            r = subprocess.run([
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell.Screenshot",
                "--object-path", "/org/gnome/Shell/Screenshot",
                "--method", "org.gnome.Shell.Screenshot.Screenshot",
                "false", "false", os.path.abspath(dest)
            ], capture_output=True, timeout=10)
            if r.returncode == 0 and os.path.exists(dest):
                return f"📸 Скриншот сохранён: {dest}"
        except Exception:
            _tlog.debug("screenshot fallback exhausted at this level")
        try:
            subprocess.run(["gnome-screenshot", "-f", dest], timeout=10)
            if os.path.exists(dest):
                return f"📸 Скриншот сохранён: {dest}"
        except Exception:
            _tlog.debug("screenshot fallback exhausted at this level")
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=dest)
            return f"📸 Скриншот сохранён: {dest}"
        except Exception:
            _tlog.debug("screenshot method unavailable — trying next fallback")

    elif _SYSTEM == "Windows":
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(dest)
            return f"📸 Скриншот сохранён: {dest}"
        except Exception:
            _tlog.debug("screenshot fallback exhausted at this level")
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=dest)
            return f"📸 Скриншот сохранён: {dest}"
        except Exception:
            _tlog.debug("screenshot method unavailable — trying next fallback")

    elif _SYSTEM == "Darwin":
        try:
            subprocess.run(["screencapture", "-x", dest], check=True, timeout=10)
            if os.path.exists(dest):
                return f"📸 Скриншот сохранён: {dest}"
        except Exception:
            _tlog.debug("screenshot method unavailable — trying next fallback")

    try:
        import mss
        with mss.mss() as sct:
            sct.shot(output=dest)
        return f"📸 Скриншот сохранён: {dest}"
    except Exception as e:
        return f"⚠️ Не удалось сделать скриншот: {e}"


# ===== 5. PLAY MUSIC =====
def play_music(mood: str = "нейтральное") -> str:
    """Открывает YouTube/YT Music с плейлистом по настроению."""
    mood = mood.strip().lower()
    urls = {
        "весёлое": "https://music.youtube.com/watch?v=ZbZSe6N_BXs",
        "грустное": "https://music.youtube.com/watch?v=5qap5aO4i9A",
        "спокойное": "https://music.youtube.com/watch?v=jfKfPfyJRdk",
        "сердитое": "https://music.youtube.com/watch?v=5yx6BWlEVcM",
        "усталое": "https://music.youtube.com/watch?v=DWcJFNfaw9c",
        "нейтральное": "https://music.youtube.com/watch?v=jfKfPfyJRdk",
        "энергичное": "https://music.youtube.com/watch?v=ZbZSe6N_BXs",
    }
    url = urls.get(mood, urls["нейтральное"])
    try:
        webbrowser.open(url)
        return f"🎵 Включаю музыку для настроения «{mood}»"
    except Exception as e:
        return f"⚠️ Ошибка: {e}"


# ===== 6. WINDOW CONTROL =====
def window_control(action: str = "", name: str = "") -> str:
    """Управляет окнами через GNOME Shell D-Bus (работает на Wayland).
    Закрытие и разворачивание по имени на Wayland не делаем через Eval — это небезопасно."""
    from core import linux_env

    action = action.strip().lower()
    name = name.strip()

    if _SYSTEM != "Linux":
        return "⚠️ Управление окнами доступно только на Linux."

    if action in ("switch", "focus"):
        if not name:
            return "⚠️ Укажи название окна."
        if linux_env.focus_window_by_title(name):
            return f"🪟 Переключился на «{name}»"
        if linux_env.is_wayland():
            _tlog.warning("switch «%s»: GNOME Shell Eval недоступен или окно не найдено", name)
            return "⚠️ Не удалось переключить окно. Управление окнами на Wayland работает через GNOME Shell (проверь, что окно открыто)."
        return f"⚠️ Окно «{name}» не найдено."

    if action == "close":
        if not name:
            return "⚠️ Укажи название окна."
        _tlog.warning("close «%s»: не поддерживается на Wayland", name)
        return "⚠️ Закрытие окна по имени не поддерживается на Wayland. Закрой его вручную."

    if action in ("minimize_all", "show_desktop"):
        # Super+D через ydotool (если ввод доступен)
        reason = linux_env.input_unavailable_reason()
        if reason is None:
            _safe_run(["ydotool", "key", "125:1", "32:1", "32:0", "125:0"])
            return "🖥️ Все окна свёрнуты."
        _tlog.warning("show_desktop: ввод недоступен — %s", reason)
        return f"⚠️ {reason}"

    if action == "maximize":
        if not name:
            return "⚠️ Укажи название окна."
        _tlog.warning("maximize «%s»: не поддерживается на Wayland", name)
        return "⚠️ Разворачивание окна по имени не поддерживается на Wayland. Разверни его вручную."

    return f"⚠️ Неизвестное действие: {action}."


# ===== 7. WRITE FILE =====
def write_file(path: str, content: str) -> str:
    """Записывает текст в файл с защитой от Path Traversal."""
    if not path or not path.strip():
        return "⚠️ Укажи путь к файлу."
    path = path.strip().strip('"').strip("'")

    from core.utils import _is_safe_path

    if not _is_safe_path(path):
        return "⛔ Доступ запрещён: нельзя писать в системные директории."

    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ Записано: {path} ({len(content)} байт)"
    except Exception as e:
        return f"⚠️ Ошибка записи: {e}"


# ===== 8. GENERATE CODE =====
def generate_code(prompt: str, language: str = "python") -> str:
    """Генерирует код через API. Возвращает чистый код."""
    if not prompt or not prompt.strip():
        return "⚠️ Укажи, какой код нужен."

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY", "")
    if not api_key:
        return "⚠️ Нет API_KEY — генерация кода недоступна."

    try:
        from openai import OpenAI
        base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("API_URL", "https://api.provod.ai/v1")
        client = OpenAI(api_key=api_key, base_url=base_url)

        resp = client.chat.completions.create(
            model="deepseek/deepseek-v4.1-flash",
            messages=[{
                "role": "user",
                "content": f"Напиши код на {language}: {prompt}. Ответь ТОЛЬКО кодом, без объяснений и markdown."
            }],
            max_tokens=4000,
            temperature=0.3,
            timeout=300,
        )
        code = resp.choices[0].message.content or ""
        code = re.sub(r'^```\w*\n', '', code.strip())
        code = re.sub(r'\n```$', '', code)
        return code.strip()
    except Exception as e:
        return f"⚠️ Ошибка генерации кода: {e}"


# ===== 9. REWRITE FILE =====
def rewrite_file(path: str, language: str) -> str:
    """Читает файл, переписывает на другой язык через API, сохраняет."""
    if not path or not path.strip():
        return "⚠️ Укажи путь к файлу."
    path = path.strip().strip('"').strip("'")

    allowed = {".py", ".js", ".rs", ".txt", ".md"}
    ext = os.path.splitext(path)[1].lower()
    if ext not in allowed:
        return f"⚠️ Перезапись файлов {ext} не поддерживается. Разрешены: {', '.join(allowed)}"

    content = read_file(path)
    if content.startswith("⚠️") or content.startswith("⛔"):
        return f"❌ Не удалось прочитать: {content}"

    lang_ext = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "rust": ".rs", "rs": ".rs",
        "text": ".txt", "txt": ".txt",
        "markdown": ".md", "md": ".md",
    }
    new_ext = lang_ext.get(language.lower(), f".{language}")
    new_code = generate_code(f"Перепиши этот код на {language}:\n{content}", language)
    if new_code.startswith("⚠️"):
        return new_code

    base = os.path.splitext(path)[0]
    new_path = f"{base}{new_ext}"
    result = write_file(new_path, new_code)
    if result.startswith("✅"):
        return f"✅ Файл переписан на {language}: {new_path}"
    return result


# ===== 10. RUN COMMAND =====
_SAFE_COMMANDS = frozenset({"ls", "pwd", "echo", "cat", "grep", "whoami", "date", "uptime",
                            "uname", "df", "du", "head", "tail", "wc", "sort", "uniq"})


def run_command(cmd: str) -> str:
    """Выполняет безопасную команду из белого списка. Без shell: операторы и подстановки
    не интерпретируются, а вся строка разбивается на аргументы."""
    if not cmd or not cmd.strip():
        return "⚠️ Укажи команду."

    try:
        argv = shlex.split(cmd.strip())
    except ValueError as e:
        return f"⛔ Некорректная команда: {e}"
    if not argv:
        return "⚠️ Укажи команду."

    program = argv[0]
    if program not in _SAFE_COMMANDS:
        return f"⛔ Команда '{program}' не разрешена. Доступны: {', '.join(sorted(_SAFE_COMMANDS))}"

    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return f"⚠️ Программа '{program}' не найдена."
    except subprocess.TimeoutExpired:
        return "⚠️ Команда выполнялась дольше 10 сек и была прервана."
    except Exception as e:
        return f"⚠️ Ошибка выполнения: {e}"

    out = r.stdout.strip()
    err = r.stderr.strip()
    if r.returncode == 0:
        return out if out else "(пустой вывод)"
    return f"⚠️ Ошибка ({r.returncode}): {err or out}"


# ============================================================
# ИНСТРУМЕНТЫ ПОЛНОГО ДОСТУПА (1.6.2)
# ============================================================

def _run_argv(argv: list, timeout: int) -> str:
    """Запуск без оболочки: операторы и подстановки не интерпретируются."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return f"⚠️ Программа '{argv[0]}' не найдена."
    except subprocess.TimeoutExpired:
        return f"⚠️ Команда выполнялась дольше {timeout} сек и была прервана."
    except Exception as e:
        return f"⚠️ Ошибка выполнения: {e}"
    out = r.stdout.strip()
    err = r.stderr.strip()
    if r.returncode == 0:
        return out if out else "(пустой вывод)"
    return f"⚠️ Ошибка ({r.returncode}): {err or out}"


def run_command_full(cmd: str) -> str:
    """Выполняет любую программу с аргументами (без оболочки). Требует подтверждения!"""
    if not cmd or not cmd.strip():
        return "⚠️ Укажи команду."
    try:
        argv = shlex.split(cmd.strip())
    except ValueError as e:
        return f"⛔ Некорректная команда: {e}"
    return _run_argv(argv, 15)


def sudo_command(cmd: str) -> str:
    """Выполняет программу с sudo (без оболочки, без интерактивного пароля). Требует подтверждения!"""
    if not cmd or not cmd.strip():
        return "⚠️ Укажи команду."
    try:
        argv = shlex.split(cmd.strip())
    except ValueError as e:
        return f"⛔ Некорректная команда: {e}"
    return _run_argv(["sudo", "-n"] + argv, 30)


def kill_process(pid: str) -> str:
    """Убивает процесс по PID/имени. Требует подтверждения!"""
    if not pid:
        return "⚠️ Укажи PID или имя процесса."
    pid = pid.strip()
    try:
        if _SYSTEM == "Windows":
            r = subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True, text=True, timeout=10)
        else:
            r = subprocess.run(["kill", "-9", pid],
                               capture_output=True, text=True, timeout=10)
        out = r.stdout.strip()
        err = r.stderr.strip()
        if r.returncode == 0:
            return f"✅ Процесс {pid} завершён." + (f"\n{out}" if out else "")
        return f"⚠️ Ошибка завершения процесса {pid}: {err or out}"
    except Exception as e:
        return f"⚠️ Ошибка: {e}"


def system_info() -> str:
    """Системная информация (CPU, RAM, диски). Без подтверждения."""
    import platform as _plat
    parts = [f"🖥 Система: {_plat.system()} {_plat.release()}",
             f"🔧 Архитектура: {_plat.machine()}",
             f"🐍 Python: {_plat.python_version()}"]
    try:
        import psutil
        parts.append(f"🧠 CPU: {psutil.cpu_percent(interval=0.5)}% "
                     f"({psutil.cpu_count(logical=True)} логических ядер)")
        mem = psutil.virtual_memory()
        parts.append(f"📊 RAM: {mem.percent}% "
                     f"({mem.used // (1024**2)} / {mem.total // (1024**2)} МБ)")
        disk = psutil.disk_usage("/")
        parts.append(f"💾 Диск: {disk.percent}% "
                     f"({disk.free // (1024**3)} ГБ свободно из {disk.total // (1024**3)} ГБ)")
    except Exception:
        parts.append("⚠️ psutil не установлен — статистика недоступна.")
    return "\n".join(parts)


def network_info() -> str:
    """Сетевая информация (IP, шлюз, DNS). Без подтверждения."""
    import socket
    lines = []
    try:
        host = socket.gethostname()
        ip = socket.gethostbyname(host)
        lines.append(f"🌐 Хост: {host}")
        lines.append(f"📡 Локальный IP: {ip}")
    except Exception:
        lines.append("⚠️ Не удалось получить IP.")
    try:
        r = subprocess.run(["ip", "route", "show", "default"],
                           capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            lines.append(f"🚪 Шлюз: {r.stdout.strip().split()[2]}")
    except Exception:
        _tlog.debug("пропущено в core/tools.py (строка 487)")
    try:
        r = subprocess.run(["cat", "/etc/resolv.conf"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if line.startswith("nameserver"):
                lines.append(f"🔍 DNS: {line.split()[1]}")
                break
    except Exception:
        _tlog.debug("пропущено в core/tools.py (строка 496)")
    return "\n".join(lines)


def install_package(pkg: str) -> str:
    """Устанавливает пакет через apt. Требует подтверждения!"""
    if not pkg or not pkg.strip():
        return "⚠️ Укажи имя пакета."
    pkg = pkg.strip()
    try:
        r = subprocess.run(["sudo", "apt-get", "install", "-y", pkg],
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return f"✅ Пакет {pkg} установлен."
        return f"⚠️ Ошибка установки {pkg}: {r.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        return f"⚠️ Установка {pkg} заняла > 2 мин и была прервана."
    except Exception as e:
        return f"⚠️ Ошибка: {e}"


def _power_action(action: str) -> str:
    """Выключение/перезагрузка через systemd (logind). Возвращает честный результат.
    Без прав logind требует пароль через polkit — это видно по коду возврата, а не угадывается."""
    if _SYSTEM != "Linux":
        return f"⚠️ Питание: действие «{action}» пока только для Linux."
    try:
        r = subprocess.run(["systemctl", action], capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        return "⚠️ systemctl не найден."
    except subprocess.TimeoutExpired:
        return "⚠️ systemctl не ответил за 15 сек."
    if r.returncode == 0:
        return "🔄 Перезагрузка запущена." if action == "reboot" else "⏻ Выключение запущено."
    err = (r.stderr or r.stdout).strip()
    _tlog.warning("systemctl %s не выполнен (код %s): %s", action, r.returncode, err)
    return (f"⚠️ Нет прав. Запусти sudo systemctl {action}. "
            f"Детали: {err[:200]}")


def shutdown_pc() -> str:
    """Выключает ПК. Требует подтверждения!"""
    return _power_action("poweroff")


def reboot_pc() -> str:
    """Перезагружает ПК. Требует подтверждения!"""
    return _power_action("reboot")


def lock_screen() -> str:
    """Блокирует экран. Без подтверждения."""
    try:
        if _SYSTEM == "Windows":
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        elif _SYSTEM == "Linux":
            subprocess.Popen(["xdg-screensaver", "lock"])
        elif _SYSTEM == "Darwin":
            subprocess.Popen(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                              "-suspend"])
        return "🔒 Экран заблокирован."
    except Exception as e:
        return f"⚠️ Ошибка блокировки: {e}"


def click_at(x: str, y: str) -> str:
    """Клик мышью по координатам. Без подтверждения."""
    try:
        x, y = int(x), int(y)
        if _SYSTEM == "Windows":
            try:
                import pyautogui
                pyautogui.click(x, y)
                return f"🖱 Клик: ({x}, {y})"
            except Exception:
                _tlog.debug("пропущено в core/tools.py (строка 571)")
        if _SYSTEM == "Linux":
            from core import linux_env
            reason = linux_env.input_unavailable_reason()
            if reason:
                _tlog.warning("click_at: %s", reason)
                return f"⚠️ {reason}"
            ok, err = _ydotool(["mousemove", "-x", str(x), "-y", str(y)])
            if ok:
                ok, err = _ydotool(["click", "0xC0", "0x00"])
            if ok:
                return f"🖱 Клик через ydotool: ({x}, {y})"
            return f"⚠️ Клик не выполнен: {err}"
        return f"⚠️ Клик не поддерживается на {_SYSTEM}."
    except Exception as e:
        return f"⚠️ Ошибка клика: {e}"


def type_text(text: str) -> str:
    """Набирает текст (эмуляция клавиатуры). Без подтверждения."""
    if not text:
        return "⚠️ Укажи текст."
    try:
        if _SYSTEM == "Windows":
            import pyautogui
            pyautogui.write(text, interval=0.05)
            return f"⌨ Напечатано: «{text[:50]}...»" if len(text) > 50 else f"⌨ Напечатано: «{text}»"
        elif _SYSTEM == "Linux":
            from core import linux_env
            reason = linux_env.input_unavailable_reason()
            if reason:
                _tlog.warning("type_text: %s", reason)
                return f"⚠️ {reason}"
            ok, err = _ydotool(["type", text])
            if ok:
                return f"⌨ Напечатано через ydotool: «{text[:50]}»"
            return f"⚠️ Ввод текста не выполнен: {err}"
        return f"⚠️ Набор текста не поддерживается на {_SYSTEM}."
    except Exception as e:
        return f"⚠️ Ошибка ввода: {e}"


def press_key(key: str) -> str:
    """Нажимает клавишу. Без подтверждения."""
    if not key:
        return "⚠️ Укажи клавишу."
    try:
        if _SYSTEM == "Windows":
            import pyautogui
            pyautogui.press(key)
            return f"⌨ Клавиша '{key}' нажата."
        elif _SYSTEM == "Linux":
            from core import linux_env
            reason = linux_env.input_unavailable_reason()
            if reason:
                _tlog.warning("press_key: %s", reason)
                return f"⚠️ {reason}"
            ok, err = _ydotool(["key", key])
            if ok:
                return f"⌨ Клавиша '{key}' нажата через ydotool."
            return f"⚠️ Клавиша не нажата: {err}"
        return f"⚠️ Нажатие клавиш не поддерживается на {_SYSTEM}."
    except Exception as e:
        return f"⚠️ Ошибка: {e}"