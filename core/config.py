"""
config.py — конфигурация Фитца 1.5.0
Хранит настройки в data/config.json. Кроссплатформенный.
"""
import json
import os
from . import os_layer


class Config:
    DEFAULTS = {
        "voice": {
            "speaker": "xenia",
            "speed": 1.0,
            "enabled": True,
            "fallback": "espeak",  # если Silero не загрузился
        },
        "camera": {
            "index": 0,
            "enabled": False,
        },
        "security": {
            "intrusion_log": True,
            "fake_data_on_intrusion": True,
        },
        "api": {
            "enabled": True,
            "url": "https://api.provod.ai/v1",
            "model": "deepseek-v4-flash",
        },
        "awareness": {
            "enabled": False,
            "interval_sec": 5,
        },
        "initiative": {
            "enabled": False,
            "min_interval_sec": 600,
        },
        "autosave": {
            "enabled": True,
            "interval_sec": 60,
        },
    }

    def __init__(self, path: str = "data/config.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.data = self._load()

    # ---------- загрузка/сохранение ----------
    def _load(self) -> dict:
        data = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        # подставляем дефолты рекурсивно
        return self._merge_defaults(data, self.DEFAULTS)

    def _merge_defaults(self, data: dict, defaults: dict) -> dict:
        if not isinstance(data, dict):
            data = {}
        result = dict(data)
        for k, v in defaults.items():
            if isinstance(v, dict):
                result[k] = self._merge_defaults(result.get(k, {}), v)
            else:
                result.setdefault(k, v)
        return result

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Не удалось сохранить config: {e}")

    # ---------- доступ по ключу "a.b.c" ----------
    def get(self, key: str, default=None):
        cur = self.data
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, key: str, value):
        parts = key.split(".")
        cur = self.data
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
        self.save()

    # ---------- удобные свойства ----------
    @property
    def platform(self) -> str:
        return os_layer.SYSTEM

    @property
    def is_windows(self) -> bool:
        return os_layer.is_windows()

    @property
    def is_linux(self) -> bool:
        return os_layer.is_linux()