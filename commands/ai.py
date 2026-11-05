"""
ai.py — Запомни / выучи / покажи факты.
Использует brain (knowledge) и memory.
"""
from core.logger import get_logger
_log = get_logger("ai")


def handle(text, memory, core):
    low = text.lower().strip()

    # ===== ЗАПОМНИ =====
    if low.startswith("запомни "):
        info = text[8:].strip()
        if not info:
            return "Что запомнить?"
        # кладём в knowledge
        try:
            core.add_knowledge("заметка", info)
        except Exception:
            _log.debug("пропущено в commands/ai.py (строка 22)")
        memory.log(f"📌 Запомнено: {info}")
        return f"🧠 Запомнил: {info}"

    # ===== ВЫУЧИ =====
    if low.startswith("выучи "):
        topic = text[6:].strip()
        if not topic:
            return "Что выучить?"
        try:
            response = core.ask(f"Кратко расскажи о теме: {topic}. 3–5 фактов, без воды.")
            core.add_knowledge(topic, response)
            memory.log(f"📚 Выучено: {topic}")
            return f"📚 Выучил '{topic}':\n{response}"
        except Exception as e:
            return f"⚠️ Ошибка: {e}"

    # ===== ЧТО ТЫ ЗНАЕШЬ О =====
    if low.startswith("что ты знаешь о "):
        topic = text[15:].strip()
        try:
            hits = core.search_knowledge(topic)
        except Exception:
            hits = []
        if hits:
            k = hits[0]
            return f"📚 {k.get('topic', topic)}:\n{k.get('content', '')}"
        # если нет — спросим ИИ
        try:
            return f"📚 {topic}:\n{core.ask(f'Кратко о {topic}')}"
        except Exception as e:
            return f"⚠️ {e}"

    # ===== ПОКАЖИ ФАКТЫ =====
    if low in ("покажи факты", "мои факты", "что ты запомнил", "мои знания"):
        knowledge = core.data.get("knowledge", [])
        if not knowledge:
            return "📭 Я пока ничего не запомнил"
        lines = ["📚 МОИ ЗНАНИЯ:"]
        for k in knowledge[-20:]:
            topic = k.get("topic", "?")
            content = (k.get("content", "") or "")[:80]
            lines.append(f"  • {topic}: {content}")
        return "\n".join(lines)

    # ===== ГОЛОС <имя> =====
    if low.startswith("голос "):
        name = text[6:].strip().lower()
        valid = ("xenia", "aidar", "baya", "kseniya", "eugene")
        if name in valid or name in ("ксения", "ксюша", "айдар", "бая", "евгений", "евгения"):
            # Русские имена → английские ключи
            ru_to_en = {
                "ксения": "xenia", "ксюша": "xenia",
                "айдар": "aidar",
                "бая": "baya",
                "евгений": "eugene", "евгения": "eugene",
            }
            speaker = ru_to_en.get(name, name)
            if core and getattr(core, "voice", None):
                result = core.voice.set_speaker(speaker)
                return result
            return f"🎤 Голос изменён на {speaker}"
        return f"❌ Голос «{name}» не найден. Доступны: xenia, aidar, baya, kseniya, eugene"

    return None