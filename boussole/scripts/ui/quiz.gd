extends CanvasLayer
## Quiz — self-discovery quiz shown at the start of a new game.
## 8 questions mapping to 5 skill axes. Results give starting skill bonuses
## and a personality profile label stored in GameManager.

const FONT := preload("res://fonts/ArialUnicode.ttf")

@onready var bg: ColorRect = $BG
@onready var title_label: Label = $Panel/VBox/TitleLabel
@onready var subtitle_label: Label = $Panel/VBox/SubtitleLabel
@onready var progress_label: Label = $Panel/VBox/ProgressLabel
@onready var question_label: Label = $Panel/VBox/QuestionLabel
@onready var choice_container: VBoxContainer = $Panel/VBox/ChoiceContainer
@onready var hint_label: Label = $Panel/VBox/HintLabel

var q_index: int = 0
var weights: Dictionary = {
	"technical": 0, "creativity": 0, "communication": 0,
	"problem_solving": 0, "organization": 0,
}
var finished: bool = false

func _ready() -> void:
	_show_question()

func _show_question() -> void:
	if q_index >= QuizData.QUESTIONS.size():
		_show_results()
		return

	var q: Dictionary = QuizData.QUESTIONS[q_index]
	progress_label.text = "Question " + str(q_index + 1) + " of " + str(QuizData.QUESTIONS.size())
	question_label.text = q["text"]
	hint_label.text = "Click an answer to continue"

	# Clear previous choices
	for child in choice_container.get_children():
		child.queue_free()

	# Create choice buttons
	var choices: Array = q["choices"]
	for i in range(choices.size()):
		var choice: Dictionary = choices[i]
		var btn := Button.new()
		btn.text = choice["text"]
		btn.add_theme_font_override("font", FONT)
		btn.add_theme_font_size_override("font_size", 16)
		btn.custom_minimum_size = Vector2(0, 50)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		var w: Dictionary = choice["weights"]
		btn.pressed.connect(func(): _on_answer(w))
		choice_container.add_child(btn)

func _on_answer(w: Dictionary) -> void:
	# Accumulate weights
	for skill in w:
		weights[skill] = weights.get(skill, 0) + w[skill]
	q_index += 1
	_show_question()

func _show_results() -> void:
	finished = true

	# Determine personality type
	var profile: String = QuizData.get_profile_type(weights)
	GameManager.quiz_taken = true
	GameManager.quiz_profile = profile

	# Apply starting skill bonuses — give XP to the top 2 skills
	var sorted_keys: Array = weights.keys()
	sorted_keys.sort_custom(func(a, b): return weights[a] > weights[b])

	# Top skill gets +50 XP, second gets +30 XP, others get +10 XP
	for i in range(sorted_keys.size()):
		var skill: String = sorted_keys[i]
		var xp_amount: int
		if i == 0:
			xp_amount = 50
		elif i == 1:
			xp_amount = 30
		else:
			xp_amount = 10
		GameManager.add_skill_xp(skill, xp_amount)

	# Build results display
	progress_label.text = ""
	question_label.text = ""

	for child in choice_container.get_children():
		child.queue_free()

	# Title
	title_label.text = "Your Profile: " + profile

	# Build skill ranking text
	var lines: Array = []
	lines.append("Based on your answers, here's your skill profile:")
	lines.append("")
	for i in range(sorted_keys.size()):
		var skill: String = sorted_keys[i]
		var score: int = weights[skill]
		var label: String = skill.replace("_", " ").capitalize()
		var bar_len: int = int(float(score) / 24.0 * 20.0)
		var bar: String = ""
		for _j in range(bar_len):
			bar += "|"
		for _j in range(20 - bar_len):
			bar += "."
		lines.append(label + "  [" + bar + "]  " + str(score))

	lines.append("")
	lines.append("You've received bonus XP in your top skills!")
	lines.append("Try careers that match your strengths — press P to see your full profile with career matches.")

	# Display as a single label
	var result_label := Label.new()
	result_label.add_theme_font_override("font", FONT)
	result_label.add_theme_font_size_override("font_size", 15)
	result_label.add_theme_color_override("font_color", Color(0.85, 0.85, 0.9))
	result_label.text = "\n".join(lines)
	result_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	result_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	result_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	result_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	choice_container.add_child(result_label)

	# Start game button
	var start_btn := Button.new()
	start_btn.text = "Enter Boussole"
	start_btn.add_theme_font_override("font", FONT)
	start_btn.add_theme_font_size_override("font_size", 20)
	start_btn.custom_minimum_size = Vector2(0, 50)
	start_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	start_btn.pressed.connect(_on_start_game)
	choice_container.add_child(start_btn)

	hint_label.text = ""

func _on_start_game() -> void:
	# Transition to town
	TransitionManager.change_scene("res://scenes/town.tscn")

func _input(event: InputEvent) -> void:
	if not finished:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_E or event.keycode == KEY_SPACE or event.keycode == KEY_ENTER:
			get_viewport().set_input_as_handled()
			_on_start_game()
