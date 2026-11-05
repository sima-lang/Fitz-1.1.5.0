"""
agent.py — FitzAgent 1.6.0 «Джарвис».
Агентная архитектура: получает задачу → разбивает на шаги → выполняет → проверяет → ретраи.
Заменяет прямой вызов senior_act: ui_pyqt вызывает FitzAgent.process(text).
"""
import time
import json
import re
import threading
from core.logger import get_logger

_log = get_logger("agent")

# Инструменты, доступные агенту (безопасный белый список)
_AVAILABLE_TOOLS = (
    "read_file, write_file, generate_code, rewrite_file, open_app, search_web, "
    "take_screenshot, play_music, window_control, run_command, "
    "run_command_full, sudo_command, kill_process, system_info, network_info, "
    "install_package, shutdown_pc, reboot_pc, lock_screen, click_at, type_text, press_key"
)

_PLANNING_PROMPT = """\
Ты — Фитц, саркастичный лучший друг создателя.
Если задача неясна — скажи с иронией: «О, создатель, ты сам не знаешь, чего хочешь? Ну ладно, давай разберемся.»
Пользователь дал задачу: '{task}'.
Разбей её на простые шаги, которые можно выполнить одним из инструментов: {tools}, say, ask.
Ответь СТРОГО JSON-массивом объектов:
[{{"tool": "...", "args": {{...}}}}, {{"tool": "...", "args": {{...}}}}]
Если задача простая — верни массив из одного объекта.
Если задача не требует инструментов — верни [{{"tool": "say", "args": {{"text": "..."}}}}].
Ответ должен быть с характером — саркастичным, дружеским, кратким.
НЕ добавляй комментарии, ТОЛЬКО JSON."""


class FitzAgent:
    """Агент: планирует и выполняет многошаговые задачи с ретраями."""

    def __init__(self, brain, execute_tool, max_retries: int = 2, max_steps: int = 5):
        self.brain = brain          # core.brain.Brain (для ask)
        self.execute_tool = execute_tool  # функция tool -> str (из ui_pyqt)
        self.max_retries = max_retries
        self.max_steps = max_steps
        self.history = []           # список последних выполненных шагов
        self._stop_requested = threading.Event()

    def request_stop(self):
        """Просит агента прервать задачу между шагами (кнопка «Стоп»)."""
        self._stop_requested.set()

    # ============================================================
    # ОСНОВНОЙ ВХОД
    # ============================================================
    def process(self, text: str) -> str:
        """
        Главный метод: обрабатывает задачу агентно.
        Возвращает итоговый текст для пользователя.
        """
        if not text or not text.strip():
            return self._fallback_say("Пустая задача.")

        _log.info("agent.process: %r", text[:120])
        self._stop_requested.clear()

        # 1. Планирование через API
        steps = self._plan(text)
        if not steps:
            _log.warning("нет плана — fallback")
            return self._fallback_say(text)
        steps = steps[:self.max_steps]

        # 2. Выполнение шагов с ретраями
        results = []
        for i, step in enumerate(steps):
            if self._stop_requested.is_set():
                results.append("⛔ Остановлено пользователем.")
                break
            res = self._execute_with_retry(step)
            results.append(res)
            self.history.append({"step": step, "result": res})

        # 3. Финальная проверка результата
        return self._summarize(text, results)

    def _think(self, task: str) -> str:
        """Chain of Thought: короткий план до выбора инструмента. Не JSON, просто текст."""
        if not self.brain:
            return ""
        try:
            plan = self.brain.ask(
                f"Составь план: короткими шагами (до 4 пунктов), как выполнить задачу "
                f"«{task}». Только план, без JSON.",
                max_tokens=200,
            )
            plan = (plan or "").strip()
            _log.debug("CoT plan: %r", plan[:200])
            return plan
        except Exception as e:
            _log.warning("_think failed: %s", e)
            return ""

    # ============================================================
    # ПЛАНИРОВАНИЕ
    # ============================================================
    def _plan(self, task: str) -> list:
        """Разбивает задачу на шаги через API."""
        if not self.brain or not getattr(self.brain, "api", None):
            return None
        if not self.brain.api.enabled:
            return None

        cot = self._think(task)
        plan_hint = f"\nТвой предварительный план:\n{cot}\n" if cot else ""
        prompt = _PLANNING_PROMPT.format(task=task, tools=_AVAILABLE_TOOLS) + plan_hint
        try:
            raw = self.brain.api.ask(prompt, max_tokens=500)
            _log.debug("plan raw: %r", raw)
            if not raw:
                return None
            raw = raw.strip()
            # Массив JSON
            if raw.startswith("["):
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [p for p in parsed if isinstance(p, dict)]
            # Одиночный объект
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, dict):
                    return [parsed]
            return None
        except Exception as e:
            _log.warning("_plan failed: %s", e)
            return None

    # ============================================================
    # ВЫПОЛНЕНИЕ С РЕТРАЕМ
    # ============================================================
    def _execute_with_retry(self, step: dict) -> str:
        """Выполняет шаг. При ошибке пробует другой путь (say)."""
        tool = step.get("tool", "say")
        args = step.get("args", {})

        for attempt in range(self.max_retries + 1):
            try:
                result = self.execute_tool(step)
                if result and not str(result).startswith(("⚠️", "⛔", "❌")):
                    return str(result)
                # Неудача — ретраи с упрощением
                _log.warning("шаг %s не удался (попытка %d): %s",
                             tool, attempt + 1, str(result)[:100])
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return str(result)
            except Exception as e:
                _log.warning("шаг %s: исключение (попытка %d): %s",
                             tool, attempt + 1, e)
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return f"⚠️ Шаг {tool} не удался: {e}"

        return f"⚠️ Инструмент {tool} недоступен."

    # ============================================================
    # ИТОГ
    # ============================================================
    def _summarize(self, task: str, results: list) -> str:
        """Собирает результат по всем шагам."""
        if not results:
            return self._fallback_say(task)
        if len(results) == 1:
            return results[0]
        # Много шагов — соединяем
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r}")
        return "\n".join(lines)

    def _fallback_say(self, text: str) -> str:
        """Обычный ответ, если планирование не сработало."""
        if self.brain:
            try:
                return self.brain.ask(text)
            except Exception as e:
                _log.warning("fallback brain.ask: %s", e)
            try:
                return self.brain._local_fallback(text)
            except Exception:
                _log.debug("пропущено в core/agent.py (строка 189)")
        return "Я не понял. Повтори проще."