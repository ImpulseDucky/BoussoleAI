@tool
extends Node2D
## Town — the main overworld. 80x60 tile map with 4 buildings, NPCs, paths, water, trees.
## Uses a TileMapLayer node so tiles are visible & editable in the Godot editor.
## Doors transition to interior scenes. NPCs offer dialogue.

const TILE_SIZE := 32.0
const TILE_GRASS := 0
const TILE_PATH := 1
const TILE_WATER := 2
const TILE_WALL := 3
const TILE_WOOD := 4
const TILE_STONE := 5
const TILE_ROOF := 6
const TILE_TREE := 7
const TILE_FLOWERS := 8
const TILE_SAND := 9
const TILE_ROAD := 10

const MAP_W := 80
const MAP_H := 60

# Building positions (top-left corner)
const HOME_X := 5
const HOME_Y := 4
const TECH_X := 61
const TECH_Y := 4
const LIB_X := 5
const LIB_Y := 48
const CAFE_X := 61
const CAFE_Y := 48
const ART_X := 24
const ART_Y := 4
const CC_X := 44
const CC_Y := 48
const BLD_W := 14
const BLD_H := 10
const BLD_HALF_W := 7  # BLD_W / 2 — pre-computed to avoid integer-division warning

var map: Array = []

@onready var player: CharacterBody2D = $Player
@onready var tile_map: TileMapLayer = $TileMapLayer

func _ready() -> void:
	_generate_and_paint()
	if Engine.is_editor_hint():
		return
	# Runtime-only setup
	_create_collisions()
	_create_doors()
	_create_npcs()
	_create_labels()
	_create_wanderers()
	_setup_camera()
	# Place player at return position or default center (on road, not in water)
	if GameManager.game_started and GameManager.current_location != "town":
		player.global_position = GameManager.return_position
	else:
		player.global_position = Vector2(40 * TILE_SIZE, 24 * TILE_SIZE)
	GameManager.set_location("town")

# ── Map Generation + Tile Painting ──

func _generate_and_paint() -> void:
	map = _generate_map()
	tile_map.clear()
	var src_id := 0  # TileSetAtlasSource ID
	for y in MAP_H:
		for x in MAP_W:
			var t: int = map[y][x]
			# Road tiles use rotated alternative (alt=1) for vertical orientation
			var alt := 1 if t == TILE_ROAD else 0
			tile_map.set_cell(Vector2i(x, y), src_id, Vector2i(t, 0), alt)

func _generate_map() -> Array:
	var m: Array = []
	for y in MAP_H:
		var row: Array = []
		for x in MAP_W:
			row.append(TILE_GRASS)
		m.append(row)
	# Border walls
	for x in MAP_W:
		m[0][x] = TILE_WALL
		m[MAP_H - 1][x] = TILE_WALL
	for y in MAP_H:
		m[y][0] = TILE_WALL
		m[y][MAP_W - 1] = TILE_WALL
	# Buildings (walls on perimeter, floor inside, roof on top)
	_add_building(m, HOME_X, HOME_Y, TILE_WOOD, false)     # Home — wood floor, south door
	_add_building(m, TECH_X, TECH_Y, TILE_STONE, false)    # Tech Studio — stone floor, south door
	_add_building(m, LIB_X, LIB_Y, TILE_WOOD, true)       # Library — wood floor, north door
	_add_building(m, CAFE_X, CAFE_Y, TILE_STONE, true)     # Café — stone floor, north door
	_add_building(m, ART_X, ART_Y, TILE_WOOD, false)       # Art Studio — wood floor, south door
	_add_building(m, CC_X, CC_Y, TILE_STONE, true)         # Community Center — stone floor, north door
	# Main paths (horizontal) — 3 tiles wide pavement
	for x in range(2, MAP_W - 2):
		m[19][x] = TILE_PATH
		m[20][x] = TILE_PATH
		m[21][x] = TILE_PATH
		m[39][x] = TILE_PATH
		m[40][x] = TILE_PATH
		m[41][x] = TILE_PATH
	# Central road (vertical)
	for y in range(20, 41):
		m[y][39] = TILE_ROAD
		m[y][40] = TILE_ROAD
		m[y][41] = TILE_ROAD
	# Connector walkways from buildings to main paths (wood planks, 4 tiles wide)
	# Home door (11, 13) → path at y=20
	for y in range(14, 21):
		for x in range(10, 14):
			m[y][x] = TILE_WOOD
	# Tech door (67, 13) → path at y=20
	for y in range(14, 21):
		for x in range(66, 70):
			m[y][x] = TILE_WOOD
	# Library door (11, 50) → path at y=40
	for y in range(40, 48):
		for x in range(10, 14):
			m[y][x] = TILE_WOOD
	# Café door (67, 50) → path at y=40
	for y in range(40, 48):
		for x in range(66, 70):
			m[y][x] = TILE_WOOD
	# Art Studio door (30, 13) → path at y=20
	for y in range(14, 21):
		for x in range(29, 33):
			m[y][x] = TILE_WOOD
	# Community Center door (50, 50) → path at y=40
	for y in range(40, 48):
		for x in range(49, 53):
			m[y][x] = TILE_WOOD
	# Town Square — flowers and decorations (avoid road columns 39-41)
	for pos in [[33, 24], [47, 24], [33, 36], [47, 36], [28, 22], [52, 22], [28, 38], [52, 38], [22, 18], [58, 18], [22, 42], [58, 42], [20, 15], [60, 15], [20, 45], [60, 45], [55, 28], [25, 33], [55, 33], [50, 30], [15, 22], [65, 22], [15, 38], [65, 38], [22, 24], [31, 24], [22, 33], [31, 33], [37, 24], [43, 24], [37, 36], [43, 36]]:
		m[pos[1]][pos[0]] = TILE_FLOWERS
	# Water pond — scenic spot in open grass (left of road, between paths)
	_add_water(m, 24, 26, 6, 6)
	# Trees around the map
	for pos in [[3, 15], [3, 25], [3, 35], [76, 15], [76, 25], [76, 35], [25, 3], [55, 3], [25, 57], [55, 3], [20, 10], [60, 10], [3, 8], [3, 45], [3, 53], [76, 8], [76, 45], [76, 53], [15, 3], [35, 3], [45, 3], [65, 3], [15, 57], [35, 57], [65, 57], [22, 8], [58, 8], [22, 50], [58, 50], [52, 35], [15, 25], [65, 35], [15, 35], [65, 25], [38, 17], [50, 15], [30, 45], [42, 43], [32, 24], [21, 33], [33, 24], [47, 36], [58, 57], [37, 57]]:
		m[pos[1]][pos[0]] = TILE_TREE
	# Sand beach around the pond (full ring)
	for x in range(23, 31):
		m[25][x] = TILE_SAND
		m[32][x] = TILE_SAND
	for y in range(26, 32):
		m[y][23] = TILE_SAND
		m[y][30] = TILE_SAND
	return m

func _add_building(m: Array, bx: int, by: int, floor_tile: int, north_door: bool) -> void:
	# Fill interior with floor tiles
	for dy in range(2, BLD_H):
		for dx in range(1, BLD_W - 1):
			if by + dy < MAP_H and bx + dx < MAP_W:
				m[by + dy][bx + dx] = floor_tile
	# Wall border (perimeter only, not the roof area)
	for dx in BLD_W:
		m[by + 2][bx + dx] = TILE_WALL  # top wall row
		m[by + BLD_H - 1][bx + dx] = TILE_WALL  # bottom wall row
	for dy in range(2, BLD_H):
		m[by + dy][bx] = TILE_WALL  # left wall
		m[by + dy][bx + BLD_W - 1] = TILE_WALL  # right wall
	# Roof on top 2 rows
	for dy in 2:
		for dx in BLD_W:
			m[by + dy][bx + dx] = TILE_ROOF
	# Door gap (2 tiles wide, center) — wood to match walkways
	var door_x := bx + BLD_HALF_W - 1
	if north_door:
		# Door in top wall row (y = by + 2)
		m[by + 2][door_x] = TILE_WOOD
		m[by + 2][door_x + 1] = TILE_WOOD
	else:
		# Door in bottom wall row (y = by + BLD_H - 1)
		m[by + BLD_H - 1][door_x] = TILE_WOOD
		m[by + BLD_H - 1][door_x + 1] = TILE_WOOD

func _add_water(m: Array, x: int, y: int, w: int, h: int) -> void:
	for dy in h:
		for dx in w:
			if x + dx < MAP_W and y + dy < MAP_H:
				m[y + dy][x + dx] = TILE_WATER

# ── Collision Bodies ──

func _create_collisions() -> void:
	for y in MAP_H:
		for x in MAP_W:
			var t: int = map[y][x]
			if t == TILE_WALL or t == TILE_WATER or t == TILE_TREE:
				var body := StaticBody2D.new()
				body.position = Vector2(x * TILE_SIZE + TILE_SIZE / 2.0, y * TILE_SIZE + TILE_SIZE / 2.0)
				var col := CollisionShape2D.new()
				var shape := RectangleShape2D.new()
				shape.size = Vector2(TILE_SIZE, TILE_SIZE)
				col.shape = shape
				body.add_child(col)
				add_child(body)

# ── Door Interaction Zones ──

func _create_doors() -> void:
	# Home door (south-facing, door at bottom of building)
	_create_door("home", HOME_X + BLD_HALF_W, HOME_Y + BLD_H - 1)
	# Tech Studio door
	_create_door("tech_studio", TECH_X + BLD_HALF_W, TECH_Y + BLD_H - 1)
	# Library door (north-facing, door at top wall row)
	_create_door("library", LIB_X + BLD_HALF_W, LIB_Y + 2)
	# Café door
	_create_door("cafe", CAFE_X + BLD_HALF_W, CAFE_Y + 2)
	# Art Studio door
	_create_door("art_studio", ART_X + BLD_HALF_W, ART_Y + BLD_H - 1)
	# Community Center door
	_create_door("community_center", CC_X + BLD_HALF_W, CC_Y + 2)

func _create_door(building_id: String, tile_x: int, tile_y: int) -> void:
	var door := Area2D.new()
	door.position = Vector2(tile_x * TILE_SIZE + TILE_SIZE, tile_y * TILE_SIZE + TILE_SIZE / 2.0)
	door.add_to_group("interactable")
	door.set_meta("type", "door")
	door.set_meta("id", building_id)
	var display := building_id.replace("_", " ").capitalize()
	door.set_meta("prompt", "Enter " + display)
	var col := CollisionShape2D.new()
	var shape := CircleShape2D.new()
	shape.radius = 28.0
	col.shape = shape
	door.add_child(col)
	# Quest marker above door (shows floating "!")
	var marker := Node2D.new()
	marker.set_script(preload("res://scripts/quest_marker.gd"))
	marker.position = Vector2(0, -24)
	door.add_child(marker)
	add_child(door)

# ── NPCs ──

func _create_npcs() -> void:
	# Friend in Town Square
	_create_npc("Alex", Vector2(34 * TILE_SIZE, 28 * TILE_SIZE), Color(0.40, 0.70, 0.50), "friend")
	# Librarian near Library
	_create_npc("Pat", Vector2(11 * TILE_SIZE, 43 * TILE_SIZE), Color(0.50, 0.60, 0.85), "librarian")
	# Barista near Café
	_create_npc("Maya", Vector2(67 * TILE_SIZE, 43 * TILE_SIZE), Color(0.80, 0.55, 0.30), "barista")
	# Town guide near center
	_create_npc("Sam", Vector2(40 * TILE_SIZE, 22 * TILE_SIZE), Color(0.60, 0.70, 0.40), "guide")
	# Art Studio guide
	_create_npc("Riley", Vector2(28 * TILE_SIZE, 17 * TILE_SIZE), Color(0.65, 0.35, 0.55), "art_guide")
	# Community Center guide
	_create_npc("Jordan", Vector2(50 * TILE_SIZE, 43 * TILE_SIZE), Color(0.35, 0.55, 0.65), "cc_guide")

func _create_npc(first_name: String, pos: Vector2, color: Color, dialogue_id: String) -> void:
	var npc := Area2D.new()
	npc.position = pos
	npc.set_script(preload("res://scripts/npc.gd"))
	npc.set_meta("npc_name", first_name)
	npc.set_meta("npc_color", color)
	npc.set_meta("dialogue_id", dialogue_id)
	# Area shape for interaction detection
	var area_col := CollisionShape2D.new()
	var area_shape := CircleShape2D.new()
	area_shape.radius = 28.0
	area_col.shape = area_shape
	npc.add_child(area_col)
	add_child(npc)

# ── Building Name Labels ──

func _create_labels() -> void:
	var font := load("res://fonts/ArialUnicode.ttf")
	# South-facing doors (Home, Tech, Art Studio): label just below building on walkway
	_create_label("Home", HOME_X, HOME_Y + BLD_H, font)
	_create_label("Tech Studio", TECH_X, TECH_Y + BLD_H, font)
	_create_label("Art Studio", ART_X, ART_Y + BLD_H, font)
	# North-facing doors (Library, Cafe, Community Center): label just above building on walkway
	_create_label("Library", LIB_X, LIB_Y - 1, font)
	_create_label("Cafe", CAFE_X, CAFE_Y - 1, font)
	_create_label("Community Center", CC_X, CC_Y - 1, font)

func _create_label(text: String, bx: int, label_tile_y: int, font: Font) -> void:
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", font)
	label.add_theme_font_size_override("font_size", 16)
	label.add_theme_color_override("font_color", Color(1, 1, 1, 0.95))
	label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.85))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	# Center label in front of the door
	var center_x := (bx + BLD_HALF_W) * TILE_SIZE
	var center_y := label_tile_y * TILE_SIZE
	label.size = Vector2(300, 24)
	label.position = Vector2(center_x - 150, center_y - 12)
	add_child(label)

# ── Wandering Citizens ──

func _create_wanderers() -> void:
	var colors := [
		Color(0.80, 0.40, 0.30),  # warm red
		Color(0.30, 0.60, 0.80),  # sky blue
		Color(0.70, 0.60, 0.20),  # mustard
		Color(0.50, 0.70, 0.40),  # green
		Color(0.80, 0.50, 0.70),  # pink
		Color(0.40, 0.50, 0.70),  # navy
		Color(0.70, 0.70, 0.40),  # olive
		Color(0.60, 0.30, 0.60),  # purple
		Color(0.35, 0.75, 0.65),  # teal
		Color(0.90, 0.65, 0.35),  # orange
		Color(0.55, 0.55, 0.60),  # gray
		Color(0.75, 0.45, 0.35),  # brown
		Color(0.45, 0.65, 0.80),  # light blue
		Color(0.80, 0.60, 0.45),  # tan
		Color(0.50, 0.80, 0.50),  # lime
		Color(0.65, 0.40, 0.50),  # maroon
		Color(0.40, 0.60, 0.50),  # forest
		Color(0.75, 0.55, 0.55),  # dusty rose
		Color(0.60, 0.60, 0.30),  # khaki
		Color(0.55, 0.40, 0.70),  # violet
		Color(0.85, 0.75, 0.55),  # cream
		Color(0.30, 0.50, 0.40),  # teal-dark
	]
	# Start positions spread across the entire map
	var starts := [
		# Top road (y=20)
		Vector2(8 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(15 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(22 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(30 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(35 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(42 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(50 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(55 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(62 * TILE_SIZE, 20 * TILE_SIZE),
		Vector2(68 * TILE_SIZE, 20 * TILE_SIZE),
		# Bottom road (y=40)
		Vector2(8 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(15 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(22 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(30 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(38 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(45 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(52 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(60 * TILE_SIZE, 40 * TILE_SIZE),
		Vector2(68 * TILE_SIZE, 40 * TILE_SIZE),
		# Town square area (center)
		Vector2(40 * TILE_SIZE, 24 * TILE_SIZE),
		Vector2(34 * TILE_SIZE, 26 * TILE_SIZE),
		Vector2(46 * TILE_SIZE, 26 * TILE_SIZE),
		Vector2(40 * TILE_SIZE, 30 * TILE_SIZE),
		Vector2(34 * TILE_SIZE, 32 * TILE_SIZE),
		Vector2(46 * TILE_SIZE, 32 * TILE_SIZE),
		Vector2(40 * TILE_SIZE, 36 * TILE_SIZE),
		# Left side open areas
		Vector2(12 * TILE_SIZE, 24 * TILE_SIZE),
		Vector2(12 * TILE_SIZE, 28 * TILE_SIZE),
		Vector2(15 * TILE_SIZE, 32 * TILE_SIZE),
		Vector2(12 * TILE_SIZE, 36 * TILE_SIZE),
		# Right side open areas
		Vector2(68 * TILE_SIZE, 24 * TILE_SIZE),
		Vector2(68 * TILE_SIZE, 28 * TILE_SIZE),
		Vector2(65 * TILE_SIZE, 32 * TILE_SIZE),
		Vector2(68 * TILE_SIZE, 36 * TILE_SIZE),
		# Near buildings
		Vector2(25 * TILE_SIZE, 22 * TILE_SIZE),   # near Art Studio
		Vector2(50 * TILE_SIZE, 22 * TILE_SIZE),   # near Tech
		Vector2(20 * TILE_SIZE, 44 * TILE_SIZE),   # near Library
		Vector2(50 * TILE_SIZE, 44 * TILE_SIZE),   # near Café
		Vector2(44 * TILE_SIZE, 44 * TILE_SIZE),   # near Community Center
		# Pond area
		Vector2(22 * TILE_SIZE, 28 * TILE_SIZE),
		Vector2(28 * TILE_SIZE, 30 * TILE_SIZE),
		# Scattered grassy areas
		Vector2(33 * TILE_SIZE, 24 * TILE_SIZE),
		Vector2(52 * TILE_SIZE, 32 * TILE_SIZE),
		Vector2(30 * TILE_SIZE, 36 * TILE_SIZE),
		Vector2(56 * TILE_SIZE, 36 * TILE_SIZE),
	]
	for i in starts.size():
		var w := Node2D.new()
		w.set_script(preload("res://scripts/wanderer.gd"))
		add_child(w)
		w.setup(map, MAP_W, MAP_H, starts[i], colors[i % colors.size()])

# ── Camera ──

func _setup_camera() -> void:
	var cam := player.get_node("Camera2D") as Camera2D
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = MAP_W * int(TILE_SIZE)
	cam.limit_bottom = MAP_H * int(TILE_SIZE)
