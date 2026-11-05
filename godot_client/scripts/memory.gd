extends Node
## Память Фитца: короткая история диалога и долгосрочные факты.
## Хранится в user://brain.json (в Godot это ~/.local/share/godot/app_userdata/...).

const SAVE_PATH := "user://brain.json"
const CONTEXT_WINDOW_MESSAGES := 10
const LONG_TERM_LIMIT := 100

var data: Dictionary = {
	"context_window": [],   # [{"role": "user"|"assistant", "content": String}]
	"long_term": [],        # [{"text": String, "ts": int}]
	"mood": "нейтральное",
}


func _ready() -> void:
	load_memory()


func load_memory() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		push_warning("memory: не удалось открыть %s" % SAVE_PATH)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	if typeof(parsed) == TYPE_DICTIONARY:
		for key in data.keys():
			if parsed.has(key):
				data[key] = parsed[key]


func save_memory() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f == null:
		push_warning("memory: не удалось записать %s" % SAVE_PATH)
		return
	f.store_string(JSON.stringify(data, "\t"))


func push_message(role: String, content: String) -> void:
	var window: Array = data["context_window"]
	window.append({"role": role, "content": content})
	while window.size() > CONTEXT_WINDOW_MESSAGES:
		window.pop_front()
	data["context_window"] = window
	save_memory()


# Последние сообщения для промпта (без лишних полей)
func context_for_api() -> Array:
	return data["context_window"].duplicate(true)


# Долгосрочный факт. Лимит 100: удаляем самые старые.
func remember(text: String) -> void:
	var t := text.strip_edges()
	if t == "":
		return
	var facts: Array = data["long_term"]
	facts.append({"text": t, "ts": int(Time.get_unix_time_from_system())})
	while facts.size() > LONG_TERM_LIMIT:
		facts.pop_front()
	data["long_term"] = facts
	save_memory()


# Поиск по подстроке (без учёта регистра)
func recall(query: String) -> Array:
	var q := query.to_lower().strip_edges()
	var hits: Array = []
	for fact in data["long_term"]:
		if q != "" and str(fact["text"]).to_lower().contains(q):
			hits.append(fact["text"])
	return hits


func forget_all() -> void:
	data["context_window"] = []
	data["long_term"] = []
	save_memory()
