extends Control
## Main — root scene. Loads the welcome screen on startup.

@onready var screen_container: Control = $ScreenContainer

func _ready() -> void:
	_load_welcome()

func _load_welcome() -> void:
	for child in screen_container.get_children():
		child.queue_free()
	var packed := load("res://scenes/welcome.tscn") as PackedScene
	if packed == null:
		push_error("Boussole: cannot load welcome scene")
		return
	screen_container.add_child(packed.instantiate())
