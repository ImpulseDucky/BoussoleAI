extends CanvasLayer
## Journal — career quest log and skills display. Toggle with J or from pause menu.
## Shows career quest progress by location and skill levels.
## Found via group "journal".

@onready var panel: Panel = $Panel
@onready var quest_label: RichTextLabel = $Panel/Scroll/VBox/QuestLabel
@onready var skills_label: RichTextLabel = $Panel/Scroll/VBox/SkillsLabel

var is_open: bool = false

const LOCATIONS := ["Tech Studio", "Library", "Cafe", "Town Square", "Home"]

func _ready() -> void:
	add_to_group("journal")
	panel.visible = false

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_J or event.keycode == KEY_M or event.keycode == KEY_C or event.keycode == KEY_P or event.keycode == KEY_ESCAPE or event.keycode == KEY_E or event.keycode == KEY_SPACE:
			close()
			get_viewport().set_input_as_handled()

func toggle() -> void:
	if is_open:
		close()
	else:
		open()

func open() -> void:
	is_open = true
	panel.visible = true
	_refresh()
	_lock_player(true)

func close() -> void:
	is_open = false
	panel.visible = false
	_lock_player(false)

func _refresh() -> void:
	var text := "[b]CAREER JOURNAL[/b]\n\n"
	var total_done: int = GameManager.get_total_quests_done()
	var total_quests: int = GameManager.get_total_career_quests()
	text += "Quests completed: " + str(total_done) + "/" + str(total_quests) + "\n"
	var careers_started: int = 0
	var careers_complete: int = GameManager.get_careers_completed_count()
	for career_id in CareerData.get_all_career_ids():
		if GameManager.get_career_progress(career_id) > 0:
			careers_started += 1
	text += "Careers started: " + str(careers_started) + "/" + str(CareerData.get_career_count()) + "\n"
	text += "Careers completed: " + str(careers_complete) + "\n\n"

	# Career quest progress by location
	for location in LOCATIONS:
		var career_ids: Array = CareerData.get_careers_by_location(location)
		text += "[b]" + location + ":[/b]\n"
		for career_id in career_ids:
			var cname: String = CareerData.get_career_name(career_id)
			var progress: int = GameManager.get_career_progress(career_id)
			var total: int = CareerData.get_quest_count(career_id)
			if progress >= total:
				text += "  [color=#4ade80][v][/color] " + cname + " (COMPLETE " + str(total) + "/" + str(total) + ")\n"
			elif progress > 0:
				text += "  [color=#fbbf24][o][/color] " + cname + " (" + str(progress) + "/" + str(total) + " quests)\n"
			else:
				text += "  [color=#9ca3af][ ][/color] " + cname + " (0/" + str(total) + " quests)\n"
		text += "\n"
	quest_label.text = text

	# Skills
	var st := "[b]SKILLS[/b]\n\n"
	for skill in ["technical", "creativity", "communication", "problem_solving", "organization"]:
		var level = GameManager.get_skill_level(skill)
		var xp = GameManager.get_skill_xp(skill)
		var needed = GameManager.get_xp_needed(skill)
		var display = skill.replace("_", " ").capitalize()
		st += "  " + display + ": Lv." + str(level) + " (" + str(xp) + "/" + str(needed) + " XP)\n"
	st += "\n[b]Status:[/b] " + (GameManager.career.replace("_", " ").capitalize() if GameManager.career != "" else "Exploring - try different careers!")
	skills_label.text = st

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
