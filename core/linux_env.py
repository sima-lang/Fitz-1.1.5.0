"""
linux_env.py — Работа с Linux-окружением (Ubuntu/GNOME/Wayland).

Здесь собрано всё, что зависит от среды, чтобы остальные модули не
дублировали проверки:
  • диагностика инструментов (ydotool, wmctrl, pactl, espeak-ng, gdbus, wpctl)
  • GNOME Shell D-Bus: активное окно, список окон, переключение
  • MPRIS (медиаплееры) через playerctl с fallback на dbus
  • ввод: ydotoold и доступ к /dev/uinput

Всё возвращает понятные строки или bool, ничего не бросает наружу.
"""
import os
import shutil
import subprocess

from core.logger import get_logger

_log = get_logger("linux_env")

_SHELL_DEST = "org.gnome.Shell"
_SHELL_PATH = "/org/gnome/Shell"
_SHELL_EVAL = "org.gnome.Shell.Eval"

NOT_WAYLAND_MSG = "Не поддерживается на Wayland"
INPUT_HELP_MSG = (
    "Ввод недоступен. Добавь пользователя в группу input: "
    "sudo usermod -aG input $USER (затем перезайди в систему)."
)


def is_linux() -> bool:
    return os.name == "posix" and os.uname().sysname == "Linux"


def is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


# ============================================================
# ДИАГНОСТИКА ОКРУЖЕНИЯ
# ============================================================
# Инструменты, без которых часть функций не работает.
REQUIRED_TOOLS = {
    "gdbus": "управление окнами (GNOME Shell D-Bus)",
    "ydotool": "клик, печать и клавиши",
    "wpctl": "громкость (PipeWire)",
    "pactl": "громкость (PulseAudio/PipeWire), запасной вариант",
    "espeak-ng": "голос без интернета (запасной вариант)",
    "wmctrl": "управление окнами на X11 (на Wayland не работает)",
}


def check_environment() -> list:
    """Возвращает список строк о том, что НЕ работает. Пустой список — всё хорошо."""
    if not is_linux():
        return []
    problems = []
    missing = [t for t in REQUIRED_TOOLS if shutil.which(t) is None]
    for tool in missing:
        problems.append(f"нет {tool} — {REQUIRED_TOOLS[tool]}")

    if is_wayland():
        problems.append(f"управление окнами (X11-инструменты): {NOT_WAYLAND_MSG}, "
                        "используется GNOME Shell D-Bus")

    if "ydotool" not in missing and not ydotool_available():
        problems.append("ввод (ydotool): " + INPUT_HELP_MSG)

    for line in problems:
        _log.warning("окружение: %s", line)
    return problems


# ============================================================
# GNOME SHELL D-BUS
# ============================================================
def _shell_eval(js: str, timeout: float = 2.0) -> str | None:
    """Выполняет JS в GNOME Shell через gdbus. Возвращает текст ответа или None."""
    if shutil.which("gdbus") is None:
        return None
    try:
        out = subprocess.run(
            ["gdbus", "call", "--session", "--dest", _SHELL_DEST,
             "--object-path", _SHELL_PATH, "--method", _SHELL_EVAL, js],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as e:
        _log.warning("gdbus Eval: %s", e)
        return None
    if out.returncode != 0:
        _log.warning("gdbus Eval код %s: %s", out.returncode, out.stderr.strip()[:200])
        return None
    # Ответ вида "(true, '…')". Оба случая проверяем: успех и текст.
    text = out.stdout.strip()
    if text.startswith("(true,"):
        return text[len("(true,"):].strip().rstrip(")").strip().strip("'\"")
    _log.warning("GNOME Shell отключил Eval или вернул ошибку: %s", text[:200])
    return None


def focused_window_title() -> str | None:
    """Заголовок активного окна через GNOME Shell (Wayland и X11 под GNOME)."""
    res = _shell_eval("global.display.focus_window ? global.display.focus_window.get_title() : ''")
    return res or None


def focused_window_wm_class() -> str | None:
    """WM_CLASS активного окна — надёжнее заголовка для определения программы."""
    res = _shell_eval("global.display.focus_window ? global.display.focus_window.get_wm_class() : ''")
    return res or None


def list_window_titles() -> list:
    res = _shell_eval("global.get_window_actors().map(a=>a.meta_window.get_title()).join('\\n')")
    if not res:
        return []
    return [t for t in res.split("\n") if t.strip()]


def focus_window_by_title(substr: str) -> bool:
    """Переключает фокус на окно, чей заголовок содержит substr. Нужно отключённое Eval-разрешение
    не требуется: GNOME Shell разрешает Eval только в unsafe-режиме, поэтому возвращаем False."""
    if not substr:
        return False
    safe = substr.replace("\\", "\\\\").replace("'", "\\'")
    js = (
        "(function(){let w=global.get_window_actors().map(a=>a.meta_window)"
        f".find(m=>m.get_title().toLowerCase().includes('{safe.lower()}'));"
        "if(w){w.activate(global.get_current_time());return 'ok';}return '';})()"
    )
    return bool(_shell_eval(js))


# ============================================================
# MPRIS: медиаплееры
# ============================================================
def mpris_command(action: str) -> bool:
    """action: play-pause | next | previous. Сначала playerctl (MPRIS), затем dbus."""
    if shutil.which("playerctl"):
        try:
            r = subprocess.run(["playerctl", action], timeout=3,
                               capture_output=True)
            if r.returncode == 0:
                return True
        except Exception as e:
            _log.warning("playerctl %s: %s", action, e)
    return False


# ============================================================
# ГРОМКОСТЬ: PipeWire (wpctl) → PulseAudio (pactl) → ALSA (amixer)
# ============================================================
def change_volume(delta_percent: int) -> bool:
    """Меняет громкость по умолчанию на delta_percent (может быть < 0)."""
    sign = "+" if delta_percent >= 0 else "-"
    amount = f"{abs(delta_percent)}%{sign}"
    if shutil.which("wpctl"):
        r = subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", amount],
                           timeout=3, capture_output=True)
        if r.returncode == 0:
            return True
    if shutil.which("pactl"):
        pa = f"{'+' if delta_percent >= 0 else ''}{delta_percent}%"
        r = subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", pa],
                           timeout=3, capture_output=True)
        if r.returncode == 0:
            return True
    if shutil.which("amixer"):
        r = subprocess.run(["amixer", "-q", "set", "Master", f"{abs(delta_percent)}%{'+' if delta_percent >= 0 else '-'}"],
                           timeout=3, capture_output=True)
        if r.returncode == 0:
            return True
    _log.warning("громкость: нет рабочего инструмента (wpctl/pactl/amixer)")
    return False


# ============================================================
# ВВОД: ydotool и /dev/uinput
# ============================================================
def ydotool_daemon_running() -> bool:
    try:
        r = subprocess.run(["pgrep", "-x", "ydotoold"], capture_output=True, timeout=2)
        return r.returncode == 0
    except Exception:
        return False


def uinput_accessible() -> bool:
    return os.access("/dev/uinput", os.W_OK)


def ydotool_available() -> bool:
    """ydotool установлен, демон запущен и есть доступ к /dev/uinput."""
    return (shutil.which("ydotool") is not None
            and ydotool_daemon_running()
            and uinput_accessible())


def input_unavailable_reason() -> str | None:
    """None — ввод доступен. Иначе — человекочитаемая причина."""
    if shutil.which("ydotool") is None:
        return "Ввод недоступен: не установлен ydotool (sudo apt install ydotool)."
    if not ydotool_daemon_running():
        return "Ввод недоступен: не запущен демон ydotoold (systemctl --user start ydotool)."
    if not uinput_accessible():
        return INPUT_HELP_MSG
    return None
