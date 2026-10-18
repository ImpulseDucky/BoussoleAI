@tool
extends Node2D
## Tech Studio Interior — stone floor, computer stations, mentor NPC Sarah.
## Computer activity routes to the current career quest dialogue.

const TILE_SIZE := 32.0
const TILE_PATH := 1
const TILE_WALL := 3
const TILE_STONE := 5
const TILE_DESK := 11
const TILE_COMPUTER := 15

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
				row.append(TILE_STONE)
		m.append(row)
	# Computer stations along top wall
	for cx in [4, 10, 16]:
		m[2][cx] = TILE_COMPUTER
		m[2][cx + 1] = TILE_COMPUTER
		m[3][cx] = TILE_DESK
		m[3][cx + 1] = TILE_DESK
	# Extra desk row
	for cx in [4, 10, 16]:
		m[4][cx] = TILE_DESK
	# Door gap
	m[MAP_H - 1][MAP_HALF_W] = TILE_PATH
	m[MAP_H - 1][MAP_HALF_W + 1] = TILE_PATH
	return m

func _create_collisions() -> void:
	var solid := [TILE_WALL, TILE_DESK, TILE_COMPUTER]
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
	# Computer station — activity routes to career quest dialogue
	_create_zone("activity", "computer", Vector2(5 * TILE_SIZE, 3 * TILE_SIZE), "Use Computer")
	_create_zone("activity", "computer", Vector2(11 * TILE_SIZE, 3 * TILE_SIZE), "Use Computer")
	_create_zone("activity", "computer", Vector2(17 * TILE_SIZE, 3 * TILE_SIZE), "Use Computer")
	# Mentor NPC — Sarah
	_create_npc("Sarah", Vector2(12 * TILE_SIZE, 10 * TILE_SIZE), Color(0.85, 0.45, 0.40), "mentor")
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

func _create_npc(npc_name: String, pos: Vector2, color: Color, dialogue_id: String) -> void:
	var npc := Area2D.new()
	npc.position = pos
	npc.set_script(preload("res://scripts/npc.gd"))
	npc.set_meta("npc_name", npc_name)
	npc.set_meta("npc_color", color)
	npc.set_meta("dialogue_id", dialogue_id)
	var area_col := CollisionShape2D.new()
	var area_shape := CircleShape2D.new()
	area_shape.radius = 28.0
	area_col.shape = area_shape
	npc.add_child(area_col)
	add_child(npc)

func _setup_camera() -> void:
	var cam := player.get_node("Camera2D") as Camera2D
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = MAP_W * int(TILE_SIZE)
	cam.limit_bottom = MAP_H * int(TILE_SIZE)
