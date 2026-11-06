"""
core/task_runner.py — Agentic Loop (версия 1.4.0.0).

1. run_cycle(goal) — итеративный цикл: на каждой итерации модель получает
   полный контекст (что сделано, какие ошибки) и предлагает ОДИН следующий шаг.
2. Модель возвращает {"thought": "...", "tool": "...", "arg": "..."} или
   {"done": true, "summary": "Задача выполнена"}.
3. Максимум 10 итераций. Ошибки передаются в контекст для самопочинки.
4. Очередь задач хранится в data/autonomy.json (ключ "queue").
"""
import json
import re

from core import agent_tools
from core.logger import get_logger

_log = get_logger("task_runner", file="autonomy.log")


def _load_setting(key: str, default: str) -> str:
    """Читает настройку из data/settings.json."""
    try:
        from pathlib import Path
        p = Path(__file__).parent.parent / "data" / "settings.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as fh:
                return json.load(fh).get(key, default)
    except Exception:
        pass
    return default


# Белый список инструментов.
ALLOWED_TOOLS = {
    "run_command": lambda step: agent_tools.run_command_safe(step["arg"]),
    "write_file": lambda step: agent_tools.write_file_safe(step["arg"], step.get("content", "")),
    "apply_patch": lambda step: agent_tools.apply_patch_safe(
        step["arg"], step.get("old", ""), step.get("new", "")),
    "search_code": lambda step: agent_tools.search_code(step["arg"]),
    "read_file": lambda step: agent_tools.read_file_safe(step["arg"]),
    "search_web": lambda step: agent_tools.search_web_saved(step["arg"]),
    "open_app": lambda step: agent_tools.open_app_safe(step["arg"]),
    "write_plan": lambda step: agent_tools.write_plan(step["arg"], title="plan"),
}

EMULATION_TOOLS = ("click_at", "type_text", "press_key")

# Системный промпт для Agentic Loop — одна итерация.
AGENT_SYSTEM = (
    "Ты — инженер-агент. Твоя задача: решить проблему пользователя шаг за шагом.\n\n"
    "Инструменты:\n"
    "- run_command: выполнить команду (mkdir, python3, pytest, git, npm, ...)\n"
    "- write_file: создать/перезаписать файл. arg=путь, content=содержимое\n"
    "- apply_patch: точечная замена old→new в файле. arg=путь, old=старый код, new=новый код\n"
    "- search_code: grep по проекту. arg=запрос (возвращает файл:строка:текст)\n"
    "- read_file: прочитать файл. arg=путь\n"
    "- search_web: поиск в интернете. arg=запрос\n"
    "- open_app: открыть приложение (steam, firefox, терминал, блокнот, код)\n"
    "- write_plan: сохранить план/заметку. arg=текст\n\n"
    "ФОРМАТ ОТВЕТА — СТРОГО один JSON-объект (не массив):\n"
    '{"thought": "мой план на этот шаг", "tool": "ИМЯ", "arg": "...", "content": "..."}\n'
    "ИЛИ когда задача решена:\n"
    '{"done": true, "summary": "что сделано и результат"}\n\n'
    "ПРАВИЛА:\n"
    "1. ОДИН шаг за раз. Не пиши план наперёд — просто делай следующий логический шаг.\n"
    "2. Если предыдущий шаг упал с ошибкой — прочитай код, исправь через apply_patch, перезапусти.\n"
    "3. Для создания проекта: mkdir → write_file → run_command. По одному шагу.\n"
    "4. Для отладки: run_command(pytest) → read_file(файл с ошибкой) → apply_patch.\n"
    "5. apply_patch: old должен быть ТОЧНОЙ копией строк из файла. new — исправленная версия.\n"
    "6. Когда цель достигнута — верни {\"done\": true}."
)

MAX_ITERATIONS = 10


def _exec_one(step: dict) -> dict:
    """Выполняет ОДИН шаг. fn принимает полный step dict."""
    tool = step["tool"]
    fn = ALLOWED_TOOLS.get(tool)
    if fn is None:
        return {"ok": False, "error": f"инструмент {tool!r} не разрешён"}
    try:
        res = fn(step)
    except Exception as e:
        return {"ok": False, "error": repr(e)}
    if not isinstance(res, dict):
        res = {"ok": False, "error": "неверный ответ инструмента"}
    return {"tool": tool, **res}


def _step_to_text(step: dict, res: dict) -> str:
    """Форматирует результат шага для контекста API."""
    tool = step["tool"]
    if res.get("ok"):
        if tool == "run_command":
            out = res.get("stdout", "")[:300]
            return f"[OK] {tool}({step['arg']}) → stdout: {out}"
        elif tool == "write_file":
            return f"[OK] {tool}({step['arg']}) → {res.get('size', '?')} байт"
        elif tool == "apply_patch":
            return f"[OK] {tool}({step['arg']}) → {res.get('replaced', '?')} замен(ы)"
        elif tool == "search_code":
            cnt = res.get("count", 0)
            matches = "\n".join(res.get("matches", [])[:5])
            return f"[OK] {tool}({step['arg']}) → {cnt} совпадений:\n{matches}"
        elif tool == "read_file":
            text = (res.get("text", "") or "")[:300]
            return f"[OK] {tool}({step['arg']}) → прочитано:\n{text}"
        else:
            return f"[OK] {tool}({step['arg']})"
    else:
        err = res.get("stderr", "") or res.get("error", "?")
        return f"[ОШИБКА] {tool}({step['arg']}): {err[:300]}"


def _format_history(history: list) -> str:
    """Форматирует историю шагов для контекстного окна API."""
    lines = []
    for step, res in history:
        lines.append(_step_to_text(step, res))
    return "\n".join(lines)


def run_cycle(goal: str, api=None) -> dict:
    """
    Agentic Loop:
    1. На каждой итерации отправляет API текущий контекст (историю + ошибки).
    2. API возвращает ОДИН следующий шаг или {"done": true}.
    3. Максимум MAX_ITERATIONS итераций.
    """
    from core import autonomy

    if api is None or not getattr(api, "enabled", False):
        # Без API: линейный fallback
        return _run_linear(goal, api)

    history = []  # list of (step_dict, result_dict)
    autonomy._journal(f"AGENTIC старт: «{goal[:80]}»")

    for iteration in range(1, MAX_ITERATIONS + 1):
        # Строим контекст
        context = AGENT_SYSTEM + "\n\nЦель: " + goal + "\n\n"
        if history:
            context += "История шагов:\n" + _format_history(history) + "\n\n"
        context += f"Итерация {iteration}/{MAX_ITERATIONS}. Твой следующий шаг (ОДИН JSON-объект):"

        # Запрос к API
        try:
            answer = api.ask(context, max_tokens=500, temperature=0.2,
                            model=_load_setting("code_model", "anthropic/claude-haiku-5.5"))
        except Exception as e:
            _log.error("AGENTIC итерация %d: ошибка API: %r", iteration, e)
            break

        if not answer or not answer.strip():
            _log.warning("AGENTIC итерация %d: пустой ответ API", iteration)
            continue

        # Парсим JSON-ответ
        m = re.search(r"\{.*\}", answer, re.S)
        if not m:
            _log.warning("AGENTIC итерация %d: ответ без JSON: %s", iteration, answer[:200])
            continue

        try:
            agent_resp = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            _log.warning("AGENTIC итерация %d: битый JSON: %r", iteration, e)
            continue

        # Проверяем done
        if agent_resp.get("done"):
            summary = agent_resp.get("summary", "Задача выполнена")
            autonomy._journal(f"AGENTIC финиш: {summary}")
            ok = sum(1 for _, r in history if r.get("ok"))
            return {"goal": goal, "iterations": iteration, "ok": ok,
                    "done": True, "summary": summary,
                    "results": [{"step": i, **r} for i, (_, r) in enumerate(history, 1)]}

        # Выполняем шаг
        tool = agent_resp.get("tool", "")
        arg = agent_resp.get("arg", "")
        thought = agent_resp.get("thought", "")

        if not tool:
            _log.warning("AGENTIC итерация %d: нет tool в ответе: %s", iteration, answer[:200])
            continue

        step = {"tool": tool, "arg": arg}
        if tool == "write_file":
            step["content"] = agent_resp.get("content", "")
        if tool == "apply_patch":
            step["old"] = agent_resp.get("old", "")
            step["new"] = agent_resp.get("new", "")

        # Эмуляция — сразу
        if tool in EMULATION_TOOLS:
            if not autonomy.is_emulation_enabled():
                res = {"tool": tool, "ok": False, "error": "эмуляция выключена"}
            else:
                from core import agent_tools as at
                res = at.emulate(tool, arg)
        else:
            res = _exec_one(step)

        history.append((step, res))
        autonomy._journal(f"AGENTIC {iteration} {tool}: "
                          + ("ok" if res.get("ok") else f"error: {res.get('error') or res.get('stderr', '?')[:120]}"))
        if thought:
            _log.info("AGENTIC %d thought: %s", iteration, thought[:120])

    # Исчерпали итерации
    ok = sum(1 for _, r in history if r.get("ok"))
    autonomy._journal(f"AGENTIC стоп: {ok} ok из {len(history)} шагов, лимит итераций {MAX_ITERATIONS}")
    return {"goal": goal, "iterations": MAX_ITERATIONS, "ok": ok, "done": False,
            "results": [{"step": i, **r} for i, (_, r) in enumerate(history, 1)]}


def _run_linear(goal: str, api=None) -> dict:
    """Линейный fallback: parse_goal → run_steps (без API)."""
    steps = _fallback_steps(goal)
    results = run_steps(steps)
    ok = sum(1 for r in results if r.get("ok"))
    return {"goal": goal, "steps": len(steps), "ok": ok, "done": True, "results": results}


# ----------------------------------------------------------------------
# Обратная совместимость: parse_goal, _fallback_steps, run_steps, continue_chain
# ----------------------------------------------------------------------
def _validate_steps(raw) -> list:
    steps = []
    if not isinstance(raw, list):
        return steps
    for item in raw[:10]:
        if not isinstance(item, dict):
            continue
        tool = item.get("tool")
        arg = item.get("arg", "")
        if tool not in ALLOWED_TOOLS and tool not in EMULATION_TOOLS:
            continue
        if not isinstance(arg, str):
            continue
        step = {"tool": tool, "arg": arg.strip()[:2000]}
        if tool == "write_file":
            step["content"] = str(item.get("content", ""))[:20000]
        steps.append(step)
    return steps


def _fallback_steps(goal: str) -> list:
    low = goal.lower()
    steps = []

    if "напиши" in low and ("блокнот" in low or "терминал" in low) and "файл" not in low:
        m = re.search(r"напиши\s+['\"«]?([^'\"»]+)['\"»]?", goal, re.I)
        text = m.group(1).strip() if m else "привет"
        app = "блокнот" if "блокнот" in low else "терминал"
        return [{"tool": "open_app", "arg": app}, {"tool": "type_text", "arg": text}]

    m_dir = re.search(r"(?:создай|сделай)\s+(?:папку|директорию)\s+['\"]?([^\s,]+)['\"]?(?:[,\s]|$)", goal, re.I)
    if m_dir:
        folder = m_dir.group(1).strip().rstrip(",.")
        steps.append({"tool": "run_command", "arg": f"mkdir -p {folder}"})

    m_file = re.search(r"(?:напиши|создай)\b.*?\bфайл\s+['\"]?([^\s,]+)['\"]?(?:[,\s]|$)", goal, re.I)
    if m_file:
        fname = m_file.group(1).strip().rstrip(",.")
        if m_dir:
            fname = m_dir.group(1).strip().rstrip(",./") + "/" + fname
        code = "#!/usr/bin/env python3\nprint('Hello from Fitz!')\n"
        m_code = re.search(r"(?:с\s+кодом|с\s+содержимым)\s+(.+)", goal, re.I)
        if m_code:
            raw = m_code.group(1).strip()
            tail = re.search(r"\s+(?:запусти|проверь|выполни)\b", raw, re.I)
            if tail:
                raw = raw[:tail.start()]
            raw = raw.strip().strip('"').strip("'").strip("«").strip("»").strip()
            if raw:
                code = raw.replace("\\n", "\n")
        steps.append({"tool": "write_file", "arg": fname, "content": code})

    if "запусти" in low or "проверь" in low or "выполни" in low:
        if m_file:
            target = fname
        else:
            target = "."
        if m_dir and "/" not in target and target != ".":
            target = m_dir.group(1).strip().rstrip(",./") + "/" + target
        steps.append({"tool": "run_command", "arg": f"python3 {target}"})

    if not steps:
        steps.append({"tool": "write_plan",
                       "arg": f"План по цели: {goal}\n\n(составлен без API: шаги по умолчанию)"})
    return steps


def parse_goal(goal: str, api=None) -> list:
    if api is not None and getattr(api, "enabled", False):
        prompt = "Разбей задачу на atomic-шаги.\n\n" + AGENT_SYSTEM + "\n\nЗадача: " + goal
        try:
            answer = api.ask(prompt, max_tokens=800, temperature=0.2,
                       model=_load_setting("code_model", "anthropic/claude-haiku-5.5"))
            if not answer or not answer.strip():
                _log.warning("[parse_goal] пустой ответ — fallback")
                return _fallback_steps(goal)
            m = re.search(r"\[.*\]", answer, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError as e:
                    _log.warning("[parse_goal] битый JSON: %r — ответ: %s", e, answer[:200])
                    return _fallback_steps(goal)
                steps = _validate_steps(parsed)
                if steps:
                    return steps
                _log.warning("[parse_goal] все шаги отброшены: %s", answer[:200])
            else:
                _log.warning("[parse_goal] нет JSON-массива: %s", answer[:200])
        except Exception as e:
            _log.warning("[parse_goal] ошибка API: %r", e)
    return _fallback_steps(goal)


def run_steps(steps: list) -> list:
    results = []
    for i, step in enumerate(steps, 1):
        res = _exec_one(step)
        _log.info("шаг %d %s: %s", i, step["tool"], "ok" if res.get("ok") else res.get("error"))
        results.append({"step": i, **res})
    return results


def run_task(goal: str, api=None) -> dict:
    steps = parse_goal(goal, api=api)
    _log.info("задача «%s»: %d шагов", goal[:80], len(steps))
    results = run_steps(steps)
    ok = sum(1 for r in results if r.get("ok"))
    return {"goal": goal, "steps": len(steps), "ok": ok, "results": results}


def continue_chain() -> str | None:
    from core import autonomy
    from core import agent_tools as at
    steps = autonomy.load_chain()
    if not steps:
        return None
    done = []
    for step in steps:
        tool = step["tool"]
        if tool in EMULATION_TOOLS:
            if not autonomy.is_emulation_enabled():
                autonomy.clear_chain()
                autonomy._journal("ЦЕПОЧКА прервана: эмуляция выключена")
                return "Эмуляция выключена — остаток задачи отменён."
            res = at.emulate(tool, step["arg"])
            done.append({"tool": tool, **res})
        else:
            res = _exec_one(step)
            done.append(res)
        autonomy._journal(f"ЦЕПОЧКА шаг {tool}: {'ok' if res.get('ok') else res.get('error')}")
    autonomy.clear_chain()
    autonomy._journal("Задача выполнена полностью")
    ok = sum(1 for r in done if r.get("ok"))
    return f"Задача выполнена полностью ({ok}/{len(done)} шагов ok)."