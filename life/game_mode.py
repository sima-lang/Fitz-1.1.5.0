"""
game_mode.py — Игровой режим Фитца.
Кроссплатформенно: psutil (процессы) + voice.
Реагирует на игры, игнорирует лаунчеры и системные процессы.
"""
import time
import random
import threading
from core.logger import get_logger
_log = get_logger("game_mode")

try:
    import psutil
except Exception:
    psutil = None


class GameMode:
    def __init__(self, voice=None, brain=None, memory=None, fact_interval: int = 600):
        self.voice = voice
        self.brain = brain
        self.memory = memory
        self.fact_interval = fact_interval

        self.running = False
        self.current_game = None
        self.last_fact_time = 0
        self._thread = None

        # ===== СПИСОК ИГР =====
        # ВАЖНО: используем точные имена процессов (без .exe),
        # чтобы не было ложных срабатываний на подстроки.
        self.games = [
            # Шутеры
            "cs2", "csgo", "valorant", "apex", "apexlegends",
            "overwatch", "overwatch2", "pubg", "fortnite",
            "rainbowsix", "r6s", "callofduty", "modernwarfare",
            "warzone", "battlefield", "bf1", "bf4", "bf5", "bf2042",
            "halo", "doom", "doometernal", "quake", "titanfall",
            "destiny2", "warframe", "division", "division2",
            "escapefromtarkov", "rust", "ark", "dayz",
            # MOBA / RTS
            "dota2", "leagueoflegends", "lol", "hots",
            "starcraft", "starcraft2", "warcraft", "warcraft3",
            "ageofempires", "aoe2", "aoe4", "totalwar",
            "civilization", "civ5", "civ6", "stellaris",
            "frostpunk", "anno1800", "citiesskylines", "simcity",
            # RPG
            "cyberpunk2077", "witcher3", "skyrim", "fallout4",
            "fallout76", "starfield", "elderscrolls",
            "baldursgate3", "bg3", "divinity", "pillarsofeternity",
            "discoelysium", "dragonage", "masseffect",
            "kotor", "starwarsjedi", "hogwartslegacy",
            "persona5", "finalfantasy", "ff14", "ff7",
            "nierautomata", "monsterhunter", "monsterhunterworld",
            "darksouls", "darksouls3", "sekiro", "eldenring",
            "bloodborne", "nioh",
            # Хоррор
            "residentevil", "re2", "re3", "re4", "re7", "re8",
            "silenthill", "deadspace", "outlast", "amnesia",
            "phasmophobia", "lethalcompany", "fnaf",
            # Выживание
            "minecraft", "terraria", "valheim", "conanexiles",
            "7daystodie", "projectzomboid", "dontstarve",
            "theforest", "raft", "subnautica", "nomanssky",
            "astroneer", "satisfactory", "factorio", "rimworld",
            "kenshi", "mountandblade", "bannerlord",
            # Песочницы
            "gmod", "garrysmod", "roblox", "stardewvalley",
            "sims4", "planetcoaster", "planetzoo",
            # Гонки
            "forzahorizon", "forzahorizon5", "forzamotorsport",
            "needforspeed", "nfs", "assettocorsa", "iracing",
            "dirt", "dirtrally", "eurotrucks2", "beamng",
            "wreckfest", "snowrunner",
            # Симуляторы
            "microsoftflightsimulator", "msfs", "xplane",
            "dcs", "farmingsimulator", "fs22", "fs25",
            "houseflipper", "powerwash",
            # Спорт
            "fifa", "fc24", "fc25", "eafc", "efootball",
            "nba2k", "madden", "nfl", "nhl", "mlb",
            "rocketleague", "f1", "f12023", "f12024",
            "wwe", "wwe2k", "ufc",
            # Стратегии
            "xcom", "xcom2", "intothebreach", "ftl",
            "slaythespire", "darkestdungeon", "battlebrothers",
            "fireemblem", "tactics", "finalfantasytactics",
            # Платформеры / экшен
            "hollowknight", "celeste", "cuphead", "ori",
            "rayman", "crash", "spyro", "sonic", "mario",
            "zelda", "metroid", "deadcells", "hades",
            "bindingofisaac", "riskofrain", "vampiresurvivors",
            "brotato",
            # MMO
            "worldofwarcraft", "wow", "ffxiv", "guildwars",
            "blackdesert", "lostark", "neworld", "runescape",
            "osrs", "eveonline", "albion",
            "starwarstheoldrepublic", "swtor",
            # Карточные
            "hearthstone", "magic", "mtg", "mtgarena",
            "legendsofruneterra", "gwent", "yugioh", "balatro",
            # Инди / весёлые
            "amongus", "fallguys", "humanfallflat",
            "gangbeasts", "overcooked", "movingout",
            "ittakestwo", "contentwarning", "jackbox",
            "gartic",
            # Визуальные новеллы
            "danganronpa", "aceattorney", "persona",
            "steinsgate", "clannad", "fate", "umineko",
            "higurashi",
            # Общее / сборники
            "gta5", "gtaonline", "gtasa", "gtavc", "gta3",
            "rdr2", "mafia", "saintsrow", "watchdogs",
            "justcause", "hitman", "assassinscreed",
            "farcry", "tombraider", "uncharted",
            "horizon", "spiderman", "godofwar",
            "lastofus", "ghostoftsushima", "daysgone",
            "deathstranding", "control", "alanwake",
            "maxpayne", "bully", "lanoire",
            "mortalkombat", "mk1", "mk11", "injustice",
            "tekken", "streetfighter", "guiltygear",
            "dragonballfighterz", "narutostorm4", "smashbros",
        ]

        # ===== ЛАУНЧЕРЫ (игнорируем) =====
        self.launchers = [
            "steam", "steamwebhelper", "epicgameslauncher",
            "origin", "goggalaxy", "battlenet",
            "ubisoftconnect", "uplay", "eaapp", "eadesktop",
        ]

        # ===== СИСТЕМНЫЕ ПРОЦЕССЫ (игнорируем) =====
        self.system_processes = {
            "system", "system idle", "svchost", "explorer",
            "gnome-shell", "gnome-terminal", "bash", "zsh",
            "python", "python3", "code", "firefox", "chrome",
            "chromium", "opera", "discord", "telegram",
            "xdg-desktop-portal", "xdg-desktop-portal-gtk",
            "xdg-desktop-portal-gnome", "xdg-document-portal",
            "pulseaudio", "pipewire", "wireplumber",
            "gdbus", "dbus-daemon", "systemd", "gnome-software",
        }

        self.greetings = [
            "Отличный выбор! Удачи в игре, создатель. 🎮",
            "О, знакомая игра! Приятной сессии.",
            "Запустил игру? Я рядом. 🛡️",
            "Удачи! Если что — зови.",
            "Играешь? Не отвлекаю, просто желаю победы. 🔥",
        ]

        self.farewells = [
            "Хорошая была сессия. Отдохни.",
            "До встречи. Ты молодец.",
            "Игра окончена. Я на посту.",
        ]

    def start(self) -> str:
        if psutil is None:
            return "⚠️ psutil не установлен — game mode недоступен"
        if self.running:
            return "🎮 Игровой режим уже активен"
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return "🎮 Игровой режим активирован"

    def stop(self) -> str:
        self.running = False
        return "⏹️ Игровой режим выключен"

    def _loop(self):
        while self.running:
            try:
                game = self._detect_game()
                if game and game != self.current_game:
                    self.current_game = game
                    print(f"🎮 Обнаружена игра: {game}")
                    self._on_game_start(game)
                elif game and game == self.current_game:
                    now = time.time()
                    if now - self.last_fact_time > self.fact_interval:
                        self.last_fact_time = now
                        self._say_fact(game)
                elif not game and self.current_game:
                    print(f"🎮 Игра {self.current_game} завершена")
                    self._on_game_end()
                    self.current_game = None
                time.sleep(10)
            except Exception as e:
                print(f"⚠️ GameMode: {e}")
                time.sleep(15)

    def _detect_game(self):
        """Определяет РЕАЛЬНУЮ игру по точному имени процесса."""
        if psutil is None:
            return None
        try:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info.get("name") or "").lower()
                if not name:
                    continue
                # системные — пропускаем
                if name in self.system_processes:
                    continue
                # лаунчеры — пропускаем
                if any(l in name for l in self.launchers):
                    continue
                # игры: точное совпадение или game.exe / game_x
                for g in self.games:
                    g_low = g.lower()
                    if name == g_low or name == g_low + ".exe":
                        return g.capitalize()
                    if name.startswith(g_low + ".") or name.startswith(g_low + "_"):
                        return g.capitalize()
        except Exception:
            _log.debug("пропущено в life/game_mode.py (строка 218)")
        return None

    def _on_game_start(self, game):
        if not self.voice:
            return
        greeting = random.choice(self.greetings)
        self.voice.speak(greeting)
        if self.memory:
            try:
                self.memory.log(f"🎮 Запущена игра: {game}")
            except Exception:
                _log.debug("пропущено в life/game_mode.py (строка 230)")
        time.sleep(5)
        self._say_fact(game)

    def _on_game_end(self):
        if self.voice:
            try:
                self.voice.speak(random.choice(self.farewells))
            except Exception:
                _log.debug("пропущено в life/game_mode.py (строка 239)")

    def _say_fact(self, game):
        if not self.voice:
            return

        fact = None
        if self.brain and getattr(self.brain, "api", None) and self.brain.api.enabled:
            try:
                prompt = (
                    f"Ты — Фитц. Создатель играет в {game}. "
                    f"Расскажи один короткий (1-2 предложения) живой факт "
                    f"или забавную историю про эту игру. Без вступлений."
                )
                fact = self.brain.ask(prompt)
            except Exception:
                fact = None

        if not fact or len(fact) < 5:
            fact = self._local_fact(game)

        try:
            self.voice.speak(fact)
        except Exception:
            _log.debug("пропущено в life/game_mode.py (строка 263)")
        if self.memory:
            try:
                self.memory.log(f"🎮 Факт ({game}): {fact}")
            except Exception:
                _log.debug("пропущено в life/game_mode.py (строка 268)")

    def _local_fact(self, game):
        facts = {
            "cs2": [
                "CS2 работает на движке Source 2 — графика стала заметно лучше.",
                "В CS2 теперь можно тренировать гранаты прямо в игре.",
            ],
            "dota2": [
                "В Dota 2 больше 120 героев — каждый уникален.",
                "The International — главный турнир года по Dota 2.",
            ],
            "minecraft": [
                "Minecraft — самая продаваемая игра в истории.",
                "В Minecraft больше 100 миллионов активных игроков.",
            ],
            "cyberpunk2077": [
                "В Cyberpunk 2077 больше 1000 уникальных NPC.",
                "Ночной город — один из самых детализированных в играх.",
            ],
        }
        low = game.lower()
        for key, arr in facts.items():
            if key in low:
                return random.choice(arr)
        return random.choice([
            "У этой игры огромное сообщество по всему миру.",
            "Говорят, разработчики готовят большое обновление.",
            "Интересно, сколько часов ты уже в неё наиграл?",
        ])

    def is_gaming(self) -> bool:
        return self._detect_game() is not None

    def get_status(self) -> str:
        if not self.running:
            return "🎮 Игровой режим выключен"
        status = "🎮 Игровой режим активен"
        if self.current_game:
            status += f"\n🎯 Текущая игра: {self.current_game}"
        return status


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_game_mode = None


def get_game_mode(voice=None, brain=None, memory=None) -> GameMode:
    global _game_mode
    if _game_mode is None:
        _game_mode = GameMode(voice=voice, brain=brain, memory=memory)
    return _game_mode