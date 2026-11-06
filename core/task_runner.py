"""
core/task_runner.py — исполнитель задач автономного агента (Task Runner).

1. parse_goal(goal) — разбивает цель на шаги через API (с запасным вариантом без API).
2. Шаги берутся ТОЛЬКО из ALLOWED_TOOLS. Незнакомое действие от API отбрасывается.
3. run_task(goal) выполняет шаги по порядку, пишет каждый шаг в data/autonomy.log.
4. Очередь задач хранится в data/autonomy.json (ключ "queue").
"""
import json
import re

from core import agent_tools
from core.logger import get_logger

_log = get_logger("task_runner", file="autonomy.log")

# Белый список инструментов. Удаление, выключение, отправка наружу сюда не входят.
ALLOWED_TOOLS = {
    "search_web": lambda arg: agent_tools.search_web_saved(arg),
    "read_youtube": lambda arg: agent_tools.read_youtube_transcript(arg),
    "write_plan": lambda arg: agent_tools.write_plan(arg, title="plan"),
    "read_file": lambda arg: agent_tools.read_file_safe(arg),
    "open_app": lambda arg: agent_tools.open_app_safe(arg),
}

# Эмуляция ввода. Работает ТОЛЬКО при emulation_enabled=True и через подтверждение «да».
EMULATION_TOOLS = ("click_at", "type_text", "press_key")

# Описание инструментов для модели. Должно совпадать с ALLOWED_TOOLS и EMULATION_TOOLS.
TOOLS_PROMPT = (
    "Доступные инструменты:\n"
    "- search_web: поиск в интернете, arg = запрос\n"
    "- read_file: прочитать файл проекта, arg = путь внутри проекта\n"
    "- open_app: открыть приложение из списка (steam, firefox, терминал, код и др.), arg = имя\n"
    "- write_plan: сохранить план в файл, arg = текст плана\n"
    "- type_text: напечатать текст (только если пользователь разрешил эмуляцию), arg = текст\n"
    "- click_at: клик по экрану (только если эмуляция разрешена), arg = \"x,y\"\n"
)

MAX_STEPS = 8


def _validate_steps(raw) -> list:
    """Оставляет только шаги с разрешённым инструментом и строковым аргументом."""
    steps = []
    if not isinstance(raw, list):
        return steps
    for item in raw[:MAX_STEPS]:
        if not isinstance(item, dict):
            continue
        tool = item.get("tool")
        arg = item.get("arg", "")
        # Эмуляция проходит валидацию, но в run_cycle выполняется только с флагом и подтверждением «да».
        if (tool not in ALLOWED_TOOLS and tool not in EMULATION_TOOLS) or not isinstance(arg, str):
            _log.warning("шаг отброшен: инструмент %r не разрешён", tool)
            continue
        steps.append({"tool": tool, "arg": arg.strip()[:2000]})
    return steps


def _fallback_steps(goal: str) -> list:
    """Запасной разбор без API. «открой терминал … напиши X» → открыть терминал и напечатать X (X — с подтверждением)."""
    low = goal.lower()
    if "терминал" in low and "напиши" in low:
        m = re.search(r"напиши\s+['\"«]?([^'\"»]+)['\"»]?", goal, re.I)
        text = m.group(1).strip() if m else "привет"
        return [
            {"tool": "open_app", "arg": "терминал"},
            {"tool": "type_text", "arg": text},
        ]
    steps = []
    if "pyqt" in low or "код" in low or "улучши" in low:
        steps.append({"tool": "search_web", "arg": "PyQt6 новые возможности best practices"})
    if "youtube" in low or "транскрипт" in low or "видео" in low:
        steps.append({"tool": "search_web", "arg": "PyQt6 tutorial youtube"})
    steps.append({"tool": "write_plan", "arg": f"План по цели: {goal}\n\n(составлен без API: шаги по умолчанию)"})
    return steps


def parse_goal(goal: str, api=None) -> list:
    """Разбивает цель на шаги. С API — через модель; без — запасной разбор."""
    if api is not None and getattr(api, "enabled", False):
        prompt = (
            "Разбей задачу на шаги. Ответь ТОЛЬКО JSON-массивом вида "
            '[{"tool": "open_app|type_text|click_at|search_web|read_file|write_plan", "arg": "..."}]. '
            "Максимум 8 шагов.\n\n" + TOOLS_PROMPT + "\nЗадача: " + goal
        )
        try:
            answer = api.ask(prompt, max_tokens=600, temperature=0.2)
            m = re.search(r"\[.*\]", answer or "", re.S)
            if m:
                steps = _validate_steps(json.loads(m.group(0)))
                if steps:
                    return steps
        except Exception as e:
            _log.warning("разбор через API не удался: %r — запасной вариант", e)
    return _fallback_steps(goal)


def run_steps(steps: list) -> list:
    """Выполняет шаги по порядку. Ошибка одного шага не останавливает остальные."""
    results = []
    for i, step in enumerate(steps, 1):
        fn = ALLOWED_TOOLS.get(step["tool"])
        if fn is None:
            results.append({"step": i, "tool": step["tool"], "ok": False, "error": "не разрешён"})
            continue
        try:
            res = fn(step["arg"])
        except Exception as e:
            res = {"ok": False, "error": repr(e)}
        res = res if isinstance(res, dict) else {"ok": False, "error": "неверный ответ"}
        _log.info("шаг %d %s: %s", i, step["tool"], "ok" if res.get("ok") else res.get("error"))
        results.append({"step": i, "tool": step["tool"], **res})
    return results


def run_task(goal: str, api=None) -> dict:
    """Полный цикл: разбор цели → выполнение шагов. Возвращает сводку."""
    steps = parse_goal(goal, api=api)
    _log.info("задача «%s»: %d шагов", goal[:80], len(steps))
    results = run_steps(steps)
    ok = sum(1 for r in results if r.get("ok"))
    return {"goal": goal, "steps": len(steps), "ok": ok, "results": results}


def run_cycle(goal: str, api=None) -> dict:
    """
    Цикл: разбор → шаги по очереди → отчёт в data/autonomy.log.
    open_app выполняется сразу (белый список). Эмуляция без emulation_enabled отклоняется;
    с флагом — ставится на подтверждение «да» и цикл останавливается на этом шаге.
    """
    from core import autonomy
    steps = parse_goal(goal, api=api)
    autonomy._journal(f"ЦИКЛ старт: «{goal[:80]}», шагов {len(steps)}")
    results = []
    for i, step in enumerate(steps, 1):
        tool = step["tool"]
        if tool in EMULATION_TOOLS:
            if not autonomy.is_emulation_enabled():
                res = {"ok": False, "error": "эмуляция выключена"}
            else:
                req = autonomy.request_dangerous_action(tool, step["arg"])
                res = {"ok": False, "pending_confirm": True, "question": req["question"]}
        else:
            res = run_steps([step])[0]
        results.append({"step": i, "tool": tool, **res})
        if res.get("pending_confirm"):
            autonomy._journal(f"ЦИКЛ шаг {i} {tool}: ожидает подтверждения, цикл приостановлен")
            autonomy.save_chain(steps[i:])  # остаток задачи ждёт продолжения после «да»
            break
        autonomy._journal(f"ЦИКЛ шаг {i} {tool}: {'ok' if res.get('ok') else res.get('error')}")
    ok = sum(1 for r in results if r.get("ok"))
    autonomy._journal(f"ЦИКЛ отчёт: {ok}/{len(steps)} шагов ok")
    return {"goal": goal, "steps": len(steps), "ok": ok, "results": results}


def continue_chain() -> str | None:
    """
    Выполняет сохранённый остаток задачи после подтверждения «да».
    Идёт по шагам, пока не встретит следующую эмуляцию (тогда снова ждёт «да»).
    Когда остаток исчерпан — очищает цепочку, пишет «Задача выполнена полностью».
    Возвращает None, если продолжать было нечего.
    """
    from core import autonomy
    steps = autonomy.load_chain()
    if not steps:
        return None
    done = []
    for i, step in enumerate(steps):
        tool = step["tool"]
        if tool in EMULATION_TOOLS:
            if not autonomy.is_emulation_enabled():
                autonomy.clear_chain()
                autonomy._journal("ЦЕПОЧКА прервана: эмуляция выключена")
                return "Эмуляция выключена — остаток задачи отменён."
            req = autonomy.request_dangerous_action(tool, step["arg"])
            autonomy.save_chain(steps[i + 1:])  # этот шаг ждёт «да», остаток сохраняем
            return f"Следующий шаг: {req['question']}"
        res = run_steps([step])[0]
        done.append(res)
        autonomy._journal(f"ЦЕПОЧКА шаг {tool}: {'ok' if res.get('ok') else res.get('error')}")
    autonomy.clear_chain()
    autonomy._journal("Задача выполнена полностью")
    ok = sum(1 for r in done if r.get("ok"))
    return f"Задача выполнена полностью ({ok}/{len(done)} шагов ok)."


def _run_emulation(tool: str, arg: str) -> dict:
    from core import agent_tools
    return agent_tools.emulate(tool, arg)
