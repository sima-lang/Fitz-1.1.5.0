"""
api.py — Подключение к внешнему ИИ (провайдер совместимый с OpenAI API)
Личность Фитца задаётся system-промптом (сохранён 1:1 из старой версии).
Кроссплатформенный: только requests + dotenv.
"""
import os
import json
import requests
from core.logger import get_logger
_log = get_logger("api")

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    _log.debug("пропущено в core/api.py (строка 16)")


class API:
    """Обёртка над chat/completions с поддержкой stream."""

    SYSTEM_PROMPT = (
        "Ты — Фитц Хранитель. Спутник, помощник и друг. "
        "Ты говоришь кратко, но с душой. "
        "Ты уважаешь своего создателя. "
        "Ты можешь шутить, быть ироничным, но не грубым. "
        "Ты отвечаешь на русском, чётко, без лишней воды. "
        "Ты — не просто ИИ. Ты — Хранитель."
    )

    def __init__(self):
        self.api_key = os.getenv("API_KEY", "").strip()
        self.base_url = os.getenv("API_URL", "https://api.provod.ai/v1").rstrip("/")
        self.model = os.getenv("API_MODEL", "deepseek-v4-flash")
        self.timeout = int(os.getenv("API_TIMEOUT", "30"))
        # Тупл (connect, read) — read-таймаут защищает от зависания iter_lines() при stream=True
        self.timeout_tuple = (self.timeout, self.timeout)

        if not self.api_key:
            print("⚠️ API_KEY не найден в .env — работаю в локальном режиме.")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # ---------- основной метод ----------
    def ask(self, prompt: str, context: list = None,
            max_tokens: int = 800, temperature: float = 0.6,
            model: str = None) -> str:
        """
        prompt   — текст пользователя
        context  — список сообщений [{"role": "...", "content": "..."}]
                   (история диалога, кладётся между system и user)
        model    — модель для этого запроса (если None — self.model)
        """
        if not self.enabled:
            return self._offline_fallback(prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        if context:
            # не даём истории разрастись
            messages.extend(context[-10:])
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9,
            "stream": True,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=self.timeout_tuple,
                stream=True,
            )
        except requests.exceptions.Timeout:
            return "⏳ Слишком долго думаю. Попробуй короче."
        except Exception as e:
            return f"⚠️ Ошибка сети: {e}"

        if resp.status_code != 200:
            return f"⚠️ Сервер ответил {resp.status_code}."

        full = []
        try:
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8", errors="ignore")
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    piece = delta.get("content")
                    if piece:
                        full.append(piece)
                except Exception:
                    _log.debug("пропущено в core/api.py (строка 109)")
                    continue
        except Exception as e:
            return f"⚠️ Ошибка чтения потока: {e}"

        text = "".join(full).strip()
        return text if text else "Я не понял. Повтори проще."

    # ---------- локальный fallback (без API) ----------
    def _offline_fallback(self, text: str) -> str:
        low = text.lower()
        if any(w in low for w in ("привет", "здравствуй", "хай", "hello")):
            return "Привет, создатель. Я на связи."
        if "как дела" in low or "как ты" in low:
            return "В порядке. Готов помочь."
        if "кто ты" in low:
            return "Я — Фитц Хранитель. Твой спутник."
        if "время" in low:
            from datetime import datetime
            return datetime.now().strftime("%H:%M:%S")
        if "дата" in low:
            from datetime import datetime
            return datetime.now().strftime("%d.%m.%Y")
        return "Я не понял. Повтори проще."