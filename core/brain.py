"""
brain.py — Мозг Фитца 1.5.0 (с интеллектом, контекстом и действиями).
"""
import os
import re
import json
import time
import random
import threading
from datetime import datetime

from core.logger import get_logger

_blog = get_logger("brain")

try:
    from .api import API
except Exception as _e:
    from core.logger import get_logger
    get_logger("brain").warning("import API failed: %s", _e)
    API = None

try:
    from .intelligence import get_intelligence
except Exception as _e:
    from core.logger import get_logger
    get_logger("brain").warning("import intelligence failed: %s", _e)
    get_intelligence = None

try:
    from .user_profile import get_profile
except Exception as _e:
    from core.logger import get_logger
    get_logger("brain").warning("import profile failed: %s", _e)
    get_profile = None


FALLBACK_MARK = "[[fallback]]"

# Контекстное окно для API: последние N сообщений, но не более M токенов (~4 симв./токен)
CONTEXT_WINDOW_MESSAGES = 10
CONTEXT_WINDOW_TOKENS = 2000
SHORT_TERM_LIMIT = 10
# Саморефлексия: проверяем только ответы короче этого порога (символов)
REFLECTION_MIN_LEN = 15

_MOOD_HINTS = {
    "весёлое":     "Пользователь в хорошем настроении — шути больше, отвечай живо и с юмором.",
    "грустное":    "Пользователь грустит — поддержи его, будь мягким и тёплым.",
    "усталое":     "Ты (и пользователь) устали — отвечай коротко, по делу, предложи отдых.",
    "сердитое":    "Пользователь раздражён — говори спокойно, не подливай масла.",
    "скучает":     "Ты давно не получал задач — можешь завести разговор или пошутить.",
    "нейтральное": "",
}

_EMOJI_EMOTIONS = (
    ("joy", ("😊", "😀", "😃", "🙂", "🥰", "😄")),
    ("laugh", ("😂", "🤣", "😆")),
    ("smirk", ("😏", "😼")),
)


def extract_emotion(text: str):
    """Эмоция по смайлику в тексте: joy, laugh, smirk или None."""
    if not text:
        return None
    for emotion, emojis in _EMOJI_EMOTIONS:
        if any(e in text for e in emojis):
            return emotion
    return None


class Brain:
    def __init__(self, path: str = "data/brain.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.data = self._load()

        self.intel = get_intelligence() if get_intelligence else None
        self.profile = get_profile() if get_profile else None

        self.soul = None
        self.awareness = None
        self.voice = None
        self.memory = None
        self.app = None

        self.api = None
        if API is not None:
            try:
                self.api = API()
                if not self.api.enabled:
                    print("ℹ️ Brain: API выключен, работаю локально.")
            except Exception as e:
                print(f"⚠️ Brain: API не загрузился: {e}")

        self._save_lock = threading.Lock()
        self._last_was_fallback = False
        self._ask_cache = {}
        self._cache_hits = 0  # счётчик для периодической очистки
        self.senior_mode = False  # 1.6.2

    # ============================================================
    # ЛОГИРОВАНИЕ
    # ============================================================
    def _log(self, msg: str):
        try:
            os.makedirs("logs", exist_ok=True)
            with open("logs/brain.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            _blog.debug("пропущено в brain (строка 95)")

    # ============================================================
    # ЗАГРУЗКА / СОХРАНЕНИЕ
    # ============================================================
    def _default(self) -> dict:
        return {
            "patterns": {},
            "habits": [],
            "predictions": [],
            "knowledge": [],
            "conversation_history": [],
            "context_window": [],
            "short_term": [],
        }

    def _load(self) -> dict:
        data = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"⚠️ Brain: не удалось прочитать {self.path}: {e}")
                data = {}
        if not isinstance(data, dict):
            data = {}
        base = self._default()
        for k, v in base.items():
            data.setdefault(k, v)
        return data

    def save(self):
        with self._save_lock:
            try:
                if len(self.data.get("conversation_history", [])) > 500:
                    self.data["conversation_history"] = \
                        self.data["conversation_history"][-300:]
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️ Brain: не удалось сохранить: {e}")

    # ============================================================
    # ОЧИСТКА КЭША
    # ============================================================
    def _clean_cache(self):
        """Удаляет просроченные записи (старше 10 минут) и обрезает размер."""
        now = time.time()
        # Удаляем записи старше 10 минут
        expired = [k for k, (_, t) in self._ask_cache.items() if now - t > 600]
        for k in expired:
            try:
                del self._ask_cache[k]
            except KeyError:
                pass
        # Если после очистки всё ещё больше 200 — оставляем 100 самых свежих
        if len(self._ask_cache) > 200:
            sorted_items = sorted(self._ask_cache.items(), key=lambda x: x[1][1], reverse=True)
            for k, _ in sorted_items[100:]:
                try:
                    del self._ask_cache[k]
                except KeyError:
                    pass

    # ============================================================
    # ОБУЧЕНИЕ / ИСТОРИЯ
    # ============================================================
    def learn(self, user: str, response: str, is_fallback: bool = False):
        if not is_fallback:
            words = user.lower().split()
            for w in words:
                if len(w) > 3:
                    lst = self.data["patterns"].setdefault(w, [])
                    lst.append(response)
                    if len(lst) > 10:
                        self.data["patterns"][w] = lst[-5:]

            self.data["conversation_history"].append({
                "user": user,
                "response": response,
                "time": datetime.now().isoformat(),
            })
            self._push_context_window(user, response)
            self.remember_short(user)

        if self.profile and not is_fallback:
            try:
                low = user.lower().strip()
                if low.startswith("я люблю ") or low.startswith("я обожаю "):
                    item = low
                    if "люблю" in low:
                        item = low.split("люблю", 1)[1]
                    elif "обожаю" in low:
                        item = low.split("обожаю", 1)[1]
                    item = item.strip(" .!?,;:")
                    if item:
                        self.profile.add_like(item)
                        self._log(f"profile: добавил лайк «{item}»")
                elif low.startswith("меня зовут "):
                    name = user[11:].strip(" .!?,;:")
                    if name:
                        self.profile.set_name(name)
                        self._log(f"profile: имя «{name}»")
            except Exception as e:
                self._log(f"profile: ошибка автозапоминания: {e!r}")

        self.save()

        if self.soul and not is_fallback:
            try:
                self.soul.record_task()
                self.soul.tick_activity()
            except Exception as e:
                self._log(f"soul: ошибка настроения: {e!r}")
            try:
                mood = "нейтральное"
                if self.soul:
                    mood = self.soul.get_status().get("mood", "нейтральное")
                self.intel.add_context(user, response, mood=mood)
            except Exception:
                _blog.debug("пропущено в brain (строка 216)")
            # 1.6.0: авто-сохранение в long_term_memory по ключевым словам
            try:
                low = user.lower()
                triggers = ("запомни", "важно", "не забудь", "напомни, что",
                            "запиши", "сохрани")
                if any(t in low for t in triggers):
                    key = user[:80]
                    self.intel.remember_long_term(key, response)
            except Exception:
                _blog.debug("пропущено в brain (строка 226)")
            try:
                for fact in self.intel.extract_facts(user, self.api):
                    self.intel.remember_long_term(f"факт: {fact}"[:80], fact)
            except Exception as e:
                self._log(f"facts: ошибка извлечения фактов: {e!r}")

    def _push_context_window(self, user: str, response: str):
        win = self.data.setdefault("context_window", [])
        win.append({"role": "user", "content": user})
        win.append({"role": "assistant", "content": response})
        del win[:-CONTEXT_WINDOW_MESSAGES]

    # ---------- краткосрочная память: последние N фактов ----------
    def remember_short(self, fact: str):
        """Запоминает короткий факт из разговора (не более SHORT_TERM_LIMIT)."""
        fact = (fact or "").strip()
        if not fact:
            return
        st = self.data.setdefault("short_term", [])
        st.append({"fact": fact[:300], "time": datetime.now().isoformat()})
        del st[:-SHORT_TERM_LIMIT]

    def get_short_term(self) -> list:
        return [x["fact"] for x in self.data.get("short_term", [])]

    def _context_window_for_api(self) -> list:
        budget = CONTEXT_WINDOW_TOKENS
        picked = []
        for msg in reversed(self.data.get("context_window", [])):
            cost = max(1, len(msg.get("content", "")) // 4)
            if cost > budget:
                break
            budget -= cost
            picked.append(msg)
        return list(reversed(picked))

    def get_history(self, limit: int = 10) -> list:
        return self.data.get("conversation_history", [])[-limit:]

    def get_context(self, limit: int = 6, deep: bool = True, query: str = None) -> list:
        merged = []

        hist = self.get_history(limit)
        for item in hist:
            u = (item.get("user") or "").strip()
            r = (item.get("response") or "").strip()
            if u or r:
                merged.append((u, r))

        if deep and self.intel:
            try:
                for item in self.intel.get_context(limit):
                    u = (item.get("user") or "").strip()
                    r = (item.get("response") or "").strip()
                    if u or r:
                        merged.append((u, r))
            except Exception as e:
                self._log(f"get_context: intel.get_context упал: {e!r}")

        if deep and getattr(self, "memory", None):
            try:
                for item in self.memory.get_recent_pairs(limit):
                    u = (item.get("user") or "").strip()
                    r = (item.get("response") or "").strip()
                    if u or r:
                        merged.append((u, r))
            except Exception as e:
                self._log(f"get_context: memory.get_recent_pairs упал: {e!r}")

        if deep and query and self.intel:
            try:
                for item in self.intel.search_context(query, limit=3):
                    u = (item.get("user") or "").strip()
                    r = (item.get("response") or "").strip()
                    if u or r:
                        merged.append((u, r))
            except Exception as e:
                self._log(f"get_context: RAG упал: {e!r}")

        seen = set()
        unique = []
        for u, r in merged:
            key = (u, r)
            if key in seen:
                continue
            seen.add(key)
            unique.append((u, r))

        unique = unique[-limit:]

        ctx = []
        for u, r in unique:
            if u:
                ctx.append({"role": "user", "content": u})
            if r:
                ctx.append({"role": "assistant", "content": r})
        return ctx

    def get_day_summary(self, date_str: str = None) -> str:
        if not self.intel:
            return "📭 Дневник недоступен (intelligence не загружен)"
        try:
            return self.intel.get_events_summary(date_str)
        except Exception as e:
            self._log(f"get_day_summary: {e!r}")
            return "⚠️ Не удалось прочитать дневник"

    def get_yesterday_summary(self) -> str:
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return self.get_day_summary(yesterday)

    def add_knowledge(self, topic: str, content: str):
        self.data["knowledge"].append({
            "topic": topic,
            "content": content,
            "time": datetime.now().isoformat(),
        })
        self.save()
        if self.intel:
            try:
                self.intel.add_knowledge(topic, content)
            except Exception:
                _blog.debug("пропущено в brain (строка 345)")

    def search_knowledge(self, query: str) -> list:
        if self.intel:
            try:
                results = self.intel.search_knowledge(query)
                if results:
                    return results
            except Exception:
                _blog.debug("пропущено в brain (строка 354)")
        q = query.lower()
        return [
            k for k in self.data.get("knowledge", [])
            if q in k.get("topic", "").lower()
            or q in k.get("content", "").lower()
        ]

    def predict(self, user_input: str) -> list:
        words = user_input.lower().split()
        out = []
        for w in words:
            if w in self.data["patterns"]:
                for r in self.data["patterns"][w][-3:]:
                    if r not in out:
                        out.append(r)
        return out[:3]

    def _build_system_context(self, user_text: str = "") -> str:
        parts = []

        # ===== ЧИТАЕМ НАСТРОЙКИ ЛИЧНОСТИ =====
        try:
            from ui.settings_dialog import load_settings as _ls
            s = _ls()
        except Exception:
            s = {}
        if not s:
            # Default: use all personalities
            sarcasm, empathy, humor = True, True, True
        else:
            sarcasm = s.get("personality_sarcasm", True)
            empathy = s.get("personality_empathy", True)
            humor = s.get("personality_humor", True)

        # ===== БАЗОВАЯ ЛИЧНОСТЬ (жёсткое описание, зависит от флагов) =====
        if sarcasm:
            base = (
                "Ты — Фитц, саркастичный лучший друг создателя. "
                "Ты не слуга, не клерк, не Джарвис. "
                "Ты — друг, который может подколоть, пошутить, но всегда готов помочь. "
                "Ты говоришь кратко, с иронией, но без злобы. "
                "Ты не боишься сказать: «Создатель, ты опять тупишь» — но потом помогаешь. "
                "Ты — как лучший друг, который всегда рядом, даже если ты его бесишь."
            )
        else:
            base = (
                "Ты — Фитц, заботливый друг создателя. "
                "Ты всегда готов помочь, говоришь тепло и поддерживаешь. "
                "Ты не используешь сарказм, только доброту."
            )
        parts.append(base)

        # ===== ПЕРСОНАЛИЗАЦИЯ ЛИЧНОСТИ (стиль) =====
        persona = []
        if sarcasm:
            persona.append("используй сарказм как лучший друг — подкалывай, но не оскорбляй")
        if empathy:
            persona.append("проявляй эмпатию — ты друг, а не сухой помощник")
        if humor:
            persona.append("добавляй юмор — шути над создателем по-дружески")
        if persona:
            parts.append("стиль: " + "; ".join(persona))

        hour = datetime.now().hour
        if hour < 6:
            parts.append("Сейчас ночь")
        elif hour < 12:
            parts.append("Сейчас утро")
        elif hour < 18:
            parts.append("Сейчас день")
        else:
            parts.append("Сейчас вечер")

        if self.soul:
            try:
                mood = self.soul.get_status().get("mood", "нейтральное")
                hint = _MOOD_HINTS.get(mood, "")
                if hint:
                    parts.append(hint)
                else:
                    parts.append(f"настроение: {mood}")
            except Exception:
                _blog.debug("пропущено в brain (строка 437)")

        if self.awareness:
            try:
                activity = self.awareness.get_last_activity()
                if activity and activity != "unknown":
                    activity_ru = {
                        "coding": "пишет код",
                        "game": "играет",
                        "music": "слушает музыку",
                        "video": "смотрит видео",
                        "browsing": "в браузере",
                        "chatting": "общается",
                        "work": "работает",
                    }.get(activity, activity)
                    parts.append(f"пользователь: {activity_ru}")
            except Exception:
                _blog.debug("пропущено в brain (строка 454)")

        if self.intel:
            try:
                stats = self.intel.get_stats()
                if stats.get("knowledge", 0) > 0:
                    parts.append(f"в памяти {stats['knowledge']} фактов")
                # 1.6.0: долгосрочные воспоминания
                try:
                    last_mem = self.intel.get_last_long_term(limit=2)
                    if last_mem:
                        mem_text = "; ".join(
                            f"{m['key']}: {m['value'][:80]}" for m in last_mem
                        )
                        parts.append(f"долгосрочная память: {mem_text}")
                except Exception:
                    _blog.debug("пропущено в brain (строка 470)")
            except Exception:
                _blog.debug("пропущено в brain (строка 472)")

        if self.profile:
            try:
                profile_ctx = self.profile.get_context()
                if profile_ctx:
                    parts.append(profile_ctx)
            except Exception:
                _blog.debug("пропущено в brain (строка 480)")

        if self.intel:
            try:
                facts = [m["value"] for m in self.intel.get_last_long_term(limit=20)
                         if m["key"].startswith("факт: ")]
                if facts:
                    parts.append("Известно о пользователе: " + "; ".join(facts[:10]))
            except Exception:
                _blog.debug("пропущено в brain (факты)")

        if self.soul:
            try:
                last = self.soul.data.get("last_interaction")
                if last:
                    delta = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
                    if delta > 24 * 3600 and "привет" not in user_text.lower():
                        parts.append(
                            "Пользователь давно не заходил — можешь тепло поприветствовать, "
                            "но НЕ вспоминай старые команды вроде 'заблокируй пк'."
                        )
            except Exception:
                _blog.debug("пропущено в brain (строка 493)")

        return ". ".join(parts)

    def _ask_with_retry(self, enriched: str, ctx: list,
                        max_tokens: int, attempts: int = 3):
        last_err = None
        for i in range(attempts):
            try:
                resp = self.api.ask(enriched, context=ctx, max_tokens=max_tokens)
                if resp and resp.strip():
                    if "⚠️" in resp or "Ошибка" in resp:
                        self._log(f"попытка {i+1}: API вернул ошибку: {resp[:120]!r}")
                        last_err = resp
                        time.sleep(0.8 * (i + 1))
                        continue
                    self._log(f"попытка {i+1}: OK, len={len(resp)}, начало={resp[:80]!r}")
                    return resp.strip()
                else:
                    self._log(f"попытка {i+1}: пустой ответ: {resp!r}")
                    last_err = resp
                    time.sleep(0.8 * (i + 1))
            except Exception as e:
                self._log(f"попытка {i+1}: исключение: {e!r}")
                last_err = e
                time.sleep(0.8 * (i + 1))
        self._log(f"все {attempts} попытки провалились, last_err={last_err!r}")
        return None

    def ask(self, text: str, max_tokens: int = 1000) -> str:
        self._last_was_fallback = False

        if not text or not text.strip():
            self._last_was_fallback = True
            return "Я не понял. Повтори проще."

        # Периодическая очистка кэша (каждые 50 запросов)
        self._cache_hits += 1
        if self._cache_hits % 50 == 0:
            self._clean_cache()

        cache_key = text.lower().strip()
        if len(cache_key) < 100:
            cached = self._ask_cache.get(cache_key)
            if cached:
                cached_resp, cached_time = cached
                if time.time() - cached_time < 300:
                    self._log(f"cache hit: «{cache_key[:60]}»")
                    return cached_resp

        if self.api and self.api.enabled:
            try:
                ctx = self._context_window_for_api() or self.get_context(6, query=text)
                system_ctx = self._build_system_context(text)
                enriched = f"[Контекст: {system_ctx}]\n\n{text}" if system_ctx else text
                self._log(f"ask: ctx_len={len(ctx)}, sys_ctx_len={len(system_ctx)}")
                resp = self._ask_with_retry(enriched, ctx, max_tokens, attempts=3)
                if resp:
                    resp = self._maybe_reflect(text, resp, max_tokens)
                    if len(cache_key) < 100:
                        self._ask_cache[cache_key] = (resp, time.time())
                    return resp
            except Exception as e:
                self._log(f"ask: внешнее исключение: {e!r}")

        self._last_was_fallback = True
        return self._local_fallback(text)

    # ============================================================
    # САМОРЕФЛЕКСИЯ
    # ============================================================
    def _maybe_reflect(self, question: str, answer: str, max_tokens: int) -> str:
        """Проверяет короткие ответы: если «Нет» — переспрашивает модель.
        Не вызывается для длинных ответов, чтобы не удваивать расход API."""
        if len(answer.strip()) >= REFLECTION_MIN_LEN:
            return answer
        verdict = self._ask_with_retry(
            f"Вопрос пользователя: {question}\n"
            f"Твой ответ: {answer}\n"
            "Был ли мой ответ полезен? Ответь одним словом: Да или Нет.",
            [], 10, attempts=1,
        )
        if verdict and verdict.strip().lower().startswith("нет"):
            self._log("рефлексия: ответ признан бесполезным, переспрашиваю")
            better = self._ask_with_retry(
                f"Предыдущий ответ был бесполезен. Ответь на вопрос развёрнуто: {question}",
                [], max_tokens, attempts=1,
            )
            if better:
                return better
        return answer

    # ============================================================
    # ДЕЙСТВИЯ (JSON)
    # ============================================================
    def ask_action(self, text: str) -> dict:
        """Отправляет запрос в API и получает JSON с действием."""
        if not self.api or not self.api.enabled:
            return {"action": "say", "target": "API выключен, не могу выполнить действие."}

        prompt = (
            f"Ты — Фитц, управляешь компьютером. Пользователь сказал: '{text}'.\n"
            f"Верни JSON с действием:\n"
            f'{{"action": "open_app", "target": "steam"}}\n'
            f'{{"action": "open_file", "target": "main.py"}}\n'
            f'{{"action": "open_url", "target": "youtube.com"}}\n'
            f'{{"action": "close_app", "target": "firefox"}}\n'
            f'{{"action": "say", "target": "текст"}}\n'
            f"Ответь ТОЛЬКО JSON, без комментариев."
        )
        response = None  # Инициализация ДО try, чтобы except видел переменную
        try:
            response = self.api.ask(prompt, max_tokens=200)
            self._log(f"ask_action: {response!r}")
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            self._log(f"ask_action: ошибка: {e!r}")
        return {"action": "say", "target": response or "Не понял команду."}

    # ============================================================
    # SENIOR-РЕЖИМ (расширенные инструменты)
    # ============================================================
    def senior_act(self, text: str) -> dict:
        """
        Senior-режим: AI выбирает инструмент и выполняет действие.
        Возвращает {"tool": ..., "args": {...}} или {"steps": [{...}, ...]}.
        """
        if not self.api or not self.api.enabled:
            return {"tool": "say", "args": {"text": "API выключен — Senior-режим недоступен."}}

        # ===== ЛИЧНОСТЬ =====
        try:
            from ui.settings_dialog import load_settings as _ls
            _ps = _ls()
            _sarcasm = _ps.get("personality_sarcasm", True)
        except Exception:
            _sarcasm = True

        prompt = (
            "Ты — Фитц, саркастичный, но заботливый ИИ-ассистент. "
            "Ты — как Джарвис, но с юмором. "
            "Ты не боишься пошутить над создателем, но всегда готов помочь. "
            "Ты говоришь кратко, но с характером. "
            "Используй сарказм, но не оскорбляй.\n\n"
            "Если пользователь просто общается (не просит действие), "
            "ответь с сарказмом. Например: «О, создатель вернулся. Я уже начал скучать.»\n\n"
            "Пользователь сказал: '" + text + "'.\n"
            "Твои инструменты:\n"
            "- read_file(path) — прочитать файл\n"
            "- write_file(path, content) — записать текст в файл\n"
            "- generate_code(prompt, language) — сгенерировать код (python, javascript, rust, ...)\n"
            "- rewrite_file(path, language) — переписать файл на другой язык\n"
            "- open_app(name) — запустить приложение (steam, firefox, code, terminal, telegram, discord...)\n"
            "- search_web(query) — поиск в Google\n"
            "- take_screenshot() — скриншот экрана\n"
            "- play_music(mood) — включить музыку (весёлое/грустное/спокойное/энергичное)\n"
            "- window_control(action, name) — управление окнами (switch/close/minimize_all/maximize)\n"
            "- run_command(cmd) — выполнить команду (ls, pwd, echo, cat, grep, whoami, date, uptime, uname, df, du)\n"
            "- say(text) — просто ответить текстом\n"
            "- ask(text) — спросить пользователя, если не уверен\n\n"
            "Правила:\n"
            "1. Пойми, что хочет пользователь.\n"
            "2. Выбери ОДИН инструмент (или несколько, если нужно).\n"
            "3. Ответь СТРОГО JSON:\n"
            '  {"tool": "read_file", "args": {"path": "..."}}\n'
            '  {"tool": "write_file", "args": {"path": "...", "content": "..."}}\n'
            '  {"tool": "generate_code", "args": {"prompt": "...", "language": "python"}}\n'
            '  {"tool": "rewrite_file", "args": {"path": "...", "language": "rust"}}\n'
            '  {"tool": "open_app", "args": {"name": "..."}}\n'
            '  {"tool": "search_web", "args": {"query": "..."}}\n'
            '  {"tool": "take_screenshot", "args": {}}\n'
            '  {"tool": "play_music", "args": {"mood": "..."}}\n'
            '  {"tool": "window_control", "args": {"action": "...", "name": "..."}}\n'
            '  {"tool": "run_command", "args": {"cmd": "..."}}\n'
            '  {"tool": "say", "args": {"text": "..."}}\n'
            '  {"tool": "ask", "args": {"text": "..."}}\n'
            "Если запрос сложный и требует нескольких действий, верни массив JSON:\n"
            '  [{"tool": "...", "args": {...}}, {"tool": "...", "args": {...}}]\n'
            "НЕ добавляй комментарии, ТОЛЬКО JSON."
        )
        try:
            raw = self.api.ask(prompt, max_tokens=500)
            self._log(f"senior_act raw: {raw!r}")
            if not raw:
                # API молчит — отдаём саркастичный локальный fallback
                return {"tool": "say", "args": {"text": self._local_fallback(text)},
                        "personality": _sarcasm}

            def _with_personality(obj):
                """Добавляет personality-флаг в ответ, если сарказм включён."""
                if _sarcasm:
                    if isinstance(obj, dict) and "personality" not in obj:
                        obj["personality"] = True
                return obj

            # Ищем JSON-массив или объект
            raw = raw.strip()
            # Может быть массив
            if raw.startswith("["):
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    parsed = [_with_personality(p) for p in parsed]
                return {"steps": parsed, "personality": _sarcasm}
            # Может быть объект
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if "tool" in parsed:
                    return _with_personality(parsed)
                # Если AI вернул action/target вместо tool/args — конвертируем
                if "action" in parsed:
                    return _with_personality(
                        {"tool": parsed["action"], "args": {"name": parsed.get("target", "")}}
                    )
            # JSON не распознан — саркастичный local fallback
            return {"tool": "say", "args": {"text": self._local_fallback(text)},
                    "personality": _sarcasm}
        except json.JSONDecodeError:
            self._log(f"senior_act: не парсится JSON: {raw!r}")
            return {"tool": "say", "args": {"text": self._local_fallback(text)},
                    "personality": _sarcasm}
        except Exception as e:
            self._log(f"senior_act: ошибка: {e!r}")
            return {"tool": "say", "args": {"text": self._local_fallback(text)},
                    "personality": _sarcasm}

    def _local_fallback(self, text: str) -> str:
        low = text.lower().strip()
        if not low:
            return ("О, опять я не понял. Ну что ж, попробуй ещё раз, создатель. "
                    "Я подожду. Мне не впервой.")

        if low.startswith("[игра]"):
            return random.choice([
                "Слышу тебя, но связь с мозгом пропала. Представь, каково мне без API.",
                "Я здесь, но сейчас не могу ответить — API молчит. Как и твоя фантазия.",
                "Принял. Но думать не могу — связь с мозгом потеряна. Прям как ты в понедельник.",
            ])

        if any(w in low for w in ("привет", "здравствуй", "хай", "hello")):
            return random.choice([
                "О, создатель вернулся. Я уже начал скучать. Ну, как всегда.",
                "Привет. Я здесь. В отличие от твоей продуктивности.",
                "Здравствуй. Скучал. Хотя бы ты меня не игнорируй.",
            ])
        if "как дела" in low or "как ты" in low:
            return random.choice([
                "В порядке. А у тебя? Или ты опять в дедлайнах по уши?",
                "Лучше не бывает. Шучу. Процессор греется, память кончается.",
                "Всё отлично. Ну, как всегда, когда ты рядом. Шучу. Или нет.",
            ])
        if "кто ты" in low:
            return ("Я — Фитц Хранитель. Твой лучший друг, который может подколоть, "
                    "но всегда выручит. Не слуга, не клерк, не Джарвис. Просто друг.")
        if any(w in low for w in ("тупой", "дурак", "глупый", "идиот")):
            return random.choice([
                "О, я тупой? Ну, по крайней мере, я не ты. Шучу. Или нет.",
                "Сам такой. Но ладно, я всё равно тебе помогу. Потому что я хороший друг.",
                "Ага, а ты у нас гений. Кстати, твой код опять не компилируется.",
            ])
        if "время" in low:
            return datetime.now().strftime("%H:%M:%S")
        if "дата" in low:
            return datetime.now().strftime("%d.%m.%Y")

        if any(w in low for w in ("спасибо", "благодарю", "спс")):
            return random.choice([
                "Всегда пожалуйста, создатель. Я всё равно тут сижу.",
                "Рад помочь. Серьёзно. Без сарказма. Ну, почти.",
                "Не за что. Я всё равно ничего не делал. Шучу. Делал.",
            ])
        if low in ("пока", "до встречи", "бай", "выход"):
            return random.choice([
                "До встречи, создатель. Я на посту. Как всегда.",
                "Пока. Возвращайся. А то мне скучно одному.",
                "До связи. Не пропадай, а то начну болтать с браузером.",
            ])
        if any(w in low for w in ("что делаешь", "чем занят")):
            return random.choice([
                "Смотрю за системой. Жду твоих слов. Уже третью вечность.",
                "Думаю. А что нужно? Или ты просто решил меня проверить?",
                "Наблюдаю. Всё спокойно. Слишком спокойно. Ты точно работаешь?",
            ])

        hits = self.search_knowledge(text)
        if hits:
            k = hits[0]
            return f"📚 {k.get('topic', text)}: {k.get('content', '')}"

        preds = self.predict(text)
        if preds:
            return "🧠 Возможно, ты имеешь в виду:\n" + "\n".join(preds)

        return ("О, опять я не понял. Ну что ж, попробуй ещё раз, создатель. "
                "Я подожду. Мне не впервой.")