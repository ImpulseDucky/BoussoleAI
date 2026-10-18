extends CanvasLayer
## Profile — full-screen overlay showing the player's skill radar chart,
## career match scores, and career path tree.
## Press P to toggle. Found via group "profile".

const FONT := preload("res://fonts/ArialUnicode.ttf")

@onready var bg: ColorRect = $BG
@onready var title_label: Label = $TitleLabel
@onready var radar_area: Control = $RadarArea
@onready var match_vbox: VBoxContainer = $MatchPanel/MatchScroll/MatchVBox
@onready var tree_vbox: VBoxContainer = $TreePanel/TreeScroll/TreeVBox
@onready var hint_label: Label = $HintLabel

var is_open: bool = false
var radar: RadarChart

func _ready() -> void:
	add_to_group("profile")
	visible = false
	radar = RadarChart.new()
	radar_area.add_child(radar)
	radar.position = Vector2.ZERO
	radar.size = radar_area.size

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_P or event.keycode == KEY_ESCAPE or event.keycode == KEY_E or event.keycode == KEY_SPACE or event.keycode == KEY_M or event.keycode == KEY_C or event.keycode == KEY_J:
			close()
			get_viewport().set_input_as_handled()

func toggle() -> void:
	if is_open:
		close()
	else:
		open()

func open() -> void:
	is_open = true
	visible = true
	_refresh_all()
	_lock_player(true)

func close() -> void:
	is_open = false
	visible = false
	_lock_player(false)

func _refresh_all() -> void:
	if GameManager.quiz_taken and GameManager.quiz_profile != "":
		title_label.text = "My Profile — " + GameManager.quiz_profile
	else:
		title_label.text = "My Profile"

	radar.size = radar_area.size
	radar.queue_redraw()
	_refresh_matches()
	_refresh_paths()

func _refresh_matches() -> void:
	for child in match_vbox.get_children():
		child.queue_free()

	# Header
	var header := Label.new()
	header.text = "Career Matches"
	header.add_theme_font_override("font", FONT)
	header.add_theme_font_size_override("font_size", 20)
	header.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	match_vbox.add_child(header)

	# Personality summary
	var ptype := Label.new()
	ptype.text = CareerMatch.get_personality_summary()
	ptype.add_theme_font_override("font", FONT)
	ptype.add_theme_font_size_override("font_size", 13)
	ptype.add_theme_color_override("font_color", Color(0.7, 0.8, 1))
	ptype.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ptype.custom_minimum_size = Vector2(360, 0)
	match_vbox.add_child(ptype)

	match_vbox.add_child(HSeparator.new())

	# Top 5 career matches
	var matches: Array = CareerMatch.get_top_matches(5)
	for m in matches:
		var row := VBoxContainer.new()
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_theme_constant_override("separation", 3)

		# Career name + score
		var top_row := HBoxContainer.new()
		top_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

		var name_lbl := Label.new()
		name_lbl.text = m.name
		name_lbl.add_theme_font_override("font", FONT)
		name_lbl.add_theme_font_size_override("font_size", 14)
		var score: int = m.score
		var text_color: Color
		if score >= 80:
			text_color = Color(0.4, 0.9, 0.4)
		elif score >= 60:
			text_color = Color(0.8, 0.75, 0.3)
		else:
			text_color = Color(0.7, 0.7, 0.75)
		name_lbl.add_theme_color_override("font_color", text_color)
		name_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		top_row.add_child(name_lbl)

		var score_lbl := Label.new()
		score_lbl.text = str(score) + "%"
		score_lbl.add_theme_font_override("font", FONT)
		score_lbl.add_theme_font_size_override("font_size", 14)
		score_lbl.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
		score_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		score_lbl.custom_minimum_size = Vector2(50, 0)
		top_row.add_child(score_lbl)

		row.add_child(top_row)

		# Score bar
		var bar_bg := Panel.new()
		bar_bg.custom_minimum_size = Vector2(360, 8)
		bar_bg.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(bar_bg)

		var bar_fill := ColorRect.new()
		var bar_color: Color
		if score >= 80:
			bar_color = Color(0.4, 0.9, 0.4)
		elif score >= 60:
			bar_color = Color(0.8, 0.75, 0.3)
		else:
			bar_color = Color(0.5, 0.5, 0.55)
		bar_fill.color = bar_color
		bar_fill.position = Vector2(2, 2)
		bar_fill.size = Vector2(356.0 * score / 100.0, 4)
		bar_bg.add_child(bar_fill)

		# Reasoning
		var reason := Label.new()
		reason.text = m.reasoning
		reason.add_theme_font_override("font", FONT)
		reason.add_theme_font_size_override("font_size", 12)
		reason.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))
		reason.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		reason.custom_minimum_size = Vector2(360, 0)
		row.add_child(reason)

		match_vbox.add_child(row)

		# Spacer
		var spacer := Control.new()
		spacer.custom_minimum_size = Vector2(0, 6)
		match_vbox.add_child(spacer)

func _refresh_paths() -> void:
	for child in tree_vbox.get_children():
		child.queue_free()

	# Header
	var header := Label.new()
	header.text = "Career Paths"
	header.add_theme_font_override("font", FONT)
	header.add_theme_font_size_override("font_size", 20)
	header.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	tree_vbox.add_child(header)

	# Subtitle
	var sub := Label.new()
	sub.text = "How careers connect — skills transfer between roles"
	sub.add_theme_font_override("font", FONT)
	sub.add_theme_font_size_override("font_size", 12)
	sub.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))
	sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	sub.custom_minimum_size = Vector2(360, 0)
	tree_vbox.add_child(sub)

	tree_vbox.add_child(HSeparator.new())

	# Each path
	for i in range(CareerPaths.get_path_count()):
		var path: Dictionary = CareerPaths.get_path_data(i)
		var career_ids: Array = path["careers"]

		# Path name
		var pname := Label.new()
		pname.text = path["name"]
		pname.add_theme_font_override("font", FONT)
		pname.add_theme_font_size_override("font_size", 14)
		pname.add_theme_color_override("font_color", path["color"])
		tree_vbox.add_child(pname)

		# Description
		var pdesc := Label.new()
		pdesc.text = path["desc"]
		pdesc.add_theme_font_override("font", FONT)
		pdesc.add_theme_font_size_override("font_size", 12)
		pdesc.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))
		tree_vbox.add_child(pdesc)

		# Career chain with arrows
		var chain := HBoxContainer.new()
		chain.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		chain.add_theme_constant_override("separation", 2)

		for j in range(career_ids.size()):
			var cid: String = career_ids[j]
			var cname: String = CareerData.get_career_name(cid)
			var progress: int = GameManager.get_career_progress(cid)
			var total: int = CareerData.get_quest_count(cid)

			var pill := Label.new()
			pill.add_theme_font_override("font", FONT)
			pill.add_theme_font_size_override("font_size", 11)
			if progress >= total and total > 0:
				pill.text = "[v] " + cname
				pill.add_theme_color_override("font_color", Color(0.4, 0.9, 0.4))
			elif progress > 0:
				pill.text = "[o] " + cname
				pill.add_theme_color_override("font_color", Color(0.8, 0.75, 0.3))
			else:
				pill.text = "[ ] " + cname
				pill.add_theme_color_override("font_color", Color(0.65, 0.65, 0.7))
			pill.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			pill.custom_minimum_size = Vector2(80, 0)
			pill.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			chain.add_child(pill)

			if j < career_ids.size() - 1:
				var arrow := Label.new()
				arrow.text = " >"
				arrow.add_theme_font_override("font", FONT)
				arrow.add_theme_font_size_override("font_size", 11)
				arrow.add_theme_color_override("font_color", path["color"])
				chain.add_child(arrow)

		tree_vbox.add_child(chain)

		var spacer := Control.new()
		spacer.custom_minimum_size = Vector2(0, 8)
		tree_vbox.add_child(spacer)

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)

# ── Inner class: RadarChart ──
# Draws a spider/radar chart of the 5 skills using _draw().
class RadarChart:
	extends Control

	const SKILL_ORDER := ["technical", "creativity", "communication", "problem_solving", "organization"]
	const SKILL_COLORS := {
		"technical": Color(0.30, 0.50, 0.80),
		"creativity": Color(0.65, 0.40, 0.75),
		"communication": Color(0.80, 0.65, 0.25),
		"problem_solving": Color(0.35, 0.65, 0.35),
		"organization": Color(0.55, 0.45, 0.55),
	}
	const MAX_LEVEL := 5

	func _draw() -> void:
		var center := size * 0.5
		var radius := minf(size.x, size.y) * 0.38
		var n := SKILL_ORDER.size()

		# Background grid — concentric pentagons
		for ring in range(1, MAX_LEVEL + 1):
			var r := radius * float(ring) / float(MAX_LEVEL)
			var pts := PackedVector2Array()
			for i in range(n):
				var angle := -PI / 2.0 + TAU * float(i) / float(n)
				pts.append(center + Vector2(cos(angle), sin(angle)) * r)
			pts.append(pts[0])
			var grid_color := Color(1, 1, 1, 0.08) if ring < MAX_LEVEL else Color(1, 1, 1, 0.15)
			draw_polyline(pts, grid_color, 1.0, true)

		# Axis lines from center to each vertex
		for i in range(n):
			var angle := -PI / 2.0 + TAU * float(i) / float(n)
			var end_pt := center + Vector2(cos(angle), sin(angle)) * radius
			draw_line(center, end_pt, Color(1, 1, 1, 0.1), 1.0)

		# Data polygon — the player's skill levels
		var data_pts := PackedVector2Array()
		for i in range(n):
			var skill: String = SKILL_ORDER[i]
			var lvl: int = 1
			if GameManager and GameManager.skills.has(skill):
				lvl = GameManager.skills[skill].level
			lvl = clampi(lvl, 0, MAX_LEVEL)
			var r := radius * float(lvl) / float(MAX_LEVEL)
			var angle := -PI / 2.0 + TAU * float(i) / float(n)
			var pt := center + Vector2(cos(angle), sin(angle)) * r
			data_pts.append(pt)

		# Filled polygon
		if data_pts.size() >= 3:
			var fill_pts := data_pts.duplicate()
			fill_pts.append(data_pts[0])
			draw_colored_polygon(PackedVector2Array(fill_pts), Color(1, 0.85, 0.3, 0.15))
			draw_polyline(PackedVector2Array(fill_pts), Color(1, 0.85, 0.3, 0.7), 2.0, true)

		# Data points
		for i in range(n):
			draw_circle(data_pts[i], 5, SKILL_COLORS[SKILL_ORDER[i]])
			draw_arc(data_pts[i], 5, 0, TAU, 16, Color(1, 1, 1, 0.5), 1.5)

		# Skill labels
		var font := preload("res://fonts/ArialUnicode.ttf")
		for i in range(n):
			var skill: String = SKILL_ORDER[i]
			var angle := -PI / 2.0 + TAU * float(i) / float(n)
			var label_pos := center + Vector2(cos(angle), sin(angle)) * (radius + 30)
			var label_text: String = skill.replace("_", " ").capitalize()
			var lvl: int = 1
			if GameManager and GameManager.skills.has(skill):
				lvl = GameManager.skills[skill].level
			label_text += "\nLv " + str(lvl)
			draw_string(font, label_pos + Vector2(-40, -10), label_text,
				HORIZONTAL_ALIGNMENT_CENTER, -1, 13, SKILL_COLORS[skill])
