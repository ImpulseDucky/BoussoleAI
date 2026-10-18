@tool
extends Node2D
## Library Interior — wood floor, bookshelves, study desks.
## Study activity advances time, costs energy, gains Technical XP.

const TILE_SIZE := 32.0
const TILE_PATH := 1
const TILE_WALL := 3
const TILE_WOOD := 4
const TILE_DESK := 11
const TILE_BOOKSHELF := 12

const MAP_W := 24
const MAP_H := 18
const MAP_HALF_W := 12  # MAP_W / 2 — pre-computed to avoid integer-division warning

var map: Array = []

@onready var player: CharacterBody2D = $Player
@onready var tile_map: TileMapLayer = $TileMapLayer

func _ready() -> void:
	_generate_and_paint()
	if Engine.is_editor_hint():
		return
	_create_collisions()
	_create_interactables()
	_setup_camera()
	player.global_position = Vector2(MAP_HALF_W * TILE_SIZE, (MAP_H - 2) * TILE_SIZE)

func _generate_and_paint() -> void:
	map = _generate_map()
	tile_map.clear()
	var src_id := 0
	for y in MAP_H:
		for x in MAP_W:
			var t: int = map[y][x]
			tile_map.set_cell(Vector2i(x, y), src_id, Vector2i(t, 0))

func _generate_map() -> Array:
	var m: Array = []
	for y in MAP_H:
		var row: Array = []
		for x in MAP_W:
			if x == 0 or x == MAP_W - 1 or y == 0 or y == MAP_H - 1:
				row.append(TILE_WALL)
			else:
				row.append(TILE_WOOD)
		m.append(row)
	# Bookshelves along left and right walls
	for y in range(2, MAP_H - 2):
		m[y][2] = TILE_BOOKSHELF
		m[y][3] = TILE_BOOKSHELF
		m[y][MAP_W - 3] = TILE_BOOKSHELF
		m[y][MAP_W - 4] = TILE_BOOKSHELF
	# Study desks in center
	for dx in [8, 14]:
		for dy in [6, 10]:
			m[dy][dx] = TILE_DESK
			m[dy][dx + 1] = TILE_DESK
	# Door gap
	m[MAP_H - 1][MAP_HALF_W] = TILE_PATH
	m[MAP_H - 1][MAP_HALF_W + 1] = TILE_PATH
	return m

func _create_collisions() -> void:
	var solid := [TILE_WALL, TILE_DESK, TILE_BOOKSHELF]
	for y in MAP_H:
		for x in MAP_W:
			if map[y][x] in solid:
				var body := StaticBody2D.new()
				body.position = Vector2(x * TILE_SIZE + TILE_SIZE / 2.0, y * TILE_SIZE + TILE_SIZE / 2.0)
				var col := CollisionShape2D.new()
				var shape := RectangleShape2D.new()
				shape.size = Vector2(TILE_SIZE, TILE_SIZE)
				col.shape = shape
				body.add_child(col)
				add_child(body)

func _create_interactables() -> void:
	# Study desks
	_create_zone("activity", "study", Vector2(9 * TILE_SIZE, 7 * TILE_SIZE), "Study")
	_create_zone("activity", "study", Vector2(15 * TILE_SIZE, 7 * TILE_SIZE), "Study")
	_create_zone("activity", "study", Vector2(9 * TILE_SIZE, 11 * TILE_SIZE), "Study")
	_create_zone("activity", "study", Vector2(15 * TILE_SIZE, 11 * TILE_SIZE), "Study")
	# Exit door
	_create_zone("exit", "town", Vector2(MAP_HALF_W * TILE_SIZE + 16, (MAP_H - 1) * TILE_SIZE + 16), "Exit to Town")

func _create_zone(type: String, id: String, pos: Vector2, prompt: String) -> void:
	var zone := Area2D.new()
	zone.position = pos
	zone.add_to_group("interactable")
	zone.set_meta("type", type)
	zone.set_meta("id", id)
	zone.set_meta("prompt", prompt)
	var col := CollisionShape2D.new()
	var shape := CircleShape2D.new()
	shape.radius = 28.0
	col.shape = shape
	zone.add_child(col)
	# Quest marker above zone
	var marker := Node2D.new()
	marker.set_script(preload("res://scripts/quest_marker.gd"))
	marker.position = Vector2(0, -24)
	zone.add_child(marker)
	add_child(zone)

func _setup_camera() -> void:
	var cam := player.get_node("Camera2D") as Camera2D
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = MAP_W * int(TILE_SIZE)
	cam.limit_bottom = MAP_H * int(TILE_SIZE)
