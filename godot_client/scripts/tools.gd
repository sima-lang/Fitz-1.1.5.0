extends Node
## Инструменты ПК для Фитца (Linux / Ubuntu / Wayland).
## Все функции возвращают Dictionary: {"ok": bool, "text": String}.
## Опасные действия (run_command, click_at, type_text, press_key) работают
## ТОЛЬКО при full_access = true. Это проверка на стороне клиента, а не доверие модели.

var full_access: bool = false


func set_full_access(enabled: bool) -> void:
	full_access = enabled


func _result(ok: bool, text: String) -> Dictionary:
	return {"ok": ok, "text": text}


func _deny() -> Dictionary:
	return _result(false, "⛔ Полный доступ выключен. Включи его в настройках.")


# Выполняет внешнюю программу. Возвращает {"ok", "text", "code"}.
# OS.execute: exit code и вывод. read_stderr=true, чтобы видеть ошибки.
func _exec(program: String, args: PackedStringArray, timeout_hint: String = "") -> Dictionary:
	var output: Array = []
	var code: int = OS.execute(program, args, output, true)
	var text: String = ""
	for line in output:
		text += str(line)
	text = text.strip_edges()
	if code == -1:
		return {"ok": false, "text": "⚠️ Не найдена программа %s. %s" % [program, timeout_hint], "code": code}
	return {"ok": code == 0, "text": text if text != "" else ("OK" if code == 0 else "код %d" % code), "code": code}


# ===== ОКНА (GNOME Shell D-Bus, как в core/linux_env.py) =====
# Прямой Eval GNOME Shell у Godot-клиента не нужен: окна переключает Python-мост.
# Здесь — только получение заголовка активного окна через gdbus.
func focused_window_title() -> Dictionary:
	var r := _exec("gdbus", PackedStringArray([
		"call", "--session", "--dest", "org.gnome.Shell",
		"--object-path", "/org/gnome/Shell", "--method", "org.gnome.Shell.Eval",
		"global.display.focus_window ? global.display.focus_window.get_title() : ''",
	]))
	return _result(r["ok"], r["text"])


# ===== КОМАНДЫ =====
# Запуск команды через shell. Только при full_access.
func run_command(cmd: String) -> Dictionary:
	if not full_access:
		return _deny()
	if cmd.strip_edges() == "":
		return _result(false, "⚠️ Пустая команда.")
	var r := _exec("bash", PackedStringArray(["-c", cmd]))
	return _result(r["ok"], r["text"])


# ===== ВВОД (ydotool) =====
func click_at(x: int, y: int) -> Dictionary:
	if not full_access:
		return _deny()
	var move := _exec("ydotool", PackedStringArray(["mousemove", "-x", str(x), "-y", str(y)]),
		"Установи: sudo apt install ydotool")
	if not move["ok"]:
		return _result(false, move["text"])
	var click := _exec("ydotool", PackedStringArray(["click", "0xC0", "0x00"]))
	return _result(click["ok"], "🖱 Клик (%d, %d)" % [x, y] if click["ok"] else click["text"])


func type_text(text: String) -> Dictionary:
	if not full_access:
		return _deny()
	if text == "":
		return _result(false, "⚠️ Укажи текст.")
	var r := _exec("ydotool", PackedStringArray(["type", text]),
		"Установи: sudo apt install ydotool")
	return _result(r["ok"], "⌨ Напечатано" if r["ok"] else r["text"])


# key — код клавиши в формате ydotool (например "28:1 28:0" для Enter).
func press_key(key: String) -> Dictionary:
	if not full_access:
		return _deny()
	var parts := key.strip_edges().split(" ", false)
	if parts.is_empty():
		return _result(false, "⚠️ Укажи клавишу.")
	var args := PackedStringArray(["key"])
	for p in parts:
		args.append(p)
	var r := _exec("ydotool", args, "Установи: sudo apt install ydotool")
	return _result(r["ok"], "⌨ Клавиша нажата" if r["ok"] else r["text"])


# ===== ГРОМКОСТЬ (wpctl / PipeWire) =====
# Возвращает уровень 0.0..1.5 (1.0 = 100%).
func get_volume() -> Dictionary:
	var r := _exec("wpctl", PackedStringArray(["get-volume", "@DEFAULT_AUDIO_SINK@"]),
		"Установи: sudo apt install wireplumber")
	if not r["ok"]:
		return _result(false, r["text"])
	# Вывод вида: "Volume: 0.55" или "Volume: 0.55 [MUTED]"
	var txt: String = r["text"]
	var parts := txt.split(" ", false)
	if parts.size() < 2:
		return _result(false, "⚠️ Не удалось разобрать громкость: " + txt)
	return _result(true, parts[1])


# level: 0.0..1.5. Ограничиваем, чтобы не оглушить.
func set_volume(level: float) -> Dictionary:
	var clamped := clampf(level, 0.0, 1.0)
	var r := _exec("wpctl", PackedStringArray(["set-volume", "@DEFAULT_AUDIO_SINK@", str(clamped)]),
		"Установи: sudo apt install wireplumber")
	return _result(r["ok"], "🔊 Громкость %d%%" % int(round(clamped * 100)) if r["ok"] else r["text"])


# ===== МЕДИА (MPRIS через playerctl) =====
# action: play-pause | next | previous | stop
func media_control(action: String) -> Dictionary:
	var allowed := ["play-pause", "next", "previous", "stop"]
	if not allowed.has(action):
		return _result(false, "⚠️ Неизвестное медиа-действие: " + action)
	var r := _exec("playerctl", PackedStringArray([action]),
		"Установи: sudo apt install playerctl")
	return _result(r["ok"], "🎵 " + action if r["ok"] else r["text"])


# ===== УВЕДОМЛЕНИЯ =====
func notify(title: String, text: String) -> Dictionary:
	var r := _exec("notify-send", PackedStringArray([title, text]),
		"Установи: sudo apt install libnotify-bin")
	return _result(r["ok"], "🔔 Уведомление отправлено" if r["ok"] else r["text"])
