extends Node
## Мозг Фитца: вызов API (OpenAI-совместимый /chat/completions) через HTTPRequest.
## Ключ и адрес берутся из переменных окружения или .env рядом с проектом
## (те же имена, что в Python: API_KEY, API_URL, API_MODEL). В код ключ не пишется.

signal reply_ready(text: String, ok: bool)

const SYSTEM_PROMPT := "Ты — Фитц, дружелюбный голосовой ассистент на ПК. Отвечай коротко, по-русски."
const DEFAULT_URL := "https://api.provod.ai/v1"
const DEFAULT_MODEL := "deepseek-v4-flash"
const TIMEOUT_SEC := 30.0

var api_key: String = ""
var base_url: String = DEFAULT_URL
var model: String = DEFAULT_MODEL
var _http: HTTPRequest
var _busy: bool = false
var memory: Node = null


func _ready() -> void:
	_load_config()
	_http = HTTPRequest.new()
	_http.timeout = TIMEOUT_SEC
	add_child(_http)
	_http.request_completed.connect(_on_completed)


# Читает .env рядом с проектом, затем переменные окружения (env важнее).
func _load_config() -> void:
	var env_values: Dictionary = _read_dotenv("res://../.env")
	api_key = _env("API_KEY", env_values)
	base_url = _env("API_URL", env_values, DEFAULT_URL).rstrip("/")
	model = _env("API_MODEL", env_values, DEFAULT_MODEL)
	if api_key == "":
		push_warning("brain: API_KEY не найден — работаю без облака")


func _env(name: String, dotenv: Dictionary, fallback: String = "") -> String:
	var v := OS.get_environment(name).strip_edges()
	if v != "":
		return v
	return str(dotenv.get(name, fallback)).strip_edges()


func _read_dotenv(path: String) -> Dictionary:
	var out: Dictionary = {}
	var real := ProjectSettings.globalize_path(path)
	if not FileAccess.file_exists(real):
		return out
	var f := FileAccess.open(real, FileAccess.READ)
	if f == null:
		return out
	for line in f.get_as_text().split("\n"):
		var s := line.strip_edges()
		if s == "" or s.begins_with("#") or not s.contains("="):
			continue
		var idx := s.find("=")
		var k := s.substr(0, idx).strip_edges()
		var v := s.substr(idx + 1).strip_edges().trim_prefix("\"").trim_suffix("\"")
		out[k] = v
	return out


func is_enabled() -> bool:
	return api_key != ""


func is_busy() -> bool:
	return _busy


# Отправляет запрос. Ответ придёт сигналом reply_ready (асинхронно).
func ask(prompt: String) -> void:
	if _busy:
		reply_ready.emit("⚠️ Я ещё отвечаю на предыдущий вопрос.", false)
		return
	if not is_enabled():
		reply_ready.emit("⚠️ API_KEY не задан. Добавь его в .env.", false)
		return

	var messages: Array = [{"role": "system", "content": SYSTEM_PROMPT}]
	if memory != null:
		messages.append_array(memory.context_for_api())
	messages.append({"role": "user", "content": prompt})

	var body := JSON.stringify({"model": model, "messages": messages})
	var headers := PackedStringArray([
		"Authorization: Bearer " + api_key,
		"Content-Type: application/json",
	])
	_busy = true
	var err := _http.request(base_url + "/chat/completions", headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		_busy = false
		reply_ready.emit("⚠️ Не удалось отправить запрос (код %d)." % err, false)


func _on_completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_busy = false
	if result != HTTPRequest.RESULT_SUCCESS:
		reply_ready.emit("⚠️ Сеть недоступна (код %d)." % result, false)
		return
	if code != 200:
		reply_ready.emit("⚠️ API ответил кодом %d." % code, false)
		return
	var parsed = JSON.parse_string(body.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("choices"):
		reply_ready.emit("⚠️ Не разобрал ответ API.", false)
		return
	var text: String = str(parsed["choices"][0]["message"]["content"]).strip_edges()
	reply_ready.emit(text if text != "" else "Я не понял. Повтори проще.", true)
