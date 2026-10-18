extends Control
## Welcome — title screen with Start New Game and Continue buttons.

@onready var start_btn: Button = $VBox/StartButton
@onready var continue_btn: Button = $VBox/ContinueButton

func _ready() -> void:
	AudioManager.play_bgm("menu")
	start_btn.pressed.connect(_on_start)
	if SaveManager.has_save():
		continue_btn.visible = true
		continue_btn.pressed.connect(_on_continue)
	else:
		continue_btn.visible = false

func _on_start() -> void:
	AudioManager.play_sfx("click")
	GameManager.new_game()
	# Launch the self-discovery quiz before entering town
	TransitionManager.change_scene("res://scenes/ui/quiz.tscn")

func _on_continue() -> void:
	AudioManager.play_sfx("click")
	SaveManager.load_game()
	TransitionManager.change_scene("res://scenes/town.tscn")
