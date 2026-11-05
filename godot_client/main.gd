extends Node2D
## Клиент Фитца: получает состояние от ui_pyqt.py по WebSocket и меняет вид.
## Протокол: JSON {"state": "think"} где state ∈ calm | think | talk | error | joy

const SERVER_URL := "ws://127.0.0.1:8765"
const RECONNECT_SECONDS := 2.0

const STATES := {
	"calm":  {"label": "спокойствие", "color": Color(0.40, 0.60, 1.00)},
	"think": {"label": "думает",      "color": Color(0.70, 0.50, 1.00)},
	"talk":  {"label": "говорит",     "color": Color(0.30, 0.90, 0.60)},
	"error": {"label": "ошибка",      "color": Color(1.00, 0.30, 0.30)},
	"joy":   {"label": "радость",     "color": Color(1.00, 0.85, 0.30)},
}

@onready var fitz: ColorRect = $Fitz
@onready var label: Label = $Label
@onready var status: Label = $Status

var _peer := WebSocketPeer.new()
var _connected := false
var _reconnect_timer := 0.0
var _state := "calm"
var _tween: Tween

# Мозг: память, инструменты, брейн (API), агент. Собираются в _build_brain().
var memory: Node
var tools: Node
var brain: Node
var agent: Node
var _input: LineEdit
var _answer: RichTextLabel
var _confirm_bar: HBoxContainer


func _ready() -> void:
	_set_state("calm", false)
	_connect_to_server()
	_build_brain()


func _process(delta: float) -> void:
	_peer.poll()
	var st := _peer.get_ready_state()

	if st == WebSocketPeer.STATE_OPEN:
		if not _connected:
			_connected = true
			status.text = "связь с ui_pyqt: OK"
		while _peer.get_available_packet_count() > 0:
			_handle_packet(_peer.get_packet().get_string_from_utf8())
	elif st == WebSocketPeer.STATE_CLOSED:
		if _connected:
			_connected = false
			status.text = "связь потеряна, переподключаюсь..."
		_reconnect_timer -= delta
		if _reconnect_timer <= 0.0:
			_reconnect_timer = RECONNECT_SECONDS
			_connect_to_server()


func _connect_to_server() -> void:
	_peer = WebSocketPeer.new()
	var err := _peer.connect_to_url(SERVER_URL)
	if err != OK:
		status.text = "не удалось подключиться (код %d)" % err
	else:
		status.text = "подключение к %s..." % SERVER_URL


func _handle_packet(text: String) -> void:
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY or not data.has("state"):
		return
	_set_state(str(data["state"]), true)


func _set_state(state: String, animate: bool) -> void:
	if not STATES.has(state):
		return
	_state = state
	var cfg: Dictionary = STATES[state]
	label.text = cfg["label"]

	if _tween and _tween.is_valid():
		_tween.kill()
	_tween = create_tween().set_parallel(true)
	var dur := 0.3 if animate else 0.0
	_tween.tween_property(fitz, "color", cfg["color"], dur)

	# Лёгкая реакция на смену состояния: «подпрыгивание» масштаба.
	fitz.scale = Vector2.ONE
	_tween.tween_property(fitz, "scale", Vector2(1.08, 1.08), dur * 0.5)
	_tween.chain().tween_property(fitz, "scale", Vector2.ONE, dur * 0.5)


# ===== МОЗГ: сборка узлов и UI =====
func _build_brain() -> void:
	memory = preload("res://scripts/memory.gd").new()
	tools = preload("res://scripts/tools.gd").new()
	brain = preload("res://scripts/brain.gd").new()
	agent = preload("res://scripts/agent.gd").new()
	for n in [memory, tools, brain, agent]:
		add_child(n)
	brain.memory = memory
	agent.setup(brain, tools, memory)
	agent.said.connect(_on_said)
	agent.confirm_requested.connect(_on_confirm_requested)

	# Строка ввода внизу окна
	_input = LineEdit.new()
	_input.placeholder_text = "Напиши Фитцу..."
	_input.position = Vector2(10, 300)
	_input.size = Vector2(300, 26)
	_input.text_submitted.connect(_on_text_submitted)
	add_child(_input)

	# Ответ Фитца
	_answer = RichTextLabel.new()
	_answer.position = Vector2(10, 110)
	_answer.size = Vector2(300, 0)
	_answer.visible = false
	add_child(_answer)

	# Панель подтверждения опасного действия
	_confirm_bar = HBoxContainer.new()
	_confirm_bar.position = Vector2(10, 300)
	_confirm_bar.visible = false
	add_child(_confirm_bar)
	var yes := Button.new()
	yes.text = "Да, выполнить"
	yes.pressed.connect(func(): _confirm_bar.visible = false; agent.confirm(true))
	var no := Button.new()
	no.text = "Нет"
	no.pressed.connect(func(): _confirm_bar.visible = false; agent.confirm(false))
	_confirm_bar.add_child(yes)
	_confirm_bar.add_child(no)


func _on_text_submitted(text: String) -> void:
	var t := text.strip_edges()
	if t == "":
		return
	_input.clear()
	_set_state("think", true)
	agent.process(t)


func _on_said(text: String, ok: bool) -> void:
	_set_state("talk" if ok else "error", true)
	_answer.text = text
	_answer.visible = true
	# Возврат в спокойствие после короткой паузы
	get_tree().create_timer(2.0).timeout.connect(func(): _set_state("calm", true))


func _on_confirm_requested(tool: String, args: Dictionary) -> void:
	_set_state("error", true)  # предупреждаем: опасное действие ждёт решения
	_answer.text = "Выполнить опасное действие «%s» %s?" % [tool, JSON.stringify(args)]
	_answer.visible = true
	_confirm_bar.visible = true
