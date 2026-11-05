"""
system.py — Системные команды: время, дата, мониторинг, диски, процессы, окна, дневник.
Кроссплатформенно (psutil + time + platform). Окна — Linux через GNOME Shell D-Bus (core/tools.window_control).
"""
import time
import platform
import subprocess
import shutil
from datetime import datetime
from core.logger import get_logger
_log = get_logger("system")

try:
    import psutil
except Exception:
    psutil = None


def _run(cmd: list, timeout: float = 5) -> str:
    """Выполняет системную команду и возвращает stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip()
    except FileNotFoundError:
        return ""
    except Exception as e:
        return str(e)


def handle(text, memory, core):
    low = text.lower().strip()

    # ===== ВРЕМЯ =====
    if low in ("время", "сколько время", "который час", "время сейчас"):
        return time.strftime("%H:%M:%S")

    # ===== ДАТА =====
    if low == "дата":
        return time.strftime("%d.%m.%Y")

    # ===== ДЕНЬ НЕДЕЛИ =====
    if low in ("день недели", "день"):
        weekdays = ["Понедельник", "Вторник", "Среда", "Четверг",
                    "Пятница", "Суббота", "Воскресенье"]
        return f"📅 Сегодня {weekdays[datetime.now().weekday()]}"

    # ===== ИНФО О ПК =====
    if low in ("инфо о пк", "состояние пк", "информация о системе"):
        lines = [f"🖥️ Система: {platform.system()} {platform.release()}"]
        lines.append(f"🧠 Процессор: {platform.processor() or 'Неизвестно'}")
        if psutil:
            try:
                ram = psutil.virtual_memory()
                lines.append(f"💾 ОЗУ: {round(ram.total / (1024**3), 1)} ГБ "
                             f"(занято {ram.percent}%)")
            except Exception:
                _log.debug("пропущено в commands/system.py (строка 57)")
        return "\n".join(lines)

    # ===== МОНИТОРИНГ =====
    if low in ("мониторинг", "состояние", "статус системы"):
        if not psutil:
            return "⚠️ psutil не установлен"
        try:
            cpu = psutil.cpu_percent(interval=0.3)
            ram = psutil.virtual_memory()
            return (f"🖥️ МОНИТОРИНГ:\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📊 ЦП: {cpu}%\n"
                    f"🧠 ОЗУ: {ram.percent}% "
                    f"({ram.used // 1024**3} ГБ / {ram.total // 1024**3} ГБ)")
        except Exception as e:
            return f"⚠️ Ошибка мониторинга: {e}"

    # ===== ДИСКИ =====
    if low in ("диски", "инфо о дисках"):
        if not psutil:
            return "⚠️ psutil не установлен"
        try:
            lines = ["💽 ДИСКИ:"]
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    lines.append(f"{part.device}: {usage.percent}% "
                                 f"({usage.free // 1024**3} ГБ свободно)")
                except Exception:
                    lines.append(f"{part.device}: недоступен")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Ошибка дисков: {e}"

    # ===== ПРОЦЕССЫ =====
    if low in ("процессы", "список процессов"):
        if not psutil:
            return "⚠️ psutil не установлен"
        try:
            procs = []
            for p in psutil.process_iter(["name", "memory_percent"]):
                try:
                    info = p.info
                    procs.append((info["name"], info["memory_percent"] or 0))
                except Exception:
                    _log.debug("пропущено в commands/system.py (строка 103)")
                    continue
            procs.sort(key=lambda x: x[1], reverse=True)
            lines = ["📊 ТОП ПРОЦЕССОВ:"]
            for name, mem in procs[:15]:
                lines.append(f"  • {name} ({mem:.1f}%)")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Ошибка процессов: {e}"

    # ===== ПЕРЕКЛЮЧИСЬ НА ОКНО =====
    if low.startswith("переключись на ") or low.startswith("переключи на "):
        target = text.split(" на ", 1)[1].strip().strip('"').strip("'")
        if not target:
            return "Какое окно переключить?"
        from core.tools import window_control
        return window_control("switch", target)

    # ===== ЗАКРОЙ ОКНО =====
    if low.startswith("закрой окно ") or low == "закрой окно":
        if "закрой окно " in low:
            target = text.split("закрой окно ", 1)[1].strip().strip('"').strip("'")
        else:
            target = text[11:].strip()
        if not target:
            return "Какое окно закрыть?"
        from core.tools import window_control
        return window_control("close", target)

    # ===== СВЕРНИ ВСЁ =====
    if low in ("сверни всё", "свернуть всё", "сверни все окна", "показать рабочий стол"):
        from core.tools import window_control
        return window_control("minimize_all")

    # ===== РАЗВЕРНИ ОКНО =====
    if low.startswith("разверни окно ") or low.startswith("разверни "):
        target = text.split("разверни ", 1)[1].strip().strip('"').strip("'")
        if not target:
            return "Какое окно развернуть?"
        from core.tools import window_control
        return window_control("maximize", target)

    # ===== ДНЕВНИК / ЧТО Я ДЕЛАЛ СЕГОДНЯ =====
    if low in ("дневник", "что я делал сегодня", "дневник за сегодня",
               "сводка за день", "сводка за сегодня"):
        date_str = datetime.now().strftime("%Y-%m-%d")
        if "вчера" in low:
            from datetime import timedelta
            date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if core and getattr(core, "intel", None):
            return core.intel.get_events_summary(date_str)
        return "📭 Дневник недоступен (нет модуля intelligence)"

    # ===== ПРЕДЛОЖИ РАЗВЛЕЧЕНИЕ =====
    if low in ("предложи развлечение", "развлеки меня", "чем заняться", "что посмотреть",
               "что послушать", "что включить"):
        if core and getattr(core, "app", None):
            app = core.app
            initiative = getattr(app, "initiative", None)
            if initiative:
                return initiative.suggest_now()
        return "⚠️ Инициатива не активна. Включи её в настройках."

    return None