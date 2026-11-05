"""
apps.py — Открытие приложений и сайтов.
Кроссплатформенно: Linux (xdg-open, subprocess), Windows (os.startfile, subprocess), macOS (open).
Браузер: приоритет Firefox → Chrome → Opera → Chromium → Edge.
Все дочерние процессы запускаются с DEVNULL, чтобы не спамили в консоль.
"""
import os
import shutil
import subprocess
import webbrowser

from core import os_layer


# ============================================================
# ПОИСК БРАУЗЕРА
# ============================================================
_BROWSER_CACHE = {"path": None}


def _find_browser():
    if _BROWSER_CACHE["path"] is not None:
        return _BROWSER_CACHE["path"]

    if os_layer.is_windows():
        candidates = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\Admin\AppData\Local\Programs\Opera\opera.exe",
            r"C:\Program Files\Opera\opera.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                _BROWSER_CACHE["path"] = c
                return c
        for name in ("firefox", "chrome", "opera", "msedge"):
            p = shutil.which(name)
            if p:
                _BROWSER_CACHE["path"] = p
                return p

    elif os_layer.is_linux():
        for name in ("firefox", "google-chrome", "google-chrome-stable",
                     "chromium", "chromium-browser", "opera"):
            p = shutil.which(name)
            if p:
                _BROWSER_CACHE["path"] = p
                return p

    elif os_layer.is_macos():
        candidates = [
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Opera.app/Contents/MacOS/Opera",
        ]
        for c in candidates:
            if os.path.exists(c):
                _BROWSER_CACHE["path"] = c
                return c

    return None


def _spawn(cmd):
    """Запускает процесс без спама в консоль."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _open_url_in_browser(url: str) -> str:
    browser = _find_browser()
    if browser:
        if _spawn([browser, url]):
            name = os.path.basename(browser)
            return f"🌐 Открываю в {name}: {url}"
    try:
        webbrowser.open(url)
        return f"🌐 Открываю: {url}"
    except Exception as e:
        return f"❌ Не удалось открыть: {e}"


# ============================================================
# ПРИЛОЖЕНИЯ
# ============================================================
def _open_app(name: str):
    if name in ("терминал", "terminal", "консоль"):
        if os_layer.is_windows():
            _spawn(["cmd"])
            return "💻 Открываю cmd"
        for term in ("gnome-terminal", "konsole", "xterm", "kitty",
                     "alacritty", "terminator"):
            p = shutil.which(term)
            if p:
                _spawn([p])
                return f"💻 Открываю {term}"
        return "❌ Терминал не найден"

    if name in ("код", "code", "vscode", "vs code"):
        vscode = os_layer.find_vscode()
        if vscode:
            _spawn([vscode])
            return "📝 Открываю VS Code"
        return "❌ VS Code не найден"

    if name in ("файлы", "файловый менеджер", "проводник"):
        if os_layer.is_windows():
            _spawn(["explorer"])
            return "📁 Открываю Проводник"
        for fm in ("nautilus", "dolphin", "thunar", "pcmanfm", "nemo", "caja"):
            p = shutil.which(fm)
            if p:
                _spawn([p])
                return f"📁 Открываю {fm}"
        return "❌ Файловый менеджер не найден"

    if name in ("калькулятор", "calc"):
        if os_layer.is_windows():
            _spawn(["calc"])
            return "🧮 Открываю калькулятор"
        for c in ("gnome-calculator", "kcalc", "galculator", "xcalc"):
            p = shutil.which(c)
            if p:
                _spawn([p])
                return f"🧮 Открываю {c}"
        return "❌ Калькулятор не найден"

    return None


# ============================================================
# САЙТЫ
# ============================================================
_SITES = {
    "ютуб": "https://youtube.com",
    "youtube": "https://youtube.com",
    "гугл": "https://google.com",
    "google": "https://google.com",
    "гитхаб": "https://github.com",
    "github": "https://github.com",
    "вк": "https://vk.com",
    "vk": "https://vk.com",
    "телеграм": "https://web.telegram.org",
    "telegram": "https://web.telegram.org",
    "яндекс": "https://yandex.ru",
    "yandex": "https://yandex.ru",
    "почта": "https://mail.google.com",
    "gmail": "https://mail.google.com",
    "карты": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "википедия": "https://ru.wikipedia.org",
    "wiki": "https://ru.wikipedia.org",
    "погода": "https://wttr.in",
    "discord": "https://discord.com/app",
    "дискорд": "https://discord.com/app",
}


def handle(text, memory, core):
    low = text.lower().strip()

    if low in ("открой браузер", "открой интернет", "браузер", "browser"):
        browser = _find_browser()
        if browser:
            if _spawn([browser]):
                return f"🌐 Открываю браузер: {os.path.basename(browser)}"
            return "❌ Не удалось открыть браузер"
        return "❌ Браузер не найден"

    if low.startswith("открой "):
        target = text[7:].strip().lower()

        if target in _SITES:
            return _open_url_in_browser(_SITES[target])

        if target.startswith(("http://", "https://")) or "." in target:
            if not target.startswith("http"):
                target = "https://" + target
            return _open_url_in_browser(target)

        app_result = _open_app(target)
        if app_result:
            return app_result

    if low in ("открой код", "открой vs code", "открой вскод", "код"):
        r = _open_app("код")
        if r:
            return r

    if low in ("открой терминал", "терминал", "открой консоль"):
        r = _open_app("терминал")
        if r:
            return r

    if low in ("открой калькулятор", "калькулятор"):
        r = _open_app("калькулятор")
        if r:
            return r

    if low in ("открой файлы", "открой проводник", "файловый менеджер"):
        r = _open_app("файлы")
        if r:
            return r

    return None