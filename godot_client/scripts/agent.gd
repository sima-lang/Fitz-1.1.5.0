extends Node
## Агентный цикл Фитца: решает — ответить словами или вызвать инструмент.
## Модель возвращает JSON {"tool": "...", "args": {...}} или {"say": "..."}.
## Опасные инструменты НЕ выполняются без подтверждения пользователя (confirm_requested).

signal said(text: String, ok: bool)
signal confirm_requested(tool: String, args: Dictionary)

const DANGEROUS := ["run_command", "click_at", "type_text", "press_key"]
const SAFE := ["media_control", "get_volume", "set_volume", "notify", "focused_window_title"]

var brain: Node
var tools: Node
var memory: Node

var _pending: Dictionary = {}   # ожидающее подтверждения действие


func setup(b: Node, t: Node, m: Node) -> void:
	brain = b
	tools = t
	memory = m
	brain.reply_ready.connect(_on_brain_reply)
	brain.memory = memory


# Точка входа: текст пользователя.
func process(text: String) -> void:
	memory.push_message("user", text)
	# Инструкция модели: отвечать JSON. Сам текст — в prompt.
	var prompt := (
		"Ответь ОДНИМ JSON-объектом без пояснений. "
		+ "Либо {\"say\": \"ответ\"}, либо {\"tool\": \"имя\", \"args\": {...}}. "
		+ "Инструменты: run_command(cmd), click_at(x,y), type_text(text), press_key(key), "
		+ "get_volume(), set_volume(level 0..1), media_control(action: play-pause|next|previous|stop), "
		+ "notify(title,text), focused_window_title().\n\nПользователь: " + text
	)
	brain.ask(prompt)


func _on_brain_reply(text: String, ok: bool) -> void:
	if not ok:
		said.emit(text, false)
		return
	var parsed = _parse_action(text)
	if parsed == null:
		# Модель ответила обычным текстом — просто показываем.
		memory.push_message("assistant", text)
		said.emit(text, true)
		return
	if parsed.has("say"):
		var s := str(parsed["say"])
		memory.push_message("assistant", s)
		said.emit(s, true)
		return
	if parsed.has("tool"):
		_run_tool(str(parsed["tool"]), parsed.get("args", {}))


# Достаёт JSON из ответа модели (может быть обёрнут в ```json ... ```).
func _parse_action(text: String) -> Variant:
	var s := text.strip_edges()
	if s.begins_with("```"):
		s = s.trim_prefix("```json").trim_prefix("```").trim_suffix("```").strip_edges()
	var parsed = JSON.parse_string(s)
	if typeof(parsed) == TYPE_DICTIONARY:
		return parsed
	return null


func _run_tool(tool: String, args: Dictionary) -> void:
	if DANGEROUS.has(tool):
		# Не выполняем сразу: спрашиваем пользователя.
		_pending = {"tool": tool, "args": args}
		confirm_requested.emit(tool, args)
		return
	if not (SAFE.has(tool)):
		said.emit("⚠️ Неизвестный инструмент: %s" % tool, false)
		return
	var result := _dispatch(tool, args)
	said.emit(str(result["text"]), bool(result["ok"]))


# Вызывается UI после того, как пользователь нажал «Да» / «Нет».
func confirm(allowed: bool) -> void:
	if _pending.is_empty():
		return
	var tool: String = _pending["tool"]
	var args: Dictionary = _pending["args"]
	_pending = {}
	if not allowed:
		said.emit("Отменил.", true)
		return
	var result := _dispatch(tool, args)
	said.emit(str(result["text"]), bool(result["ok"]))


func _dispatch(tool: String, args: Dictionary) -> Dictionary:
	match tool:
		"run_command":
			return tools.run_command(str(args.get("cmd", "")))
		"click_at":
			return tools.click_at(int(args.get("x", 0)), int(args.get("y", 0)))
		"type_text":
			return tools.type_text(str(args.get("text", "")))
		"press_key":
			return tools.press_key(str(args.get("key", "")))
		"get_volume":
			return tools.get_volume()
		"set_volume":
			return tools.set_volume(float(args.get("level", 0.5)))
		"media_control":
			return tools.media_control(str(args.get("action", "")))
		"notify":
			return tools.notify(str(args.get("title", "Фитц")), str(args.get("text", "")))
		"focused_window_title":
			return tools.focused_window_title()
	return {"ok": false, "text": "⚠️ Неизвестный инструмент: " + tool}
