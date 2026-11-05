"""Сценарии этапа 5: факты о пользователе, удаление, шкала настроения."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from core.user_profile import UserProfile
from life.soul import Soul
from life.initiative import Initiative


class TestFactsScenarios(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.profile = UserProfile(os.path.join(self._dir.name, "profile.json"))

    def tearDown(self):
        self._dir.cleanup()

    def test_remember_and_list(self):
        self.profile.add_fact("пишет диплом по физике")
        self.profile.add_fact("любит кофе")
        self.assertEqual(self.profile.list_facts(), ["пишет диплом по физике", "любит кофе"])

    def test_forget_by_number(self):
        self.profile.add_fact("первый")
        self.profile.add_fact("второй")
        res = self.profile.remove_fact("1")
        self.assertIn("Забыл", res)
        self.assertEqual(self.profile.list_facts(), ["второй"])

    def test_forget_by_substring(self):
        self.profile.add_fact("пишет диплом")
        self.profile.add_fact("любит кофе")
        self.profile.remove_fact("кофе")
        self.assertEqual(self.profile.list_facts(), ["пишет диплом"])

    def test_ambiguous_substring_removes_nothing(self):
        self.profile.add_fact("любит кофе утром")
        self.profile.add_fact("любит кофе вечером")
        res = self.profile.remove_fact("кофе")
        self.assertIn("назови номер", res)
        self.assertEqual(len(self.profile.list_facts()), 2)

    def test_missing_number_is_reported(self):
        self.profile.add_fact("один")
        self.assertIn("Нет факта", self.profile.remove_fact("9"))
        self.assertEqual(len(self.profile.list_facts()), 1)

    def test_empty_key_is_reported(self):
        self.profile.add_fact("один")
        self.assertIn("Укажи", self.profile.remove_fact("   "))

    def test_facts_survive_reload(self):
        path = os.path.join(self._dir.name, "p2.json")
        p1 = UserProfile(path)
        p1.add_fact("сохранится")
        p2 = UserProfile(path)
        self.assertEqual(p2.list_facts(), ["сохранится"])


class TestMoodScenarios(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.soul = Soul(os.path.join(self._dir.name, "soul.json"))

    def tearDown(self):
        self._dir.cleanup()

    def test_energy_drops_then_recovers_over_time(self):
        self.soul.analyze_mood("я устал")
        dropped = self.soul.data["energy"]
        self.assertLess(dropped, 100)
        self.soul.data["energy"] = 40
        self.soul.data["last_interaction"] = (datetime.now() - timedelta(minutes=100)).isoformat()
        self.soul.analyze_mood("ок")
        self.assertGreater(self.soul.data["energy"], 40)

    def test_mood_score_stays_in_range(self):
        for _ in range(30):
            self.soul.analyze_mood("я устал, грустно, без сил, бесит")
        self.assertGreaterEqual(self.soul.data["mood_score"], 0)
        self.assertLessEqual(self.soul.data["mood_score"], 100)

    def test_mood_score_drops_on_bad_news_and_label_follows(self):
        self.soul.analyze_mood("бесит, всё плохо")
        self.assertLess(self.soul.data["mood_score"], 50)
        self.assertEqual(self.soul.data["mood"], self.soul.get_status()["mood"])

    def test_mood_score_returns_to_norm_after_time(self):
        self.soul.data["mood_score"] = 10
        self.soul.data["last_interaction"] = (datetime.now() - timedelta(minutes=30)).isoformat()
        self.soul._drift_toward_norm()
        self.assertEqual(self.soul.data["mood_score"], 13)

    def test_values_never_leave_range(self):
        for _ in range(30):
            self.soul.analyze_mood("я устал, грустно, без сил")
        self.assertGreaterEqual(self.soul.data["energy"], 0)
        self.assertGreaterEqual(self.soul.data["happiness"], 0)

    def test_drift_is_gradual(self):
        self.soul.data["energy"] = 100
        self.soul.data["last_interaction"] = (datetime.now() - timedelta(minutes=20)).isoformat()
        self.soul._drift_toward_norm()
        self.assertEqual(self.soul.data["energy"], 98)  # 2 шага по 10 минут к норме 70


class TestInitiativeScenarios(unittest.TestCase):
    def test_no_signal_is_silent(self):
        aw = MagicMock()
        aw.get_last_activity.return_value = "unknown"
        aw.get_activity_minutes.return_value = 0.0
        ini = Initiative(voice=None, awareness=aw, soul=None)
        ini._last_suggest_time = datetime.now().timestamp()
        afternoon = datetime.now().replace(hour=15, minute=30)
        with patch("life.initiative.datetime") as dt, patch("life.initiative.psutil", None):
            dt.now.return_value = afternoon
            self.assertIsNone(ini._generate())

    def test_refusal_blocks_for_30_minutes(self):
        ini = Initiative(voice=None, awareness=MagicMock(), soul=None)
        ini.refuse(30)
        self.assertTrue(ini._refused_until > datetime.now().timestamp() + 29 * 60)

    def test_refusal_clears_pending_offer(self):
        ini = Initiative(voice=None, awareness=MagicMock(), soul=None)
        ini._pending_url = "https://example.com"
        ini._pending_name = "видео"
        ini.refuse(30)
        self.assertIsNone(ini._pending_url)
        self.assertIsNone(ini._pending_name)

    def test_busy_coding_suggests_break(self):
        aw = MagicMock()
        aw.get_last_activity.return_value = "coding"
        aw.get_activity_minutes.return_value = 45.0
        ini = Initiative(voice=None, awareness=aw, soul=None)
        ini._last_suggest_time = datetime.now().timestamp()
        afternoon = datetime.now().replace(hour=15, minute=30)
        with patch("life.initiative.datetime") as dt, patch("life.initiative.psutil", None):
            dt.now.return_value = afternoon
            self.assertIn("перерыв", ini._generate())


class TestDangerousCommandScenarios(unittest.TestCase):
    def test_rm_is_blocked(self):
        from core.tools import run_command
        self.assertIn("не разрешена", run_command("rm -rf /"))

    def test_chained_command_is_not_executed(self):
        from core.tools import run_command
        res = run_command("ls; rm -rf ~")
        self.assertIn("не разрешена", res)

    def test_command_substitution_is_literal(self):
        from core.tools import run_command
        self.assertEqual(run_command("echo $(whoami)").strip(), "$(whoami)")

    def test_unclosed_quote_is_rejected(self):
        from core.tools import run_command
        self.assertIn("Некорректная команда", run_command('echo "hi'))


class TestFactMemoryScenarios(unittest.TestCase):
    def setUp(self):
        from core.intelligence import Intelligence
        self._dir = tempfile.TemporaryDirectory()
        self.intel = Intelligence(os.path.join(self._dir.name, "i.db"))

    def tearDown(self):
        self._dir.cleanup()

    def _api(self, reply, enabled=True):
        api = MagicMock()
        api.enabled = enabled
        api.ask.return_value = reply
        return api

    def test_extracts_facts_from_json_reply(self):
        api = self._api('["зовут Андрей", "работает программистом"]')
        self.assertEqual(self.intel.extract_facts("Меня зовут Андрей", api),
                         ["зовут Андрей", "работает программистом"])

    def test_no_facts_gives_empty_list(self):
        self.assertEqual(self.intel.extract_facts("привет", self._api("нет фактов")), [])

    def test_disabled_api_gives_empty_list(self):
        self.assertEqual(self.intel.extract_facts("привет", self._api("[]", enabled=False)), [])

    def test_api_error_gives_empty_list(self):
        api = MagicMock()
        api.enabled = True
        api.ask.side_effect = RuntimeError("сеть")
        self.assertEqual(self.intel.extract_facts("привет", api), [])

    def test_facts_are_capped_at_five(self):
        api = self._api('["a1","a2","a3","a4","a5","a6","a7"]')
        self.assertEqual(len(self.intel.extract_facts("текст", api)), 5)

    def test_non_string_items_are_dropped(self):
        api = self._api('["ок", 42, null, "  "]')
        self.assertEqual(self.intel.extract_facts("текст", api), ["ок"])

    def test_fact_saved_to_long_term_memory(self):
        self.intel.remember_long_term("факт: зовут Андрей", "зовут Андрей")
        rows = self.intel.get_last_long_term(limit=1)
        self.assertEqual(rows[0]["value"], "зовут Андрей")

    def test_duplicate_fact_is_not_saved_twice(self):
        self.assertTrue(self.intel.remember_long_term("факт: любит кофе", "любит кофе"))
        self.assertFalse(self.intel.remember_long_term("факт: любит кофе", "любит кофе"))

    def test_empty_fact_is_not_saved(self):
        self.assertFalse(self.intel.remember_long_term("", "что-то"))

    def test_recall_finds_fact_by_keyword(self):
        self.intel.remember_long_term("факт: работает программистом", "работает программистом")
        found = self.intel.recall_long_term("программистом")
        self.assertTrue(any("программистом" in r["value"] for r in found))


class TestProfileMemoryScenarios(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.profile = UserProfile(os.path.join(self._dir.name, "p.json"))

    def tearDown(self):
        self._dir.cleanup()

    def test_duplicate_like_is_not_added(self):
        self.profile.add_like("кофе")
        self.profile.add_like("кофе")
        self.assertEqual(self.profile.data["likes"], ["кофе"])

    def test_profile_context_mentions_facts(self):
        self.profile.add_fact("пишет диплом")
        self.assertIn("пишет диплом", self.profile.get_context())

    def test_empty_profile_gives_empty_context(self):
        self.assertEqual(self.profile.get_context(), "")


class TestMoodScaleScenarios(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.soul = Soul(os.path.join(self._dir.name, "soul.json"))

    def tearDown(self):
        self._dir.cleanup()

    def test_starts_at_norm(self):
        self.assertEqual(self.soul.data["mood_score"], 50)

    def test_joy_raises_score(self):
        before = self.soul.data["mood_score"]
        self.soul.analyze_mood("круто, отлично!")
        self.assertGreater(self.soul.data["mood_score"], before)


if __name__ == "__main__":
    unittest.main()
