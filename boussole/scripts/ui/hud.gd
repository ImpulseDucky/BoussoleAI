extends CanvasLayer
## HUD — top bar with day/time/money, skills top-right, settings button.
## Quest tracker on the left, quest notification toasts in the center-top.
## Found via group "hud". Updated by GameManager signals.

@onready var day_label: Label = $TopBar/DayLabel
@onready var time_label: Label = $TopBar/TimeLabel
@onready var money_label: Label = $TopBar/MoneyLabel
@onready var energy_label: Label = $TopBar/EnergyLabel
@onready var energy_bar: ProgressBar = $TopBar/EnergyBar
@onready var happiness_label: Label = $TopBar/HappinessLabel
@onready var happiness_bar: ProgressBar = $TopBar/HappinessBar
@onready var settings_btn: Button = $TopBar/SettingsBtn
@onready var skills_vbox: VBoxContainer = $SkillsPanel/SkillsVBox
@onready var prompt_label: Label = $PromptLabel
@onready var quest_tracker: Panel = $QuestTracker
@onready var quest_title: Label = $QuestTracker/QuestTitle
@onready var quest_desc: Label = $QuestTracker/QuestDesc
@onready var quest_notify: Panel = $QuestNotify
@onready var notify_label: Label = $QuestNotify/NotifyLabel

var _notify_timer: float = 0.0
var _prev_quests_done: int = 0
var _skill_bars: Dictionary = {}  # skill_name → {"lvl": Label, "bar": ProgressBar}
var _prev_skill_levels: Dictionary = {}  # skill_name → int (previous level)
var _flash_timers: Dictionary = {}  # skill_name → float (remaining flash time)
var _energy_warn_pulse: float = 0.0
var _low_energy_warned: bool = false
var _happy_warn_pulse: float = 0.0
var _low_happy_warned: bool = false

const NOTIFY_DURATION := 3.5
const SKILL_FLASH_DURATION := 2.0
const SKILL_FLASH_COLOR := Color(1.0, 0.85, 0.2, 1.0)
const SKILL_NORMAL_COLOR := Color(0.6, 0.75, 0.95)
const LOW_ENERGY_THRESHOLD := 15.0
const LOW_HAPPINESS_THRESHOLD := 15.0

const SKILL_LIST := ["technical", "creativity", "communication", "problem_solving", "organization"]

# ── NPC display data for friendship panel ──
const NPC_DISPLAY := [
	{"id": "mentor", "name": "Sarah", "role": "Mentor"},
	{"id": "librarian", "name": "Pat", "role": "Librarian"},
	{"id": "barista", "name": "Maya", "role": "Barista"},
	{"id": "guide", "name": "Sam", "role": "Guide"},
	{"id": "friend", "name": "Alex", "role": "Friend"},
	{"id": "art_guide", "name": "Riley", "role": "Art"},
	{"id": "cc_guide", "name": "Jordan", "role": "Comm."},
]
var _friend_rows: Array = []  # array of {name_lbl, hearts_lbl, val_lbl}

var quest_info := {}  # No longer used for linear quests

func _ready() -> void:
	add_to_group("hud")
	prompt_label.visible = false
	quest_notify.visible = false
	settings_btn.pressed.connect(_on_settings)
	_build_skill_bars()
	_build_key_hints()
	_build_friendship_panel()
	_refresh()
	GameManager.stats_changed.connect(_refresh)
	GameManager.time_changed.connect(_refresh)
	GameManager.quest_updated.connect(_on_quest_updated)
	GameManager.achievement_unlocked.connect(_on_achievement_unlocked)
	GameManager.challenges_updated.connect(_on_challenges_updated)
	_on_quest_updated()

func _process(delta: float) -> void:
	if _notify_timer > 0:
		_notify_timer -= delta
		if _notify_timer <= 0:
			quest_notify.visible = false
		else:
			var fade := clampf(_notify_timer / 0.5, 0.0, 1.0) if _notify_timer < 0.5 else 1.0
			quest_notify.modulate.a = fade
	# Update skill bar flash timers
	for skill in SKILL_LIST:
		if _flash_timers.get(skill, 0.0) > 0.0:
			_flash_timers[skill] = _flash_timers[skill] - delta
			if _flash_timers[skill] <= 0.0:
				_flash_timers[skill] = 0.0
				if _skill_bars.has(skill):
					_skill_bars[skill]["lvl"].add_theme_color_override("font_color", SKILL_NORMAL_COLOR)
	# Low energy pulse warning
	var en := int(GameManager.energy)
	if en <= int(LOW_ENERGY_THRESHOLD) and en > 0:
		_energy_warn_pulse += delta * 4.0
		var pulse := (sin(_energy_warn_pulse) * 0.5 + 0.5) * 0.6 + 0.4
		energy_bar.modulate = Color(1.0, pulse * 0.3, pulse * 0.3, 1.0)
		if not _low_energy_warned:
			_low_energy_warned = true
			_show_notify("WARNING: Low energy! Go home to sleep.")
	elif en <= 0:
		energy_bar.modulate = Color(1.0, 0.2, 0.2, 1.0)
		if not _low_energy_warned:
			_low_energy_warned = true
			_show_notify("EXHAUSTED! You need to sleep before doing any work.")
	else:
		energy_bar.modulate = Color(1, 1, 1, 1)
		_low_energy_warned = false
	# Low happiness pulse warning
	var hp := int(GameManager.happiness)
	if hp <= int(LOW_HAPPINESS_THRESHOLD) and hp > 0:
		_happy_warn_pulse += delta * 3.0
		var hp_pulse := (sin(_happy_warn_pulse) * 0.5 + 0.5) * 0.5 + 0.5
		happiness_bar.modulate = Color(hp_pulse * 0.5, hp_pulse * 0.2, hp_pulse * 0.6, 1.0)
		if not _low_happy_warned:
			_low_happy_warned = true
			_show_notify("Feeling down? Visit the cafe or buy a snack to cheer up!")
	elif hp <= 0:
		happiness_bar.modulate = Color(0.3, 0.15, 0.4, 1.0)
		if not _low_happy_warned:
			_low_happy_warned = true
			_show_notify("You're miserable! Do something fun to feel better.")
	else:
		happiness_bar.modulate = Color(1, 1, 1, 1)
		_low_happy_warned = false

func _build_skill_bars() -> void:
	var font := load("res://fonts/ArialUnicode.ttf")
	for skill in SKILL_LIST:
		# Label row: skill name + level
		var row := HBoxContainer.new()
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var name_lbl := Label.new()
		name_lbl.text = skill.replace("_", " ").capitalize()
		name_lbl.add_theme_font_override("font", font)
		name_lbl.add_theme_font_size_override("font_size", 11)
		name_lbl.add_theme_color_override("font_color", Color(0.82, 0.82, 0.88))
		name_lbl.custom_minimum_size = Vector2(110, 14)
		var lvl_lbl := Label.new()
		lvl_lbl.text = "Lv.1"
		lvl_lbl.add_theme_font_override("font", font)
		lvl_lbl.add_theme_font_size_override("font_size", 11)
		lvl_lbl.add_theme_color_override("font_color", Color(0.6, 0.75, 0.95))
		lvl_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		lvl_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		lvl_lbl.custom_minimum_size = Vector2(40, 14)
		row.add_child(name_lbl)
		row.add_child(lvl_lbl)
		skills_vbox.add_child(row)
		# XP progress bar
		var bar := ProgressBar.new()
		bar.min_value = 0
		bar.max_value = 100
		bar.value = 0
		bar.show_percentage = false
		bar.custom_minimum_size = Vector2(0, 10)
		bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		skills_vbox.add_child(bar)
		_skill_bars[skill] = {"lvl": lvl_lbl, "bar": bar}
		_prev_skill_levels[skill] = 1
		_flash_timers[skill] = 0.0

func _build_key_hints() -> void:
	var font := load("res://fonts/ArialUnicode.ttf")
	# Move prompt label up to make room for the key-hints bar
	prompt_label.offset_top = -68.0
	prompt_label.offset_bottom = -38.0

	# Bottom-center styled key-hints bar
	var bar := Panel.new()
	bar.name = "KeyHints"
	bar.anchor_left = 0.5
	bar.anchor_right = 0.5
	bar.anchor_top = 1.0
	bar.anchor_bottom = 1.0
	bar.offset_left = -420.0
	bar.offset_top = -34.0
	bar.offset_right = 420.0
	bar.offset_bottom = -4.0

	var bar_style := StyleBoxFlat.new()
	bar_style.bg_color = Color(0, 0, 0, 0)
	bar_style.content_margin_left = 8.0
	bar_style.content_margin_top = 3.0
	bar_style.content_margin_right = 8.0
	bar_style.content_margin_bottom = 3.0
	bar.add_theme_stylebox_override("panel", bar_style)

	var hbox := HBoxContainer.new()
	hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_theme_constant_override("separation", 10)
	hbox.anchor_right = 1.0
	hbox.anchor_bottom = 1.0
	hbox.offset_left = 8.0
	hbox.offset_top = 3.0
	hbox.offset_right = -8.0
	hbox.offset_bottom = -3.0
	bar.add_child(hbox)

	var hints := [
		{"key": "M", "label": "Map", "color": Color(0.35, 0.7, 1.0)},
		{"key": "C", "label": "Careers", "color": Color(0.3, 0.85, 0.4)},
		{"key": "P", "label": "Profile", "color": Color(0.95, 0.75, 0.3)},
		{"key": "B", "label": "Badges", "color": Color(0.9, 0.5, 0.85)},
		{"key": "N", "label": "Shop", "color": Color(1.0, 0.8, 0.35)},
		{"key": "J", "label": "Journal", "color": Color(0.65, 0.65, 0.85)},
		{"key": "ESC", "label": "Pause", "color": Color(0.85, 0.45, 0.45)},
	]

	for h in hints:
		var badge := HBoxContainer.new()
		badge.add_theme_constant_override("separation", 4)
		badge.alignment = BoxContainer.ALIGNMENT_CENTER

		# Key chip — styled to look like a keyboard key
		var chip := Panel.new()
		chip.custom_minimum_size = Vector2(30, 20)
		var chip_style := StyleBoxFlat.new()
		chip_style.bg_color = h.color.darkened(0.25)
		chip_style.border_width_left = 1
		chip_style.border_width_top = 1
		chip_style.border_width_right = 1
		chip_style.border_width_bottom = 2
		chip_style.border_color = h.color
		chip_style.corner_radius_top_left = 4
		chip_style.corner_radius_top_right = 4
		chip_style.corner_radius_bottom_left = 4
		chip_style.corner_radius_bottom_right = 4
		chip_style.content_margin_left = 3.0
		chip_style.content_margin_top = 1.0
		chip_style.content_margin_right = 3.0
		chip_style.content_margin_bottom = 1.0
		chip.add_theme_stylebox_override("panel", chip_style)

		var chip_lbl := Label.new()
		chip_lbl.text = h.key
		chip_lbl.add_theme_font_override("font", font)
		chip_lbl.add_theme_font_size_override("font_size", 11)
		chip_lbl.add_theme_color_override("font_color", Color.WHITE)
		chip_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		chip_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		chip_lbl.anchor_right = 1.0
		chip_lbl.anchor_bottom = 1.0
		chip.add_child(chip_lbl)
		badge.add_child(chip)

		# Action label
		var lbl := Label.new()
		lbl.text = h.label
		lbl.add_theme_font_override("font", font)
		lbl.add_theme_font_size_override("font_size", 11)
		lbl.add_theme_color_override("font_color", Color(0.68, 0.68, 0.76))
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		badge.add_child(lbl)

		hbox.add_child(badge)

	add_child(bar)

func _build_friendship_panel() -> void:
	var font := load("res://fonts/ArialUnicode.ttf")
	var panel := Panel.new()
	panel.name = "FriendshipPanel"
	panel.offset_left = 8.0
	panel.offset_top = 268.0
	panel.offset_right = 320.0
	panel.offset_bottom = 408.0
	add_child(panel)

	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.10, 0.09, 0.08, 0.88)
	style.border_width_left = 1
	style.border_width_top = 1
	style.border_width_right = 1
	style.border_width_bottom = 1
	style.border_color = Color(1.0, 0.35, 0.45, 0.4)
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	panel.add_theme_stylebox_override("panel", style)

	var vbox := VBoxContainer.new()
	vbox.offset_left = 8.0
	vbox.offset_top = 4.0
	vbox.offset_right = 304.0
	vbox.offset_bottom = 136.0
	vbox.add_theme_constant_override("separation", 1)
	panel.add_child(vbox)

	# Header
	var hdr := Label.new()
	hdr.text = "Relationships"
	hdr.add_theme_font_override("font", font)
	hdr.add_theme_font_size_override("font_size", 13)
	hdr.add_theme_color_override("font_color", Color(1.0, 0.5, 0.55))
	vbox.add_child(hdr)

	# 7 NPC rows
	for npc in NPC_DISPLAY:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 4)

		var name_lbl := Label.new()
		name_lbl.text = npc.name + " (" + npc.role + ")"
		name_lbl.add_theme_font_override("font", font)
		name_lbl.add_theme_font_size_override("font_size", 11)
		name_lbl.add_theme_color_override("font_color", Color(0.82, 0.72, 0.72))
		name_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(name_lbl)

		var hearts_lbl := Label.new()
		hearts_lbl.text = ""
		hearts_lbl.add_theme_font_override("font", font)
		hearts_lbl.add_theme_font_size_override("font_size", 12)
		hearts_lbl.add_theme_color_override("font_color", Color(1.0, 0.35, 0.45))
		hearts_lbl.custom_minimum_size = Vector2(48, 14)
		hearts_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		row.add_child(hearts_lbl)

		var val_lbl := Label.new()
		val_lbl.text = "0"
		val_lbl.add_theme_font_override("font", font)
		val_lbl.add_theme_font_size_override("font_size", 11)
		val_lbl.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))
		val_lbl.custom_minimum_size = Vector2(28, 14)
		val_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		row.add_child(val_lbl)

		vbox.add_child(row)
		_friend_rows.append({"id": npc.id, "name": name_lbl, "hearts": hearts_lbl, "val": val_lbl})

func _refresh_friendship() -> void:
	for row in _friend_rows:
		var fid: String = row.id
		var val: int = GameManager.get_npc_friendship(fid)
		var level: int = GameManager.get_npc_friendship_level(fid)
		var hearts_str: String = ""
		for i in range(level):
			hearts_str += "\u2665"  # ♥
		for i in range(level, 3):
			hearts_str += "\u2661"  # ♡ (outline heart)
		row.hearts.text = hearts_str
		row.val.text = str(val)
		# Color the value based on level
		if level >= 3:
			row.val.add_theme_color_override("font_color", Color(1.0, 0.35, 0.45))
		elif level >= 2:
			row.val.add_theme_color_override("font_color", Color(0.95, 0.6, 0.5))
		elif level >= 1:
			row.val.add_theme_color_override("font_color", Color(0.85, 0.7, 0.6))
		else:
			row.val.add_theme_color_override("font_color", Color(0.5, 0.5, 0.55))

func _refresh() -> void:
	day_label.text = "Day " + str(GameManager.day)
	time_label.text = GameManager.get_time_string()
	money_label.text = "$" + str(GameManager.money)
	# Energy bar
	var en: int = int(GameManager.energy)
	energy_label.text = "EN " + str(en)
	energy_bar.value = en
	# Happiness bar
	var hp: int = int(GameManager.happiness)
	happiness_label.text = "HP " + str(hp)
	happiness_bar.value = hp
	# Friendship panel
	_refresh_friendship()
	# Update skill bars + detect level-ups
	var level_ups: Array = []
	for skill in SKILL_LIST:
		if not _skill_bars.has(skill):
			continue
		var entry = _skill_bars[skill]
		var lvl: int = GameManager.get_skill_level(skill)
		var xp: int = GameManager.get_skill_xp(skill)
		var needed: int = GameManager.get_xp_needed(skill)
		entry["lvl"].text = "Lv." + str(lvl)
		entry["bar"].max_value = needed
		entry["bar"].value = xp
		# Detect level-up
		var prev_lvl: int = _prev_skill_levels.get(skill, 1)
		if lvl > prev_lvl:
			level_ups.append({"skill": skill, "prev": prev_lvl, "new": lvl})
			_flash_timers[skill] = SKILL_FLASH_DURATION
			entry["lvl"].add_theme_color_override("font_color", SKILL_FLASH_COLOR)
		_prev_skill_levels[skill] = lvl
	# Show level-up notifications
	if level_ups.size() > 0:
		var parts: Array = []
		for lu in level_ups:
			parts.append(lu.skill.replace("_", " ").capitalize() + " Lv." + str(lu.new) + "!")
		_show_notify("SKILL UP!\n" + "  ".join(parts))
		AudioManager.play_sfx("levelup")

func _on_settings() -> void:
	AudioManager.play_sfx("click")
	var s := get_tree().get_first_node_in_group("settings")
	if s and s.has_method("open"):
		s.open()

func show_prompt(text: String) -> void:
	prompt_label.text = "[ " + text + " ]"
	prompt_label.visible = true

func hide_prompt() -> void:
	prompt_label.visible = false

func _on_quest_updated() -> void:
	var quests_done: int = GameManager.get_total_quests_done()
	var total_quests: int = GameManager.get_total_career_quests()
	var careers_started: int = 0
	for career_id in CareerData.get_all_career_ids():
		if GameManager.get_career_progress(career_id) > 0:
			careers_started += 1
	var pinned: Array = GameManager.pinned_jobs

	quest_title.text = "Quest Tracker"

	var lines: Array = []

	# --- Active Quests section ---
	lines.append("Quest: " + str(quests_done) + "/" + str(total_quests) + " done | " + str(careers_started) + "/" + str(CareerData.get_career_count()) + " careers")

	if pinned.is_empty():
		lines.append("  No active quests tracked")
	else:
		for career_id in pinned:
			var cname = CareerData.get_career_name(career_id)
			var progress = GameManager.get_career_progress(career_id)
			var total = CareerData.get_quest_count(career_id)
			if progress >= total:
				lines.append(">> " + cname + " (DONE!)")
			else:
				lines.append(">> " + cname + " (" + str(progress) + "/" + str(total) + ")")

	# --- Recommended section ---
	lines.append("")
	var recommended: Array = _get_recommended_careers(2)
	if recommended.is_empty():
		lines.append("Recommended: Explore careers")
	else:
		var rec_parts: Array = []
		for rec in recommended:
			rec_parts.append(CareerData.get_career_name(rec.career_id) + " (" + str(rec.score) + "%)")
		lines.append("Recommended: " + "  ".join(rec_parts))

	quest_desc.text = "\n".join(lines)
	quest_tracker.visible = true

	# Show notification when a quest is completed
	if quests_done > _prev_quests_done:
		_show_notify("QUEST COMPLETE!\n" + str(quests_done) + "/" + str(total_quests) + " quests done")
		AudioManager.play_sfx("quest")

	_prev_quests_done = quests_done

func _get_recommended_careers(count: int) -> Array:
	var matches: Array = CareerMatch.get_top_matches(27)
	var result: Array = []
	for m in matches:
		var progress: int = GameManager.get_career_progress(m.career_id)
		var total: int = CareerData.get_quest_count(m.career_id)
		# Skip completed careers
		if progress >= total:
			continue
		result.append(m)
		if result.size() >= count:
			break
	return result

func _show_notify(text: String) -> void:
	notify_label.text = text
	quest_notify.visible = true
	quest_notify.modulate.a = 1.0
	_notify_timer = NOTIFY_DURATION
	AudioManager.play_sfx("notify")

## Public method for external systems (random events, etc.) to show a notification.
func show_notification(text: String) -> void:
	_show_notify(text)

func _on_achievement_unlocked(aid: String) -> void:
	var a := AchievementData.get_by_id(aid)
	if a.is_empty():
		_show_notify("ACHIEVEMENT UNLOCKED!")
	else:
		_show_notify("ACHIEVEMENT UNLOCKED!\n" + a.name)

func _on_challenges_updated() -> void:
	# Show notification when a challenge is completed
	for c in GameManager.daily_challenges:
		if c.completed:
			_show_notify("CHALLENGE DONE!\n" + c.desc + " (+" + str(c.reward) + "$)")
