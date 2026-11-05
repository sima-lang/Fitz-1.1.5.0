"""
os_layer.py — Кроссплатформенный слой (Windows / Linux / macOS).
Единственное место в ядре, где есть if is_windows().
"""
import os
import re
import subprocess
import shutil
import platform

from core.logger import get_logger

_log_os = get_logger("os_layer")

SYSTEM = platform.system()  # "Windows" / "Linux" / "Darwin"


def is_windows() -> bool:
    return SYSTEM == "Windows"


def is_linux() -> bool:
    return SYSTEM == "Linux"


def is_macos() -> bool:
    return SYSTEM == "Darwin"


# ============================================================
# ПОЛЬЗОВАТЕЛЬСКИЕ ПАПКИ
# ============================================================
def user_dir(name: str) -> str:
    name = name.upper()
    if is_linux():
        try:
            out = subprocess.run(
                ["xdg-user-dir", name],
                capture_output=True, text=True, timeout=2
            )
            if out.returncode == 0:
                path = out.stdout.strip()
                if path and os.path.isdir(path):
                    return path
        except Exception:
            _log_os.debug("пропущено в core/os_layer.py (строка 46)")
    mapping = {
        "DESKTOP": "~/Desktop",
        "DOWNLOAD": "~/Downloads",
        "DOCUMENTS": "~/Documents",
        "MUSIC": "~/Music",
        "PICTURES": "~/Pictures",
        "VIDEOS": "~/Videos",
    }
    return os.path.expanduser(mapping.get(name, "~"))


# ============================================================
# ОКНА
# ============================================================
def get_active_window_title():
    if is_windows():
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd) or None
        except Exception:
            return None
    if is_linux():
        try:
            from core import linux_env
            title = linux_env.focused_window_title()
            if title:
                return title
        except Exception as e:
            _log_os.warning("заголовок окна (GNOME): %s", e)
        return None
    if is_macos():
        try:
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first '
                 'application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2
            )
            return out.stdout.strip() or None
        except Exception:
            return None
    return None


def get_active_process_name():
    if is_windows():
        try:
            import win32gui, win32process, psutil
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name()
        except Exception:
            return None
    if is_linux():
        try:
            from core import linux_env
            return linux_env.focused_window_wm_class()
        except Exception:
            return None
    if is_macos():
        try:
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get unix id of first '
                 'application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2
            )
            if out.returncode == 0 and out.stdout.strip():
                import psutil
                return psutil.Process(int(out.stdout.strip())).name()
        except Exception:
            return None
    return None


def list_windows():
    if is_windows():
        try:
            import win32gui
            result = []
            def _cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if t:
                        result.append(t)
            win32gui.EnumWindows(_cb, None)
            return result
        except Exception:
            return []
    if is_linux():
        try:
            from core import linux_env
            return linux_env.list_window_titles()
        except Exception as e:
            _log_os.warning("список окон (GNOME): %s", e)
        return []
    if is_macos():
        try:
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process '
                 'whose background only is false'],
                capture_output=True, text=True, timeout=2
            )
            if out.returncode == 0:
                return [w.strip() for w in out.stdout.strip().split(",") if w.strip()]
        except Exception:
            _log_os.debug("пропущено в core/os_layer.py (строка 155)")
    return []


def find_window_by_title(substr: str) -> bool:
    if not substr:
        return False
    substr = substr.lower()
    return any(substr in w.lower() for w in list_windows())


def activate_window(substr: str) -> bool:
    if is_windows():
        try:
            import win32gui, win32con
            found = []
            def _cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if substr.lower() in t.lower():
                        found.append(hwnd)
            win32gui.EnumWindows(_cb, None)
            if found:
                win32gui.ShowWindow(found[0], win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(found[0])
                return True
        except Exception:
            return False
    if is_linux():
        try:
            from core import linux_env
            return linux_env.focus_window_by_title(substr)
        except Exception as e:
            _log_os.warning("активация окна (GNOME): %s", e)
            return False
    if is_macos():
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "{substr}" to activate'],
                capture_output=True, timeout=2
            )
            return True
        except Exception:
            return False
    return False


# ============================================================
# ОТКРЫТИЕ ФАЙЛОВ И URL
# ============================================================
def open_path(path: str) -> str:
    if not os.path.exists(path):
        return f"❌ Не найдено: {path}"
    try:
        if is_windows():
            os.startfile(path)  # noqa
        elif is_linux():
            subprocess.Popen(["xdg-open", path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        elif is_macos():
            subprocess.Popen(["open", path])
        return f"📁 Открываю: {path}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


def open_url(url: str) -> str:
    import webbrowser
    try:
        webbrowser.open(url)
        return f"🌐 Открываю: {url}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


# ============================================================
# ПИТАНИЕ
# ============================================================
def shutdown_pc(delay: int = 5) -> str:
    try:
        if is_linux():
            from core.tools import shutdown_pc as _linux_poweroff
            return _linux_poweroff()
        if is_windows():
            subprocess.run(["shutdown", "/s", "/t", str(delay)])
        elif is_macos():
            subprocess.run(["sudo", "shutdown", "-h", "+1"])
        return f"⏻ Выключение через ~{delay} сек"
    except Exception as e:
        return f"❌ Не удалось выключить: {e}"


def restart_pc(delay: int = 5) -> str:
    try:
        if is_linux():
            from core.tools import reboot_pc as _linux_reboot
            return _linux_reboot()
        if is_windows():
            subprocess.run(["shutdown", "/r", "/t", str(delay)])
        elif is_macos():
            subprocess.run(["sudo", "shutdown", "-r", "+1"])
        return f"🔄 Перезагрузка через ~{delay} сек"
    except Exception as e:
        return f"❌ Не удалось перезагрузить: {e}"


def cancel_shutdown() -> str:
    try:
        if is_windows():
            subprocess.run(["shutdown", "/a"])
        elif is_linux():
            return "ℹ️ Отложенного выключения нет: systemctl выполняет его сразу, отменять нечего."
        return "✅ Отменено"
    except Exception as e:
        return f"⚠️ {e}"


def lock_pc() -> str:
    try:
        if is_windows():
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "🔒 ПК заблокирован"
        if is_linux():
            try:
                r = subprocess.run(
                    ["gdbus", "call", "--session",
                     "--dest", "org.gnome.ScreenSaver",
                     "--object-path", "/org/gnome/ScreenSaver",
                     "--method", "org.gnome.ScreenSaver.Lock"],
                    capture_output=True, text=True, timeout=3,
                )
                if r.returncode == 0:
                    return "🔒 ПК заблокирован (GNOME D-Bus)"
            except Exception:
                _log_os.debug("пропущено в core/os_layer.py (строка 291)")
            for cmd in [
                ["loginctl", "lock-session"],
                ["xdg-screensaver", "lock"],
                ["dm-tool", "lock"],
                ["swaylock"],
            ]:
                if shutil.which(cmd[0]):
                    try:
                        subprocess.run(cmd, timeout=3,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                        return f"🔒 ПК заблокирован ({cmd[0]})"
                    except Exception:
                        _log_os.debug("пропущено в core/os_layer.py (строка 305)")
                        continue
            return "⚠️ Не удалось заблокировать"
        if is_macos():
            subprocess.run(["pmset", "displaysleepnow"])
            return "🔒 Экран заблокирован"
        return "⚠️ Не поддерживается"
    except Exception as e:
        return f"❌ Не удалось заблокировать: {e}"


# ============================================================
# КАМЕРА
# ============================================================
def get_camera_backend():
    import cv2
    if is_windows():
        return cv2.CAP_DSHOW
    if is_linux():
        return cv2.CAP_V4L2
    return cv2.CAP_ANY


# ============================================================
# МЕДИА И ГРОМКОСТЬ
# ============================================================
def _run_first(candidates):
    for c in candidates:
        if shutil.which(c[0]):
            try:
                subprocess.run(c, timeout=3,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                return True
            except Exception:
                _log_os.debug("пропущено в core/os_layer.py (строка 339)")
                continue
    return False


def _linux_mpris(action: str) -> bool:
    try:
        from core import linux_env
        return linux_env.mpris_command(action)
    except Exception as e:
        _log_os.warning("MPRIS %s: %s", action, e)
        return False


def media_play_pause() -> bool:
    if is_windows():
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
            return True
        except Exception:
            return False
    if is_linux():
        return _linux_mpris("play-pause")
    return False


def media_next() -> bool:
    if is_windows():
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0)
            return True
        except Exception:
            return False
    if is_linux():
        return _linux_mpris("next")
    return False


def media_prev() -> bool:
    if is_windows():
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0)
            return True
        except Exception:
            return False
    if is_linux():
        return _linux_mpris("previous")
    return False


def _linux_volume(delta: int) -> bool:
    try:
        from core import linux_env
        return linux_env.change_volume(delta)
    except Exception as e:
        _log_os.warning("громкость: %s", e)
        return False


def volume_up() -> bool:
    if is_windows():
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            return True
        except Exception:
            return False
    if is_linux():
        return _linux_volume(+5)
    return False


def volume_down() -> bool:
    if is_windows():
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
            return True
        except Exception:
            return False
    if is_linux():
        return _linux_volume(-5)
    return False


# ============================================================
# VS CODE
# ============================================================
def find_vscode():
    if is_windows():
        for p in (
            r"C:\Users\Admin\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ):
            if os.path.exists(p):
                return p
        return shutil.which("code")
    if is_linux():
        return shutil.which("code") or shutil.which("code-insiders")
    if is_macos():
        p = "/Applications/Visual Studio Code.app/Contents/MacOS/Electron"
        return p if os.path.exists(p) else shutil.which("code")
    return None


# ============================================================
# АВТОЗАГРУЗКА
# ============================================================
_SAFE_STARTUP_NAME = re.compile(r"^[A-Za-zА-Яа-яЁё0-9 _.\-]{1,64}$")


def _check_startup_name(name: str) -> str | None:
    """Возвращает текст ошибки или None. Имя попадает в путь файла, поэтому без / и .."""
    if not _SAFE_STARTUP_NAME.match(name or "") or ".." in name:
        return "⚠️ Недопустимое имя для автозагрузки (буквы, цифры, пробел, - _ .)"
    return None


def add_to_startup(name: str, command: str) -> str:
    try:
        err = _check_startup_name(name)
        if err:
            return err
        if "\n" in command or "\r" in command:
            return "⚠️ Команда автозагрузки не может содержать переводов строки"
        if is_windows():
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return f"✅ Добавлено в автозагрузку: {name}"
        if is_linux():
            autostart = os.path.expanduser("~/.config/autostart")
            os.makedirs(autostart, exist_ok=True)
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={name}\n"
                f"Exec={command}\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            with open(os.path.join(autostart, f"{name}.desktop"),
                      "w", encoding="utf-8") as f:
                f.write(content)
            return f"✅ Автозагрузка: {name}"
        return "⚠️ Не поддерживается"
    except Exception as e:
        return f"❌ Ошибка: {e}"


def remove_from_startup(name: str) -> str:
    try:
        err = _check_startup_name(name)
        if err:
            return err
        if is_windows():
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.DeleteValue(key, name)
            winreg.CloseKey(key)
            return "🗑️ Удалено из автозагрузки"
        if is_linux():
            p = os.path.expanduser(f"~/.config/autostart/{name}.desktop")
            if os.path.exists(p):
                os.remove(p)
                return "🗑️ Удалено из автозагрузки"
            return "⚠️ Не найдено в автозагрузке"
        return "⚠️ Не поддерживается"
    except Exception as e:
        return f"❌ Ошибка: {e}"


# ============================================================
# ПРАВА АДМИНА
# ============================================================
def is_admin() -> bool:
    if is_windows():
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    if is_linux() or is_macos():
        try:
            return os.geteuid() == 0
        except Exception:
            return False
    return False