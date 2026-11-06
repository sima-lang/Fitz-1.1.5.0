"""
core/agent_tools.py — инструменты автономного агента (Task Runner).

Правила безопасности:
- Агент только читает (поиск, транскрипты) и пишет в data/plans/ и projects/.
- Удаление, выключение, перезагрузка и отправка наружу сюда НЕ входят.
- Пути разрешаются через resolve(); симлинки и выход за пределы разрешённых папок отклоняются.
"""
import json
import os as _os
import re
import shlex
import shutil
import subprocess
import time as _time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse, parse_qs
from urllib.request import Request, urlopen

from core.logger import get_logger

_log = get_logger("agent_tools", file="autonomy.log")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANS_DIR = PROJECT_ROOT / "data" / "plans"
RESEARCH_DIR = PROJECT_ROOT / "data" / "research"
PROJECTS_DIR = PROJECT_ROOT / "projects"
WRITABLE_ROOTS = (PLANS_DIR, PROJECTS_DIR)

_TIMEOUT = 15
_UA = "Mozilla/5.0 (X11; Linux x86_64) Fitz-agent/1.2.0.1"


# ----------------------------------------------------------------------
# Пути
# ----------------------------------------------------------------------
def safe_write_path(path: Path) -> Path | None:
    """Возвращает разрешённый путь для записи или None, если он вне разрешённых папок."""
    try:
        target = Path(path).resolve()
    except (OSError, RuntimeError):
        return None
    for root in WRITABLE_ROOTS:
        root_resolved = root.resolve()
        if target == root_resolved or root_resolved in target.parents:
            return target
    return None


def _slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^\w\-]+", "-", text.strip().lower(), flags=re.UNICODE).strip("-")
    return (s or "item")[:limit]


# ----------------------------------------------------------------------
# 1. Поиск с сохранением результатов
# ----------------------------------------------------------------------
def search_web_saved(query: str, max_results: int = 5) -> dict:
    """
    Ищет через DuckDuckGo HTML и сохраняет результаты в data/research/.
    Возвращает {"ok": bool, "query": ..., "results": [...], "file": ...}.
    Без сети возвращает ok=False, а не падает.
    """
    if not query or not query.strip():
        return {"ok": False, "error": "пустой запрос"}
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    try:
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=_TIMEOUT) as r:
            page = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        _log.warning("поиск «%s» не выполнен: %r", query, e)
        return {"ok": False, "query": query, "error": f"сеть: {e}"}

    results = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        results.append({"title": title, "url": m.group(1)})
        if len(results) >= max_results:
            break

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file = RESEARCH_DIR / f"{stamp}_{_slug(query)}.json"
    with open(file, "w", encoding="utf-8") as f:
        json.dump({"query": query, "results": results}, f, ensure_ascii=False, indent=2)
    _log.info("поиск «%s»: %d результатов сохранено в %s", query, len(results), file.name)
    return {"ok": True, "query": query, "results": results, "file": str(file)}


# ----------------------------------------------------------------------
# 2. Транскрипт YouTube
# ----------------------------------------------------------------------
def _youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in ("youtu.be",):
        return parsed.path.lstrip("/") or None
    if host.endswith("youtube.com"):
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
    return None


def read_youtube_transcript(url: str) -> dict:
    """
    Транскрипт видео через библиотеку youtube-transcript-api.
    Если библиотеки нет или у видео нет субтитров — честная ошибка, без угадывания.
    """
    vid = _youtube_video_id(url or "")
    if not vid:
        return {"ok": False, "error": "не похоже на ссылку YouTube"}
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return {"ok": False, "error": "не установлена библиотека youtube-transcript-api (pip install youtube-transcript-api)"}
    try:
        parts = YouTubeTranscriptApi.get_transcript(vid, languages=["ru", "en"])
    except Exception as e:
        _log.warning("транскрипт %s недоступен: %r", vid, e)
        return {"ok": False, "error": f"транскрипт недоступен: {e}"}
    text = " ".join(p.get("text", "") for p in parts)
    return {"ok": True, "video_id": vid, "text": text[:20000]}


# ----------------------------------------------------------------------
# 3. Запись плана
# ----------------------------------------------------------------------
def write_plan(text: str, title: str = "plan") -> dict:
    """Сохраняет план в data/plans/<дата>_<название>.md. Других мест записи нет."""
    if not text or not text.strip():
        return {"ok": False, "error": "пустой план"}
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = safe_write_path(PLANS_DIR / f"{stamp}_{_slug(title)}.md")
    if target is None:
        return {"ok": False, "error": "путь вне разрешённых папок"}
    target.write_text(text, encoding="utf-8")
    _log.info("план сохранён: %s", target.name)
    return {"ok": True, "file": str(target)}


# ----------------------------------------------------------------------
# 4. Эмуляция ввода (через core/tools, ydotool). Работает ТОЛЬКО при флаге emulation_enabled.
# ----------------------------------------------------------------------
def _focus_editor_window() -> None:
    """Переключает фокус на окно редактора через клик в центр экрана (ydotool).
    wmctrl не работает на Wayland — вместо этого кликаем мышью в центр,
    что переводит фокус на открывшееся окно (блокнот/gedit)."""
    # Проверяем, работает ли ydotool (нужен демон ydotoold)
    if not shutil.which("ydotool"):
        _log.info("ydotool не найден — пропускаю фокусировку")
        return
    _log.info("фокус: клик ydotool в центр экрана")
    try:
        subprocess.run(["ydotool", "mousemove", "960", "540"], capture_output=True, timeout=3)
        _time.sleep(0.15)
        subprocess.run(["ydotool", "click", "1"], capture_output=True, timeout=3)
        _time.sleep(0.5)  # даём оконному менеджеру время на переключение фокуса
        _log.info("фокус: клик выполнен")
    except Exception as e:
        _log.info("фокус: ошибка ydotool — %s", e)


def emulate(action: str, arg: str) -> dict:
    """
    Выполняет эмуляцию ввода. Проверка флага — здесь, до любого вызова ydotool.
    action: click_at (arg = "x,y"), type_text (arg = текст), press_key (arg = клавиша).
    Перед type_text окно редактора выводится на передний план через wmctrl.
    """
    from core import autonomy
    if not autonomy.is_emulation_enabled():
        return {"ok": False, "error": "эмуляция выключена"}
    from core import tools
    try:
        if action == "click_at":
            x, y = (v.strip() for v in arg.split(","))
            res = tools.click_at(x, y)
        elif action == "type_text":
            _focus_editor_window()
            res = tools.type_text(arg)
        elif action == "press_key":
            res = tools.press_key(arg)
        else:
            return {"ok": False, "error": f"неизвестная эмуляция: {action}"}
    except ValueError:
        return {"ok": False, "error": "неверные координаты (нужно «x,y»)"}
    return {"ok": not str(res).startswith("⚠️"), "result": str(res)}


# ----------------------------------------------------------------------
# 5. Чтение файла агентом: только проект и data/
# ----------------------------------------------------------------------
READABLE_ROOTS = (PROJECT_ROOT,)


def read_file_safe(path: str) -> dict:
    """Чтение файла, но только внутри проекта. Симлинки и выход за пределы отклоняются."""
    if not path or not path.strip():
        return {"ok": False, "error": "пустой путь"}
    try:
        target = (PROJECT_ROOT / path.strip()).resolve() if not Path(path).is_absolute() \
            else Path(path).resolve()
    except (OSError, RuntimeError):
        return {"ok": False, "error": "неверный путь"}
    if not any(target == r or r in target.parents for r in (p.resolve() for p in READABLE_ROOTS)):
        return {"ok": False, "error": "путь вне проекта"}
    if not target.is_file():
        return {"ok": False, "error": "файл не найден"}
    text = target.read_text(encoding="utf-8", errors="replace")
    return {"ok": True, "file": str(target), "text": text[:20000]}


# ----------------------------------------------------------------------
# 6. Запуск приложения агентом: белый список + правило автономности
# ----------------------------------------------------------------------
def open_app_safe(name: str) -> dict:
    """
    Запуск приложения. Вне автономного режима агент сюда не попадает —
    подтверждение обеспечивает commands/apps.py. Здесь проверяется белый список.
    """
    from core import autonomy
    if not autonomy.is_allowed_app(name):
        return {"ok": False, "error": f"«{name}» не в списке разрешённых приложений"}
    from core import tools
    res = str(tools.open_app(name))
    return {"ok": not res.startswith("⚠️"), "result": res}


# ----------------------------------------------------------------------
# 7. Запуск команд агентом (CLI-агент)
# ----------------------------------------------------------------------
_AGENT_SAFE_CMDS = frozenset({
    # Утилиты
    "ls", "pwd", "echo", "cat", "grep", "whoami", "date", "uptime",
    "uname", "df", "du", "head", "tail", "wc", "sort", "uniq", "cut", "tr",
    # Файлы
    "mkdir", "touch", "cp", "mv", "ln", "basename", "dirname", "realpath",
    "chmod", "test", "env",
    # Сборка и языки
    "python3", "python", "pytest", "pip", "pip3",
    "node", "npm", "npx",
    "git", "make", "cmake", "find", "xargs",
})


def run_command_safe(cmd: str) -> dict:
    """Выполняет безопасную команду из расширенного белого списка. Без shell.
    Возвращает {"ok": bool, "stdout": ..., "stderr": ..., "code": int}."""
    if not cmd or not cmd.strip():
        return {"ok": False, "error": "пустая команда"}
    try:
        argv = shlex.split(cmd.strip())
    except ValueError as e:
        return {"ok": False, "error": f"некорректная команда: {e}"}
    if not argv:
        return {"ok": False, "error": "пустая команда"}
    if argv[0] not in _AGENT_SAFE_CMDS:
        return {"ok": False, "error": f"команда '{argv[0]}' не в белом списке агента"}
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "команда выполнялась >30 сек"}
    except FileNotFoundError:
        return {"ok": False, "error": f"программа '{argv[0]}' не найдена"}
    except Exception as e:
        return {"ok": False, "error": repr(e)}
    return {
        "ok": r.returncode == 0,
        "stdout": r.stdout.strip()[:5000],
        "stderr": r.stderr.strip()[:2000],
        "code": r.returncode,
    }


# ----------------------------------------------------------------------
# 8. Запись файла агентом: создаёт папки, пишет в корень проекта
# ----------------------------------------------------------------------
def write_file_safe(path: str, content: str = "") -> dict:
    """Записывает файл. Путь — относительно корня проекта. os.makedirs — авто.
    Возвращает {"ok": bool, "file": ..., "size": int}."""
    if not path or not path.strip():
        return {"ok": False, "error": "пустой путь"}
    path = path.strip().strip('"').strip("'")
    try:
        target = (PROJECT_ROOT / path).resolve()
    except (OSError, RuntimeError):
        return {"ok": False, "error": "неверный путь"}
    # Защита: не даём выйти за PROJECT_ROOT
    if PROJECT_ROOT not in (target,) and PROJECT_ROOT not in target.parents:
        return {"ok": False, "error": "путь вне проекта"}
    try:
        _os.makedirs(target.parent, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"ошибка записи: {e}"}
    _log.info("записан файл: %s (%d байт)", target, len(content))
    return {"ok": True, "file": str(target), "size": len(content)}


# ----------------------------------------------------------------------
# 9. apply_patch — точечное изменение файла (old_string → new_string)
# ----------------------------------------------------------------------
def apply_patch_safe(path: str, old: str, new: str) -> dict:
    """Заменяет old_string на new_string в файле. Без перезаписи всего файла.
    Возвращает {"ok": bool, "file": ..., "replaced": int}."""
    if not path or not path.strip():
        return {"ok": False, "error": "пустой путь"}
    if not old:
        return {"ok": False, "error": "пустой old_string"}
    path = path.strip().strip('"').strip("'")
    try:
        target = (PROJECT_ROOT / path).resolve()
    except (OSError, RuntimeError):
        return {"ok": False, "error": "неверный путь"}
    if PROJECT_ROOT not in (target,) and PROJECT_ROOT not in target.parents:
        return {"ok": False, "error": "путь вне проекта"}
    if not target.exists():
        return {"ok": False, "error": f"файл не найден: {path}"}
    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"ошибка чтения: {e}"}
    count = content.count(old)
    if count == 0:
        return {"ok": False, "error": f"old_string не найден в {path} (проверь точное совпадение)"}
    new_content = content.replace(old, new)
    try:
        target.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"ошибка записи: {e}"}
    _log.info("apply_patch %s: %d замен", target, count)
    return {"ok": True, "file": str(target), "replaced": count}


# ----------------------------------------------------------------------
# 10. search_code — grep по проекту
# ----------------------------------------------------------------------
def search_code(query: str) -> dict:
    """Ищет query через grep -rnI в корне проекта. Только .py, .md, .txt, .json, .toml, .cfg.
    Возвращает {"ok": bool, "matches": [...], "count": int}."""
    if not query or not query.strip():
        return {"ok": False, "error": "пустой запрос"}
    try:
        r = subprocess.run(
            ["grep", "-rnI", "--include=*.py", "--include=*.md", "--include=*.txt",
             "--include=*.json", "--include=*.toml", "--include=*.cfg",
             query.strip(), "."],
            capture_output=True, text=True, timeout=10, cwd=str(PROJECT_ROOT))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "поиск занял >10 сек"}
    except FileNotFoundError:
        return {"ok": False, "error": "grep не найден"}
    except Exception as e:
        return {"ok": False, "error": repr(e)}
    lines = r.stdout.strip().split("\n") if r.stdout.strip() else []
    _log.info("search_code «%s»: %d совпадений", query, len(lines))
    return {"ok": True, "matches": lines[:50], "count": len(lines)}
