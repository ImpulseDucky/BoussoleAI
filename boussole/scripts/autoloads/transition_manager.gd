extends Node
## TransitionManager — smooth fade-to-black on scene changes.
## Autoload singleton. Call change_scene() instead of get_tree().change_scene_to_file().

signal transition_started
signal transition_finished

var _rect: ColorRect
var _tween: Tween
var _is_fading: bool = false

func _ready() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 100  # above everything
	add_child(layer)
	_rect = ColorRect.new()
	_rect.color = Color(0, 0, 0, 0)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	layer.add_child(_rect)

func change_scene(path: String) -> void:
	if _is_fading:
		return
	_is_fading = true
	_rect.mouse_filter = Control.MOUSE_FILTER_STOP  # block input during fade
	transition_started.emit()
	_tween = create_tween()
	_tween.tween_property(_rect, "color:a", 1.0, 0.3)
	_tween.tween_callback(_do_change.bind(path))
	_tween.tween_interval(0.05)
	_tween.tween_property(_rect, "color:a", 0.0, 0.4)
	_tween.tween_callback(_on_finish)

func _do_change(path: String) -> void:
	get_tree().change_scene_to_file(path)

func _on_finish() -> void:
	_is_fading = false
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	transition_finished.emit()
