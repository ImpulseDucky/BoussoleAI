extends CanvasLayer
## Settings overlay — BGM/SFX volume sliders, ambient particles toggle,
## fullscreen toggle. Accessible from pause menu or settings button.
## Found via group "settings".

const FONT := preload("res://fonts/ArialUnicode.ttf")

var is_open: bool = false
var _panel: Panel
var _bgm_slider: HSlider
var _sfx_slider: HSlider
var _particles_check: CheckBox
var _fullscreen_check: CheckBox
var _bgm_value_lbl: Label
var _sfx_value_lbl: Label

func _ready() -> void:
	add_to_group("settings")
	_build_ui()
	_panel.visible = false

func _build_ui() -> void:
	_panel = Panel.new()
	_panel.offset_right = 1280.0
	_panel.offset_bottom = 768.0
	add_child(_panel)

	var bg := ColorRect.new()
	bg.position = Vector2.ZERO
	bg.size = Vector2(1280, 768)
	bg.color = Color(0.04, 0.04, 0.06, 0.96)
	_panel.add_child(bg)

	var card := Panel.new()
	card.position = Vector2(340, 120)
	card.size = Vector2(600, 500)
	_panel.add_child(card)

	var title := Label.new()
	title.text = "SETTINGS"
	title.add_theme_font_override("font", FONT)
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 20)
	title.size = Vector2(600, 40)
	card.add_child(title)

	var content := VBoxContainer.new()
	content.position = Vector2(40, 80)
	content.size = Vector2(520, 380)
	content.add_theme_constant_override("separation", 24)
	card.add_child(content)

	# BGM volume
	var bgm_row := HBoxContainer.new()
	bgm_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bgm_row.add_theme_constant_override("separation", 12)
	var bgm_lbl := Label.new()
	bgm_lbl.text = "Music Volume"
	bgm_lbl.add_theme_font_override("font", FONT)
	bgm_lbl.add_theme_font_size_override("font_size", 16)
	bgm_lbl.add_theme_color_override("font_color", Color(0.82, 0.82, 0.88))
	bgm_lbl.custom_minimum_size = Vector2(160, 0)
	bgm_row.add_child(bgm_lbl)
	_bgm_slider = HSlider.new()
	_bgm_slider.min_value = 0.0
	_bgm_slider.max_value = 1.0
	_bgm_slider.step = 0.05
	_bgm_slider.value = GameManager.settings_bgm_volume
	_bgm_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bgm_slider.custom_minimum_size = Vector2(200, 20)
	_bgm_slider.value_changed.connect(_on_bgm_changed)
	bgm_row.add_child(_bgm_slider)
	_bgm_value_lbl = Label.new()
	_bgm_value_lbl.text = str(int(GameManager.settings_bgm_volume * 100)) + "%"
	_bgm_value_lbl.add_theme_font_override("font", FONT)
	_bgm_value_lbl.add_theme_font_size_override("font_size", 14)
	_bgm_value_lbl.add_theme_color_override("font_color", Color(0.6, 0.75, 0.95))
	_bgm_value_lbl.custom_minimum_size = Vector2(40, 0)
	_bgm_value_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	bgm_row.add_child(_bgm_value_lbl)
	content.add_child(bgm_row)

	# SFX volume
	var sfx_row := HBoxContainer.new()
	sfx_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sfx_row.add_theme_constant_override("separation", 12)
	var sfx_lbl := Label.new()
	sfx_lbl.text = "Sound Effects"
	sfx_lbl.add_theme_font_override("font", FONT)
	sfx_lbl.add_theme_font_size_override("font_size", 16)
	sfx_lbl.add_theme_color_override("font_color", Color(0.82, 0.82, 0.88))
	sfx_lbl.custom_minimum_size = Vector2(160, 0)
	sfx_row.add_child(sfx_lbl)
	_sfx_slider = HSlider.new()
	_sfx_slider.min_value = 0.0
	_sfx_slider.max_value = 1.0
	_sfx_slider.step = 0.05
	_sfx_slider.value = GameManager.settings_sfx_volume
	_sfx_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_sfx_slider.custom_minimum_size = Vector2(200, 20)
	_sfx_slider.value_changed.connect(_on_sfx_changed)
	sfx_row.add_child(_sfx_slider)
	_sfx_value_lbl = Label.new()
	_sfx_value_lbl.text = str(int(GameManager.settings_sfx_volume * 100)) + "%"
	_sfx_value_lbl.add_theme_font_override("font", FONT)
	_sfx_value_lbl.add_theme_font_size_override("font_size", 14)
	_sfx_value_lbl.add_theme_color_override("font_color", Color(0.6, 0.75, 0.95))
	_sfx_value_lbl.custom_minimum_size = Vector2(40, 0)
	_sfx_value_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	sfx_row.add_child(_sfx_value_lbl)
	content.add_child(sfx_row)

	# Particles toggle
	var part_row := HBoxContainer.new()
	part_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	part_row.add_theme_constant_override("separation", 12)
	var part_lbl := Label.new()
	part_lbl.text = "Ambient Particles"
	part_lbl.add_theme_font_override("font", FONT)
	part_lbl.add_theme_font_size_override("font_size", 16)
	part_lbl.add_theme_color_override("font_color", Color(0.82, 0.82, 0.88))
	part_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	part_row.add_child(part_lbl)
	_particles_check = CheckBox.new()
	_particles_check.text = "On"
	_particles_check.add_theme_font_override("font", FONT)
	_particles_check.add_theme_font_size_override("font_size", 14)
	_particles_check.button_pressed = GameManager.settings_particles
	_particles_check.toggled.connect(_on_particles_toggled)
	part_row.add_child(_particles_check)
	content.add_child(part_row)

	# Fullscreen toggle
	var fs_row := HBoxContainer.new()
	fs_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fs_row.add_theme_constant_override("separation", 12)
	var fs_lbl := Label.new()
	fs_lbl.text = "Fullscreen"
	fs_lbl.add_theme_font_override("font", FONT)
	fs_lbl.add_theme_font_size_override("font_size", 16)
	fs_lbl.add_theme_color_override("font_color", Color(0.82, 0.82, 0.88))
	fs_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fs_row.add_child(fs_lbl)
	_fullscreen_check = CheckBox.new()
	_fullscreen_check.text = "On"
	_fullscreen_check.add_theme_font_override("font", FONT)
	_fullscreen_check.add_theme_font_size_override("font_size", 14)
	_fullscreen_check.button_pressed = GameManager.settings_fullscreen
	_fullscreen_check.toggled.connect(_on_fullscreen_toggled)
	fs_row.add_child(_fullscreen_check)
	content.add_child(fs_row)

	# Close button
	var close_btn := Button.new()
	close_btn.text = "Done"
	close_btn.add_theme_font_override("font", FONT)
	close_btn.add_theme_font_size_override("font_size", 18)
	close_btn.custom_minimum_size = Vector2(200, 44)
	close_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	close_btn.pressed.connect(close)
	content.add_child(close_btn)

	# Hint
	var hint := Label.new()
	hint.text = "Press ESC to close"
	hint.add_theme_font_override("font", FONT)
	hint.add_theme_font_size_override("font_size", 13)
	hint.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.position = Vector2(0, 460)
	hint.size = Vector2(600, 24)
	card.add_child(hint)

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE or event.keycode == KEY_E or event.keycode == KEY_SPACE:
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
	_refresh_values()
	_lock_player(true)

func close() -> void:
	is_open = false
	_panel.visible = false
	AudioManager.play_sfx("click")
	SaveManager.save_game()
	_lock_player(false)

func _refresh_values() -> void:
	_bgm_slider.value = GameManager.settings_bgm_volume
	_sfx_slider.value = GameManager.settings_sfx_volume
	_bgm_value_lbl.text = str(int(GameManager.settings_bgm_volume * 100)) + "%"
	_sfx_value_lbl.text = str(int(GameManager.settings_sfx_volume * 100)) + "%"
	_particles_check.button_pressed = GameManager.settings_particles
	_fullscreen_check.button_pressed = GameManager.settings_fullscreen

func _on_bgm_changed(val: float) -> void:
	GameManager.settings_bgm_volume = val
	AudioManager.set_bgm_volume(val)
	_bgm_value_lbl.text = str(int(val * 100)) + "%"

func _on_sfx_changed(val: float) -> void:
	GameManager.settings_sfx_volume = val
	AudioManager.set_sfx_volume(val)
	_sfx_value_lbl.text = str(int(val * 100)) + "%"
	AudioManager.play_sfx("click")

func _on_particles_toggled(pressed: bool) -> void:
	GameManager.settings_particles = pressed
	AmbientManager.particles_enabled = pressed
	AudioManager.play_sfx("click")

func _on_fullscreen_toggled(pressed: bool) -> void:
	GameManager.settings_fullscreen = pressed
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if pressed else DisplayServer.WINDOW_MODE_WINDOWED)
	AudioManager.play_sfx("click")

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
