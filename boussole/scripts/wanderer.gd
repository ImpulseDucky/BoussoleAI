extends Node2D
## Wanderer — decorative citizen that walks around town randomly.
## Interactable! Talk to them for random tips and knowledge.
## Created by town.gd at runtime. Has walk/idle bob animation,
## eyes that look in movement direction, and visual variety.

const TILE_SIZE := 32.0

# Walkable tile types (copied from town.gd to check collision)
const TILE_GRASS := 0
const TILE_PATH := 1
const TILE_WOOD := 4
const TILE_STONE := 5
const TILE_FLOWERS := 8
const TILE_SAND := 9
const TILE_ROAD := 10

const WALKABLE := [TILE_GRASS, TILE_PATH, TILE_WOOD, TILE_STONE, TILE_FLOWERS, TILE_SAND, TILE_ROAD]

var _map: Array = []
var _map_w: int = 80
var _map_h: int = 60
var _dir: Vector2 = Vector2.DOWN
var _speed: float = 55.0
var _move_timer: float = 0.0
var _pause_timer: float = 0.0
var _walk_t: float = 0.0
var _moving: bool = false
var _color: Color = Color(0.5, 0.5, 0.5)
var _t: float = 0.0

# Variety
var _skin: Color = Color(0.88, 0.74, 0.60)
var _hair: Color = Color(0.25, 0.18, 0.12)
var _hat_type: int = 0  # 0=none, 1=cap, 2=round hat, 3=beanie
var _hat_color: Color = Color(0.3, 0.3, 0.3)
var _body_scale: float = 1.0
var _has_bag: bool = false

func setup(map_ref: Array, map_w: int, map_h: int, start_pos: Vector2, color: Color) -> void:
	_map = map_ref
	_map_w = map_w
	_map_h = map_h
	position = start_pos
	_color = color
	# Random variety
	var skins := [
		Color(0.88, 0.74, 0.60),  # light
		Color(0.78, 0.62, 0.48),  # light-medium
		Color(0.65, 0.48, 0.35),  # medium
		Color(0.50, 0.35, 0.25),  # medium-dark
		Color(0.38, 0.26, 0.18),  # dark
	]
	_skin = skins[randi() % skins.size()]
	var hairs := [
		Color(0.25, 0.18, 0.12),  # dark brown
		Color(0.45, 0.30, 0.15),  # brown
		Color(0.65, 0.45, 0.20),  # light brown
		Color(0.85, 0.70, 0.40),  # blonde
		Color(0.90, 0.90, 0.92),  # white/gray
		Color(0.30, 0.20, 0.15),  # black
		Color(0.60, 0.30, 0.25),  # auburn
	]
	_hair = hairs[randi() % hairs.size()]
	_hat_type = randi() % 5  # 0-4, where 0 = no hat (40% chance of hat)
	if _hat_type > 0:
		_hat_color = Color(randf() * 0.6 + 0.2, randf() * 0.6 + 0.2, randf() * 0.6 + 0.2)
	_body_scale = randf_range(0.85, 1.15)
	_speed = randf_range(40.0, 70.0)
	_has_bag = randf() < 0.3  # 30% have a bag
	_create_interaction_area()
	_pick_new_direction()
	set_process(true)

func _create_interaction_area() -> void:
	var area := Area2D.new()
	area.add_to_group("interactable")
	area.set_meta("type", "dialogue")
	area.set_meta("id", "wanderer_tip")
	area.set_meta("prompt", "Talk")
	var col := CollisionShape2D.new()
	var shape := CircleShape2D.new()
	shape.radius = 16.0
	col.shape = shape
	area.add_child(col)
	add_child(area)

func _process(delta: float) -> void:
	if _map.is_empty():
		return
	_t += delta
	if _pause_timer > 0:
		_pause_timer -= delta
		if _pause_timer <= 0:
			_pick_new_direction()
		_moving = false
	else:
		_move_timer -= delta
		if _move_timer <= 0:
			# Pause for a bit before picking a new direction
			_pause_timer = randf_range(0.5, 2.0)
			_moving = false
		else:
			_moving = true
			_walk_t += delta * 10.0
			var new_pos := position + _dir * _speed * delta
			if _is_walkable(new_pos):
				position = new_pos
			else:
				_pick_new_direction()
	queue_redraw()

func _is_walkable(pos: Vector2) -> bool:
	var tx := int(pos.x / TILE_SIZE)
	var ty := int(pos.y / TILE_SIZE)
	if tx < 1 or tx >= _map_w - 1 or ty < 1 or ty >= _map_h - 1:
		return false
	return WALKABLE.has(_map[ty][tx])

func _pick_new_direction() -> void:
	var angle := randf() * TAU
	_dir = Vector2(cos(angle), sin(angle)).normalized()
	_move_timer = randf_range(2.0, 5.0)
	_moving = true

func _draw() -> void:
	var s := _body_scale
	var bob: float = (sin(_walk_t) * 2.0 if _moving else sin(_t * 1.5) * 1.0) * s
	# Shadow
	draw_circle(Vector2(0, 3), 12 * s, Color(0, 0, 0, 0.12))
	# Bag (behind body, if carrying)
	if _has_bag:
		var bag_side := 6.0 * s
		if _dir.x < 0:
			bag_side = -bag_side
		draw_rect(Rect2(bag_side - 2, bob + 1, 5, 6), Color(0.35, 0.25, 0.18))
		draw_rect(Rect2(bag_side - 2, bob + 1, 5, 2), Color(0.25, 0.18, 0.12))
	# Body (shirt)
	draw_rect(Rect2(-7 * s, bob, 14 * s, 10 * s), _color.darkened(0.2))
	draw_rect(Rect2(-7 * s, bob, 14 * s, 3 * s), _color.darkened(0.35))
	# Hair (behind head)
	draw_circle(Vector2(0, -5 * s + bob), 7 * s, _hair)
	# Head
	draw_circle(Vector2(0, -4 * s + bob), 5 * s, _skin)
	# Eyes (looking in movement direction)
	var eo := _dir * 1.5
	draw_circle(Vector2(-1.8 * s, -4 * s + bob) + eo, 1.0 * s, Color(0.12, 0.12, 0.15))
	draw_circle(Vector2(1.8 * s, -4 * s + bob) + eo, 1.0 * s, Color(0.12, 0.12, 0.15))
	# Hat
	match _hat_type:
		1:  # Cap (baseball cap)
			draw_rect(Rect2(-6 * s, -9 * s + bob, 12 * s, 3 * s), _hat_color)
			draw_rect(Rect2(0, -8 * s + bob, 8 * s, 2 * s), _hat_color)
		2:  # Round hat (fedora-ish)
			draw_rect(Rect2(-8 * s, -8 * s + bob, 16 * s, 2 * s), _hat_color)
			draw_rect(Rect2(-5 * s, -11 * s + bob, 10 * s, 4 * s), _hat_color)
		3:  # Beanie
			draw_circle(Vector2(0, -8 * s + bob), 5 * s, _hat_color)
			draw_rect(Rect2(-5 * s, -7 * s + bob, 10 * s, 2 * s), _hat_color.darkened(0.2))
		4:  # Bucket hat
			draw_rect(Rect2(-7 * s, -8 * s + bob, 14 * s, 2 * s), _hat_color)
			draw_circle(Vector2(0, -9 * s + bob), 4 * s, _hat_color)
