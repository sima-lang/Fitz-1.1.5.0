"""
files.py — Открыть файл/URL/приложение / найти файл / проверить код.
С защитой от Path Traversal (доступ только к разрешённым директориям).
"""
import os
import re
import webbrowser
import shutil
import subprocess
from core import os_layer
from core.logger import get_logger

TEXT_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".log", ".csv", ".xml", ".html", ".css",
    ".js", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".toml", ".sql",
    ".sh", ".bat", ".ps1", ".php", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".swift", ".kt", ".rb", ".pl", ".lua", ".r",
    ".m", ".mm", ".env", ".gitignore", ".dockerfile", ".makefile",
}

MEDIA_EXTENSIONS = {
    ".mp4", ".mp3", ".avi", ".mkv", ".mov", ".wav", ".flac",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

DOMAIN_ZONES = {
    ".com", ".ru", ".org", ".net", ".io", ".ai", ".dev", ".app",
    ".me", ".tv", ".co", ".uk", ".de", ".fr", ".jp", ".cn",
    ".info", ".biz", ".edu", ".gov", ".mil", ".int", ".xyz",
    ".online", ".site", ".store", ".tech", ".space", ".website",
}

# ===== ИЗВЕСТНЫЕ ПРИЛОЖЕНИЯ =====
KNOWN_APPS = {
    "steam": "steam",
    "браузер": "firefox",
    "firefox": "firefox",
    "chrome": "google-chrome",
    "код": "code",
    "vscode": "code",
    "терминал": "gnome-terminal",
    "telegram": "telegram-desktop",
    "discord": "discord",
    "музыка": "rhythmbox",
    "видео": "vlc",
}

# ===== ЗАЩИТА ОТ PATH TRAVERSAL (вынесено в core/utils.py) =====
from core.utils import _is_safe_path
_log = get_logger("files")


def _block_unsafe_path(path: str) -> bool:
    """Быстрая проверка: не начинается ли путь с / (абсолютный системный)."""
    abs_path = os.path.abspath(path)
    safe = _is_safe_path(abs_path)
    if not safe:
        print(f"⛔ Доступ запрещён (Path Traversal): {path}")
    return not safe


def _is_url(text: str) -> bool:
    if re.search(r"https?://", text, re.IGNORECASE):
        return True
    if re.search(r"\bwww\.", text, re.IGNORECASE):
        return True
    for zone in DOMAIN_ZONES:
        if zone in text.lower():
            return True
    return False


def _is_text_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in TEXT_EXTENSIONS


def _is_media_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in MEDIA_EXTENSIONS


def _read_file_content(path: str, max_size: int = 50000) -> str:
    try:
        size = os.path.getsize(path)
        if size > max_size:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(max_size)
            return content + f"\n\n... [файл обрезан, всего {size} байт]"
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"⚠️ Ошибка чтения: {e}"


def _open_in_editor(path: str) -> str:
    """Открывает файл ТОЛЬКО в редакторе."""
    # 1. VS Code
    code_cmd = shutil.which("code") or shutil.which("codium") or shutil.which("code-insiders")
    if code_cmd:
        try:
            subprocess.Popen([code_cmd, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"📝 Открыл в VS Code: {os.path.basename(path)}"
        except Exception:
            _log.debug("пропущено в commands/files.py (строка 104)")
    # 2. gnome-text-editor
    gte_cmd = shutil.which("gnome-text-editor")
    if gte_cmd:
        try:
            subprocess.Popen([gte_cmd, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"📝 Открыл в GNOME Text Editor: {os.path.basename(path)}"
        except Exception:
            _log.debug("пропущено в commands/files.py (строка 112)")
    # 3. gedit / kate / mousepad
    for editor in ["gedit", "kate", "mousepad", "pluma", "leafpad"]:
        editor_cmd = shutil.which(editor)
        if editor_cmd:
            try:
                subprocess.Popen([editor_cmd, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"📝 Открыл в {editor}: {os.path.basename(path)}"
            except Exception:
                _log.debug("пропущено в commands/files.py (строка 121)")
    # 4. Fallback
    return os_layer.open_path(path)


def _open_in_browser(url: str) -> str:
    try:
        webbrowser.open(url)
        return f"🌐 Открыл в браузере: {url}"
    except Exception as e:
        return f"⚠️ Ошибка открытия в браузере: {e}"


def _find_path(target: str) -> str | None:
    """Ищет файл по имени, НЕ выходя за пределы разрешённых директорий."""
    target = target.strip().strip('"').strip("'")
    if not target:
        return None

    # 1. Прямой путь — только если безопасен
    if os.path.exists(target):
        if _is_safe_path(target):
            return target
        else:
            print(f"⛔ Отказано в доступе: {target}")
            return None

    # 2. Абсолютный путь
    try:
        abs_path = os.path.abspath(target)
        if os.path.exists(abs_path) and _is_safe_path(abs_path):
            return abs_path
    except Exception:
        _log.debug("пропущено в commands/files.py (строка 154)")

    # 3. Путь относительно домашней директории
    try:
        home_path = os.path.join(os.path.expanduser("~"), target)
        if os.path.exists(home_path) and _is_safe_path(home_path):
            return home_path
    except Exception:
        _log.debug("пропущено в commands/files.py (строка 162)")

    # 4. Путь относительно корня проекта
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        proj_path = os.path.join(project_root, target)
        if os.path.exists(proj_path) and _is_safe_path(proj_path):
            return proj_path
    except Exception:
        _log.debug("пропущено в commands/files.py (строка 171)")

    # 5. Рекурсивный поиск только в домашней директории
    base = os.path.expanduser("~")
    try:
        for root, dirs, files in os.walk(base):
            # Пропускаем скрытые папки (безопасность + скорость)
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in dirs + files:
                if target.lower() in name.lower():
                    candidate = os.path.join(root, name)
                    if _is_safe_path(candidate):
                        return candidate
    except (PermissionError, OSError):
        pass

    return None


def _clean_target(target: str) -> str:
    target = re.sub(r"\bв\s+(vs\s*code|vs\s*код|вс\s*код|vscode|vsc|редакторе|блокноте)\b", "", target, flags=re.IGNORECASE).strip()
    target = re.sub(r"^(фитц|это|файл)\s+", "", target, flags=re.IGNORECASE).strip()
    target = re.sub(r"\bв\s+(браузере|ссылку|url|сайт)\b", "", target, flags=re.IGNORECASE).strip()
    return target


def handle(text, memory, core):
    low = text.lower().strip()

    # ===== ПРОВЕРЬ КОД / ПРОВЕРЬ ФАЙЛ =====
    if "проверь код " in low or "проверь файл " in low:
        match = re.search(r"проверь (?:код|файл)\s+(.+)", text, re.IGNORECASE)
        if not match:
            return "Что проверить? Укажи путь к файлу."
        path = match.group(1).strip()

        found = _find_path(path)
        if not found:
            return f"⚠️ Файл '{path}' не найден или доступ запрещён."

        # Дополнительная проверка безопасности перед чтением
        if not _is_safe_path(found):
            return f"⛔ Доступ к файлу '{path}' запрещён."

        try:
            content = _read_file_content(found, max_size=50000)
            if not content.strip():
                return f"⚠️ Файл '{found}' пустой."

            prompt = (
                f"Проанализируй этот код и скажи, есть ли в нём ошибки или что можно улучшить:\n"
                f"```\n{content}\n```\n"
                f"Ответь кратко: что не так и как исправить. НЕ выводи код в ответе."
            )
            result = core.ask(prompt)
            return f"🔍 Проверка '{found}':\n{result}"
        except Exception as e:
            return f"⚠️ Ошибка при чтении файла: {e}"

    # ===== ОТКРОЙ ... =====
    if "открой " in low:
        match = re.search(r"открой\s+(.+)", text, re.IGNORECASE)
        if not match:
            return "Что открыть?"
        raw_target = match.group(1).strip()
        target = _clean_target(raw_target).lower()

        # 1. Проверяем, не приложение ли это
        if target in KNOWN_APPS:
            app_cmd = KNOWN_APPS[target]
            try:
                subprocess.Popen([app_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"🚀 Запускаю приложение: {target}"
            except Exception as e:
                return f"⚠️ Не удалось запустить {target}: {e}"

        # 2. Если это URL — открываем в браузере
        if _is_url(raw_target):
            url_match = re.search(r"(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", raw_target)
            if url_match:
                url = url_match.group(1)
                if not url.startswith("http"):
                    url = "https://" + url
                return _open_in_browser(url)
            return "⚠️ Не нашёл ссылку для открытия в браузере."

        # 3. Ищем файл
        found = _find_path(target)
        if not found:
            # Может это папка из словаря?
            folders = {
                "загрузки": "DOWNLOAD", "downloads": "DOWNLOAD",
                "рабочий стол": "DESKTOP", "desktop": "DESKTOP",
                "документы": "DOCUMENTS", "documents": "DOCUMENTS",
                "музыка": "MUSIC", "music": "MUSIC",
                "картинки": "PICTURES", "pictures": "PICTURES", "изображения": "PICTURES",
                "видео": "VIDEOS", "videos": "VIDEOS",
                "домашняя": "HOME", "home": "HOME",
            }
            key = target.lower()
            if key in folders:
                xdg_name = folders[key]
                path = os.path.expanduser("~") if xdg_name == "HOME" else os_layer.user_dir(xdg_name)
                return os_layer.open_path(path)
            return f"❌ Файл '{target}' не найден."

        # 4. Проверка безопасности перед открытием
        if not _is_safe_path(found):
            return f"⛔ Доступ к '{target}' запрещён."

        # 5. Открываем
        if os.path.isdir(found):
            return os_layer.open_path(found)
        elif _is_text_file(found):
            return _open_in_editor(found)
        elif _is_media_file(found):
            return os_layer.open_path(found)
        else:
            return _open_in_editor(found)

    # ===== НАЙДИ ... =====
    if "найди " in low:
        match = re.search(r"найди\s+(.+)", text, re.IGNORECASE)
        if not match:
            return "Что найти?"
        query = match.group(1).strip()

        found = []
        base = os.path.expanduser("~")
        try:
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for name in dirs + files:
                    if query.lower() in name.lower():
                        candidate = os.path.join(root, name)
                        if _is_safe_path(candidate):
                            found.append(candidate)
                        if len(found) >= 10:
                            break
                if len(found) >= 10:
                    break
        except (PermissionError, OSError):
            pass

        if found:
            return "🔍 Найдено:\n" + "\n".join(found)
        return f"❌ Ничего не найдено: {query}"

    return None