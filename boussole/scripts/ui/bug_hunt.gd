extends CanvasLayer
## BugHunt — a full-screen code editor style GUI for the bug hunt challenge.
## Found via group "bug_hunt". Call open() to show, close() to hide.
## Replaces the dialogue-based bug hunt with an interactive code panel.

@onready var bg: ColorRect = $BG
@onready var window: Panel = $Window
@onready var title_label: Label = $Window/TitleBar/TitleLabel
@onready var code_area: Panel = $Window/CodePanel
@onready var line_numbers: Label = $Window/CodePanel/LineNumbers
@onready var code_text: RichTextLabel = $Window/CodePanel/CodeText
@onready var question_label: Label = $Window/QuestionLabel
@onready var answer_container: VBoxContainer = $Window/AnswerContainer
@onready var result_panel: Panel = $Window/ResultPanel
@onready var result_title: Label = $Window/ResultPanel/VBox/ResultTitle
@onready var result_text: Label = $Window/ResultPanel/VBox/ResultText
@onready var xp_label: Label = $Window/ResultPanel/VBox/XPLabel
@onready var continue_btn: Button = $Window/ResultPanel/VBox/ContinueBtn

# Bug hunt challenge data — multiple questions for replayability
var challenges: Array = [
	{
		"title": "Bug Hunt Challenge",
		"code_lines": [
			"function sum(items) {",
			"  let total = 0;",
			"  for (let i = 0; i <= items.length; i++) {",
			"    total += items[i];",
			"  }",
			"  return total;",
			"}",
		],
		"language": "JavaScript",
		"question": "Which line has the bug?",
		"answers": [
			{"text": "let total = 0", "line": 2, "correct": false},
			{"text": "i <= items.length", "line": 3, "correct": true},
			{"text": "total += items[i]", "line": 4, "correct": false},
			{"text": "return total", "line": 6, "correct": false},
		],
		"correct_title": "Correct!",
		"correct_text": "The loop should use i < items.length, not <=.\nUsing <= causes an off-by-one error — it reads one element past the end of the array.\n\nOff-by-one errors are among the most common bugs in programming.",
		"wrong_title": "Not quite...",
		"wrong_text": "Look again at the loop condition.\nHint: What happens when i equals items.length?\nThe array has indices 0 to length-1. Accessing index length is out of bounds.",
		"xp_reward": "+50 Technical XP\n+30 Problem-Solving XP",
	},
]

var current_challenge: int = 0
var is_open: bool = false

func _ready() -> void:
	add_to_group("bug_hunt")
	bg.visible = false
	window.visible = false
	result_panel.visible = false
	continue_btn.pressed.connect(_on_continue)

func open() -> void:
	if is_open:
		return
	is_open = true
	bg.visible = true
	window.visible = true
	result_panel.visible = false
	answer_container.visible = true
	_load_challenge(current_challenge)
	_lock_player(true)

func close() -> void:
	is_open = false
	bg.visible = false
	window.visible = false
	result_panel.visible = false
	_lock_player(false)

func _load_challenge(idx: int) -> void:
	var ch: Dictionary = challenges[idx % challenges.size()]
	# Title
	title_label.text = ch.get("title", "Bug Hunt") + "  —  " + ch.get("language", "Code")
	# Code display with line numbers
	var lines: Array = ch.get("code_lines", [])
	var ln_text := ""
	var code_body := ""
	for i in lines.size():
		var ln: String = lines[i]
		ln_text += str(i + 1) + "\n"
		# Color-code: keywords, strings, numbers (simple highlighting)
		code_body += _highlight_code(ln) + "\n"
	line_numbers.text = ln_text
	code_text.text = code_body
	# Question
	question_label.text = ch.get("question", "Find the bug:")
	# Answer buttons
	_clear_answers()
	var answers: Array = ch.get("answers", [])
	for ans in answers:
		var btn := Button.new()
		btn.text = str(ans.get("text", ""))
		btn.custom_minimum_size = Vector2(0, 44)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.add_theme_font_size_override("font_size", 15)
		var is_correct: bool = ans.get("correct", false)
		btn.pressed.connect(func(): _on_answer(is_correct, ch))
		answer_container.add_child(btn)

func _highlight_code(line: String) -> String:
	# Simple BBCode syntax highlighting for code display
	var keywords := ["function", "let", "for", "return", "if", "else", "var", "const", "while"]
	var colored := ""
	var current_word := ""
	var in_string := false

	for i in line.length():
		var ch: String = line[i]

		if in_string:
			colored += ch
			if ch == "\"" or ch == "'":
				colored += "[/color]"
				in_string = false
			continue

		if ch == "\"" or ch == "'":
			# Flush current word
			if current_word.length() > 0:
				colored += _color_word(current_word, keywords)
				current_word = ""
			colored += "[color=#e8c87a]" + ch
			in_string = true
			continue

		if ch.is_valid_int() or (ch == "." and current_word.length() > 0):
			if current_word.length() > 0:
				colored += _color_word(current_word, keywords)
				current_word = ""
			colored += "[color=#b5cea8]" + ch + "[/color]"
			continue

		# Check if character is a letter or underscore
		var code := ch.unicode_at(0)
		var is_alpha: bool = (code >= 65 and code <= 90) or (code >= 97 and code <= 122) or code == 95
		if is_alpha:
			current_word += ch
			continue

		# Non-word character — flush current word
		if current_word.length() > 0:
			colored += _color_word(current_word, keywords)
			current_word = ""
		colored += ch

	# Flush remaining word
	if current_word.length() > 0:
		colored += _color_word(current_word, keywords)

	return colored

func _color_word(word: String, keywords: Array) -> String:
	if word in keywords:
		return "[color=#569cd6]" + word + "[/color]"  # keywords = blue
	return "[color=#dcdcaa]" + word + "[/color]"  # identifiers = light yellow

func _clear_answers() -> void:
	for child in answer_container.get_children():
		child.queue_free()

func _on_answer(is_correct: bool, ch: Dictionary) -> void:
	answer_container.visible = false
	result_panel.visible = true

	if is_correct:
		result_title.text = ch.get("correct_title", "Correct!")
		result_title.add_theme_color_override("font_color", Color(0.3, 0.9, 0.4))
		result_text.text = ch.get("correct_text", "")
		xp_label.text = ch.get("xp_reward", "")
		xp_label.visible = true
		continue_btn.text = "Claim Rewards"
		# Apply rewards
		GameManager.add_skill_xp("technical", 50)
		GameManager.add_skill_xp("problem_solving", 30)
		GameManager.add_money(30)
		GameManager.complete_job("tech_bug_hunt")
		GameManager.advance_time(1.0)
		GameManager.spend_energy(5)
	else:
		result_title.text = ch.get("wrong_title", "Try Again")
		result_title.add_theme_color_override("font_color", Color(0.9, 0.5, 0.3))
		result_text.text = ch.get("wrong_text", "")
		xp_label.visible = false
		continue_btn.text = "Try Again"

func _on_continue() -> void:
	if result_title.text == "Correct!" or result_title.text.begins_with("Correct"):
		# Challenge complete — close and return to game
		close()
	else:
		# Wrong answer — go back to the challenge
		result_panel.visible = false
		answer_container.visible = true
		_load_challenge(current_challenge)

func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			get_viewport().set_input_as_handled()
			close()

func _lock_player(locked: bool) -> void:
	var p := get_tree().get_first_node_in_group("player")
	if p:
		p.set("input_locked", locked)
