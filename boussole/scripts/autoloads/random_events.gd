extends Node
## RandomEventManager — triggers spontaneous events while walking in town.
## Adds surprise, variety, and rewards exploration. Autoload singleton.

var _timer: float = 0.0
var _next_trigger: float = 20.0

const EVENTS := [
	{"text": "You found $5 on the ground!", "money": 5, "xp": {}, "happiness": 2},
	{"text": "A bird dropped a feather — you feel lucky!", "money": 0, "xp": {"creativity": 10}, "happiness": 3},
	{"text": "You helped someone carry groceries. +5 communication XP", "money": 0, "xp": {"communication": 5}, "happiness": 1},
	{"text": "You found a cool pebble. +5 problem-solving XP", "money": 0, "xp": {"problem_solving": 5}, "happiness": 1},
	{"text": "You notice a beautiful flower. +5 creativity XP", "money": 0, "xp": {"creativity": 5}, "happiness": 3},
	{"text": "A stranger smiled at you. You feel happier.", "money": 0, "xp": {}, "happiness": 5},
	{"text": "You picked up litter. +5 organization XP", "money": 0, "xp": {"organization": 5}, "happiness": 2},
	{"text": "You overheard an interesting idea. +5 technical XP", "money": 0, "xp": {"technical": 5}, "happiness": 0},
	{"text": "You returned a lost wallet. +$10 reward!", "money": 10, "xp": {"communication": 5}, "happiness": 5},
	{"text": "You discovered a hidden path. +5 problem-solving XP", "money": 0, "xp": {"problem_solving": 5}, "happiness": 1},
	{"text": "A child showed you their drawing. +5 creativity XP", "money": 0, "xp": {"creativity": 5}, "happiness": 3},
	{"text": "You helped an elderly person cross the street. +5 communication XP", "money": 0, "xp": {"communication": 5}, "happiness": 4},
	{"text": "You found a lost coin. +$3!", "money": 3, "xp": {}, "happiness": 1},
	{"text": "You organized a messy shelf at the park. +5 organization XP", "money": 0, "xp": {"organization": 5}, "happiness": 2},
]

func _ready() -> void:
	set_process(true)

func _process(delta: float) -> void:
	if not GameManager.game_started:
		return
	if GameManager.is_paused:
		return
	# Only trigger in town
	if GameManager.current_location != "town":
		return
	# Don't trigger while any overlay is open
	for g in ["dialogue", "pause_menu", "journal", "quest_map", "career_tracker", "profile"]:
		var node = get_tree().get_first_node_in_group(g)
		if node == null:
			continue
		if "is_active" in node and node.is_active:
			return
		if "visible" in node and node.visible:
			return

	_timer += delta
	if _timer >= _next_trigger:
		_timer = 0.0
		_next_trigger = randf_range(15.0, 40.0)
		_try_trigger()

func _try_trigger() -> void:
	var player = get_tree().get_first_node_in_group("player")
	if player == null:
		return
	# Only trigger when the player is actually moving
	if player.velocity.length() < 20:
		return

	var event: Dictionary = EVENTS[randi() % EVENTS.size()]

	# Apply effects
	if event.get("money", 0) > 0:
		GameManager.add_money(event.money)
	if event.get("happiness", 0) > 0:
		GameManager.add_happiness(event.happiness)
	var xp: Dictionary = event.get("xp", {})
	for skill in xp:
		GameManager.add_skill_xp(skill, xp[skill])

	# Show notification via HUD
	var hud = get_tree().get_first_node_in_group("hud")
	if hud and hud.has_method("show_notification"):
		hud.show_notification(event.text)
		AudioManager.play_sfx("notify")
