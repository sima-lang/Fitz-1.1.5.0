"""
ui/settings_dialog.py — Расширенное окно настроек Фитца 1.5.0.
Вкладки: Внешний вид, Haru, Поведение, Зрение, Майнкрафт, API, О программе.
"""
import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QComboBox, QTabWidget, QWidget,
    QFormLayout, QMessageBox, QSlider, QColorDialog, QSpinBox,
    QGroupBox
)
from PyQt6.QtGui import QColor
from core.logger import get_logger
_log = get_logger("settings_dialog")

SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"

DEFAULT_SETTINGS = {
    "api_key": "",
    "api_url": "https://api.provod.ai/v1",
    "api_model": "deepseek/deepseek-v4-flash",
    "api_timeout": 60,
    "theme": "cyberpunk",
    "accent_color": "#00d4ff",
    "window_opacity": 100,
    "chat_font_size": 13,
    "bubble_radius": 12,
    "animations_enabled": True,
    "haru_enabled": True,
    "haru_size": 450,
    "haru_eye_tracking": True,
    "haru_auto_emotions": True,
    "haru_emotions": True,
    "lipsync_speed": 0.15,
    "voice_volume": 1.0,
    "sounds_enabled": True,
    "sounds_volume": 80,
    # Зрение
    "vision_enabled": False,
    "vision_interval_min": 20,
    "vision_categories": {
        "game": True, "code": True, "browsing": True, "other": True,
    },
    # Поведение
    "initiative_enabled": True,
    "initiative_interval": 10,
    "initiative_aggression": "средняя",
    "autonomy_enabled": True,
    "personality_sarcasm": True,
    "personality_empathy": True,
    "personality_humor": True,
    # Прочее
    "check_api_on_start": True,
    "save_history": True,
    "max_history_messages": 50,
    # Майнкрафт
    "mc_host": "localhost",
    "mc_port": 34485,
    "mc_nick": "FitzBot",
    "mc_enabled": False,
    # Визуал (1.6.0)
    "haru_model": "default",
    "haru_scale": 100,
    "border_animation": True,
    # Права (1.6.2)
    "full_access": False,
}


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            _log.debug("пропущено в ui/settings_dialog.py (строка 80)")
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


class SettingsDialog(QDialog):
    mc_connect_requested = pyqtSignal(dict)
    mc_disconnect_requested = pyqtSignal()

    # ---------- карта интервалов для комбо ----------
    _INTERVAL_MAP = {0: 5, 1: 10, 2: 20, 3: 30, 4: 60}
    _INTERVAL_REV = {5: 0, 10: 1, 20: 2, 30: 3, 60: 4}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Настройки Фитца 1.5.0")
        self.resize(620, 640)
        self.setStyleSheet("background-color: #0a0a0f; color: #e0e0e0;")

        self.settings = load_settings()

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #2a2a4e; background: #1a1a2e; }
            QTabBar::tab { background: #1a1a2e; color: #888; padding: 8px 14px; }
            QTabBar::tab:selected { background: #0078d4; color: #fff; }
        """)

        tabs.addTab(self._build_behavior_tab(), "🎯 Поведение")
        tabs.addTab(self._build_visual_tab(),    "🎨 Внешний вид")
        tabs.addTab(self._build_haru_tab(),      "🐱 Haru")
        tabs.addTab(self._build_visual_tab_s(), "🎨 Визуал")  # 1.6.0
        tabs.addTab(self._build_rights_tab_s(), "🔐 Права")  # 1.6.2
        tabs.addTab(self._build_vision_tab(),    "👁️ Зрение")
        tabs.addTab(self._build_mc_tab(),        "🎮 Майнкрафт")
        tabs.addTab(self._build_api_tab(),       "🔌 API")
        tabs.addTab(self._build_about_tab(),     "ℹ️ О программе")

        layout.addWidget(tabs)

        # ===== КНОПКИ =====
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet("background: #00d4ff; color: #0a0a0f; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("background: #1a1a2e; color: #e0e0e0; padding: 8px;")
        cancel_btn.clicked.connect(self.reject)
        reset_btn = QPushButton("Сбросить")
        reset_btn.setStyleSheet("background: #3a1a1a; color: #ff4444; padding: 8px;")
        reset_btn.clicked.connect(self._reset)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    #  ВКЛАДКА: ПОВЕДЕНИЕ
    # ------------------------------------------------------------------
    def _build_behavior_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # — инициатива —
        g1 = QGroupBox("Инициатива")
        f1 = QFormLayout(g1)
        self.init_check = QCheckBox("Включить инициативу")
        self.init_check.setChecked(self.settings["initiative_enabled"])
        f1.addRow(self.init_check)

        self.init_interval = QComboBox()
        self.init_interval.addItems(["5 мин", "10 мин", "20 мин", "30 мин", "1 час"])
        iv = self.settings["initiative_interval"]
        idx = self._INTERVAL_REV.get(iv, 1)
        self.init_interval.setCurrentIndex(idx)
        f1.addRow("Интервал:", self.init_interval)

        self.init_aggr = QComboBox()
        self.init_aggr.addItems(["низкая", "средняя", "высокая"])
        aggr = self.settings.get("initiative_aggression", "средняя")
        self.init_aggr.setCurrentText(aggr)
        f1.addRow("Агрессивность:", self.init_aggr)
        layout.addWidget(g1)

        # — личность —
        g2 = QGroupBox("Личность")
        f2 = QFormLayout(g2)
        self.sarcasm_check = QCheckBox("Сарказм")
        self.sarcasm_check.setChecked(self.settings.get("personality_sarcasm", True))
        f2.addRow(self.sarcasm_check)
        self.empathy_check = QCheckBox("Эмпатия")
        self.empathy_check.setChecked(self.settings.get("personality_empathy", True))
        f2.addRow(self.empathy_check)
        self.humor_check = QCheckBox("Юмор")
        self.humor_check.setChecked(self.settings.get("personality_humor", True))
        f2.addRow(self.humor_check)
        layout.addWidget(g2)

        # — автономность —
        g3 = QGroupBox("Автономность")
        f3 = QFormLayout(g3)
        self.autonomy_check = QCheckBox("Разрешить автономные действия")
        self.autonomy_check.setChecked(self.settings.get("autonomy_enabled", True))
        f3.addRow(self.autonomy_check)
        layout.addWidget(g3)

        # — прочее —
        g4 = QGroupBox("Общие")
        f4 = QFormLayout(g4)
        self.save_history_check = QCheckBox("Сохранять историю чата")
        self.save_history_check.setChecked(self.settings["save_history"])
        f4.addRow(self.save_history_check)
        self.max_history_spin = QSpinBox()
        self.max_history_spin.setRange(10, 500)
        self.max_history_spin.setValue(self.settings["max_history_messages"])
        f4.addRow("Макс. сообщений:", self.max_history_spin)
        layout.addWidget(g4)

        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: ВНЕШНИЙ ВИД
    # ------------------------------------------------------------------
    def _build_visual_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["cyberpunk", "matrix", "strict", "night"])
        self.theme_combo.setCurrentText(self.settings["theme"])
        layout.addRow("Тема:", self.theme_combo)

        color_layout = QHBoxLayout()
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(40, 25)
        self.color_btn.setStyleSheet(
            f"background-color: {self.settings['accent_color']}; border-radius: 4px;")
        self.color_btn.clicked.connect(self._pick_color)
        self.color_label = QLabel(self.settings["accent_color"])
        color_layout.addWidget(self.color_btn)
        color_layout.addWidget(self.color_label)
        color_layout.addStretch()
        layout.addRow("Акцентный цвет:", color_layout)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(50, 100)
        self.opacity_slider.setValue(self.settings["window_opacity"])
        layout.addRow("Прозрачность окна:", self.opacity_slider)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 18)
        self.font_size_spin.setValue(self.settings["chat_font_size"])
        layout.addRow("Размер шрифта чата:", self.font_size_spin)

        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(4, 20)
        self.radius_slider.setValue(self.settings["bubble_radius"])
        layout.addRow("Скругление пузырей:", self.radius_slider)

        self.anim_check = QCheckBox("Включить анимации")
        self.anim_check.setChecked(self.settings["animations_enabled"])
        layout.addRow(self.anim_check)

        self.haru_emotions_check = QCheckBox("Эмоции Haru по контексту")
        self.haru_emotions_check.setChecked(self.settings.get("haru_emotions", True))
        layout.addRow(self.haru_emotions_check)

        self.sounds_check = QCheckBox("Звуки интерфейса")
        self.sounds_check.setChecked(self.settings.get("sounds_enabled", True))
        layout.addRow(self.sounds_check)

        self.sounds_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.sounds_vol_slider.setRange(0, 100)
        self.sounds_vol_slider.setValue(self.settings.get("sounds_volume", 80))
        layout.addRow("Громкость звуков:", self.sounds_vol_slider)

        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: HARU
    # ------------------------------------------------------------------
    def _build_haru_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.haru_check = QCheckBox("Показывать Haru")
        self.haru_check.setChecked(self.settings["haru_enabled"])
        layout.addRow(self.haru_check)

        self.haru_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.haru_size_slider.setRange(300, 600)
        self.haru_size_slider.setValue(self.settings["haru_size"])
        layout.addRow("Размер Haru:", self.haru_size_slider)

        self.eye_track_check = QCheckBox("Глаза следят за курсором")
        self.eye_track_check.setChecked(self.settings["haru_eye_tracking"])
        layout.addRow(self.eye_track_check)

        self.auto_emotions_check = QCheckBox("Авто-эмоции по контексту")
        self.auto_emotions_check.setChecked(self.settings["haru_auto_emotions"])
        layout.addRow(self.auto_emotions_check)

        self.lipsync_slider = QSlider(Qt.Orientation.Horizontal)
        self.lipsync_slider.setRange(5, 50)
        self.lipsync_slider.setValue(int(self.settings["lipsync_speed"] * 100))
        layout.addRow("Скорость липсинка:", self.lipsync_slider)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.settings.get("voice_volume", 1.0) * 100))
        layout.addRow("Громкость голоса:", self.volume_slider)

        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: ЗРЕНИЕ
    # ------------------------------------------------------------------
    def _build_vision_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        g1 = QGroupBox("Авто-зрение")
        f1 = QFormLayout(g1)
        self.vision_check = QCheckBox("Включить авто-зрение")
        self.vision_check.setChecked(self.settings["vision_enabled"])
        f1.addRow(self.vision_check)

        self.vision_interval = QComboBox()
        self.vision_interval.addItems(["5 мин", "10 мин", "20 мин", "30 мин", "1 час"])
        iv = self.settings["vision_interval_min"]
        idx = self._INTERVAL_REV.get(iv, 2)
        self.vision_interval.setCurrentIndex(idx)
        f1.addRow("Интервал:", self.vision_interval)
        layout.addWidget(g1)

        g2 = QGroupBox("Категории для скриншотов")
        f2 = QFormLayout(g2)
        cats = self.settings.get("vision_categories", {})
        self.vis_game = QCheckBox("🎮 Игры")
        self.vis_game.setChecked(cats.get("game", True))
        f2.addRow(self.vis_game)
        self.vis_code = QCheckBox("💻 Код")
        self.vis_code.setChecked(cats.get("code", True))
        f2.addRow(self.vis_code)
        self.vis_browse = QCheckBox("🌐 Серфинг")
        self.vis_browse.setChecked(cats.get("browsing", True))
        f2.addRow(self.vis_browse)
        self.vis_other = QCheckBox("📄 Прочее")
        self.vis_other.setChecked(cats.get("other", True))
        f2.addRow(self.vis_other)
        layout.addWidget(g2)

        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: ВИЗУАЛ (1.6.0)
    # ------------------------------------------------------------------
    def _build_visual_tab_s(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.haru_model_combo = QComboBox()
        self.haru_model_combo.addItems(["default", "schoolgirl", "cyberpunk", "classic"])
        self.haru_model_combo.setCurrentText(self.settings.get("haru_model", "default"))
        layout.addRow("Модель Haru:", self.haru_model_combo)

        self.haru_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.haru_scale_slider.setRange(50, 150)
        self.haru_scale_slider.setValue(self.settings.get("haru_scale", 100))
        self.haru_scale_label = QLabel(f"{self.settings.get('haru_scale', 100)}%")
        self.haru_scale_slider.valueChanged.connect(
            lambda v: self.haru_scale_label.setText(f"{v}%"))
        layout.addRow("Масштаб Haru:", self.haru_scale_slider)
        layout.addRow("", self.haru_scale_label)

        self.border_anim_check = QCheckBox("Анимация рамки")
        self.border_anim_check.setChecked(self.settings.get("border_animation", True))
        layout.addRow(self.border_anim_check)

        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: ПРАВА (1.6.2)
    # ------------------------------------------------------------------
    def _build_rights_tab_s(self):
        w = QWidget()
        layout = QFormLayout(w)

        info = QLabel(
            "⚠️ Полный доступ позволяет выполнять опасные команды:\n"
            "• run_command_full — любая команда без белого списка\n"
            "• sudo_command — команда с правами root\n"
            "• kill_process — завершение процессов\n"
            "• shutdown_pc — выключение ПК\n"
            "• reboot_pc — перезагрузка\n"
            "• install_package — установка пакетов\n\n"
            "Каждая опасная команда требует подтверждения через диалог."
        )
        info.setWordWrap(True)
        layout.addRow(info)

        self.full_access_check = QCheckBox("Разрешить полный доступ (Full Access)")
        self.full_access_check.setChecked(self.settings.get("full_access", False))
        layout.addRow(self.full_access_check)

        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: МАЙНКРАФТ
    # ------------------------------------------------------------------
    def _build_mc_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.mc_host_input = QLineEdit(self.settings.get("mc_host", "localhost"))
        layout.addRow("Хост:", self.mc_host_input)

        self.mc_port_input = QSpinBox()
        self.mc_port_input.setRange(1024, 65535)
        self.mc_port_input.setValue(self.settings.get("mc_port", 34485))
        layout.addRow("Порт:", self.mc_port_input)

        self.mc_nick_input = QLineEdit(self.settings.get("mc_nick", "FitzBot"))
        layout.addRow("Ник бота:", self.mc_nick_input)

        self.mc_auto_check = QCheckBox("Включать бота при старте")
        self.mc_auto_check.setChecked(self.settings.get("mc_enabled", False))
        layout.addRow(self.mc_auto_check)

        btn_layout = QHBoxLayout()
        self.mc_connect_btn = QPushButton("Подключить")
        self.mc_connect_btn.setStyleSheet("background: #00d4ff; color: #0a0a0f; padding: 8px;")
        self.mc_connect_btn.clicked.connect(self._on_mc_connect)
        self.mc_disconnect_btn = QPushButton("Отключить")
        self.mc_disconnect_btn.setStyleSheet("background: #3a1a1a; color: #ff4444; padding: 8px;")
        self.mc_disconnect_btn.clicked.connect(self._on_mc_disconnect)
        btn_layout.addWidget(self.mc_connect_btn)
        btn_layout.addWidget(self.mc_disconnect_btn)
        layout.addRow(btn_layout)

        self.mc_status_label = QLabel("Статус: не подключен")
        self.mc_status_label.setStyleSheet("color: #888;")
        layout.addRow(self.mc_status_label)

        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: API
    # ------------------------------------------------------------------
    def _build_api_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.api_key_input = QLineEdit(self.settings["api_key"])
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        layout.addRow("API Key:", self.api_key_input)

        self.api_url_input = QLineEdit(self.settings["api_url"])
        layout.addRow("API URL:", self.api_url_input)

        self.api_model_combo = QComboBox()
        self.api_model_combo.addItems([
            "deepseek/deepseek-v4.1-flash",
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash",
            "grok-4-flash",
        ])
        current = self.settings.get("api_model", "deepseek/deepseek-v4-flash")
        idx = self.api_model_combo.findText(current)
        if idx >= 0:
            self.api_model_combo.setCurrentIndex(idx)
        else:
            self.api_model_combo.setEditText(current)
        self.api_model_combo.setEditable(True)
        layout.addRow("Модель:", self.api_model_combo)

        self.api_timeout_spin = QSpinBox()
        self.api_timeout_spin.setRange(30, 300)
        self.api_timeout_spin.setSuffix(" сек")
        self.api_timeout_spin.setValue(self.settings.get("api_timeout", 60))
        layout.addRow("Таймаут:", self.api_timeout_spin)

        test_btn = QPushButton("Проверить подключение")
        test_btn.clicked.connect(self._test_api)
        layout.addRow(test_btn)

        self.check_api_check = QCheckBox("Проверять API при старте")
        self.check_api_check.setChecked(self.settings["check_api_on_start"])
        layout.addRow(self.check_api_check)

        return w

    # ------------------------------------------------------------------
    #  ВКЛАДКА: О ПРОГРАММЕ
    # ------------------------------------------------------------------
    def _build_about_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("🛡️ Фитц 1.5.0\n\nТвой цифровой спутник.")
        lbl.setStyleSheet("font-size: 14px; color: #00d4ff; text-align: center;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        update_btn = QPushButton("Проверить обновления")
        update_btn.clicked.connect(
            lambda: QMessageBox.information(self, "Обновления", "У тебя последняя версия!"))
        layout.addWidget(update_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    # ==================================================================
    #  ДЕЙСТВИЯ
    # ==================================================================

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.settings["accent_color"]), self, "Акцентный цвет")
        if c.isValid():
            self.settings["accent_color"] = c.name()
            self.color_btn.setStyleSheet(f"background-color: {c.name()}; border-radius: 4px;")
            self.color_label.setText(c.name())

    def _on_mc_connect(self):
        s = {
            "mc_host": self.mc_host_input.text(),
            "mc_port": self.mc_port_input.value(),
            "mc_nick": self.mc_nick_input.text(),
        }
        self.mc_connect_requested.emit(s)
        self.mc_status_label.setText("Статус: подключение...")

    def _on_mc_disconnect(self):
        self.mc_disconnect_requested.emit()
        self.mc_status_label.setText("Статус: отключен")

    def set_mc_status(self, text):
        self.mc_status_label.setText(f"Статус: {text}")

    def _test_api(self):
        from core.api import API
        import os
        os.environ["API_KEY"] = self.api_key_input.text()
        os.environ["API_URL"] = self.api_url_input.text()
        os.environ["API_MODEL"] = self.api_model_combo.currentText()

        api = API()
        if not api.enabled:
            QMessageBox.warning(self, "Ошибка", "API-ключ не задан.")
            return
        try:
            resp = api.ask("Привет")
            QMessageBox.information(self, "Успех", f"API работает!\nОтвет: {resp[:100]}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"API не работает:\n{e}")

    def _reset(self):
        if QMessageBox.question(self, "Сброс", "Сбросить все настройки?") \
                == QMessageBox.StandardButton.Yes:
            self.settings = DEFAULT_SETTINGS.copy()
            self.accept()

    def _save(self):
        s = self.settings

        # ---- API ----
        s["api_key"] = self.api_key_input.text()
        s["api_url"] = self.api_url_input.text()
        s["api_model"] = self.api_model_combo.currentText()
        s["api_timeout"] = self.api_timeout_spin.value()
        s["check_api_on_start"] = self.check_api_check.isChecked()

        # ---- Внешний вид ----
        s["theme"] = self.theme_combo.currentText()
        s["window_opacity"] = self.opacity_slider.value()
        s["chat_font_size"] = self.font_size_spin.value()
        s["bubble_radius"] = self.radius_slider.value()
        s["animations_enabled"] = self.anim_check.isChecked()
        s["haru_emotions"] = self.haru_emotions_check.isChecked()
        s["sounds_enabled"] = self.sounds_check.isChecked()
        s["sounds_volume"] = self.sounds_vol_slider.value()

        # ---- Haru ----
        s["haru_enabled"] = self.haru_check.isChecked()
        s["haru_size"] = self.haru_size_slider.value()
        s["haru_eye_tracking"] = self.eye_track_check.isChecked()
        s["haru_auto_emotions"] = self.auto_emotions_check.isChecked()
        s["lipsync_speed"] = self.lipsync_slider.value() / 100.0
        s["voice_volume"] = self.volume_slider.value() / 100.0

        # ---- Поведение ----
        s["initiative_enabled"] = self.init_check.isChecked()
        iv = self._INTERVAL_MAP.get(self.init_interval.currentIndex(), 10)
        s["initiative_interval"] = iv
        s["initiative_aggression"] = self.init_aggr.currentText()
        s["autonomy_enabled"] = self.autonomy_check.isChecked()
        s["personality_sarcasm"] = self.sarcasm_check.isChecked()
        s["personality_empathy"] = self.empathy_check.isChecked()
        s["personality_humor"] = self.humor_check.isChecked()
        s["save_history"] = self.save_history_check.isChecked()
        s["max_history_messages"] = self.max_history_spin.value()

        # ---- Зрение ----
        s["vision_enabled"] = self.vision_check.isChecked()
        iv2 = self._INTERVAL_MAP.get(self.vision_interval.currentIndex(), 20)
        s["vision_interval_min"] = iv2
        s["vision_categories"] = {
            "game": self.vis_game.isChecked(),
            "code": self.vis_code.isChecked(),
            "browsing": self.vis_browse.isChecked(),
            "other": self.vis_other.isChecked(),
        }

        # ---- Майнкрафт ----
        s["mc_host"] = self.mc_host_input.text()
        s["mc_port"] = self.mc_port_input.value()
        s["mc_nick"] = self.mc_nick_input.text()
        s["mc_enabled"] = self.mc_auto_check.isChecked()

        # ---- Визуал (1.6.0) ----
        s["haru_model"] = self.haru_model_combo.currentText()
        s["haru_scale"] = self.haru_scale_slider.value()
        s["border_animation"] = self.border_anim_check.isChecked()

        # ---- Права (1.6.2) ----
        s["full_access"] = self.full_access_check.isChecked()

        save_settings(s)
        self.accept()