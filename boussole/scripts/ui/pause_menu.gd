extends CanvasLayer
## Pause Menu — overlay with Resume, Save, Journal, Career Compass, Quit.
## Found via group "pause_menu". Toggle with ESC.

@onready var panel: Panel = $Panel
@onready var resume_btn: Button = $Panel/VBox/ResumeButton
@onready var save_btn: Button = $Panel/VBox/SaveButton
@onready var journal_btn: Button = $Panel/VBox/JournalButton
@onready var map_btn: Button = $Panel/VBox/MapButton
@onready var tracker_btn: Button = $Panel/VBox/TrackerButton
@onready var profile_btn: Button = $Panel/VBox/ProfileButton
@onready var compass_btn: Button = $Panel/VBox/CompassButton
@onready var achievement_btn: Button = $Panel/VBox/AchievementButton
@onready var shop_btn: Button = $Panel/VBox/ShopButton
@onready var settings_btn: Button = $Panel/VBox/SettingsButton
@onready var quit_btn: Button = $Panel/VBox/QuitButton
@onready var status_label: Label = $Panel/VBox/StatusLabel

var is_open: bool = false

func _ready() -> void:
	add_to_group("pause_menu")
	panel.visible = false
	resume_btn.pressed.connect(toggle)
	save_btn.pressed.connect(_on_save)
	journal_btn.pressed.connect(_on_journal)
	map_btn.pressed.connect(_on_map)
	tracker_btn.pressed.connect(_on_tracker)
	profile_btn.pressed.connect(_on_profile)
	compass_btn.pressed.connect(_on_compass)
	achievement_btn.pressed.connect(_on_achievements)
	shop_btn.pressed.connect(_on_shop)
	settings_btn.pressed.connect(_on_settings)
	quit_btn.pressed.connect(_on_quit)

func toggle() -> void:
	AudioManager.play_sfx("click")
	if is_open:
		close()
	else:
		open()

func open() -> void:
	is_open = true
	panel.visible = true
	status_label.text = "Day " + str(GameManager.day) + " | " + GameManager.get_time_string() + " | $" + str(GameManager.money)
	_lock_player(true)

func close() -> void:
	is_open = false
	panel.visible = false
	_lock_player(false)

func _on_save() -> void:
	SaveManager.save_game()
	status_label.text = "Game saved! | Day " + str(GameManager.day) + " | $" + str(GameManager.money)

func _on_journal() -> void:
	close()
	var j := get_tree().get_first_node_in_group("journal")
	if j and j.has_method("open"):
		j.open()

func _on_map() -> void:
	close()
	var qm := get_tree().get_first_node_in_group("quest_map")
	if qm and qm.has_method("open"):
		qm.open()

func _on_tracker() -> void:
	close()
	var ct := get_tree().get_first_node_in_group("career_tracker")
	if ct and ct.has_method("open"):
		ct.open()

func _on_profile() -> void:
	close()
	var p := get_tree().get_first_node_in_group("profile")
	if p and p.has_method("open"):
		p.open()

func _on_compass() -> void:
	close()
	var cc := get_tree().get_first_node_in_group("career_compass")
	if cc and cc.has_method("show_compass"):
		cc.show_compass()

func _on_achievements() -> void:
	close()
	var a := get_tree().get_first_node_in_group("achievement_screen")
	if a and a.has_method("open"):
		a.open()

func _on_shop() -> void:
	close()
	var s := get_tree().get_first_node_in_group("shop")
	if s and s.has_method("open"):
		s.open()

func _on_settings() -> void:
	close()
	var s := get_tree().get_first_node_in_group("settings")
	if s and s.has_method("open"):
		s.open()

func _on_quit() -> void:
	close()
	SaveManager.save_game()
	GameManager.game_started = false
	TransitionManager.change_scene("res://scenes/main.tscn")

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
