"""
core/agent_tools.py — инструменты автономного агента (Task Runner).

Правила безопасности:
- Агент только читает (поиск, транскрипты) и пишет в data/plans/ и projects/.
- Удаление, выключение, перезагрузка и отправка наружу сюда НЕ входят.
- Пути разрешаются через resolve(); симлинки и выход за пределы разрешённых папок отклоняются.
"""
import json
import re
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
def emulate(action: str, arg: str) -> dict:
    """
    Выполняет эмуляцию ввода. Проверка флага — здесь, до любого вызова ydotool.
    action: click_at (arg = "x,y"), type_text (arg = текст), press_key (arg = клавиша).
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
            res = tools.type_text(arg)
        elif action == "press_key":
            res = tools.press_key(arg)
        else:
            return {"ok": False, "error": f"неизвестная эмуляция: {action}"}
    except ValueError:
        return {"ok": False, "error": "неверные координаты (нужно «x,y»)"}
    return {"ok": not str(res).startswith("⚠️"), "result": str(res)}
