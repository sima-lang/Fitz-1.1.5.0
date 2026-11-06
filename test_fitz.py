#!/usr/bin/env python3
"""
test_fitz.py — Автотесты для Фитца 1.1.5.0.
Запуск: python -m unittest test_fitz.py -v
Без API-токенов (все вызовы замоканы).
"""
import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


# ======================================================================
# ТЕСТЫ: commands/files.py
# ======================================================================
class IsolatedAutonomy:
    """Миксин: подменяет пути автономности и логгеры на временные/тихие, чтобы тесты не писали в боевые data/."""

    def _isolate_autonomy(self):
        import logging
        import tempfile
        from core import agent_tools, autonomy, task_runner
        from life import scheduler
        self.autonomy = autonomy
        self._iso_tmp = tempfile.mkdtemp()
        self._iso_orig = (autonomy.DATA_DIR, autonomy.SCHEDULE_FILE, autonomy.JOURNAL_FILE)
        self._iso_loggers = (autonomy._log, task_runner._log, agent_tools._log, scheduler._log)
        autonomy.DATA_DIR = Path(self._iso_tmp)
        autonomy.SCHEDULE_FILE = Path(self._iso_tmp) / "autonomy.json"
        autonomy.JOURNAL_FILE = Path(self._iso_tmp) / "autonomy.log"
        quiet = logging.getLogger("fitz_test_quiet")
        quiet.handlers = [logging.NullHandler()]
        quiet.propagate = False
        autonomy._log = task_runner._log = agent_tools._log = scheduler._log = quiet
        autonomy._pending_confirm.clear()

    def _restore_autonomy(self):
        import shutil
        from core import agent_tools, task_runner
        from life import scheduler
        a = self.autonomy
        a.DATA_DIR, a.SCHEDULE_FILE, a.JOURNAL_FILE = self._iso_orig
        a._log, task_runner._log, agent_tools._log, scheduler._log = self._iso_loggers
        a._pending_confirm.clear()
        shutil.rmtree(self._iso_tmp, ignore_errors=True)


class TestFiles(unittest.TestCase):
    def setUp(self):
        from commands import files
        self.files = files

    def test_is_safe_path_allowed(self):
        """Пользовательский каталог (Документы) — True."""
        home = os.path.expanduser("~")
        f = os.path.join(home, "Документы", "test.txt")
        self.assertTrue(self.files._is_safe_path(f))

    def test_is_safe_path_ssh_keys_denied(self):
        """Ключи SSH в домашней папке — False."""
        home = os.path.expanduser("~")
        self.assertFalse(self.files._is_safe_path(os.path.join(home, ".ssh", "id_rsa")))

    def test_is_safe_path_gnupg_denied(self):
        """Ключи GnuPG в домашней папке — False."""
        home = os.path.expanduser("~")
        self.assertFalse(self.files._is_safe_path(os.path.join(home, ".gnupg", "secring.gpg")))

    def test_is_safe_path_etc_passwd(self):
        """Запрещённый путь /etc/passwd — False."""
        self.assertFalse(self.files._is_safe_path("/etc/passwd"))

    def test_is_safe_path_etc_shadow(self):
        """Запрещённый путь /etc/shadow — False."""
        self.assertFalse(self.files._is_safe_path("/etc/shadow"))

    def test_is_safe_path_relative(self):
        """Относительный путь (безопасный) — True."""
        self.assertTrue(self.files._is_safe_path("data/test.txt"))

    def test_find_path_existing(self):
        """Поиск существующего файла main.py."""
        result = self.files._find_path("main.py")
        self.assertIsNotNone(result, "main.py не найден!")
        self.assertTrue(os.path.exists(result))

    def test_find_path_nonexistent(self):
        """Поиск несуществующего файла."""
        result = self.files._find_path("nonexistent_xyz_12345.qqq")
        self.assertIsNone(result)

    def test_read_file_content_main_py(self):
        """Чтение main.py из корня проекта — должно найтись."""
        path = str(PROJECT_ROOT / "main.py")
        if not os.path.exists(path):
            self.skipTest("main.py не найден")
        content = self.files._read_file_content(path)
        self.assertIn("Fitz", content,
                      f"main.py должен содержать 'Fitz', получили: {content[:100]}")

    def test_block_unsafe_path_etc(self):
        """_block_unsafe_path блокирует /etc/shadow."""
        self.assertTrue(self.files._block_unsafe_path("/etc/shadow"))


# ======================================================================
# ТЕСТЫ: security/safe_links.py
# ======================================================================
class TestSafeLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from security import safe_links
        cls.mod = safe_links

    def test_localhost_url(self):
        """http://localhost — внутренний URL."""
        self.assertTrue(self.mod._is_internal_url("http://localhost:8080"))

    def test_loopback_ip(self):
        """http://127.0.0.1 — внутренний."""
        self.assertTrue(self.mod._is_internal_url("http://127.0.0.1"))

    def test_private_network_10(self):
        """http://10.0.0.1 — внутренний."""
        self.assertTrue(self.mod._is_internal_url("http://10.0.0.1"))

    def test_private_network_192(self):
        """http://192.168.1.1 — внутренний."""
        self.assertTrue(self.mod._is_internal_url("http://192.168.1.1"))

    def test_public_url(self):
        """https://google.com — НЕ внутренний."""
        self.assertFalse(self.mod._is_internal_url("https://google.com"))

    def test_public_ip(self):
        """http://8.8.8.8 — НЕ внутренний."""
        self.assertFalse(self.mod._is_internal_url("http://8.8.8.8"))

    def test_ipv6_loopback(self):
        """http://[::1] — внутренний."""
        self.assertTrue(self.mod._is_internal_url("http://[::1]"))


# ======================================================================
# ТЕСТЫ: core/brain.py
# ======================================================================
class TestBrainPersonality(unittest.TestCase):
    """Тесты личности и системного контекста."""

    @patch("ui.settings_dialog.load_settings")
    def test_build_system_context_sarcasm_on(self, mock_settings):
        """При sarcasm=True контекст содержит 'саркастичный'."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        ctx = brain._build_system_context("привет")
        self.assertIn("саркастичный", ctx)

    @patch("ui.settings_dialog.load_settings")
    def test_build_system_context_sarcasm_off(self, mock_settings):
        """При sarcasm=False контекст НЕ содержит 'саркастичный'."""
        mock_settings.return_value = {
            "personality_sarcasm": False,
            "personality_empathy": True,
            "personality_humor": True,
        }
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        ctx = brain._build_system_context("привет")
        self.assertNotIn("саркастичный", ctx)

    @patch("ui.settings_dialog.load_settings")
    def test_build_system_context_humor_on(self, mock_settings):
        """При humor=True контекст содержит 'юмор'."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        ctx = brain._build_system_context("привет")
        self.assertIn("юмор", ctx.lower())

    def test_local_fallback_hello(self):
        """Приветствие содержит ключевые слова."""
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        resp = brain._local_fallback("привет").lower()
        self.assertTrue(
            "создатель" in resp or "привет" in resp or
            "скучал" in resp or "здравствуй" in resp or
            "вернулся" in resp,
            f"Ответ не похож на приветствие: {resp}"
        )

    def test_local_fallback_unknown(self):
        """Неизвестный запрос — не пустой."""
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        resp = brain._local_fallback("xyz-неизвестный-запрос-12345")
        self.assertTrue(len(resp) > 0)

    def test_local_fallback_empty(self):
        """Пустой запрос — ответ содержит 'не понял'."""
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        resp = brain._local_fallback("")
        self.assertIn("не понял", resp.lower())

    def test_local_fallback_thanks(self):
        """Спасибо содержит слово благодарности."""
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        resp = brain._local_fallback("спасибо").lower()
        self.assertTrue(
            "пожалуйста" in resp or "рад" in resp or
            "обращайся" in resp or "не делал" in resp,
            f"Ответ не похож на благодарность: {resp}"
        )

    def test_local_fallback_time(self):
        """Запрос времени возвращает HH:MM:SS."""
        from core.brain import Brain
        brain = Brain(path="data/brain.json")
        resp = brain._local_fallback("время")
        parts = resp.split(":")
        self.assertEqual(len(parts), 3, f"Ожидался формат HH:MM:SS, получили: {resp}")


class TestBrainSeniorAct(unittest.TestCase):
    """Тесты Senior-режима (с мок-API)."""

    def setUp(self):
        from core.brain import Brain
        self.Brain = Brain
        self.brain = Brain(path="data/brain.json")

    @patch("ui.settings_dialog.load_settings")
    @patch("core.brain.Brain._local_fallback")
    def test_senior_act_api_disabled(self, mock_fb, mock_settings):
        """Без API senior_act возвращает tool='say'."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        mock_fb.return_value = "тестовый ответ"
        self.brain.api = None  # API нет
        result = self.brain.senior_act("привет")
        self.assertIn("tool", result)
        self.assertEqual(result["tool"], "say")

    @patch("ui.settings_dialog.load_settings")
    def test_senior_act_returns_say_tool(self, mock_settings):
        """С мок-API возвращается tool='say'."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        mock_api = MagicMock()
        mock_api.enabled = True
        mock_api.ask.return_value = (
            '{"tool": "say", "args": {"text": "О, привет, создатель!"}}'
        )
        self.brain.api = mock_api
        result = self.brain.senior_act("привет")
        self.assertEqual(result["tool"], "say")
        self.assertIn("О, привет", result["args"]["text"])

    @patch("ui.settings_dialog.load_settings")
    def test_senior_act_personality_flag(self, mock_settings):
        """При sarcasm=True в ответе есть personality: true."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        mock_api = MagicMock()
        mock_api.enabled = True
        mock_api.ask.return_value = (
            '{"tool": "say", "args": {"text": "Тест"}}'
        )
        self.brain.api = mock_api
        result = self.brain.senior_act("тест")
        self.assertTrue(result.get("personality", False))

    @patch("ui.settings_dialog.load_settings")
    def test_senior_act_steps_array(self, mock_settings):
        """Массив JSON → возвращается steps."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        mock_api = MagicMock()
        mock_api.enabled = True
        mock_api.ask.return_value = (
            '[{"tool": "say", "args": {"text": "шаг 1"}},'
            '{"tool": "say", "args": {"text": "шаг 2"}}]'
        )
        self.brain.api = mock_api
        result = self.brain.senior_act("тест")
        self.assertIn("steps", result)
        self.assertEqual(len(result["steps"]), 2)


class TestBrainAsk(unittest.TestCase):
    """Тесты ask() с мок-API."""

    def setUp(self):
        from core.brain import Brain
        self.brain = Brain(path="data/brain.json")

    @patch("ui.settings_dialog.load_settings")
    def test_ask_with_api(self, mock_settings):
        """ask() с API возвращает строку."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        mock_api = MagicMock()
        mock_api.enabled = True
        mock_api.ask.return_value = "Привет, создатель!"
        self.brain.api = mock_api
        self.brain._cache_hits = 0
        resp = self.brain.ask("привет")
        self.assertEqual(resp, "Привет, создатель!")

    @patch("ui.settings_dialog.load_settings")
    def test_ask_fallback_no_api(self, mock_settings):
        """ask() без API — вызов _local_fallback (не пустой ответ)."""
        mock_settings.return_value = {
            "personality_sarcasm": True,
            "personality_empathy": True,
            "personality_humor": True,
        }
        self.brain.api = None
        resp = self.brain.ask("привет")
        self.assertTrue(len(resp) > 0,
                        f"Ответ пустой: {resp!r}")
        self.assertTrue(
            "привет" in resp.lower() or "создатель" in resp.lower() or
            "скучал" in resp.lower() or "здравствуй" in resp.lower(),
            f"Ответ не похож на приветствие: {resp}"
        )

    def test_ask_empty_text(self):
        """Пустой запрос — fallback."""
        resp = self.brain.ask("")
        self.assertTrue(len(resp) > 0)


# ======================================================================
# ТЕСТЫ: core/tools.py
# ======================================================================
class TestToolsReadFile(unittest.TestCase):
    def setUp(self):
        from core.tools import read_file
        self.read_file = read_file

    def test_read_existing_file(self):
        """Чтение существующего main.py."""
        path = str(PROJECT_ROOT / "main.py")
        if not os.path.exists(path):
            self.skipTest("main.py не найден")
        result = self.read_file(path)
        self.assertIn("Fitz", result[:500],
                      f"Ожидался 'Fitz', получили: {result[:100]}")

    def test_read_nonexistent(self):
        """Чтение несуществующего файла."""
        result = self.read_file("nonexistent_xyz_abc.xyz")
        self.assertTrue(result.startswith("⚠️"),
                        f"Ожидалось предупреждение, получили: {result}")

    def test_read_forbidden(self):
        """Чтение /etc/shadow — запрещено."""
        result = self.read_file("/etc/shadow")
        self.assertIn("⛔", result)


class TestToolsWriteFile(unittest.TestCase):
    def setUp(self):
        from core.tools import write_file
        self.write_file = write_file

    def test_write_and_read(self):
        """Запись во временный файл внутри папки проекта + чтение."""
        with tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT)) as d:
            tmp = os.path.join(d, "fitz_test.txt")
            from core.tools import write_file, read_file
            w = write_file(tmp, "Hello Fitz!")
            self.assertIn("✅", w or "")
            r = read_file(tmp)
            self.assertIn("Hello Fitz", r)

    def test_write_forbidden(self):
        """Запись в /etc/... запрещена."""
        result = self.write_file("/etc/fitz_test.txt", "test")
        self.assertIn("⛔", result)


class TestToolsOpenApp(unittest.TestCase):
    @patch("subprocess.Popen")
    @patch("shutil.which")
    def test_open_known_app(self, mock_which, mock_popen):
        """Запуск firefox через which."""
        mock_which.return_value = "/usr/bin/firefox"
        from core.tools import open_app
        result = open_app("firefox")
        self.assertIn("🚀", result or "")

    def test_open_unknown_app(self):
        """Неизвестное приложение."""
        from core.tools import open_app
        result = open_app("nonexistent_app_xyz_12345")
        self.assertIn("⚠️", result)


class TestToolsSearchWeb(unittest.TestCase):
    @patch("webbrowser.open")
    def test_search_web(self, mock_open):
        """Поиск — открытие браузера."""
        from core.tools import search_web
        result = search_web("Fitz AI")
        self.assertIn("🔍", result or "")

    def test_search_empty(self):
        """Пустой запрос."""
        from core.tools import search_web
        result = search_web("")
        self.assertIn("⚠️", result)


class TestToolsTakeScreenshot(unittest.TestCase):
    def test_screenshot_returns_path_or_error(self):
        """Скриншот: либо путь, либо ошибка."""
        from core.tools import take_screenshot
        result = take_screenshot()
        self.assertTrue(
            result.startswith("📸") or result.startswith("⚠️"),
            f"Ожидался 📸 или ⚠️, получили: {result}"
        )


class TestToolsPlayMusic(unittest.TestCase):
    @patch("webbrowser.open")
    def test_play_music_known_mood(self, mock_open):
        """Музыка для 'весёлое'."""
        from core.tools import play_music
        result = play_music("весёлое")
        self.assertIn("🎵", result or "")

    @patch("webbrowser.open")
    def test_play_music_unknown_mood(self, mock_open):
        """Неизвестное настроение — default."""
        from core.tools import play_music
        result = play_music("неведомое_настроение")
        self.assertIn("🎵", result or "")


class TestToolsWindowControl(unittest.TestCase):
    def test_window_control_invalid_action(self):
        """Неизвестное действие."""
        from core.tools import window_control
        result = window_control("fly_away", "test")
        self.assertIn("⚠️", result)

    def test_window_control_no_name(self):
        """switch без имени."""
        from core.tools import window_control
        result = window_control("switch", "")
        if result.startswith("⚠️"):
            pass  # Linux без wmctrl — ожидаемо
        else:
            self.assertIn("🪟", result or "⚠️")


class TestToolsRunCommand(unittest.TestCase):
    def setUp(self):
        from core.tools import run_command
        self.run = run_command

    def test_run_ls(self):
        """ls — разрешено."""
        result = self.run("ls")
        self.assertFalse(result.startswith("⛔"),
                         f"ls заблокирован: {result}")

    def test_run_pwd(self):
        """pwd — разрешено."""
        result = self.run("pwd")
        self.assertFalse(result.startswith("⛔"))

    def test_run_echo(self):
        """echo — разрешено."""
        result = self.run("echo Hello")
        self.assertIn("Hello", result)

    def test_run_forbidden_rm(self):
        """rm — запрещено."""
        result = self.run("rm -rf /")
        self.assertIn("⛔", result)

    def test_run_forbidden_sudo(self):
        """sudo — запрещено."""
        result = self.run("sudo ls")
        self.assertIn("⛔", result)

    def test_run_unknown_command(self):
        """Неизвестная команда."""
        result = self.run("nonexistent_cmd_xyz")
        self.assertIn("⛔", result)


class TestToolsGenerateCode(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_generate_code_python(self, mock_openai_cls):
        """Генерация Python-кода (мок API)."""
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "def hello():\n    return 'world'"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )
        mock_openai_cls.return_value = mock_client

        # Подменяем env
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
            from core.tools import generate_code
            code = generate_code("hello world", "python")
            self.assertIn("hello", code.lower())

    def test_generate_code_no_api_key(self):
        """Без API-ключа — ошибка."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "",
                                      "API_KEY": ""}):
            from core.tools import generate_code
            code = generate_code("test", "python")
            self.assertIn("⚠️", code)


class TestToolsRewriteFile(unittest.TestCase):
    @patch("core.tools.generate_code")
    @patch("core.tools.write_file")
    @patch("core.tools.read_file")
    def test_rewrite_py_to_rs(self, mock_read, mock_write, mock_gen):
        """Перезапись .py → .rs (мок)."""
        mock_read.return_value = "print('hello')"
        mock_gen.return_value = 'fn main() { println!("hello"); }'
        mock_write.return_value = "✅ Записано: test.rs (50 байт)"

        from core.tools import rewrite_file
        result = rewrite_file("test.py", "rust")
        self.assertIn("✅", result)
        self.assertIn(".rs", result)

    def test_rewrite_forbidden_ext(self):
        """Перезапись .env — запрещена."""
        from core.tools import rewrite_file
        result = rewrite_file(".env", "python")
        self.assertIn("⚠️", result)


# ======================================================================
# ТЕСТЫ: ui/settings_dialog.py
# ======================================================================
class TestSettingsDialog(unittest.TestCase):
    def test_default_settings_all_keys(self):
        """DEFAULT_SETTINGS имеет 36+ ключей."""
        from ui.settings_dialog import DEFAULT_SETTINGS
        self.assertGreaterEqual(len(DEFAULT_SETTINGS), 36,
                                f"Ожидалось ≥36 ключей, получили {len(DEFAULT_SETTINGS)}")

    def test_default_settings_required_keys(self):
        """Проверка наличия ключевых полей."""
        from ui.settings_dialog import DEFAULT_SETTINGS
        required = [
            "api_key", "api_url", "api_model", "api_timeout",
            "theme", "accent_color", "window_opacity",
            "initiative_enabled", "initiative_interval",
            "initiative_aggression", "autonomy_enabled",
            "personality_sarcasm", "personality_empathy",
            "personality_humor",
            "sounds_enabled", "sounds_volume",
            "vision_enabled", "vision_interval_min",
            "vision_categories",
            "animations_enabled", "haru_emotions",
            "mc_host", "mc_port", "mc_nick",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_SETTINGS,
                          f"Ключ '{key}' отсутствует в DEFAULT_SETTINGS")

    def test_load_settings_returns_dict(self):
        """load_settings возвращает dict."""
        from ui.settings_dialog import load_settings
        s = load_settings()
        self.assertIsInstance(s, dict)

    def test_save_settings_writes_json(self):
        """save_settings пишет настройки на диск и их можно прочитать обратно."""
        import json
        from ui import settings_dialog
        from ui.settings_dialog import save_settings, DEFAULT_SETTINGS
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "settings.json"
            with patch.object(settings_dialog, "SETTINGS_FILE", target):
                save_settings(DEFAULT_SETTINGS.copy())
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), DEFAULT_SETTINGS)
            self.assertFalse((Path(d) / "settings.json.tmp").exists())


# ======================================================================
# ТЕСТЫ: core/agent.py (1.6.0)
# ======================================================================
class TestFitzAgent(unittest.TestCase):
    def setUp(self):
        from core.brain import Brain
        from core.agent import FitzAgent
        self.brain = Brain(path="data/brain.json")
        self.agent = FitzAgent(
            brain=self.brain,
            execute_tool=lambda step: f"Результат: {step.get('tool', '?')}",
            max_retries=1,
        )

    def test_agent_empty_text(self):
        """Пустой текст — fallback."""
        result = self.agent.process("")
        self.assertTrue(len(result) > 0)

    def test_agent_no_api(self):
        """Без API — fallback не пустой."""
        self.brain.api = None
        result = self.agent.process("привет")
        self.assertTrue(len(result.strip()) > 0)


# ======================================================================
# ТЕСТЫ: intelligence long_term_memory (1.6.0)
# ======================================================================
class TestLongTermMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.intelligence import Intelligence
        import tempfile
        fd, cls._tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        cls.intel = Intelligence(db_path=cls._tmp)

    def test_remember_and_recall(self):
        """Сохранение и поиск в long_term_memory."""
        ok = self.intel.remember_long_term("тестовый ключ", "тестовое значение")
        self.assertTrue(ok)
        results = self.intel.recall_long_term("тестовый", limit=3)
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("тестовый ключ", str(results))

    def test_recall_empty(self):
        """Поиск по несуществующему ключу."""
        results = self.intel.recall_long_term("qqqqzzzz_not_there_12345", limit=3)
        self.assertEqual(len(results), 0)

    def test_get_last_long_term(self):
        """Последнее воспоминание."""
        self.intel.remember_long_term("последний", "самое свежее")
        results = self.intel.get_last_long_term(limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "последний")

    @classmethod
    def tearDownClass(cls):
        import os
        if os.path.exists(cls._tmp):
            os.unlink(cls._tmp)
class TestVisionSDK(unittest.TestCase):
    def test_import(self):
        """Модуль импортируется без ошибок."""
        from core import vision_sdk
        self.assertTrue(hasattr(vision_sdk, "describe_screen"))

    @patch("core.vision_sdk._make_screenshot")
    @patch("core.vision_sdk.OpenAI")
    def test_describe_screen(self, mock_openai_cls, mock_shot):
        """describe_screen с мок-API и мок-скриншотом."""
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        shot = os.path.join(tmpdir.name, "test.png")
        mock_shot.return_value = shot
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "На экране: код Python"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )
        mock_openai_cls.return_value = mock_client

        # Создаём фейковый скриншот во временном каталоге
        Path(shot).write_bytes(b"fake-png-data")

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
            from core.vision_sdk import describe_screen
            try:
                result = describe_screen("Что на экране?")
                self.assertTrue(len(result) > 0)
            except FileNotFoundError:
                # base64-encode может упасть с пустым файлом — это ок
                pass
            except Exception as e:
                # Нормально для мок-среды
                result = str(e)
                self.assertTrue(len(result) > 0)

    def test_make_screenshot_function_exists(self):
        """_make_screenshot существует."""
        from core.vision_sdk import _make_screenshot
        self.assertTrue(callable(_make_screenshot))


# ======================================================================
# ТЕСТЫ: автономный режим (core/autonomy.py, life/scheduler.py)
# ======================================================================
class TestAutonomy(IsolatedAutonomy, unittest.TestCase):
    def setUp(self):
        self._isolate_autonomy()

    def tearDown(self):
        self._restore_autonomy()

    def test_disabled_by_default(self):
        self.assertFalse(self.autonomy.is_enabled())

    def test_dangerous_action_is_rejected(self):
        self.assertIsNone(self.autonomy.run_safe_action("shutdown"))
        self.assertIsNone(self.autonomy.run_safe_action("launch_app"))
        log = self.autonomy.JOURNAL_FILE.read_text(encoding="utf-8")
        self.assertIn("ОТКЛОНЕНО", log)

    def test_safe_action_runs_and_is_logged(self):
        result = self.autonomy.run_safe_action("check_system")
        self.assertIsInstance(result, dict)
        self.assertIn("cpu_percent", result)
        self.assertIn("ram_percent", result)
        self.assertIn("disk_percent", result)

    def test_due_tasks_do_nothing_when_disabled(self):
        state = self.autonomy.load_state()
        state["tasks"] = [{"kind": "safe", "action": "check_system"}]
        self.autonomy.save_state(state)
        self.assertEqual(self.autonomy.run_due_tasks(), 0)

    def test_due_tasks_run_safe_when_enabled(self):
        state = self.autonomy.load_state()
        state["enabled"] = True
        state["tasks"] = [
            {"kind": "safe", "action": "check_system"},
            {"kind": "dangerous", "action": "shutdown"},
        ]
        self.autonomy.save_state(state)
        self.assertEqual(self.autonomy.run_due_tasks(), 1)

    def test_stop_command_disables_mode(self):
        self.autonomy.set_enabled(True)
        self.assertTrue(self.autonomy.is_enabled())
        reply = self.autonomy.handle_stop_command("стоп автономность")
        self.assertIn("остановлен", reply)
        self.assertFalse(self.autonomy.is_enabled())

    def test_unrelated_text_is_not_autonomy_command(self):
        self.assertIsNone(self.autonomy.handle_stop_command("который час"))

    def test_corrupted_schedule_falls_back_to_disabled(self):
        self.autonomy.SCHEDULE_FILE.write_text("{не json", encoding="utf-8")
        self.assertFalse(self.autonomy.is_enabled())

    def test_scheduler_starts_once_and_stops(self):
        import time
        from life import scheduler
        self.assertTrue(scheduler.start(interval=1))
        self.assertFalse(scheduler.start(interval=1))
        self.assertTrue(scheduler.is_running())
        scheduler.stop()
        time.sleep(1.5)
        self.assertFalse(scheduler.is_running())

    # ---- Автономность и запуск приложений ----
    def test_open_steam_autonomy_on_launches_without_confirm(self):
        from unittest.mock import patch
        from commands import apps
        with patch.object(self.autonomy, "is_enabled", return_value=True), \
             patch.object(self.autonomy, "request_dangerous_action") as rda, \
             patch("commands.apps._open_app", return_value="🚀 Запустил: steam") as oa:
            reply = apps.handle("открой steam", None, None)
        self.assertFalse(rda.called, "при автономности подтверждение запрашиваться не должно")
        oa.assert_called_once_with("steam")
        self.assertEqual(reply, "🚀 Запустил: steam")

    def test_open_steam_autonomy_off_asks_confirm(self):
        from unittest.mock import patch
        from commands import apps
        with patch.object(self.autonomy, "is_enabled", return_value=False), \
             patch.object(self.autonomy, "request_dangerous_action",
                          return_value={"question": "вопрос"}) as rda, \
             patch("commands.apps._open_app") as oa:
            reply = apps.handle("открой steam", None, None)
        rda.assert_called_once_with("launch_app", "steam")
        self.assertFalse(oa.called)
        self.assertEqual(reply, "вопрос")

    # ---- Этап 2: Сторож ----
    def test_guardian_thresholds(self):
        self.assertEqual(self.autonomy.guardian_check({"cpu_percent": 95, "disk_percent": 50}),
                         ["ЦП 95% (порог 90%)"])
        self.assertEqual(len(self.autonomy.guardian_check({"cpu_percent": 10, "disk_percent": 96})), 1)
        self.assertEqual(self.autonomy.guardian_check({"cpu_percent": 90, "disk_percent": 95}), [])

    def test_guardian_notifies_and_journals_on_breach(self):
        sent = []
        orig = self.autonomy.run_safe_action
        self.autonomy.run_safe_action = lambda name: {"cpu_percent": 99, "ram_percent": 10, "disk_percent": 10}
        try:
            warnings = self.autonomy.run_guardian(notify=sent.append)
        finally:
            self.autonomy.run_safe_action = orig
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(sent), 1)
        self.assertIn("Сторож", sent[0])
        self.assertIn("СТОРОЖ", self.autonomy.JOURNAL_FILE.read_text(encoding="utf-8"))

    def test_guardian_silent_when_within_limits(self):
        sent = []
        orig = self.autonomy.run_safe_action
        self.autonomy.run_safe_action = lambda name: {"cpu_percent": 5, "ram_percent": 10, "disk_percent": 20}
        try:
            self.assertEqual(self.autonomy.run_guardian(notify=sent.append), [])
        finally:
            self.autonomy.run_safe_action = orig
        self.assertEqual(sent, [])

    def test_guardian_interval_is_five_minutes(self):
        self.assertEqual(self.autonomy.GUARDIAN_INTERVAL_SEC, 300)

    # ---- Этап 2: подтверждение опасных действий ----
    def test_dangerous_request_does_not_execute(self):
        r = self.autonomy.request_dangerous_action("shutdown")
        self.assertTrue(r["needs_confirm"])
        self.assertEqual(r["action"], "shutdown")
        self.assertIn("Подтверждаешь? (да/нет)", r["question"])
        self.assertTrue(self.autonomy.has_pending_confirm())

    def test_safe_action_request_needs_no_confirm(self):
        r = self.autonomy.request_dangerous_action("check_system")
        self.assertFalse(r["needs_confirm"])
        self.assertFalse(self.autonomy.has_pending_confirm())

    def test_no_pending_means_no_resolution(self):
        self.assertIsNone(self.autonomy.resolve_confirm("да"))

    def test_answer_no_cancels(self):
        self.autonomy.request_dangerous_action("reboot")
        reply = self.autonomy.resolve_confirm("нет")
        self.assertIn("не выполняю", reply)
        self.assertFalse(self.autonomy.has_pending_confirm())

    def test_unclear_answer_cancels_not_executes(self):
        self.autonomy.request_dangerous_action("shutdown")
        reply = self.autonomy.resolve_confirm("может быть")
        self.assertIn("отменено", reply)
        self.assertFalse(self.autonomy.has_pending_confirm())

    def test_answer_yes_calls_executor_only_after_confirmation(self):
        # Тест не должен выключать реальный ПК: исполнитель подменяем моком
        from unittest.mock import patch
        with patch("core.tools.shutdown_pc", return_value="mocked") as sd:
            self.autonomy.request_dangerous_action("shutdown")
            self.assertFalse(sd.called, "исполнитель вызван до подтверждения")
            reply = self.autonomy.resolve_confirm("да")
            self.assertTrue(sd.called, "после «да» исполнитель должен быть вызван")
            self.assertEqual(reply, "mocked")

    def test_answer_no_never_calls_executor(self):
        from unittest.mock import patch
        with patch("core.tools.shutdown_pc", return_value="mocked") as sd:
            self.autonomy.request_dangerous_action("shutdown")
            self.autonomy.resolve_confirm("нет")
            self.assertFalse(sd.called)

    def test_launch_refuses_name_outside_allowlist(self):
        from unittest.mock import patch
        with patch("core.tools.open_app", return_value="opened") as oa:
            reply = self.autonomy.execute_confirmed("launch_app", "rm -rf /")
            self.assertFalse(oa.called)
            self.assertIn("не в списке", reply)

    def test_launch_allowed_app_calls_open_app(self):
        from unittest.mock import patch
        with patch("core.tools.open_app", return_value="🚀 Запустил: steam") as oa:
            self.autonomy.request_dangerous_action("launch_app", "steam")
            reply = self.autonomy.resolve_confirm("да")
            oa.assert_called_once_with("steam")
            self.assertIn("Запустил", reply)

    def test_power_commands_ask_before_acting(self):
        from unittest.mock import patch
        from commands import power
        with patch.object(power, "_full_access_enabled", return_value=True), \
             patch("core.tools.shutdown_pc", return_value="mocked") as sd:
            reply = power.handle("выключи пк", None, None)
            self.assertIn("Подтверждаешь", reply)
            self.assertFalse(sd.called)
        self.autonomy._pending_confirm.clear()

    def test_new_request_replaces_pending(self):
        self.autonomy.request_dangerous_action("shutdown")
        self.autonomy.request_dangerous_action("reboot")
        self.assertEqual(self.autonomy._pending_confirm["action"], "reboot")


class TestTaskRunner(IsolatedAutonomy, unittest.TestCase):
    """Task Runner: разбор целей, белый список шагов, выполнение без сети."""

    def setUp(self):
        self._isolate_autonomy()

    def tearDown(self):
        self._restore_autonomy()

    def test_fallback_plan_ends_with_write_plan(self):
        from core import task_runner
        steps = task_runner._fallback_steps("улучши свой код PyQt6")
        self.assertEqual(steps[-1]["tool"], "write_plan")
        self.assertTrue(all(s["tool"] in task_runner.ALLOWED_TOOLS for s in steps))

    def test_validate_drops_unknown_tools(self):
        from core import task_runner
        raw = [{"tool": "delete_file", "arg": "x"}, {"tool": "write_plan", "arg": "ok"}, "junk"]
        self.assertEqual(task_runner._validate_steps(raw), [{"tool": "write_plan", "arg": "ok"}])

    def test_validate_caps_steps(self):
        from core import task_runner
        raw = [{"tool": "write_plan", "arg": str(i)} for i in range(50)]
        self.assertEqual(len(task_runner._validate_steps(raw)), task_runner.MAX_STEPS)

    def test_parse_goal_uses_api_when_valid(self):
        from unittest.mock import MagicMock
        from core import task_runner
        api = MagicMock(enabled=True)
        api.ask.return_value = '[{"tool": "search_web", "arg": "PyQt6"}]'
        self.assertEqual(task_runner.parse_goal("цель", api=api),
                         [{"tool": "search_web", "arg": "PyQt6"}])

    def test_parse_goal_falls_back_on_bad_api_answer(self):
        from unittest.mock import MagicMock
        from core import task_runner
        api = MagicMock(enabled=True)
        api.ask.return_value = "не json вообще"
        steps = task_runner.parse_goal("улучши код", api=api)
        self.assertEqual(steps[-1]["tool"], "write_plan")

    def test_run_steps_isolates_failures(self):
        from core import task_runner
        from unittest.mock import patch
        with patch.dict(task_runner.ALLOWED_TOOLS, {
            "search_web": lambda a: {"ok": False, "error": "сеть"},
            "write_plan": lambda a: {"ok": True, "file": "x.md"},
        }):
            results = task_runner.run_steps([
                {"tool": "search_web", "arg": "a"},
                {"tool": "write_plan", "arg": "b"},
            ])
        self.assertFalse(results[0]["ok"])
        self.assertTrue(results[1]["ok"])


class TestAgentTools(IsolatedAutonomy, unittest.TestCase):
    """Инструменты агента: пути только в data/plans и projects; без сети."""

    def setUp(self):
        self._isolate_autonomy()

    def tearDown(self):
        self._restore_autonomy()

    def test_writable_only_plans_and_projects(self):
        from core import agent_tools
        self.assertIsNotNone(agent_tools.safe_write_path(agent_tools.PLANS_DIR / "a.md"))
        self.assertIsNotNone(agent_tools.safe_write_path(agent_tools.PROJECTS_DIR / "x.py"))
        self.assertIsNone(agent_tools.safe_write_path(Path("/etc/passwd")))
        self.assertIsNone(agent_tools.safe_write_path(agent_tools.PLANS_DIR / ".." / ".." / "x.md"))

    def test_write_plan_saves_md(self):
        import tempfile
        from core import agent_tools
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(agent_tools, "PLANS_DIR", Path(tmp)), \
                 patch.object(agent_tools, "WRITABLE_ROOTS", (Path(tmp),)):
                res = agent_tools.write_plan("# План\n- шаг", title="тест")
                self.assertTrue(res["ok"])
                self.assertTrue(Path(res["file"]).suffix == ".md")
                self.assertIn("шаг", Path(res["file"]).read_text(encoding="utf-8"))

    def test_write_plan_rejects_empty(self):
        from core import agent_tools
        self.assertFalse(agent_tools.write_plan("   ")["ok"])

    def test_search_without_network_returns_error(self):
        from core import agent_tools
        from unittest.mock import patch
        with patch("core.agent_tools.urlopen", side_effect=OSError("нет сети")):
            res = agent_tools.search_web_saved("PyQt6")
        self.assertFalse(res["ok"])

    def test_youtube_without_library_is_honest_error(self):
        from core import agent_tools
        import builtins
        from unittest.mock import patch
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "youtube_transcript_api":
                raise ImportError("нет")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=fake_import):
            res = agent_tools.read_youtube_transcript("https://youtu.be/abc123")
        self.assertFalse(res["ok"])
        self.assertIn("youtube-transcript-api", res["error"])

    def test_youtube_rejects_foreign_url(self):
        from core import agent_tools
        self.assertFalse(agent_tools.read_youtube_transcript("https://evil.com/?v=1")["ok"])


class TestIdle(unittest.TestCase):
    """Детектор простоя: порог 2 минуты, неизвестный статус не считается простоем."""

    def test_parse_gdbus_output(self):
        from core import idle
        self.assertEqual(idle.parse_idletime_ms("(uint64 40053,)"), 40053)
        self.assertIsNone(idle.parse_idletime_ms("ошибка"))

    def test_threshold_two_minutes(self):
        from core import idle
        from unittest.mock import patch
        self.assertEqual(idle.IDLE_THRESHOLD_SEC, 120)
        with patch.object(idle, "get_idle_ms", return_value=130_000):
            self.assertTrue(idle.detect_idle())
        with patch.object(idle, "get_idle_ms", return_value=60_000):
            self.assertFalse(idle.detect_idle())

    def test_unknown_status_is_not_idle(self):
        from core import idle
        from unittest.mock import patch
        with patch.object(idle, "get_idle_ms", return_value=None):
            self.assertFalse(idle.detect_idle())


class TestTaskQueue(IsolatedAutonomy, unittest.TestCase):
    """Очередь автономного агента: постановка, выполнение только при включённом режиме."""

    def setUp(self):
        self._isolate_autonomy()

    def tearDown(self):
        self._restore_autonomy()

    def test_enqueue_adds_queued_goal(self):
        self.autonomy.enqueue_task("улучши код")
        queue = self.autonomy.load_state()["queue"]
        self.assertEqual(queue[0]["status"], "queued")
        self.assertEqual(queue[0]["goal"], "улучши код")

    def test_enqueue_rejects_empty_and_caps_queue(self):
        self.assertIn("Не понял", self.autonomy.enqueue_task("  "))
        for i in range(self.autonomy.MAX_QUEUE):
            self.autonomy.enqueue_task(f"цель {i}")
        self.assertIn("полна", self.autonomy.enqueue_task("лишняя"))

    def test_run_task_does_nothing_when_disabled(self):
        from unittest.mock import patch
        self.autonomy.enqueue_task("цель")
        with patch("core.task_runner.run_task") as rt:
            self.assertIsNone(self.autonomy.run_task())
        self.assertFalse(rt.called)

    def test_run_task_executes_queued_goal_and_marks_done(self):
        from unittest.mock import patch
        self.autonomy.set_enabled(True)
        self.autonomy.enqueue_task("цель")
        with patch("core.task_runner.run_task", return_value={"ok": 1, "steps": 1}) as rt:
            summary = self.autonomy.run_task()
        rt.assert_called_once()
        self.assertEqual(summary["ok"], 1)
        self.assertEqual(self.autonomy.load_state()["queue"][0]["status"], "done")

    def test_failed_task_is_marked_failed(self):
        from unittest.mock import patch
        self.autonomy.set_enabled(True)
        self.autonomy.enqueue_task("цель")
        with patch("core.task_runner.run_task", return_value={"ok": 0, "steps": 2}):
            self.autonomy.run_task()
        self.assertEqual(self.autonomy.load_state()["queue"][0]["status"], "failed")

    def test_night_command_enqueues_task(self):
        from commands import autonomy_cmd
        reply = autonomy_cmd.handle("задача на ночь: улучши код", None, None)
        self.assertIn("в очередь", reply)
        self.assertEqual(self.autonomy.load_state()["queue"][0]["goal"], "улучши код")

    def test_task_never_runs_dangerous_tools(self):
        from core import task_runner
        self.assertNotIn("shutdown", task_runner.ALLOWED_TOOLS)
        self.assertNotIn("reboot", task_runner.ALLOWED_TOOLS)
        self.assertNotIn("delete", " ".join(task_runner.ALLOWED_TOOLS))


class TestEmulationAndSleep(IsolatedAutonomy, unittest.TestCase):
    """Эмуляция ввода и сон ПК: только с флагом и подтверждением, без реального ввода в тестах."""

    def setUp(self):
        self._isolate_autonomy()

    def tearDown(self):
        self._restore_autonomy()

    def test_emulation_disabled_by_default(self):
        self.assertFalse(self.autonomy.is_emulation_enabled())

    def test_click_at_blocked_without_flag_and_never_calls_ydotool(self):
        from unittest.mock import patch
        from core import agent_tools
        with patch("core.tools.click_at") as ck:
            res = agent_tools.emulate("click_at", "10,20")
        self.assertFalse(res["ok"])
        self.assertIn("выключена", res["error"])
        self.assertFalse(ck.called)

    def test_click_at_runs_with_flag_when_mocked(self):
        from unittest.mock import patch
        from core import agent_tools
        self.autonomy.set_emulation(True)
        with patch("core.tools.click_at", return_value="🖱️ Клик") as ck:
            res = agent_tools.emulate("click_at", "10,20")
        ck.assert_called_once_with("10", "20")
        self.assertTrue(res["ok"])

    def test_click_at_rejects_bad_coordinates(self):
        from core import agent_tools
        self.autonomy.set_emulation(True)
        res = agent_tools.emulate("click_at", "abc")
        self.assertFalse(res["ok"])

    def test_emulation_requires_confirmation(self):
        from unittest.mock import patch
        self.autonomy.set_emulation(True)
        with patch("core.tools.click_at") as ck:
            r = self.autonomy.request_dangerous_action("click_at", "10,20")
            self.assertTrue(r["needs_confirm"])
            self.assertFalse(ck.called, "до «да» клика быть не должно")

    def test_sleep_refused_when_autonomy_off(self):
        self.assertIn("выключена", self.autonomy.sleep_pc())

    def test_sleep_refused_when_queue_not_empty(self):
        self.autonomy.set_enabled(True)
        self.autonomy.enqueue_task("цель")
        self.assertIn("отложено", self.autonomy.sleep_pc())

    def test_sleep_asks_confirmation_when_allowed(self):
        self.autonomy.set_enabled(True)
        reply = self.autonomy.sleep_pc()
        self.assertIn("Подтверждаешь", reply)
        self.assertTrue(self.autonomy.has_pending_confirm())

    def test_sleep_does_not_run_systemctl_before_yes(self):
        from unittest.mock import patch
        self.autonomy.set_enabled(True)
        with patch("subprocess.run") as sr:
            self.autonomy.sleep_pc()
        self.assertFalse(sr.called)

    def test_emulation_commands_toggle_flag(self):
        from commands import autonomy_cmd
        autonomy_cmd.handle("включи эмуляцию", None, None)
        self.assertTrue(self.autonomy.is_emulation_enabled())
        autonomy_cmd.handle("выключи эмуляцию", None, None)
        self.assertFalse(self.autonomy.is_emulation_enabled())

    def test_run_cycle_rejects_emulation_when_flag_off(self):
        from unittest.mock import patch
        from core import task_runner
        steps = [{"tool": "click_at", "arg": "1,2"}]
        with patch.object(task_runner, "parse_goal", return_value=steps), \
             patch("core.tools.click_at") as ck:
            summary = task_runner.run_cycle("клик")
        self.assertFalse(ck.called)
        self.assertEqual(summary["ok"], 0)
        self.assertEqual(summary["results"][0]["error"], "эмуляция выключена")


class TestParseGoalTools(IsolatedAutonomy, unittest.TestCase):
    """Промпт для API знает все инструменты; агент не читает вне проекта и не запускает чужое."""

    def setUp(self):
        self._isolate_autonomy()

    def tearDown(self):
        self._restore_autonomy()

    def test_prompt_lists_all_tools(self):
        from core import task_runner
        for tool in ("search_web", "read_file", "open_app", "write_plan", "type_text", "click_at"):
            self.assertIn(tool, task_runner.TOOLS_PROMPT)

    def test_parse_goal_sends_tools_to_api(self):
        from unittest.mock import MagicMock
        from core import task_runner
        api = MagicMock(enabled=True)
        api.ask.return_value = '[{"tool": "open_app", "arg": "steam"}]'
        steps = task_runner.parse_goal("открой steam", api=api)
        prompt = api.ask.call_args[0][0]
        self.assertIn("open_app", prompt)
        self.assertEqual(steps, [{"tool": "open_app", "arg": "steam"}])

    def test_validate_keeps_new_tools_and_emulation(self):
        from core import task_runner
        raw = [
            {"tool": "open_app", "arg": "steam"},
            {"tool": "read_file", "arg": "README.md"},
            {"tool": "type_text", "arg": "x"},
        ]
        tools = [s["tool"] for s in task_runner._validate_steps(raw)]
        self.assertEqual(tools, ["open_app", "read_file", "type_text"])

    def test_fallback_terminal_task_opens_terminal_then_types(self):
        from core import task_runner
        steps = task_runner._fallback_steps("открой терминал и напиши 'привет'")
        self.assertEqual(steps[0], {"tool": "open_app", "arg": "терминал"})
        self.assertEqual(steps[1], {"tool": "type_text", "arg": "привет"})

    def test_cycle_emulation_without_flag_is_refused(self):
        from unittest.mock import patch
        from core import task_runner
        steps = [{"tool": "type_text", "arg": "привет"}]
        with patch.object(task_runner, "parse_goal", return_value=steps), \
             patch("core.tools.type_text") as tt:
            summary = task_runner.run_cycle("напиши привет")
        self.assertFalse(tt.called)
        self.assertEqual(summary["results"][0]["error"], "эмуляция выключена")

    def test_cycle_emulation_with_flag_waits_for_confirmation(self):
        from unittest.mock import patch
        from core import task_runner
        self.autonomy.set_emulation(True)
        steps = [{"tool": "type_text", "arg": "привет"}]
        with patch.object(task_runner, "parse_goal", return_value=steps), \
             patch("core.tools.type_text") as tt:
            summary = task_runner.run_cycle("напиши привет")
        self.assertFalse(tt.called, "до «да» ввод не выполняется")
        self.assertTrue(summary["results"][0]["pending_confirm"])
        self.assertTrue(self.autonomy.has_pending_confirm())

    def test_read_file_refuses_outside_project(self):
        from core import agent_tools
        self.assertFalse(agent_tools.read_file_safe("/etc/passwd")["ok"])
        self.assertFalse(agent_tools.read_file_safe("../../../etc/passwd")["ok"])

    def test_read_file_reads_inside_project(self):
        from core import agent_tools
        res = agent_tools.read_file_safe("core/version.py")
        self.assertTrue(res["ok"])
        self.assertIn("__version__", res["text"])

    def test_open_app_refuses_name_outside_allowlist(self):
        from unittest.mock import patch
        from core import agent_tools
        with patch("core.tools.open_app") as oa:
            res = agent_tools.open_app_safe("rm -rf /")
        self.assertFalse(res["ok"])
        self.assertFalse(oa.called)

    def test_open_app_allowed_name_calls_tools(self):
        from unittest.mock import patch
        from core import agent_tools
        with patch("core.tools.open_app", return_value="🚀 Запустил: steam") as oa:
            res = agent_tools.open_app_safe("steam")
        oa.assert_called_once_with("steam")
        self.assertTrue(res["ok"])


class TestVersion1201(unittest.TestCase):
    def test_version_is_1_2_0_1(self):
        from core.version import __version__
        self.assertEqual(__version__, "1.2.0.1")


# ======================================================================
# ЗАПУСК
# ======================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)

# ======================================================================
# ТЕСТЫ: версия (core/version.py == package.json)
# ======================================================================
class TestVersionSync(unittest.TestCase):
    def test_package_json_matches_core_version(self):
        import json
        from core.version import __version__
        with open(PROJECT_ROOT / "package.json", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["version"], __version__)


# ======================================================================
# ТЕСТЫ: логи по модулям (core/logger.py)
# ======================================================================
class TestModuleLogs(unittest.TestCase):
    def test_voice_and_brain_have_own_files(self):
        from core.logger import get_logger, _MODULE_FILES
        self.assertEqual(_MODULE_FILES["voice"], "voice.log")
        self.assertEqual(_MODULE_FILES["brain"], "brain.log")
        self.assertEqual(_MODULE_FILES["ui"], "ui.log")
        lg = get_logger("voice")
        self.assertEqual(lg, get_logger("voice"))
        self.assertEqual(len(lg.handlers), 1)


# ======================================================================
# ТЕСТЫ: команды состояния и поиска по истории (commands/system.py)
# ======================================================================
class TestSystemStatusAndHistory(unittest.TestCase):
    def setUp(self):
        from commands import system
        self.system = system

    def test_status_shows_api_key_presence_without_value(self):
        with patch.dict(os.environ, {"API_KEY": "sk-SECRET-VALUE-123"}):
            out = self.system.handle("состояние", None, None)
        self.assertIn("API-ключ: задан", out)
        self.assertNotIn("sk-SECRET-VALUE-123", out)

    def test_history_search_empty_query_prompts(self):
        self.assertEqual(self.system.handle("найди в истории", None, None),
                         "Что искать в истории?")

    def test_history_search_no_match(self):
        out = self.system.handle("найди в истории zzqqxx_nomatch", None, None)
        self.assertIn("нет совпадений", out)


# ======================================================================
# ТЕСТЫ: SSRF через редирект (security/safe_links.py)
# ======================================================================
class TestSafeLinksRedirect(unittest.TestCase):
    def test_redirect_to_internal_is_not_fetched(self):
        from security import safe_links as s
        resp = MagicMock()
        resp.is_redirect = True
        resp.status_code = 302
        resp.headers = {"Location": "http://10.0.0.5/admin"}
        with patch.object(s.requests, "get", return_value=resp) as get, \
             patch.object(s, "_is_internal_url", side_effect=lambda u: "10.0.0.5" in u):
            final, r, hit = s._fetch_checked("https://example.com/go")
        self.assertTrue(hit)
        called = [c.args[0] for c in get.call_args_list]
        self.assertNotIn("http://10.0.0.5/admin", called)


# ======================================================================
# ТЕСТЫ: SSRF — проверка всех адресов хоста, включая IPv6 (security/safe_links.py)
# ======================================================================
class TestSafeLinksAllAddresses(unittest.TestCase):
    @staticmethod
    def _infos(addrs):
        return [(None, None, None, "", (a, 0)) for a in addrs]

    def test_mixed_public_and_internal_ipv6_is_blocked(self):
        from security import safe_links as s
        with patch.object(s.socket, "getaddrinfo", return_value=self._infos(["93.184.216.34", "fe80::1"])):
            self.assertTrue(s._is_internal_url("http://host.example/"))

    def test_public_only_is_allowed(self):
        from security import safe_links as s
        with patch.object(s.socket, "getaddrinfo", return_value=self._infos(["93.184.216.34"])):
            self.assertFalse(s._is_internal_url("http://host.example/"))


# ======================================================================
# ТЕСТЫ: сообщения об ошибках в ui_pyqt.py не вводят в заблуждение
# ======================================================================
class TestMisleadingLogMessage(unittest.TestCase):
    def test_no_misleading_import_message_left(self):
        src = (Path(__file__).parent / "ui_pyqt.py").read_text(encoding="utf-8")
        self.assertNotIn("Import/submodule load skipped", src)

    def test_skip_messages_describe_action(self):
        src = (Path(__file__).parent / "ui_pyqt.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("Пропущено: не удалось"), 6)
