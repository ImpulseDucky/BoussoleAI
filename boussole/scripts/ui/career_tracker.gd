extends CanvasLayer
## Career Tracker — full-screen overlay for career planning and quest tracking.
## Press C to toggle. Found via group "career_tracker".
## Shows all 27 careers with per-career quest progress (X/5) and total (X/135).

const FONT := preload("res://fonts/ArialUnicode.ttf")

const LOCATIONS := ["Tech Studio", "Library", "Cafe", "Town Square", "Home"]

const LOC_COLORS := {
	"Tech Studio": Color(0.30, 0.50, 0.80),
	"Library": Color(0.55, 0.40, 0.65),
	"Cafe": Color(0.75, 0.55, 0.30),
	"Town Square": Color(0.80, 0.65, 0.25),
	"Home": Color(0.35, 0.55, 0.35),
}

var is_open: bool = false
var _panel: Panel
var _scroll: ScrollContainer
var _vbox: VBoxContainer

func _ready() -> void:
	add_to_group("career_tracker")
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
	bg.color = Color(0.06, 0.05, 0.04, 0.97)
	_panel.add_child(bg)

	# Title
	var title := Label.new()
	title.text = "CAREER TRACKER"
	title.add_theme_font_override("font", FONT)
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 10)
	title.size = Vector2(1280, 36)
	_panel.add_child(title)

	# Scrollable career list
	_scroll = ScrollContainer.new()
	_scroll.position = Vector2(40, 56)
	_scroll.size = Vector2(1200, 668)
	_panel.add_child(_scroll)

	_vbox = VBoxContainer.new()
	_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_vbox.add_theme_constant_override("separation", 3)
	_scroll.add_child(_vbox)

	# Hint label at bottom
	var hint := Label.new()
	hint.text = "Press C or ESC to close"
	hint.add_theme_font_override("font", FONT)
	hint.add_theme_font_size_override("font_size", 14)
	hint.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.position = Vector2(0, 736)
	hint.size = Vector2(1280, 24)
	_panel.add_child(hint)

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_C or event.keycode == KEY_M or event.keycode == KEY_J or event.keycode == KEY_P or event.keycode == KEY_ESCAPE or event.keycode == KEY_E or event.keycode == KEY_SPACE:
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
	_refresh()
	_lock_player(true)

func close() -> void:
	is_open = false
	_panel.visible = false
	_lock_player(false)

func _refresh() -> void:
	# Clear existing children
	for child in _vbox.get_children():
		child.queue_free()

	var total_done: int = GameManager.get_total_quests_done()
	var total_quests: int = GameManager.get_total_career_quests()
	var careers_started: int = 0
	var careers_complete: int = GameManager.get_careers_completed_count()
	var pinned_count: int = GameManager.pinned_jobs.size()

	# Count careers started (progress > 0)
	for career_id in CareerData.get_all_career_ids():
		if GameManager.get_career_progress(career_id) > 0:
			careers_started += 1

	# Summary header
	var summary := Label.new()
	summary.text = "Quests Done: " + str(total_done) + "/" + str(total_quests) + "  |  Careers Started: " + str(careers_started) + "/" + str(CareerData.get_career_count()) + "  |  Completed: " + str(careers_complete) + "  |  Tracking: " + str(pinned_count)
	summary.add_theme_font_override("font", FONT)
	summary.add_theme_font_size_override("font_size", 16)
	summary.add_theme_color_override("font_color", Color(0.7, 0.85, 0.95))
	summary.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_vbox.add_child(summary)

	_add_spacer(10)

	# "Tracking Now" section (if any pinned careers)
	if pinned_count > 0:
		var track_header := Label.new()
		track_header.text = ">> TRACKING NOW <<"
		track_header.add_theme_font_override("font", FONT)
		track_header.add_theme_font_size_override("font_size", 16)
		track_header.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
		_vbox.add_child(track_header)

		for career_id in GameManager.pinned_jobs:
			_add_career_row(career_id, true)

		_add_spacer(12)

	# All careers by location
	for location in LOCATIONS:
		var career_ids: Array = CareerData.get_careers_by_location(location)
		if career_ids.is_empty():
			continue

		var loc_done := 0
		var loc_total := 0
		for career_id in career_ids:
			loc_done += GameManager.get_career_progress(career_id)
			loc_total += CareerData.get_quest_count(career_id)

		var loc_header := Label.new()
		loc_header.text = location + "  (" + str(loc_done) + "/" + str(loc_total) + " quests done)"
		loc_header.add_theme_font_override("font", FONT)
		loc_header.add_theme_font_size_override("font_size", 18)
		loc_header.add_theme_color_override("font_color", LOC_COLORS.get(location, Color.WHITE))
		_vbox.add_child(loc_header)

		for career_id in career_ids:
			_add_career_row(career_id, false)

		_add_spacer(10)

func _add_career_row(career_id: String, is_tracking_section: bool) -> void:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 8)

	var progress: int = GameManager.get_career_progress(career_id)
	var total: int = CareerData.get_quest_count(career_id)
	var pinned: bool = GameManager.is_job_pinned(career_id)
	var cname: String = CareerData.get_career_name(career_id)

	# Left: career name + quest progress
	var info := Label.new()
	info.add_theme_font_override("font", FONT)
	info.add_theme_font_size_override("font_size", 14)
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var progress_text: String
	if progress >= total:
		progress_text = "COMPLETE! " + str(total) + "/" + str(total)
	else:
		progress_text = "Quest " + str(progress + 1) + " of " + str(total) + "  (" + str(progress) + "/" + str(total) + " done)"

	var indent = "      " if is_tracking_section else "    "
	info.text = indent + cname + " — " + progress_text

	if progress >= total:
		info.add_theme_color_override("font_color", Color(0.4, 0.9, 0.4))
	elif progress > 0:
		info.add_theme_color_override("font_color", Color(0.82, 0.82, 0.88))
	else:
		info.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))

	row.add_child(info)

	# Right: skills label (right-aligned)
	var skill_names: Array = []
	for s in CareerData.get_career_skills(career_id):
		skill_names.append(s.replace("_", " ").capitalize())
	var skills_lbl := Label.new()
	skills_lbl.text = "Skills: " + ", ".join(skill_names)
	skills_lbl.add_theme_font_override("font", FONT)
	skills_lbl.add_theme_font_size_override("font_size", 12)
	skills_lbl.add_theme_color_override("font_color", Color(0.55, 0.7, 0.9))
	skills_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	skills_lbl.custom_minimum_size = Vector2(260, 0)
	row.add_child(skills_lbl)

	# Track/Untrack button
	var btn := Button.new()
	btn.add_theme_font_override("font", FONT)
	btn.add_theme_font_size_override("font_size", 12)
	btn.text = "Untrack" if pinned else "Track"
	btn.custom_minimum_size = Vector2(80, 30)
	var jid: String = career_id
	btn.pressed.connect(func():
		if GameManager.is_job_pinned(jid):
			GameManager.unpin_job(jid)
		else:
			GameManager.pin_job(jid)
		_refresh()
	)
	row.add_child(btn)

	_vbox.add_child(row)

func _add_spacer(height: float) -> void:
	var s := Control.new()
	s.custom_minimum_size = Vector2(0, height)
	_vbox.add_child(s)

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
