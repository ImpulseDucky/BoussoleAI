extends CanvasLayer
## Achievement Screen — full-screen overlay showing all achievements.
## Press A to toggle. Found via group "achievement_screen".

const FONT := preload("res://fonts/ArialUnicode.ttf")

var is_open: bool = false
var _panel: Panel
var _content: VBoxContainer
var _count_label: Label

func _ready() -> void:
	add_to_group("achievement_screen")
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
	bg.color = Color(0.04, 0.04, 0.06, 0.96)
	_panel.add_child(bg)

	# Title
	var title := Label.new()
	title.text = "ACHIEVEMENTS"
	title.add_theme_font_override("font", FONT)
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 12)
	title.size = Vector2(1280, 40)
	_panel.add_child(title)

	# Count label
	_count_label = Label.new()
	_count_label.add_theme_font_override("font", FONT)
	_count_label.add_theme_font_size_override("font_size", 16)
	_count_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.75))
	_count_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_count_label.position = Vector2(0, 48)
	_count_label.size = Vector2(1280, 24)
	_panel.add_child(_count_label)

	# Scroll container
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(100, 80)
	scroll.size = Vector2(1080, 640)
	_panel.add_child(scroll)

	_content = VBoxContainer.new()
	_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content.add_theme_constant_override("separation", 4)
	scroll.add_child(_content)

	# Hint label
	var hint := Label.new()
	hint.text = "Press A or ESC to close"
	hint.add_theme_font_override("font", FONT)
	hint.add_theme_font_size_override("font_size", 14)
	hint.add_theme_color_override("font_color", Color(0.5, 0.5, 0.55))
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.position = Vector2(0, 740)
	hint.size = Vector2(1280, 24)
	_panel.add_child(hint)

func _refresh() -> void:
	for child in _content.get_children():
		child.queue_free()

	var unlocked_count := GameManager.get_unlocked_count()
	var total_count := AchievementData.get_count()
	_count_label.text = "Unlocked: " + str(unlocked_count) + " / " + str(total_count)

	var categories := AchievementData.get_categories()
	for cat in categories:
		# Category header
		var hdr := Label.new()
		hdr.text = cat
		hdr.add_theme_font_override("font", FONT)
		hdr.add_theme_font_size_override("font_size", 18)
		hdr.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
		_content.add_child(hdr)

		var sep := HSeparator.new()
		sep.add_theme_constant_override("separation", 4)
		_content.add_child(sep)

		for a in AchievementData.get_all():
			if a.category != cat:
				continue
			var unlocked: bool = GameManager.is_achievement_unlocked(a.id)
			_add_achievement_row(a, unlocked)

		# Spacer between categories
		var spacer := Control.new()
		spacer.custom_minimum_size = Vector2(0, 12)
		_content.add_child(spacer)

func _add_achievement_row(a: Dictionary, unlocked: bool) -> void:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 10)

	# Icon
	var icon := Label.new()
	icon.text = a.icon if unlocked else "?"
	icon.add_theme_font_override("font", FONT)
	icon.add_theme_font_size_override("font_size", 20)
	icon.add_theme_color_override("font_color", Color(1, 0.85, 0.3) if unlocked else Color(0.35, 0.35, 0.35))
	icon.custom_minimum_size = Vector2(40, 30)
	icon.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	row.add_child(icon)

	# Name + description
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var name_lbl := Label.new()
	name_lbl.text = a.name
	name_lbl.add_theme_font_override("font", FONT)
	name_lbl.add_theme_font_size_override("font_size", 15)
	name_lbl.add_theme_color_override("font_color", Color(0.9, 0.9, 0.95) if unlocked else Color(0.45, 0.45, 0.5))
	info.add_child(name_lbl)
	var desc_lbl := Label.new()
	desc_lbl.text = a.desc
	desc_lbl.add_theme_font_override("font", FONT)
	desc_lbl.add_theme_font_size_override("font_size", 12)
	desc_lbl.add_theme_color_override("font_color", Color(0.65, 0.65, 0.7) if unlocked else Color(0.38, 0.38, 0.42))
	info.add_child(desc_lbl)
	row.add_child(info)

	# Status
	var status := Label.new()
	status.text = "UNLOCKED" if unlocked else "LOCKED"
	status.add_theme_font_override("font", FONT)
	status.add_theme_font_size_override("font_size", 11)
	status.add_theme_color_override("font_color", Color(0.4, 0.9, 0.4) if unlocked else Color(0.4, 0.4, 0.4))
	status.custom_minimum_size = Vector2(90, 0)
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(status)

	_content.add_child(row)

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

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_A or event.keycode == KEY_ESCAPE or event.keycode == KEY_E or event.keycode == KEY_SPACE:
			close()
			get_viewport().set_input_as_handled()
