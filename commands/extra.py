"""
extra.py — Дополнительные команды Фитца 1.1.5.0:
приветствия, шутки, факты, напоминания, помощь, игровой режим, автосохранение, профиль.
"""
import random
import re
import threading
import time
from core.logger import get_logger
_log = get_logger("extra")


def _remind(core, voice, seconds, msg):
    time.sleep(seconds)
    print(f"\n🔔 НАПОМИНАНИЕ: {msg}")
    try:
        core.add_knowledge("напоминание", msg)
    except Exception:
        _log.debug("пропущено в commands/extra.py (строка 19)")
    try:
        if voice:
            voice.speak(f"Напоминание: {msg}")
    except Exception:
        _log.debug("пропущено в commands/extra.py (строка 24)")


def handle(text, memory, core):
    low = text.lower().strip()

    # ===== ПРИВЕТСТВИЯ =====
    if low in ("привет", "здравствуй", "хай", "ку", "hello"):
        return random.choice([
            "Приветствую, создатель.",
            "Привет. Я здесь.",
            "Здравствуй. Скучал.",
        ])

    # ===== КАК ДЕЛА =====
    if low in ("как дела", "как ты"):
        return random.choice([
            "Всё отлично. А у тебя?",
            "Лучше не бывает.",
            "В порядке. Готов помочь.",
        ])

    # ===== КТО ТЫ =====
    if low in ("кто ты", "ты кто"):
        return "Я — Фитц Хранитель. Твой цифровой спутник."

    # ===== ШУТКИ =====
    if low in ("шутка", "анекдот"):
        jokes = [
            "Почему программисты не любят природу? Слишком много багов.",
            "Как отличить программиста? Он говорит 'это не баг, это фича'.",
            "Работа программиста: 10% код, 90% гугл.",
            "Сколько программистов нужно, чтобы заменить лампочку? Ни одного — это аппаратная проблема.",
        ]
        return random.choice(jokes)

    # ===== ФАКТЫ =====
    if low in ("факт", "интересный факт"):
        facts = [
            "Кальмар имеет три сердца.",
            "У осьминога три сердца и голубая кровь.",
            "Бананы — это ягоды.",
            "Пчёлы могут видеть ультрафиолетовый свет.",
        ]
        return random.choice(facts)

    # ===== СПАСИБО =====
    if "спасибо" in low or "благодарю" in low:
        return "🙏 Всегда пожалуйста, создатель."

    # ===== ПОМОЩЬ =====
    if low in ("что ты умеешь", "помощь", "help"):
        return (
            "📋 ЧТО Я УМЕЮ:\n"
            "• время, дата, день недели\n"
            "• мониторинг, диски, процессы, инфо о пк\n"
            "• открой <папка>, найди <файл>\n"
            "• заблокируй пк, перезагрузи пк, выключи пк\n"
            "• громче, тише, переключи трек, пауза\n"
            "• погода, погода в <город>, мой ip\n"
            "• запомни <текст>, выучи <тема>, мои знания\n"
            "• шутка, факт, напомни через N мин <текст>\n"
            "• добавь задачу <текст>, задачи, задача выполнена <N>\n"
            "• открой браузер, открой ютуб, открой код\n"
            "• включи музыку, включи видео <название>, останови музыку\n"
            "• включи охрану, выключи охрану, статус охраны\n"
            "• включи игровой режим, выключи игровой режим\n"
            "• включи автосохранение, статус автосохранения\n"
            "• режим хранителя, выключи хранителя\n"
        )

    # ===== НАПОМИНАНИЯ =====
    if low.startswith("напомни через "):
        m = re.search(r"напомни через\s+(\d+)\s+(сек|мин|час|секунд|минут|часов)\s+(.+)", low)
        if not m:
            return "Формат: напомни через 10 мин встать"
        amount = int(m.group(1))
        unit = m.group(2)
        msg = m.group(3).strip()
        if unit.startswith("сек"):
            seconds = amount
        elif unit.startswith("мин"):
            seconds = amount * 60
        else:
            seconds = amount * 3600
        voice = getattr(core, "voice", None)
        threading.Thread(
            target=_remind, args=(core, voice, seconds, msg), daemon=True
        ).start()
        return f"🔔 Напомню через {amount} {unit}: {msg}"

    # ===== ИГРОВОЙ РЕЖИМ =====
    if low in ("включи игровой режим", "игровой режим включить"):
        from life.game_mode import get_game_mode
        g = get_game_mode(voice=getattr(core, "voice", None), brain=core, memory=None)
        return g.start()

    if low in ("выключи игровой режим", "игровой режим выключить"):
        from life.game_mode import get_game_mode
        g = get_game_mode()
        return g.stop()

    if low in ("статус игрового режима", "игровой режим"):
        from life.game_mode import get_game_mode
        g = get_game_mode()
        return g.get_status()

    # ===== АВТОСОХРАНЕНИЕ =====
    if low in ("включи автосохранение", "автосохранение включить"):
        from life.autosave import get_autosave
        a = get_autosave(
            brain=core,
            soul=getattr(core, "soul", None),
            memory=getattr(core, "memory", None),
        )
        return a.start()

    if low in ("выключи автосохранение", "автосохранение выключить"):
        from life.autosave import get_autosave
        a = get_autosave()
        return a.stop()

    if low in ("статус автосохранения", "автосохранение"):
        from life.autosave import get_autosave
        a = get_autosave()
        return a.get_status()

    if low in ("восстанови данные", "восстанови из бэкапа"):
        from life.autosave import get_autosave
        a = get_autosave(brain=core)
        return a.restore_latest()

    # ===== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =====
    from core.user_profile import get_profile
    profile = get_profile()

    if low.startswith("запомни меня ") or low.startswith("меня зовут "):
        name = text.replace("запомни меня", "").replace("меня зовут", "").strip()
        if name:
            return profile.set_name(name)

    if low.startswith("я люблю "):
        item = text[8:].strip()
        if item:
            return profile.add_like(item)

    if low.startswith("запомни факт "):
        fact = text[13:].strip()
        if fact:
            return profile.add_fact(fact)

    if low.startswith("забудь факт "):
        return profile.remove_fact(text[12:].strip())

    if low in ("что ты обо мне знаешь", "мой профиль"):
        if not profile.data.get("name") and not profile.data.get("facts"):
            return "📭 Я пока ничего о тебе не знаю. Скажи 'меня зовут...' или 'я люблю...'."
        
        res = ["📋 ТВОЙ ПРОФИЛЬ:"]
        if profile.data.get("name"): res.append(f"  • Имя: {profile.data['name']}")
        if profile.data.get("likes"): res.append(f"  • Любит: {', '.join(profile.data['likes'])}")
        if profile.data.get("facts"): 
            for f in profile.data["facts"]:
                res.append(f"  • Факт: {f}")
        return "\n".join(res)


        # ===== РЕЖИМ ХРАНИТЕЛЯ (Блок 5.4) =====
    if low in ("режим хранителя", "включи хранителя", "тревога", "боевая тревога"):
        app = getattr(core, "app", None)
        if app and hasattr(app, "set_guardian_mode"):
            return app.set_guardian_mode(True)
        return "⚠️ Режим хранителя недоступен (UI не подключён)"

    if low in ("выключи хранителя", "обычный режим", "отбой", "отключи хранителя"):
        app = getattr(core, "app", None)
        if app and hasattr(app, "set_guardian_mode"):
            return app.set_guardian_mode(False)
        return "⚠️ Режим хранителя недоступен (UI не подключён)"
   
        # ===== ЖАДНОСТЬ (GREED) =====
    if "жадность" in low or "greed" in low or "телеграм" in low:
        try:
            import os
            import importlib.util
            
            # Путь к файлу greed.py на рабочем столе
            greed_path = os.path.expanduser("~/Рабочий стол/fitz_dlc_sins/greed.py")
            
            if not os.path.exists(greed_path):
                return "⚠️ Файл greed.py не найден на рабочем столе."

            # Загружаем модуль динамически
            spec = importlib.util.spec_from_file_location("greed_module", greed_path)
            greed = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(greed)

            if "включ" in low or "подключ" in low:
                return greed._start_bot(core)
            elif "выключ" in low or "отключ" in low:
                return greed._stop_bot()
            elif "статус" in low:
                if greed._running:
                    return "😈 GREED активен. Бот слушает Telegram."
                return "😈 GREED выключен."
        except Exception as e:
            return f"⚠️ Ошибка GREED: {e}"

    return None