extends CanvasLayer
## Quest Map — full-screen overlay showing town map with job locations.
## Press M to toggle. Found via group "quest_map".
## Shows 5 locations with available jobs. Pin jobs to track them on screen.

const FONT := preload("res://fonts/ArialUnicode.ttf")

# ── Travel data: location name → interior scene path ──
const TRAVEL_SCENES := {
	"Home": "res://scenes/interiors/home.tscn",
	"Tech Studio": "res://scenes/interiors/tech_studio.tscn",
	"Art Studio": "res://scenes/interiors/art_studio.tscn",
	"Library": "res://scenes/interiors/library.tscn",
	"Cafe": "res://scenes/interiors/cafe.tscn",
	"Community Center": "res://scenes/interiors/community_center.tscn",
	"Town Square": "res://scenes/town.tscn",
}

# ── Location data ──
# pos is normalized (0-1) within the map area
const LOCATIONS := [
	{
		"name": "Home",
		"pos": Vector2(0.12, 0.18),
		"color": Color(0.35, 0.55, 0.35),
		"jobs": [
			{"id": "home_freelance", "name": "Freelancer"},
			{"id": "home_content", "name": "Content Creator"},
		]
	},
	{
		"name": "Tech Studio",
		"pos": Vector2(0.88, 0.18),
		"color": Color(0.30, 0.50, 0.80),
		"jobs": [
			{"id": "tech_bug_hunt", "name": "Software Developer"},
			{"id": "tech_website", "name": "Web Developer"},
			{"id": "tech_data", "name": "Data Analyst"},
			{"id": "tech_ux", "name": "UI/UX Designer"},
			{"id": "tech_it", "name": "IT Support"},
		]
	},
	{
		"name": "Library",
		"pos": Vector2(0.12, 0.82),
		"color": Color(0.55, 0.40, 0.65),
		"jobs": [
			{"id": "lib_research", "name": "Researcher"},
			{"id": "lib_catalog", "name": "Librarian"},
			{"id": "lib_writer", "name": "Technical Writer"},
			{"id": "lib_archive", "name": "Archivist"},
		]
	},
	{
		"name": "Cafe",
		"pos": Vector2(0.88, 0.82),
		"color": Color(0.75, 0.55, 0.30),
		"jobs": [
			{"id": "cafe_latte", "name": "Barista"},
			{"id": "cafe_catering", "name": "Catering Manager"},
			{"id": "cafe_chef", "name": "Chef"},
			{"id": "cafe_service", "name": "Customer Service"},
		]
	},
	{
		"name": "Town Square",
		"pos": Vector2(0.50, 0.50),
		"color": Color(0.80, 0.65, 0.25),
		"jobs": [
			{"id": "town_event_plan", "name": "Event Planner"},
			{"id": "town_event_run", "name": "Event Manager"},
			{"id": "town_marketing", "name": "Marketing Specialist"},
			{"id": "town_consult", "name": "Consultant"},
		]
	},
	{
		"name": "Art Studio",
		"pos": Vector2(0.37, 0.18),
		"color": Color(0.65, 0.35, 0.55),
		"jobs": [
			{"id": "art_graphic", "name": "Graphic Designer"},
			{"id": "art_photo", "name": "Photographer"},
			{"id": "art_illustrator", "name": "Illustrator"},
			{"id": "art_animator", "name": "Animator"},
		]
	},
	{
		"name": "Community Center",
		"pos": Vector2(0.63, 0.82),
		"color": Color(0.35, 0.55, 0.65),
		"jobs": [
			{"id": "cc_social", "name": "Social Worker"},
			{"id": "cc_youth", "name": "Youth Counselor"},
			{"id": "cc_nonprofit", "name": "Non-Profit Coordinator"},
			{"id": "cc_organizer", "name": "Community Organizer"},
		]
	},
]

var is_open: bool = false
var selected_location: int = -1

var _panel: Panel
var _map_control: MapDrawer
var _job_list_panel: Panel
var _job_list_vbox: VBoxContainer
var _loc_labels: Array = []  # Label nodes for location name + count
var _map_size := Vector2(740, 640)

# Inner class for the map drawing surface (needs _draw() on a Control subclass)
class MapDrawer extends Control:
	var locations: Array = []
	var selected: int = -1
	var map_size: Vector2 = Vector2(740, 640)

	func _draw() -> void:
		var area = map_size
		# Map background
		draw_rect(Rect2(Vector2.ZERO, area), Color(0.10, 0.12, 0.08, 0.9), true)
		# Border
		draw_rect(Rect2(Vector2.ZERO, area), Color(0.3, 0.3, 0.3, 0.5), false, 2.0)

		# Roads connecting locations
		var rc := Color(0.25, 0.23, 0.20, 0.7)
		var rw := 8.0
		if locations.size() >= 5:
			# Home → Town Square → Tech Studio
			_draw_road(locations[0].pos, locations[4].pos, rc, rw, area)
			_draw_road(locations[4].pos, locations[1].pos, rc, rw, area)
			# Library → Town Square → Cafe
			_draw_road(locations[2].pos, locations[4].pos, rc, rw, area)
			_draw_road(locations[4].pos, locations[3].pos, rc, rw, area)
			# Home → Library (left vertical)
			_draw_road(locations[0].pos, locations[2].pos, rc, rw, area)
			# Tech → Cafe (right vertical)
			_draw_road(locations[1].pos, locations[3].pos, rc, rw, area)
		if locations.size() >= 7:
			# Town Square → Art Studio
			_draw_road(locations[4].pos, locations[5].pos, rc, rw, area)
			# Town Square → Community Center
			_draw_road(locations[4].pos, locations[6].pos, rc, rw, area)

		# Location markers
		for i in range(locations.size()):
			var loc = locations[i]
			var lp = area * loc.pos
			var is_sel = (i == selected)
			var radius = 28.0 if is_sel else 20.0
			# Glow if selected
			if is_sel:
				draw_circle(lp, radius + 8, Color(1, 0.85, 0.3, 0.25))
			# Main circle
			draw_circle(lp, radius, loc.color)
			# Inner highlight
			draw_circle(lp + Vector2(-4, -4), radius * 0.4, Color(1, 1, 1, 0.15))
			# Border ring
			draw_arc(lp, radius, 0, TAU, 32, Color(1, 1, 1, 0.5), 2.0)
			# Pin indicator if any job at this location is pinned
			var has_pinned = false
			for job in loc.jobs:
				if GameManager.is_job_pinned(job.id):
					has_pinned = true
					break
			if has_pinned:
				var pin_pos = lp + Vector2(radius * 0.7, -radius * 0.7)
				draw_circle(pin_pos, 7, Color(1, 0.85, 0.3))
				draw_arc(pin_pos, 7, 0, TAU, 16, Color(1, 1, 1, 0.7), 1.5)

		# Arrows from center to pinned locations
		if locations.size() >= 5:
			var center_pos = area * locations[4].pos  # Town Square is center
			for i in range(locations.size()):
				if i == 4:
					continue  # skip center itself
				var loc = locations[i]
				var has_pinned = false
				for job in loc.jobs:
					if GameManager.is_job_pinned(job.id):
						has_pinned = true
						break
				if has_pinned:
					var target = area * loc.pos
					_draw_arrow(center_pos, target, loc.color)

	func _draw_road(p1: Vector2, p2: Vector2, color: Color, width: float, area: Vector2) -> void:
		var a = area * p1
		var b = area * p2
		draw_line(a, b, color, width)

	func _draw_arrow(from: Vector2, to: Vector2, color: Color) -> void:
		var dir = (to - from).normalized()
		# Start and end points (offset from markers so arrow doesn't overlap)
		var start = from + dir * 40.0
		var end = to - dir * 30.0
		if start.distance_to(end) < 20.0:
			return  # too close to draw an arrow
		# Shaft — dashed bright line
		var shaft_color = Color(color.r, color.g, color.b, 0.8)
		var dash_len = 12.0
		var gap_len = 6.0
		var traveled = 0.0
		while traveled < start.distance_to(end):
			var seg_start = start + dir * traveled
			var seg_end = start + dir * minf(traveled + dash_len, start.distance_to(end))
			draw_line(seg_start, seg_end, shaft_color, 3.0)
			traveled += dash_len + gap_len
		# Arrowhead at the end
		var head_len = 16.0
		var head_width = 10.0
		var perp = Vector2(-dir.y, dir.x)
		var tip = end
		var base_l = end - dir * head_len + perp * head_width
		var base_r = end - dir * head_len - perp * head_width
		var head_pts = PackedVector2Array([tip, base_l, base_r])
		draw_colored_polygon(head_pts, Color(color.r, color.g, color.b, 0.9))
		# Outline arrowhead
		head_pts.append(tip)
		draw_polyline(head_pts, Color(1, 1, 1, 0.4), 1.0, true)

func _ready() -> void:
	add_to_group("quest_map")
	_build_ui()
	_panel.visible = false

func _build_ui() -> void:
	# Full-screen panel
	_panel = Panel.new()
	_panel.offset_right = 1280.0
	_panel.offset_bottom = 768.0
	add_child(_panel)

	# Dark background
	var bg := ColorRect.new()
	bg.position = Vector2.ZERO
	bg.size = Vector2(1280, 768)
	bg.color = Color(0.06, 0.05, 0.04, 0.96)
	_panel.add_child(bg)

	# Title
	var title := Label.new()
	title.text = "QUEST MAP"
	title.add_theme_font_override("font", FONT)
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 12)
	title.size = Vector2(1280, 40)
	_panel.add_child(title)

	# Subtitle
	var sub := Label.new()
	sub.text = "Click a location to see career quests. Pin careers to track them on screen."
	sub.add_theme_font_override("font", FONT)
	sub.add_theme_font_size_override("font_size", 13)
	sub.add_theme_color_override("font_color", Color(0.65, 0.65, 0.7))
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.position = Vector2(0, 48)
	sub.size = Vector2(1280, 20)
	_panel.add_child(sub)

	# Map area (left ~58% of screen)
	_map_control = MapDrawer.new()
	_map_control.locations = LOCATIONS
	_map_control.map_size = _map_size
	_map_control.position = Vector2(20, 80)
	_map_control.size = _map_size
	_panel.add_child(_map_control)

	# Location click buttons + name/count labels
	for i in range(LOCATIONS.size()):
		var loc = LOCATIONS[i]
		var lp = _map_size * loc.pos
		# Click button (invisible, covers the marker area)
		var btn := Button.new()
		btn.position = Vector2(lp.x - 55, lp.y - 28)
		btn.size = Vector2(110, 56)
		btn.flat = true
		btn.pressed.connect(_select_location.bind(i))
		_map_control.add_child(btn)
		# Name + count label below the marker
		var lbl := Label.new()
		lbl.add_theme_font_override("font", FONT)
		lbl.add_theme_font_size_override("font_size", 13)
		lbl.add_theme_color_override("font_color", Color(1, 1, 1))
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.position = Vector2(lp.x - 70, lp.y + 24)
		lbl.size = Vector2(140, 34)
		_map_control.add_child(lbl)
		_loc_labels.append(lbl)

	# Job list panel (right side)
	_job_list_panel = Panel.new()
	_job_list_panel.position = Vector2(780, 80)
	_job_list_panel.size = Vector2(480, 640)
	_panel.add_child(_job_list_panel)

	# Scroll container for job list
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(10, 10)
	scroll.size = Vector2(460, 620)
	_job_list_panel.add_child(scroll)

	_job_list_vbox = VBoxContainer.new()
	_job_list_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_job_list_vbox.add_theme_constant_override("separation", 6)
	scroll.add_child(_job_list_vbox)

	# Hint label at bottom
	var hint_label := Label.new()
	hint_label.text = "Press M or ESC to close"
	hint_label.add_theme_font_override("font", FONT)
	hint_label.add_theme_font_size_override("font_size", 14)
	hint_label.add_theme_color_override("font_color", Color(0.55, 0.55, 0.55))
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.position = Vector2(0, 740)
	hint_label.size = Vector2(1280, 24)
	_panel.add_child(hint_label)

	_show_no_selection()

func _refresh_loc_labels() -> void:
	for i in range(LOCATIONS.size()):
		if i < _loc_labels.size():
			var loc = LOCATIONS[i]
			var done = 0
			var total = 0
			var pinned = 0
			for job in loc.jobs:
				done += GameManager.get_career_progress(job.id)
				total += CareerData.get_quest_count(job.id)
				if GameManager.is_job_pinned(job.id):
					pinned += 1
			var txt = loc.name + "\n" + str(done) + "/" + str(total) + " quests"
			if pinned > 0:
				txt += " | " + str(pinned) + " pinned"
			_loc_labels[i].text = txt

func _select_location(idx: int) -> void:
	selected_location = idx
	_map_control.selected = idx
	_refresh_job_list()
	_refresh_loc_labels()
	_map_control.queue_redraw()

func _refresh_job_list() -> void:
	for child in _job_list_vbox.get_children():
		child.queue_free()

	if selected_location < 0:
		_show_no_selection()
		return

	var loc = LOCATIONS[selected_location]

	# Header
	var header := Label.new()
	header.text = loc.name
	header.add_theme_font_override("font", FONT)
	header.add_theme_font_size_override("font_size", 22)
	header.add_theme_color_override("font_color", loc.color)
	_job_list_vbox.add_child(header)

	# Summary
	var done_count = 0
	var total_count = 0
	for job in loc.jobs:
		done_count += GameManager.get_career_progress(job.id)
		total_count += CareerData.get_quest_count(job.id)
	var summary := Label.new()
	summary.text = "Quests Done: " + str(done_count) + "/" + str(total_count)
	summary.add_theme_font_override("font", FONT)
	summary.add_theme_font_size_override("font_size", 13)
	summary.add_theme_color_override("font_color", Color(0.7, 0.7, 0.7))
	_job_list_vbox.add_child(summary)

	# Separator
	var sep := HSeparator.new()
	sep.add_theme_constant_override("separation", 6)
	_job_list_vbox.add_child(sep)

	# Job rows
	for job in loc.jobs:
		var row := HBoxContainer.new()
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_theme_constant_override("separation", 6)

		var progress = GameManager.get_career_progress(job.id)
		var quest_total = CareerData.get_quest_count(job.id)
		var pinned = GameManager.is_job_pinned(job.id)

		# Job name + quest progress
		var info := Label.new()
		info.add_theme_font_override("font", FONT)
		info.add_theme_font_size_override("font_size", 14)
		var status = ""
		if progress >= quest_total:
			status = " (COMPLETE " + str(quest_total) + "/" + str(quest_total) + ")"
		else:
			status = " (" + str(progress) + "/" + str(quest_total) + " quests)"
		info.text = job.name + status
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if progress >= quest_total:
			info.add_theme_color_override("font_color", Color(0.4, 0.9, 0.4))
		elif progress > 0:
			info.add_theme_color_override("font_color", Color(0.82, 0.82, 0.88))
		else:
			info.add_theme_color_override("font_color", Color(0.85, 0.85, 0.9))
		row.add_child(info)

		# Pin/unpin button
		var pin_btn := Button.new()
		pin_btn.add_theme_font_override("font", FONT)
		pin_btn.add_theme_font_size_override("font_size", 12)
		pin_btn.text = "Unpin" if pinned else "Pin"
		pin_btn.custom_minimum_size = Vector2(65, 30)
		var job_id = job.id
		pin_btn.pressed.connect(func():
			if GameManager.is_job_pinned(job_id):
				GameManager.unpin_job(job_id)
			else:
				GameManager.pin_job(job_id)
			_refresh_job_list()
			_refresh_loc_labels()
			_map_control.queue_redraw()
		)
		row.add_child(pin_btn)
		_job_list_vbox.add_child(row)

	# Spacer
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 8)
	_job_list_vbox.add_child(spacer)

	# Travel Here button
	var loc_name = loc.name
	var travel_btn := Button.new()
	travel_btn.text = ">> Travel Here <<"
	travel_btn.add_theme_font_override("font", FONT)
	travel_btn.add_theme_font_size_override("font_size", 15)
	travel_btn.custom_minimum_size = Vector2(0, 38)
	travel_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	# Check if already at this location
	var already_here: bool = GameManager.current_location == loc_name or (loc_name == "Town Square" and GameManager.current_location == "town")
	if already_here:
		travel_btn.text = "(You are here)"
		travel_btn.disabled = true
	else:
		travel_btn.pressed.connect(func():
			_travel_to(loc_name)
		)
	_job_list_vbox.add_child(travel_btn)

	# Visit hint
	var hint := Label.new()
	hint.text = "Visit this location in-game\nto start career quests!"
	hint.add_theme_font_override("font", FONT)
	hint.add_theme_font_size_override("font_size", 12)
	hint.add_theme_color_override("font_color", Color(0.5, 0.5, 0.55))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size = Vector2(440, 0)
	_job_list_vbox.add_child(hint)

func _show_no_selection() -> void:
	for child in _job_list_vbox.get_children():
		child.queue_free()
	var lbl := Label.new()
	lbl.text = "Select a location\non the map\nto see available jobs."
	lbl.add_theme_font_override("font", FONT)
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", Color(0.5, 0.5, 0.55))
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lbl.custom_minimum_size = Vector2(440, 200)
	lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_job_list_vbox.add_child(lbl)

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_M or event.keycode == KEY_C or event.keycode == KEY_J or event.keycode == KEY_P or event.keycode == KEY_ESCAPE or event.keycode == KEY_E or event.keycode == KEY_SPACE:
			close()
			get_viewport().set_input_as_handled()

func toggle() -> void:
	if is_open:
		close()
	else:
		open()

func open() -> void:
	is_open = true
	_panel.visible = true
	selected_location = -1
	_map_control.selected = -1
	_show_no_selection()
	_refresh_loc_labels()
	_map_control.queue_redraw()
	_lock_player(true)

func close() -> void:
	is_open = false
	_panel.visible = false
	_lock_player(false)

func _travel_to(loc_name: String) -> void:
	if not TRAVEL_SCENES.has(loc_name):
		return
	var scene_path: String = TRAVEL_SCENES[loc_name]
	# Close map first
	close()
	# Set location in GameManager
	var loc_key := loc_name.to_lower().replace(" ", "_") if loc_name != "Town Square" else "town"
	GameManager.set_location(loc_key)
	# Transition to the scene
	TransitionManager.change_scene(scene_path)

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
