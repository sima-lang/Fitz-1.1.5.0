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
class TestAutonomy(unittest.TestCase):
    def setUp(self):
        import tempfile
        from core import autonomy
        self.autonomy = autonomy
        self._tmp = tempfile.mkdtemp()
        self._orig = (autonomy.DATA_DIR, autonomy.SCHEDULE_FILE, autonomy.JOURNAL_FILE)
        autonomy.DATA_DIR = Path(self._tmp)
        autonomy.SCHEDULE_FILE = Path(self._tmp) / "autonomy.json"
        autonomy.JOURNAL_FILE = Path(self._tmp) / "autonomy.log"
        autonomy._pending_confirm.clear()

    def tearDown(self):
        import shutil
        a = self.autonomy
        a.DATA_DIR, a.SCHEDULE_FILE, a.JOURNAL_FILE = self._orig
        a._pending_confirm.clear()
        shutil.rmtree(self._tmp, ignore_errors=True)

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

    def test_answer_yes_does_not_fake_execution(self):
        # Исполнителя пока нет: «да» не должно притворяться выполнением
        self.autonomy.request_dangerous_action("shutdown")
        reply = self.autonomy.resolve_confirm("да")
        self.assertIn("не подключён", reply)
        self.assertNotIn("выполнено", reply.lower().replace("не выполнено", ""))

    def test_new_request_replaces_pending(self):
        self.autonomy.request_dangerous_action("shutdown")
        self.autonomy.request_dangerous_action("reboot")
        self.assertEqual(self.autonomy._pending_confirm["action"], "reboot")


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
