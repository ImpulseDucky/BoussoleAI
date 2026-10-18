extends CanvasLayer
## Shop — buy items at the Café. Shows items, prices, and player's money.
## Also displays daily challenges with progress bars.
## Built entirely in code (minimal .tscn).

const FONT := preload("res://fonts/ArialUnicode.ttf")

var is_open: bool = false
var panel: Panel
var title_lbl: Label
var money_lbl: Label
var item_list: VBoxContainer
var challenge_list: VBoxContainer
var claim_btn: Button
var close_btn: Button

const SHOP_ITEMS := [
	{"id": "coffee", "name": "Coffee", "desc": "+15 energy instantly", "cost": 10, "effect": "energy", "amount": 15},
	{"id": "energy_drink", "name": "Energy Drink", "desc": "+30 energy instantly", "cost": 25, "effect": "energy", "amount": 30},
	{"id": "snack", "name": "Snack", "desc": "+10 energy, +5 happiness", "cost": 8, "effect": "snack", "amount": 10},
	{"id": "lunch", "name": "Lunch Special", "desc": "+25 energy, +10 happiness", "cost": 20, "effect": "lunch", "amount": 25},
	{"id": "book", "name": "Career Book", "desc": "+50 XP to random skill", "cost": 40, "effect": "skill_xp", "amount": 50},
	{"id": "lucky_charm", "name": "Lucky Charm", "desc": "+15 happiness instantly", "cost": 15, "effect": "happiness", "amount": 15},
	{"id": "energy_potion", "name": "Energy Potion", "desc": "Fully restore energy", "cost": 50, "effect": "full_energy", "amount": 0},
]

func _ready() -> void:
	add_to_group("shop")
	_build_ui()

func _build_ui() -> void:
	# Background panel
	panel = Panel.new()
	panel.anchor_left = 0.1
	panel.anchor_top = 0.05
	panel.anchor_right = 0.9
	panel.anchor_bottom = 0.95
	panel.visible = false
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.12, 0.12, 0.16, 0.97)
	sb.border_width_left = 2
	sb.border_width_right = 2
	sb.border_width_top = 2
	sb.border_width_bottom = 2
	sb.border_color = Color(0.4, 0.5, 0.6, 0.8)
	panel.add_theme_stylebox_override("panel", sb)
	add_child(panel)

	# Main VBox
	var vbox := VBoxContainer.new()
	vbox.anchor_right = 1.0
	vbox.anchor_bottom = 1.0
	vbox.offset_left = 20
	vbox.offset_top = 20
	vbox.offset_right = -20
	vbox.offset_bottom = -20
	vbox.add_theme_constant_override("separation", 8)
	panel.add_child(vbox)

	# Title
	title_lbl = Label.new()
	title_lbl.text = "Cafe Shop & Daily Challenges"
	title_lbl.add_theme_font_override("font", FONT)
	title_lbl.add_theme_font_size_override("font_size", 24)
	title_lbl.add_theme_color_override("font_color", Color(0.9, 0.85, 0.6, 1))
	vbox.add_child(title_lbl)

	# Money
	money_lbl = Label.new()
	money_lbl.text = "$" + str(GameManager.money)
	money_lbl.add_theme_font_override("font", FONT)
	money_lbl.add_theme_font_size_override("font_size", 18)
	money_lbl.add_theme_color_override("font_color", Color(0.4, 0.8, 0.4, 1))
	vbox.add_child(money_lbl)

	# Two-column layout
	var hbox := HBoxContainer.new()
	hbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(hbox)

	# Left column — shop items
	var left_col := VBoxContainer.new()
	left_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(left_col)

	var shop_label := Label.new()
	shop_label.text = "--- Items for Sale ---"
	shop_label.add_theme_font_override("font", FONT)
	shop_label.add_theme_font_size_override("font_size", 16)
	shop_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.85))
	left_col.add_child(shop_label)

	var scroll1 := ScrollContainer.new()
	scroll1.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll1.custom_minimum_size = Vector2(380, 0)
	left_col.add_child(scroll1)

	item_list = VBoxContainer.new()
	item_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll1.add_child(item_list)

	# Right column — daily challenges
	var right_col := VBoxContainer.new()
	right_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(right_col)

	var ch_label := Label.new()
	ch_label.text = "--- Daily Challenges ---"
	ch_label.add_theme_font_override("font", FONT)
	ch_label.add_theme_font_size_override("font_size", 16)
	ch_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.85))
	right_col.add_child(ch_label)

	var scroll2 := ScrollContainer.new()
	scroll2.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll2.custom_minimum_size = Vector2(320, 0)
	right_col.add_child(scroll2)

	challenge_list = VBoxContainer.new()
	challenge_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll2.add_child(challenge_list)

	# Buttons
	claim_btn = Button.new()
	claim_btn.text = "Claim Rewards"
	claim_btn.add_theme_font_override("font", FONT)
	claim_btn.add_theme_font_size_override("font_size", 16)
	claim_btn.custom_minimum_size = Vector2(0, 40)
	claim_btn.pressed.connect(_claim_rewards)
	vbox.add_child(claim_btn)

	close_btn = Button.new()
	close_btn.text = "Close (ESC)"
	close_btn.add_theme_font_override("font", FONT)
	close_btn.add_theme_font_size_override("font_size", 16)
	close_btn.custom_minimum_size = Vector2(0, 40)
	close_btn.pressed.connect(close)
	vbox.add_child(close_btn)

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

func _lock_player(lock: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set_deferred("process_mode", Node.PROCESS_MODE_DISABLED if lock else Node.PROCESS_MODE_INHERIT)

func _refresh() -> void:
	money_lbl.text = "$" + str(GameManager.money)
	# Build shop items
	for child in item_list.get_children():
		child.queue_free()
	for item in SHOP_ITEMS:
		var row := HBoxContainer.new()
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		# Icon
		var icon := Label.new()
		icon.text = "*"
		icon.add_theme_font_override("font", FONT)
		icon.add_theme_font_size_override("font_size", 20)
		icon.custom_minimum_size = Vector2(30, 0)
		row.add_child(icon)
		# Name + desc
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var name_lbl := Label.new()
		name_lbl.text = item.name
		name_lbl.add_theme_font_override("font", FONT)
		name_lbl.add_theme_font_size_override("font_size", 16)
		name_lbl.add_theme_color_override("font_color", Color(0.95, 0.95, 1.0))
		var desc_lbl := Label.new()
		desc_lbl.text = item.desc
		desc_lbl.add_theme_font_override("font", FONT)
		desc_lbl.add_theme_font_size_override("font_size", 12)
		desc_lbl.add_theme_color_override("font_color", Color(0.65, 0.65, 0.70))
		info.add_child(name_lbl)
		info.add_child(desc_lbl)
		row.add_child(info)
		# Owned count
		var owned := GameManager.get_item_count(item.id)
		if owned > 0:
			var own_lbl := Label.new()
			own_lbl.text = "x" + str(owned)
			own_lbl.add_theme_font_override("font", FONT)
			own_lbl.add_theme_font_size_override("font_size", 12)
			own_lbl.add_theme_color_override("font_color", Color(0.5, 0.8, 0.5))
			own_lbl.custom_minimum_size = Vector2(30, 0)
			row.add_child(own_lbl)
		# Buy button
		var buy := Button.new()
		buy.text = "$" + str(item.cost)
		buy.add_theme_font_override("font", FONT)
		buy.add_theme_font_size_override("font_size", 14)
		buy.custom_minimum_size = Vector2(70, 36)
		if GameManager.money < item.cost:
			buy.disabled = true
		buy.pressed.connect(_buy_item.bind(item))
		row.add_child(buy)
		item_list.add_child(row)
	# Build daily challenges
	for child in challenge_list.get_children():
		child.queue_free()
	var challenges: Array = GameManager.daily_challenges
	if challenges.is_empty():
		var empty := Label.new()
		empty.text = "No challenges today. Check back tomorrow!"
		empty.add_theme_font_override("font", FONT)
		empty.add_theme_font_size_override("font_size", 13)
		empty.add_theme_color_override("font_color", Color(0.5, 0.5, 0.55))
		challenge_list.add_child(empty)
	else:
		for c in challenges:
			var row2 := HBoxContainer.new()
			row2.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			var info2 := VBoxContainer.new()
			info2.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			var cname := Label.new()
			cname.text = c.desc
			cname.add_theme_font_override("font", FONT)
			cname.add_theme_font_size_override("font_size", 14)
			if c.completed:
				cname.add_theme_color_override("font_color", Color(0.3, 0.8, 0.3))
			else:
				cname.add_theme_color_override("font_color", Color(0.9, 0.9, 0.95))
			var progress_bar := ProgressBar.new()
			progress_bar.min_value = 0
			progress_bar.max_value = c.target
			progress_bar.value = c.progress
			progress_bar.show_percentage = false
			progress_bar.custom_minimum_size = Vector2(280, 12)
			info2.add_child(cname)
			info2.add_child(progress_bar)
			var reward_lbl := Label.new()
			reward_lbl.text = "+" + str(c.reward) + "$"
			reward_lbl.add_theme_font_override("font", FONT)
			reward_lbl.add_theme_font_size_override("font_size", 14)
			reward_lbl.add_theme_color_override("font_color", Color(0.3, 0.8, 0.4))
			row2.add_child(info2)
			row2.add_child(reward_lbl)
			challenge_list.add_child(row2)
	# Claim button state
	claim_btn.disabled = GameManager.challenge_rewards_claimed or not GameManager.all_challenges_done()
	claim_btn.text = "Rewards Claimed" if GameManager.challenge_rewards_claimed else "Claim Rewards"

func _buy_item(item: Dictionary) -> void:
	if GameManager.buy_item(item.id, item.cost):
		_apply_effect(item)
		AudioManager.play_sfx("buy")
		var hud := get_tree().get_first_node_in_group("hud")
		if hud and hud.has_method("show_notification"):
			hud.show_notification("Purchased " + item.name + "!")
		_refresh()

func _apply_effect(item: Dictionary) -> void:
	match item.effect:
		"energy":
			GameManager.restore_energy(item.amount)
		"snack":
			GameManager.restore_energy(item.amount)
			GameManager.add_happiness(5.0)
		"lunch":
			GameManager.restore_energy(item.amount)
			GameManager.add_happiness(10.0)
		"skill_xp":
			var skills := ["technical", "creativity", "communication", "problem_solving", "organization"]
			skills.shuffle()
			GameManager.add_skill_xp(skills[0], item.amount)
		"happiness":
			GameManager.add_happiness(float(item.amount))
		"full_energy":
			GameManager.restore_energy(GameManager.max_energy)

func _claim_rewards() -> void:
	var reward := GameManager.claim_challenge_rewards()
	if reward > 0:
		AudioManager.play_sfx("quest")
		var hud := get_tree().get_first_node_in_group("hud")
		if hud and hud.has_method("show_notification"):
			hud.show_notification("Challenge rewards: +" + str(reward) + "$!")
	_refresh()

func _input(event: InputEvent) -> void:
	if is_open and event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			close()
			get_viewport().set_input_as_handled()
