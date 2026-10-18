extends CanvasLayer
## Career Compass — real-world career info screen with a selection menu.
## Shows all 19 careers as a list. Click one to see salary, education,
## day-in-the-life, and growth outlook data from JSON files.
## Found via group "career_compass".

const FONT := preload("res://fonts/ArialUnicode.ttf")

# Map career_id → JSON filename
const CAREER_FILES := {
	"tech_bug_hunt": "software_developer",
	"tech_website": "web_developer",
	"tech_data": "data_analyst",
	"tech_ux": "ux_designer",
	"tech_it": "it_support",
	"lib_research": "researcher",
	"lib_catalog": "librarian",
	"lib_writer": "technical_writer",
	"lib_archive": "archivist",
	"cafe_latte": "barista",
	"cafe_catering": "catering_manager",
	"cafe_chef": "chef",
	"cafe_service": "customer_service",
	"town_event_plan": "event_planner",
	"town_event_run": "event_manager",
	"town_marketing": "marketing_specialist",
	"town_consult": "consultant",
	"home_freelance": "freelancer",
	"home_content": "content_creator",
	"art_graphic": "graphic_designer",
	"art_photo": "photographer",
	"art_illustrator": "illustrator",
	"art_animator": "animator",
	"cc_social": "social_worker",
	"cc_youth": "youth_counselor",
	"cc_nonprofit": "nonprofit_coordinator",
	"cc_organizer": "community_organizer",
}

@onready var panel: Panel = $Panel
@onready var title_label: Label = $Panel/TitleLabel
@onready var content: RichTextLabel = $Panel/Scroll/Content
@onready var list_vbox: VBoxContainer = $Panel/Scroll/ListVBox
@onready var back_btn: Button = $Panel/BackBtn

var is_open: bool = false
var current_career: String = ""

func _ready() -> void:
	add_to_group("career_compass")
	panel.visible = false
	back_btn.pressed.connect(_show_list)

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE or event.keycode == KEY_E or event.keycode == KEY_SPACE or event.keycode == KEY_P:
			close()
			get_viewport().set_input_as_handled()

func toggle() -> void:
	if is_open:
		close()
	else:
		show_compass()

func show_compass(career_id: String = "") -> void:
	is_open = true
	panel.visible = true
	if career_id == "":
		_show_list()
	else:
		_show_career(career_id)
	_lock_player(true)

func close() -> void:
	is_open = false
	panel.visible = false
	_lock_player(false)

func _show_list() -> void:
	current_career = ""
	title_label.text = "Career Compass"
	content.visible = false
	list_vbox.visible = true
	back_btn.visible = false
	for child in list_vbox.get_children():
		child.queue_free()

	# Group careers by location
	var locations: Array = CareerData.get_location_list()
	for loc in locations:
		var loc_header := Label.new()
		loc_header.text = loc
		loc_header.add_theme_font_override("font", FONT)
		loc_header.add_theme_font_size_override("font_size", 16)
		loc_header.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
		list_vbox.add_child(loc_header)

		var career_ids: Array = CareerData.get_careers_by_location(loc)
		for cid in career_ids:
			var cname: String = CareerData.get_career_name(cid)
			var cdesc: String = CareerData.get_career(cid).get("desc", "")
			var progress: int = GameManager.get_career_progress(cid)
			var total: int = CareerData.get_quest_count(cid)
			var status: String = ""
			if progress >= total:
				status = " (COMPLETE)"
			elif progress > 0:
				status = " (" + str(progress) + "/" + str(total) + ")"

			var btn := Button.new()
			btn.text = cname + status
			btn.add_theme_font_override("font", FONT)
			btn.add_theme_font_size_override("font_size", 14)
			btn.custom_minimum_size = Vector2(0, 36)
			btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			btn.tooltip_text = cdesc
			var captured_id = cid
			btn.pressed.connect(func(): _show_career(captured_id))
			list_vbox.add_child(btn)

		var spacer := Control.new()
		spacer.custom_minimum_size = Vector2(0, 6)
		list_vbox.add_child(spacer)

func _show_career(career_id: String) -> void:
	current_career = career_id
	var cname: String = CareerData.get_career_name(career_id)
	title_label.text = cname
	list_vbox.visible = false
	content.visible = true
	back_btn.visible = true
	_load_career_data(career_id)

func _load_career_data(career_id: String) -> void:
	var file_key: String = CAREER_FILES.get(career_id, "")
	if file_key == "":
		content.text = "[i]Career data not available for this career.[/i]"
		return

	var path := "res://data/careers/" + file_key + ".json"
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		content.text = "[i]Career data file not found: " + file_key + ".json[/i]"
		return
	var data = JSON.parse_string(file.get_as_text())
	file.close()
	if data == null:
		content.text = "[i]Career data could not be parsed.[/i]"
		return

	var s: Dictionary = data.get("sections", {})
	var text := ""
	text += "[b]" + data.get("name", "Unknown Career") + "[/b]\n\n"

	# Add career description from CareerData
	var career: Dictionary = CareerData.get_career(career_id)
	if not career.is_empty():
		text += "[i]" + career.get("desc", "") + "[/i]\n"
		var skills: Array = career.get("skills", [])
		if not skills.is_empty():
			var skill_labels: Array = []
			for skill in skills:
				skill_labels.append(skill.replace("_", " ").capitalize())
			text += "[b]Key skills:[/b] " + ", ".join(skill_labels) + "\n"
		text += "\n"

	text += "[b]Daily work:[/b]\n  " + str(s.get("daily_work", "N/A")) + "\n\n"
	text += "[b]Learning path:[/b]\n  " + str(s.get("learning", "N/A")) + "\n\n"
	text += "[b]Pay & costs:[/b]\n  " + str(s.get("pay", "N/A")) + "\n\n"
	text += "[b]Entry routes:[/b]\n  " + str(s.get("entry_routes", "N/A")) + "\n\n"
	text += "[b]Try this in real life:[/b]\n"
	for tip in data.get("try_in_real_life", []):
		text += "  - " + str(tip) + "\n"
	text += "\n[i]Sources: " + str(data.get("sources", "Verify current data.")) + "[/i]"
	content.text = text

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
