"""
anti_theft.py — Анти-вор Фитца (кроссплатформенный).
• Ловит попытки вторжения (через логи/сеть).
• Отправляет фейковые данные (пароли, карты, имена).
• Ведёт лог в logs/intrusion.log.
• Не спамит в консоль.
"""
import os
import json
import random
import string
from datetime import datetime
from core.logger import get_logger
_log = get_logger("anti_theft")


class AntiTheft:
    def __init__(self, config=None):
        self.config = config
        self.intrusion_detected = False
        self.victim_ip = None

        os.makedirs("logs", exist_ok=True)
        os.makedirs("data/security", exist_ok=True)

        self.sent_history_file = "data/security/sent_fakes.json"
        self.sent_history = self._load_history()

        self.fake_ips = [
            "192.168.1.100", "10.0.0.5", "172.16.0.1",
            "8.8.8.8", "1.1.1.1", "94.140.14.14",
        ]

    # ============================================================
    # ЗАГРУЗКА / СОХРАНЕНИЕ
    # ============================================================
    def _load_history(self) -> dict:
        if os.path.exists(self.sent_history_file):
            try:
                with open(self.sent_history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_history(self):
        try:
            with open(self.sent_history_file, "w", encoding="utf-8") as f:
                json.dump(self.sent_history, f, indent=2, ensure_ascii=False)
        except Exception:
            _log.debug("пропущено в security/anti_theft.py (строка 51)")

    # ============================================================
    # ГЕНЕРАЦИЯ ФЕЙКОВЫХ ДАННЫХ
    # ============================================================
    def _generate_fake_data(self, ip: str) -> dict:
        fake_pass = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        fake_card = (
            f"{random.randint(1000,9999)}-"
            f"{random.randint(1000,9999)}-"
            f"{random.randint(1000,9999)}-"
            f"{random.randint(1000,9999)}"
        )
        fake_names = [
            "Иван Петров", "Алексей Смирнов", "Дмитрий Иванов",
            "Сергей Кузнецов", "Анна Соколова",
        ]
        fake_addresses = [
            "ул. Ложная, д. 1, кв. 1",
            "ул. Фейковая, д. 2, кв. 2",
            "ул. Пустая, д. 3, кв. 3",
            "ул. Ненастоящая, д. 4, кв. 4",
        ]
        return {
            "target_ip": ip,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "passwords": fake_pass,
            "bank_cards": fake_card,
            "personal_data": random.choice(fake_names),
            "address": random.choice(fake_addresses),
            "note": "⚠️ ЭТО ФЕЙКОВЫЕ ДАННЫЕ! Реальные данные защищены.",
        }

    # ============================================================
    # ОБРАБОТКА ВТОРЖЕНИЯ
    # ============================================================
    def handle_intrusion(self, ip: str) -> dict | None:
        """Обрабатывает попытку вторжения (тихо)."""
        # если уже отправляли этому IP — не повторяем
        if ip in self.sent_history:
            return None

        self.intrusion_detected = True
        self.victim_ip = ip

        fake_ip = random.choice(self.fake_ips)
        fake_data = self._generate_fake_data(ip)

        self._log_intrusion(ip, fake_data, fake_ip)

        self.sent_history[ip] = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fake_data": fake_data,
            "fake_ip": fake_ip,
        }
        self._save_history()

        return fake_data

    def _log_intrusion(self, ip: str, fake_data: dict, fake_ip: str):
        """Пишет в logs/intrusion.log (тихо)."""
        try:
            with open("logs/intrusion.log", "a", encoding="utf-8") as f:
                f.write("═" * 60 + "\n")
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ ПОПЫТКА ВТОРЖЕНИЯ\n")
                f.write(f"  📍 Реальный IP: {ip}\n")
                f.write(f"  🕵️ Маскировка IP: {fake_ip}\n")
                f.write("  📝 Статус: Отправлены фейковые данные\n")
                f.write("  📋 Фейковые данные:\n")
                f.write(f"     • Пароль: {fake_data['passwords']}\n")
                f.write(f"     • Банковская карта: {fake_data['bank_cards']}\n")
                f.write(f"     • Имя: {fake_data['personal_data']}\n")
                f.write(f"     • Адрес: {fake_data['address']}\n")
                f.write("═" * 60 + "\n")
        except Exception:
            _log.debug("пропущено в security/anti_theft.py (строка 126)")

    # ============================================================
    # ОТЧЁТЫ
    # ============================================================
    def get_report(self) -> str:
        """Отчёт о всех отправленных фейках."""
        if not self.sent_history:
            return "📭 Нет записей о попытках вторжения"

        result = ["📊 ОТЧЁТ ЗАЩИТЫ (AntiTheft):"]
        result.append("═" * 40)
        for ip, data in list(self.sent_history.items())[-10:]:
            result.append(f"  📍 IP: {ip}")
            result.append(f"  🕐 Время: {data.get('time', 'Неизвестно')}")
            result.append(f"  🕵️ Маскировка IP: {data.get('fake_ip', 'Нет')}")
            result.append("  📋 Данные отправлены: ✅")
            result.append("  ─" * 20)
        result.append(f"\n📊 Всего отправлено фейков: {len(self.sent_history)}")
        return "\n".join(result)

    def get_status(self) -> str:
        """Краткий статус защиты."""
        return (
            f"🛡️ СТАТУС ЗАЩИТЫ (AntiTheft):\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔒 Отправлено фейков: {len(self.sent_history)}\n"
            f"🕵️ Маскировка IP: активна\n"
            f"📝 Логи: logs/intrusion.log\n"
        )