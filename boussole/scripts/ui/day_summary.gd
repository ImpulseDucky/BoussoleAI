extends CanvasLayer
## Day Summary — overlay shown after sleeping. Shows recap of the previous day:
## quests completed, XP gained, money earned, energy used.
## Found via group "day_summary". Called by dialogue.gd after sleep callback.

const FONT := preload("res://fonts/ArialUnicode.ttf")

var is_open: bool = false
var _panel: Panel
var _continue_btn: Button

func _ready() -> void:
	add_to_group("day_summary")
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
	bg.color = Color(0.04, 0.04, 0.06, 0.92)
	_panel.add_child(bg)

	# Center card
	var card := Panel.new()
	card.position = Vector2(290, 80)
	card.size = Vector2(700, 600)
	_panel.add_child(card)

	# Title
	var title := Label.new()
	title.text = "DAY COMPLETE"
	title.add_theme_font_override("font", FONT)
	title.add_theme_font_size_override("font_size", 32)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 20)
	title.size = Vector2(700, 48)
	card.add_child(title)

	# Subtitle (day number)
	var sub := Label.new()
	sub.add_theme_font_override("font", FONT)
	sub.add_theme_font_size_override("font_size", 16)
	sub.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.position = Vector2(0, 68)
	sub.size = Vector2(700, 24)
	sub.name = "Subtitle"
	card.add_child(sub)

	# Content container
	var content := VBoxContainer.new()
	content.position = Vector2(40, 100)
	content.size = Vector2(620, 400)
	content.add_theme_constant_override("separation", 12)
	card.add_child(content)
	content.name = "Content"

	# Continue button
	_continue_btn = Button.new()
	_continue_btn.text = "Start New Day"
	_continue_btn.add_theme_font_override("font", FONT)
	_continue_btn.add_theme_font_size_override("font_size", 18)
	_continue_btn.custom_minimum_size = Vector2(200, 44)
	_continue_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_continue_btn.position = Vector2(250, 530)
	_continue_btn.size = Vector2(200, 44)
	_continue_btn.pressed.connect(_on_continue)
	card.add_child(_continue_btn)

func show_summary(summary: Dictionary) -> void:
	is_open = true
	_panel.visible = true
	var sub: Label = _panel.get_child(1).get_node("Subtitle")
	sub.text = "Day " + str(summary.get("day", 1)) + " Recap"

	var content: VBoxContainer = _panel.get_child(1).get_node("Content")
	for child in content.get_children():
		child.queue_free()

	# Quests completed
	var quests: int = summary.get("quests", 0)
	_add_row(content, "Quests Completed", str(quests), Color(0.4, 0.9, 0.4) if quests > 0 else Color(0.6, 0.6, 0.6))

	# XP gained
	var xp_dict: Dictionary = summary.get("xp", {})
	var xp_total: int = 0
	for skill in xp_dict:
		xp_total += xp_dict[skill]
	if xp_total > 0:
		_add_header(content, "Skill XP Gained")
		for skill in xp_dict:
			var amount: int = xp_dict[skill]
			if amount > 0:
				_add_row(content, "  " + skill.replace("_", " ").capitalize(), "+" + str(amount) + " XP", Color(0.6, 0.75, 0.95))
	else:
		_add_row(content, "Skill XP", "None gained", Color(0.5, 0.5, 0.55))

	# Money
	var earned: int = summary.get("money_earned", 0)
	var spent: int = summary.get("money_spent", 0)
	_add_header(content, "Finances")
	_add_row(content, "  Money Earned", "+$" + str(earned), Color(0.4, 0.9, 0.4) if earned > 0 else Color(0.6, 0.6, 0.6))
	_add_row(content, "  Money Spent", "-$" + str(spent), Color(0.9, 0.5, 0.4) if spent > 0 else Color(0.6, 0.6, 0.6))
	var net := earned - spent
	_add_row(content, "  Net Profit", ("+$" if net >= 0 else "-$") + str(abs(net)), Color(0.4, 0.9, 0.4) if net >= 0 else Color(0.9, 0.5, 0.4))

	# Energy used
	var energy_used: float = summary.get("energy_used", 0.0)
	_add_header(content, "Activity")
	_add_row(content, "Energy Used", str(int(energy_used)) + " / 100", Color(0.8, 0.7, 0.3) if energy_used > 50 else Color(0.6, 0.6, 0.6))

	# Happiness change
	var happy_change: float = summary.get("happiness_change", 0.0)
	var happy_str: String = ("+" if happy_change >= 0 else "") + str(int(happy_change))
	_add_row(content, "Happiness Change", happy_str, Color(0.95, 0.5, 0.75) if happy_change != 0 else Color(0.6, 0.6, 0.6))

	# Friendship gained
	var friend_change: float = summary.get("friendship_change", 0.0)
	if friend_change > 0:
		_add_row(content, "Friendship Gained", "+" + str(int(friend_change)), Color(1.0, 0.5, 0.5))

	# Lock player
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", true)

func _add_row(parent: VBoxContainer, label_text: String, value_text: String, value_color: Color) -> void:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var lbl := Label.new()
	lbl.text = label_text
	lbl.add_theme_font_override("font", FONT)
	lbl.add_theme_font_size_override("font_size", 15)
	lbl.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
	lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(lbl)
	var val := Label.new()
	val.text = value_text
	val.add_theme_font_override("font", FONT)
	val.add_theme_font_size_override("font_size", 15)
	val.add_theme_color_override("font_color", value_color)
	val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	val.custom_minimum_size = Vector2(120, 0)
	row.add_child(val)
	parent.add_child(row)

func _add_header(parent: VBoxContainer, text: String) -> void:
	var sep := HSeparator.new()
	sep.add_theme_constant_override("separation", 4)
	parent.add_child(sep)
	var hdr := Label.new()
	hdr.text = text
	hdr.add_theme_font_override("font", FONT)
	hdr.add_theme_font_size_override("font_size", 14)
	hdr.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	parent.add_child(hdr)

func _on_continue() -> void:
	is_open = false
	_panel.visible = false
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", false)

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_E or event.keycode == KEY_SPACE or event.keycode == KEY_ESCAPE or event.keycode == KEY_ENTER:
			_on_continue()
			get_viewport().set_input_as_handled()
