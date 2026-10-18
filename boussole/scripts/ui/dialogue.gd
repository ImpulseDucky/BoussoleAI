extends CanvasLayer
## Dialogue - bottom dialogue box with speaker name, typewriter text, and choices.
## Dynamic career quest system: each career has 5 consecutive quests (135 total).
## Quests are generated at runtime from CareerData, not hardcoded in this file.

@onready var panel: Panel = $Panel
@onready var speaker_label: Label = $Panel/VBox/SpeakerLabel
@onready var text_label: RichTextLabel = $Panel/VBox/TextLabel
@onready var choice_container: VBoxContainer = $Panel/VBox/ChoiceContainer
@onready var hint_label: Label = $Panel/HintLabel
@onready var close_btn: Button = $Panel/CloseBtn

var is_active: bool = false
var current_id: String = ""
var current_data: Dictionary = {}  # the active dialogue entry (static or dynamic)
var lines: Array = []
var line_index: int = 0
var full_text: String = ""
var shown_chars: int = 0
var has_choices: bool = false
const CHAR_RATE := 45.0

# ── NPC dialogue IDs that grant friendship on talk ──
const NPC_TALK_IDS := ["mentor", "librarian", "barista", "guide", "friend", "art_guide", "cc_guide"]

# ── Wanderer tips (randomized on each interaction) ──
const WANDERER_TIPS := [
	# Career wisdom
	"Did you know? Most people change careers 5-7 times in their life. It's normal to explore!",
	"My advice? Try a little bit of everything before you commit to one path.",
	"I used to be a barista before I found my true calling. Never be afraid to start over.",
	"Soft skills matter just as much as hard skills. Communication can open doors you didn't know existed.",
	"Don't just chase money — find work that makes you curious. Passion compounds over time.",
	"The best career advice I ever got: 'You don't have to be the best, just be reliable and keep learning.'",
	"I heard the library has real-world career data. You should check it out!",
	"You know what's undervalued? Organization skills. Every employer wants someone who can keep things running.",
	"Creative people aren't just artists. Creativity is problem-solving — every field needs it.",
	"Technical skills open doors, but people skills build careers.",
	# Life wisdom
	"Take breaks! Your brain consolidates learning when you rest, not when you grind.",
	"Sleep is not lazy — it's the most productive thing you can do for your brain.",
	"I read somewhere that it takes about 20 days to build a habit. Start small and keep going!",
	"You know what's free? Walking outside. And it boosts creativity by 60% according to studies.",
	"Hey, don't forget to eat well. Your brain runs on what you feed it.",
	"Money comes and goes, but skills are yours forever. Invest in yourself!",
	"Comparison is the thief of joy. Run your own race.",
	"The town square is a great place to meet people. Networking starts with just saying hi!",
	# Fun facts
	"Fun fact: The word 'career' comes from the Latin word for 'road' or 'path'. You're always on a journey!",
	"Did you know? Honey bees have to visit 2 million flowers to make one pound of honey. Hard work pays off!",
	"I heard that astronauts train for years before going to space. Preparation is key to any dream!",
	"Random fact: Octopuses have three hearts and blue blood. Nature is wild, right? Keep exploring!",
	"Did you know? The first computer programmer was a woman named Ada Lovelace, back in the 1840s!",
	# Encouragement
	"You're doing great just by being here and exploring. Most people never even try!",
	"Every expert was once a beginner. Don't let intimidation stop you from starting.",
	"I believe in you! Go talk to the folks at the buildings — they all have interesting work to share.",
	"You know what? The fact that you're exploring careers means you're already ahead of most people.",
	"Don't worry about picking the 'right' path. Any path you walk with intention leads somewhere good.",
	# Study & growth tips
	"If you want to level up fast, try doing quests at different locations. Variety builds all your skills!",
	"The quiz at the start of the game isn't just for fun — it reveals your natural strengths!",
	"Did you know your skills level up faster when you do work that matches your strengths?",
	"Check your profile screen with P — it shows a radar chart of all your skills and career matches!",
	"I heard the Career Compass has real salary data and learning paths. Pretty useful stuff!",
	# Quirky chatter
	"I saw a bird steal someone's sandwich yesterday. Life is unpredictable — be adaptable!",
	"You know what I love about this town? Everyone's doing something different. So many paths!",
	"Is it just me, or do the fireflies at night feel magical? This town has good energy.",
	"I keep finding coins on the ground. Five dollars here, three dollars there. Keep your eyes open!",
	"Sometimes I just sit by the pond and think. Quiet moments matter more than busy ones.",
	"Did you notice the flowers around town? Someone planted all of those. Small things add up!",
]

# ── Static dialogue entries (NPC intros + sleep) ──
var data := {
	# === NPC INTROS ===
	"sarah_intro": {
		"speaker": "Sarah — Tech Mentor",
		"lines": [
			"Welcome to the Tech Studio! I'm Sarah.",
			"We have all kinds of tech careers here - software, web, data, design, IT support.",
			"Each career has 5 quests to complete. Try any computer when you're ready!",
		],
	},
	"pat_intro": {
		"speaker": "Pat — Librarian",
		"lines": [
			"Welcome to the Library! I'm Pat.",
			"We have research, writing, and organization careers.",
			"Each career is a chain of 5 quests. Head to a study desk to try one!",
		],
	},
	"maya_intro": {
		"speaker": "Maya — Barista",
		"lines": [
			"Hey! I'm Maya, the barista.",
			"We've got barista, catering, cooking, and customer service careers.",
			"Each has 5 quests you can complete in order. Try the counter whenever you want!",
		],
	},

	# === ACTIVITIES ===
	"sleep_prompt": {
		"speaker": "Home",
		"lines": ["Your bed looks comfy. Sleep until morning?"],
		"choices": [
			{"text": "Yes - sleep (restores energy, new day)", "next": "sleep_done"},
			{"text": "Not yet", "next": "_close"},
		],
	},
	"sleep_done": {
		"speaker": "Home",
		"lines": ["You sleep peacefully and wake up refreshed. Energy fully restored!"],
		"on_complete": "sleep;show_day_summary",
	},
}

func _ready() -> void:
	add_to_group("dialogue")
	panel.visible = false
	hint_label.visible = false
	close_btn.pressed.connect(_end)

func _process(delta: float) -> void:
	if not is_active:
		return
	if shown_chars < full_text.length():
		shown_chars += int(CHAR_RATE * delta)
		if shown_chars > full_text.length():
			shown_chars = full_text.length()
		text_label.text = full_text.substr(0, shown_chars)
		hint_label.visible = false
	else:
		if not has_choices:
			hint_label.visible = true

func _input(event: InputEvent) -> void:
	if not is_active:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_E or event.keycode == KEY_SPACE or event.keycode == KEY_ENTER:
			get_viewport().set_input_as_handled()
			_advance()
		elif event.keycode == KEY_ESCAPE or event.keycode == KEY_P:
			get_viewport().set_input_as_handled()
			_end()

# ── Entry point — called by InteractionArea ──
func start(dialogue_id: String) -> void:
	# NPC friendship: +2 on first talk each day + tier bonuses
	if NPC_TALK_IDS.has(dialogue_id):
		if not GameManager.has_talked_today(dialogue_id):
			GameManager.add_npc_friendship(dialogue_id, 2)
			GameManager.mark_talked_today(dialogue_id)
			var level: int = GameManager.get_npc_friendship_level(dialogue_id)
			if level >= 3:
				GameManager.add_happiness(3.0)
				if randi() % 3 == 0:
					GameManager.add_money(10)
			elif level >= 2:
				GameManager.add_happiness(2.0)
				if randi() % 5 == 0:
					GameManager.add_money(5)
			elif level >= 1:
				GameManager.add_happiness(1.0)
	match dialogue_id:
		# Wanderer tip — pick a random tip
		"wanderer_tip":
			var tip: String = WANDERER_TIPS[randi() % WANDERER_TIPS.size()]
			var tip_data := {"speaker": "Stranger", "lines": [tip]}
			_begin_data(tip_data)
		# Activity zones → dynamic career menus
		"computer": _show_location_menu("Tech Studio", "Tech Studio Computer")
		"study": _show_location_menu("Library", "Study Desk")
		"work": _show_location_menu("Cafe", "Cafe Counter")
		"desk": _show_location_menu("Home", "Home Desk")
		"easel": _show_location_menu("Art Studio", "Art Studio Easel")
		"help_desk": _show_location_menu("Community Center", "Community Center Desk")
		# NPCs → intros or direct menus
		"mentor": _begin("sarah_intro")
		"librarian": _begin("pat_intro")
		"barista": _begin("maya_intro")
		"guide": _show_location_menu("Town Square", "Sam — Town Guide", "Hey! What kind of town work interests you?")
		"friend": _show_location_menu("Town Square", "Alex — Local Friend", "Hey! I've got some projects that could use help.")
		"art_guide": _show_location_menu("Art Studio", "Riley — Art Studio Guide", "Welcome to the Art Studio! What creative path calls to you?")
		"cc_guide": _show_location_menu("Community Center", "Jordan — Community Center Guide", "Welcome! Ready to make a difference in someone's life?")
		# Fallback — treat as a static dialogue ID
		_: _begin(dialogue_id)

# ── Dynamic career menu generation ──
func _show_location_menu(location: String, speaker: String = "", intro_line: String = "What would you like to work on?") -> void:
	if speaker == "":
		speaker = location
	var career_ids: Array = CareerData.get_careers_by_location(location)
	var choices: Array = []
	for career_id in career_ids:
		var cname: String = CareerData.get_career_name(career_id)
		var progress: int = GameManager.get_career_progress(career_id)
		var total: int = CareerData.get_quest_count(career_id)
		var label: String = cname
		if progress >= total:
			label = cname + " (COMPLETE " + str(total) + "/" + str(total) + ")"
		else:
			label = cname + " (" + str(progress) + "/" + str(total) + ")"
		choices.append({"text": label, "next": "_career:" + career_id})
	choices.append({"text": "Back", "next": "_close"})
	_begin_data({
		"speaker": speaker,
		"lines": [intro_line],
		"choices": choices,
	})

# ── Dynamic career quest dialogue ──
func _begin_career_quest(career_id: String) -> void:
	# Check energy — quests cost 15 energy
	if not GameManager.has_energy(15.0):
		_begin_data({
			"speaker": "Exhausted",
			"lines": [
				"You're too tired to work right now.",
				"Your energy is at " + str(int(GameManager.energy)) + "/100. You need at least 15 energy to attempt a quest.",
				"Go home and sleep, or explore the town to pass time.",
			],
			"choices": [
				{"text": "Okay", "next": "_close"},
			],
		})
		return
	var progress: int = GameManager.get_career_progress(career_id)
	var total: int = CareerData.get_quest_count(career_id)
	var cname: String = CareerData.get_career_name(career_id)

	if progress >= total:
		_begin_data({
			"speaker": cname,
			"lines": [
				"You've completed all " + str(total) + " quests in the " + cname + " career!",
				"You're a master of this craft. Try another career for more challenges!",
			],
		})
		return

	var quest: Dictionary = CareerData.get_quest(career_id, progress)
	var choices: Array = []
	for i in range(quest.choices.size()):
		var next_id: String
		if i == quest.correct:
			next_id = "_career:correct:" + career_id + ":" + str(progress)
		else:
			next_id = "_career:wrong:" + career_id + ":" + str(progress)
		choices.append({"text": quest.choices[i], "next": next_id})

	# Add option to leave without answering
	choices.append({"text": "Leave", "next": "_close"})

	_begin_data({
		"speaker": cname + "  (Quest " + str(progress + 1) + " of " + str(total) + ")",
		"lines": [quest.scenario, quest.question],
		"choices": choices,
	})

func _begin_career_correct(career_id: String, quest_idx: int) -> void:
	var quest: Dictionary = CareerData.get_quest(career_id, quest_idx)
	var progress: int = GameManager.get_career_progress(career_id)
	var total: int = CareerData.get_quest_count(career_id)
	var cname: String = CareerData.get_career_name(career_id)

	# Build reward summary line
	var reward_parts: Array = []
	for skill in quest.xp:
		reward_parts.append("+" + str(quest.xp[skill]) + " " + skill.replace("_", " ").capitalize() + " XP")
	reward_parts.append("+$" + str(quest.money))
	reward_parts.append("-15 Energy, +5 Happiness, +1.5h")
	var reward_line: String = " | ".join(reward_parts)

	# Build completion lines
	var result_lines: Array = [quest.feedback, reward_line]
	if progress + 1 >= total:
		result_lines.append("Career Complete! You've finished all " + str(total) + " " + cname + " quests!")
	else:
		result_lines.append("Quest " + str(progress + 1) + " done! Quest " + str(progress + 2) + " is now available.")

	# Build callback string
	var cb: String = ""
	for skill in quest.xp:
		cb += "give_xp:" + skill + ":" + str(quest.xp[skill]) + ";"
	cb += "give_money:" + str(quest.money) + ";"
	cb += "advance_time:1.5;spend_energy:15;add_happiness:5;"
	cb += "add_quest_friendship:" + career_id + ";"
	cb += "complete_career_quest:" + career_id

	_begin_data({
		"speaker": "Quest Complete!",
		"lines": result_lines,
		"on_complete": cb,
	})

func _begin_career_wrong(career_id: String, quest_idx: int) -> void:
	var quest: Dictionary = CareerData.get_quest(career_id, quest_idx)
	# Getting it wrong costs some energy and happiness
	GameManager.spend_energy(5.0)
	GameManager.add_happiness(-3.0)
	_begin_data({
		"speaker": "Not quite...",
		"lines": [quest.wrong_feedback, "-5 Energy, -3 Happiness"],
		"choices": [
			{"text": "Try again", "next": "_career:" + career_id},
			{"text": "Give up", "next": "_close"},
		],
	})

# ── Core dialogue engine ──
func _begin(dialogue_id: String) -> void:
	if not data.has(dialogue_id):
		push_error("Dialogue: unknown id " + dialogue_id)
		_end()
		return
	_begin_data(data[dialogue_id])

func _begin_data(d: Dictionary) -> void:
	current_data = d
	current_id = "_dynamic"
	speaker_label.text = d.get("speaker", "")
	lines = d.get("lines", [])
	line_index = 0
	is_active = true
	panel.visible = true
	_lock_player(true)
	_clear_choices()
	has_choices = d.has("choices") and line_index >= lines.size() - 1
	if lines.is_empty() and has_choices:
		_show_choices(d["choices"])
		full_text = ""
		text_label.text = ""
	else:
		_show_line()

func _show_line() -> void:
	if line_index >= lines.size():
		_on_lines_done()
		return
	full_text = lines[line_index]
	shown_chars = 0
	text_label.text = ""
	has_choices = current_data.has("choices") and line_index >= lines.size() - 1

func _advance() -> void:
	if shown_chars < full_text.length():
		shown_chars = full_text.length()
		text_label.text = full_text
		hint_label.visible = not has_choices
		return
	AudioManager.play_sfx("click")
	if has_choices:
		if choice_container.get_child_count() == 0:
			_on_lines_done()
		return
	line_index += 1
	if line_index >= lines.size():
		_on_lines_done()
	else:
		_show_line()

func _on_lines_done() -> void:
	if current_data.has("choices"):
		_show_choices(current_data["choices"])
	else:
		_execute_callbacks(current_data.get("on_complete", ""))
		_end()

func _show_choices(choices: Array) -> void:
	has_choices = true
	hint_label.visible = false
	_clear_choices()
	for choice in choices:
		var btn := Button.new()
		btn.text = choice["text"]
		btn.custom_minimum_size = Vector2(0, 34)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.add_theme_font_size_override("font_size", 16)
		var next_id: String = choice["next"]
		btn.pressed.connect(func(): _go_to(next_id))
		choice_container.add_child(btn)

func _clear_choices() -> void:
	for child in choice_container.get_children():
		child.queue_free()

func _go_to(next_id: String) -> void:
	AudioManager.play_sfx("click")
	if next_id == "_close":
		_end()
		return
	# Career quest routing
	if next_id.begins_with("_career:correct:"):
		var parts = next_id.split(":")
		_clear_choices()
		has_choices = false
		_begin_career_correct(parts[2], int(parts[3]))
		return
	if next_id.begins_with("_career:wrong:"):
		var parts = next_id.split(":")
		_clear_choices()
		has_choices = false
		_begin_career_wrong(parts[2], int(parts[3]))
		return
	if next_id.begins_with("_career:"):
		var career_id = next_id.substr(8)  # len("_career:") = 8
		_clear_choices()
		has_choices = false
		_begin_career_quest(career_id)
		return
	# Static dialogue routing
	_clear_choices()
	has_choices = false
	_begin(next_id)

func _execute_callbacks(cb_str: String) -> void:
	if cb_str == "":
		return
	for cb in cb_str.split(";"):
		_execute_single(cb.strip_edges())

func _execute_single(cb: String) -> void:
	var parts = cb.split(":")
	var action = parts[0]
	match action:
		"start_quest": GameManager.start_quest(parts[1])
		"complete_quest": GameManager.complete_quest(parts[1])
		"complete_job": GameManager.complete_job(parts[1])
		"complete_career_quest": GameManager.complete_career_quest(parts[1])
		"add_quest_friendship": GameManager.add_quest_friendship(parts[1])
		"give_money": GameManager.add_money(int(parts[1]))
		"give_xp": GameManager.add_skill_xp(parts[1], int(parts[2]))
		"advance_time": GameManager.advance_time(float(parts[1]))
		"spend_energy": GameManager.spend_energy(float(parts[1]))
		"add_happiness": GameManager.add_happiness(float(parts[1]))
		"sleep":
			AudioManager.play_sfx("sleep")
			GameManager.sleep()
			AudioManager.play_bgm("home")
		"show_day_summary":
			var ds := get_tree().get_first_node_in_group("day_summary")
			if ds and ds.has_method("show_summary"):
				ds.show_summary(GameManager.last_day_summary)
		"set_career": GameManager.career = parts[1]
		"open_compass":
			var cc := get_tree().get_first_node_in_group("career_compass")
			if cc and cc.has_method("show_compass"):
				cc.show_compass()

func _end() -> void:
	is_active = false
	panel.visible = false
	hint_label.visible = false
	_clear_choices()
	_lock_player(false)

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
