extends Node2D
## QuestMarker — a floating, bobbing exclamation mark drawn above a position.
## Add as a child of any Node2D. The mark appears at local (0, -20) and bobs.

var _t: float = 0.0
var color: Color = Color(1.0, 0.85, 0.1, 1.0)

func _ready() -> void:
	set_process(true)

func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	_t += delta
	queue_redraw()

func _draw() -> void:
	if Engine.is_editor_hint():
		return
	var bob: float = sin(_t * 3.0) * 2.0
	var y: float = -20.0 + bob
	# Glow circle behind
	draw_circle(Vector2(0, y), 6, Color(color.r, color.g, color.b, 0.25))
	# Exclamation bar
	draw_rect(Rect2(-2, y - 6, 4, 9), color)
	# Dot
	draw_circle(Vector2(0, y + 6), 2, color)
