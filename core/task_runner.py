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
}

# Эмуляция ввода. Работает ТОЛЬКО при emulation_enabled=True и через подтверждение «да».
EMULATION_TOOLS = ("click_at", "type_text", "press_key")

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
        if tool not in ALLOWED_TOOLS or not isinstance(arg, str):
            _log.warning("шаг отброшен: инструмент %r не разрешён", tool)
            continue
        steps.append({"tool": tool, "arg": arg.strip()[:2000]})
    return steps


def _fallback_steps(goal: str) -> list:
    """Запасной разбор без API: поиск по ключевым словам и план в конце."""
    low = goal.lower()
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
            '[{"tool": "search_web|read_youtube|write_plan", "arg": "..."}]. '
            "Максимум 8 шагов. Задача: " + goal
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
    Цикл выполнения задачи: разбор → шаги по очереди → отчёт в data/autonomy.log.
    Эмуляция ввода отклоняется без emulation_enabled. Возвращает сводку.
    """
    from core import autonomy
    steps = parse_goal(goal, api=api)
    autonomy._journal(f"ЦИКЛ старт: «{goal[:80]}», шагов {len(steps)}")
    results = []
    for i, step in enumerate(steps, 1):
        tool = step["tool"]
        if tool in EMULATION_TOOLS:
            res = {"ok": False, "error": "эмуляция выключена"} if not autonomy.is_emulation_enabled() \
                else _run_emulation(tool, step["arg"])
        else:
            res = run_steps([step])[0]
        results.append({"step": i, "tool": tool, **res})
        autonomy._journal(f"ЦИКЛ шаг {i} {tool}: {'ok' if res.get('ok') else res.get('error')}")
    ok = sum(1 for r in results if r.get("ok"))
    autonomy._journal(f"ЦИКЛ отчёт: {ok}/{len(steps)} шагов ok")
    return {"goal": goal, "steps": len(steps), "ok": ok, "results": results}


def _run_emulation(tool: str, arg: str) -> dict:
    from core import agent_tools
    return agent_tools.emulate(tool, arg)
