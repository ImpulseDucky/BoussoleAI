extends Area2D
## NPC — blocks movement (StaticBody2D) + interaction (Area2D) + draws character.
## Place in scene or create via town.gd. Set meta: npc_name, npc_color, dialogue_id.
## Draws a floating exclamation mark above head to indicate dialogue available.

const DIALOGUE_ROLES := {
	"friend": "Local Friend",
	"librarian": "Librarian",
	"barista": "Barista",
	"guide": "Town Guide",
	"art_guide": "Art Studio Guide",
	"cc_guide": "Community Center Guide",
	"mentor": "Tech Mentor",
}

var npc_name: String = "NPC"
var npc_color: Color = Color(0.8, 0.5, 0.4)
var dialogue_id: String = ""
var npc_role: String = ""

var _bob_t: float = 0.0
var _last_friendship_level: int = -1

func _ready() -> void:
	# Read data from meta (set by creator before adding to tree)
	npc_name = get_meta("npc_name", "NPC")
	npc_color = get_meta("npc_color", Color(0.8, 0.5, 0.4))
	dialogue_id = get_meta("dialogue_id", "")
	npc_role = DIALOGUE_ROLES.get(dialogue_id, "")

	add_to_group("interactable")
	set_meta("type", "dialogue")
	set_meta("id", dialogue_id)
	_update_prompt()

	# Collision body — blocks player from walking through
	var body := StaticBody2D.new()
	var col := CollisionShape2D.new()
	var shape := CircleShape2D.new()
	shape.radius = 10.0
	col.shape = shape
	body.add_child(col)
	add_child(body)

	set_process(true)
	queue_redraw()

func _update_prompt() -> void:
	var level: int = 0
	if dialogue_id != "":
		level = GameManager.get_npc_friendship_level(dialogue_id)
	var hearts_str: String = ""
	for i in range(level):
		hearts_str += " \u2665"
	if npc_role != "":
		set_meta("prompt", "Talk to " + npc_name + " — " + npc_role + hearts_str)
	else:
		set_meta("prompt", "Talk to " + npc_name + hearts_str)

func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	_bob_t += delta
	# Update friendship hearts in prompt if level changed
	if dialogue_id != "":
		var level: int = GameManager.get_npc_friendship_level(dialogue_id)
		if level != _last_friendship_level:
			_last_friendship_level = level
			_update_prompt()
	queue_redraw()

func _draw() -> void:
	var bob: float = sin(_bob_t * 1.5) * 1.5  # subtle body idle bob
	# Shadow
	draw_circle(Vector2(0, 3), 14, Color(0, 0, 0, 0.12))
	# Body (shirt) — shifted by idle bob
	draw_rect(Rect2(-9, bob, 18, 12), npc_color.darkened(0.2))
	draw_rect(Rect2(-9, bob, 18, 3), npc_color.darkened(0.35))
	# Hair (behind head)
	var hair_c := npc_color.darkened(0.5) if npc_color.r > 0.3 else Color(0.25, 0.18, 0.12)
	draw_circle(Vector2(0, -6 + bob), 8, hair_c)
	# Head
	draw_circle(Vector2(0, -5 + bob), 6, Color(0.88, 0.74, 0.60))
	# Eyes
	draw_circle(Vector2(-2.2, -5 + bob), 1.2, Color(0.12, 0.12, 0.15))
	draw_circle(Vector2(2.2, -5 + bob), 1.2, Color(0.12, 0.12, 0.15))

	# Floating exclamation mark above head (bobbing animation)
	if not Engine.is_editor_hint():
		var ex_bob: float = sin(_bob_t * 3.0) * 2.0
		var y: float = -18.0 + ex_bob
		# Dot
		draw_circle(Vector2(0, y + 5), 2.5, Color(1.0, 0.85, 0.1))
		# Exclamation bar
		draw_rect(Rect2(-1.5, y - 5, 3, 7), Color(1.0, 0.85, 0.1))

		# Friendship hearts above exclamation mark
		if dialogue_id != "":
			var level: int = GameManager.get_npc_friendship_level(dialogue_id)
			if level > 0:
				var heart_y: float = -30.0 + ex_bob * 0.4
				for i in range(level):
					var hx: float = (i - float(level - 1) * 0.5) * 9.0
					_draw_heart(Vector2(hx, heart_y), 3.5, Color(1.0, 0.35, 0.45))

func _draw_heart(center: Vector2, size: float, color: Color) -> void:
	# Two top lobes
	draw_circle(center + Vector2(-size * 0.45, -size * 0.15), size * 0.55, color)
	draw_circle(center + Vector2(size * 0.45, -size * 0.15), size * 0.55, color)
	# Bottom triangle
	var pts := PackedVector2Array([
		center + Vector2(-size * 0.95, -size * 0.05),
		center + Vector2(size * 0.95, -size * 0.05),
		center + Vector2(0, size * 0.75),
	])
	draw_colored_polygon(pts, color)
