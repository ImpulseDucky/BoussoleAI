extends CharacterBody2D
## Player — top-down movement, interaction system, character drawing.
## Keys: WASD/Arrows=move, E/Space=interact, ESC=pause, M=map, C=careers,
##       P=profile, B=badges, N=shop, J=journal.

const SPEED := 300.0
const RADIUS := 11.0

var facing := Vector2.DOWN
var input_locked := false
var nearby: Array = []
var _walk_t: float = 0.0
var _moving: bool = false

@onready var interaction_area: Area2D = $InteractionArea

func _ready() -> void:
	add_to_group("player")
	interaction_area.area_entered.connect(_on_area_entered)
	interaction_area.area_exited.connect(_on_area_exited)

func _physics_process(_delta: float) -> void:
	if input_locked:
		velocity = Vector2.ZERO
		move_and_slide()
		return
	var dir := Vector2.ZERO
	dir.x = Input.get_axis("ui_left", "ui_right")
	dir.y = Input.get_axis("ui_up", "ui_down")
	if Input.is_physical_key_pressed(KEY_A): dir.x -= 1.0
	if Input.is_physical_key_pressed(KEY_D): dir.x += 1.0
	if Input.is_physical_key_pressed(KEY_W): dir.y -= 1.0
	if Input.is_physical_key_pressed(KEY_S): dir.y += 1.0
	if dir.length() > 0:
		facing = dir.normalized()
	dir = dir.normalized()
	velocity = dir * SPEED
	_moving = velocity.length() > 10
	if _moving:
		_walk_t += _delta * 11.0
	move_and_slide()
	queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_E, KEY_SPACE:
				_try_interact()
			KEY_ESCAPE:
				_toggle_pause()
			KEY_J:
				_toggle_journal()
			KEY_M:
				_toggle_quest_map()
			KEY_C:
				_toggle_career_tracker()
			KEY_P:
				_toggle_profile()
			KEY_B:
				_toggle_achievements()
			KEY_N:
				_toggle_shop()

func _on_area_entered(area: Area2D) -> void:
	if area.is_in_group("interactable"):
		nearby.append(area)
		_update_prompt()

func _on_area_exited(area: Area2D) -> void:
	nearby.erase(area)
	_update_prompt()

func _get_nearest() -> Area2D:
	if nearby.is_empty():
		return null
	var nearest: Area2D = nearby[0]
	for area in nearby:
		if global_position.distance_to(area.global_position) < global_position.distance_to(nearest.global_position):
			nearest = area
	return nearest

func _try_interact() -> void:
	var nearest := _get_nearest()
	if nearest == null:
		return
	AudioManager.play_sfx("click")
	var type := str(nearest.get_meta("type", ""))
	var id := str(nearest.get_meta("id", ""))
	match type:
		"dialogue", "activity":
			if id == "shop":
				var shop := get_tree().get_first_node_in_group("shop")
				if shop and shop.has_method("open"):
					shop.open()
				return
			var d := get_tree().get_first_node_in_group("dialogue")
			if d and d.has_method("start"):
				d.start(id)
		"door":
			GameManager.return_position = global_position
			GameManager.set_location(id)
			SaveManager.save_game()
			TransitionManager.change_scene("res://scenes/interiors/" + id + ".tscn")
		"exit":
			TransitionManager.change_scene("res://scenes/town.tscn")

func _update_prompt() -> void:
	var hud := get_tree().get_first_node_in_group("hud")
	if hud == null:
		return
	var nearest := _get_nearest()
	if nearest == null:
		if hud.has_method("hide_prompt"):
			hud.hide_prompt()
	else:
		var prompt := str(nearest.get_meta("prompt", "Press E"))
		if hud.has_method("show_prompt"):
			hud.show_prompt(prompt)

func _toggle_pause() -> void:
	AudioManager.play_sfx("click")
	var pm := get_tree().get_first_node_in_group("pause_menu")
	if pm and pm.has_method("toggle"):
		pm.toggle()

func _toggle_journal() -> void:
	AudioManager.play_sfx("click")
	var j := get_tree().get_first_node_in_group("journal")
	if j and j.has_method("toggle"):
		j.toggle()

func _toggle_quest_map() -> void:
	AudioManager.play_sfx("click")
	var qm := get_tree().get_first_node_in_group("quest_map")
	if qm and qm.has_method("toggle"):
		qm.toggle()

func _toggle_career_tracker() -> void:
	AudioManager.play_sfx("click")
	var ct := get_tree().get_first_node_in_group("career_tracker")
	if ct and ct.has_method("toggle"):
		ct.toggle()

func _toggle_profile() -> void:
	AudioManager.play_sfx("click")
	var p := get_tree().get_first_node_in_group("profile")
	if p and p.has_method("toggle"):
		p.toggle()

func _toggle_achievements() -> void:
	AudioManager.play_sfx("click")
	var a := get_tree().get_first_node_in_group("achievement_screen")
	if a and a.has_method("toggle"):
		a.toggle()

func _toggle_shop() -> void:
	AudioManager.play_sfx("click")
	var s := get_tree().get_first_node_in_group("shop")
	if s and s.has_method("toggle"):
		s.toggle()

func _draw() -> void:
	var bob: float = sin(_walk_t) * 2.0 if _moving else 0.0
	# Shadow
	draw_circle(Vector2(0, 3), 14, Color(0, 0, 0, 0.12))
	# Body (shirt) — shifted by walk bob
	draw_rect(Rect2(-9, bob, 18, 12), Color(0.20, 0.45, 0.70))
	draw_rect(Rect2(-9, bob, 18, 3), Color(0.15, 0.35, 0.60))
	# Hair (behind head)
	draw_circle(Vector2(0, -6 + bob), 8, Color(0.25, 0.18, 0.12))
	# Head (skin)
	draw_circle(Vector2(0, -5 + bob), 6, Color(0.88, 0.74, 0.60))
	# Eyes (shifted by facing)
	var eo := facing * 2.0
	draw_circle(Vector2(-2.2, -5 + bob) + eo, 1.2, Color(0.12, 0.12, 0.15))
	draw_circle(Vector2(2.2, -5 + bob) + eo, 1.2, Color(0.12, 0.12, 0.15))
	# Direction indicator
	if facing.length() > 0:
		draw_circle(facing * 10, 2, Color(1, 1, 1, 0.4))
