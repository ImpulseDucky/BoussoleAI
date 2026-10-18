extends Node
## AudioManager — singleton autoload. Plays BGM per location and SFX on demand.
## All audio is generated WAV files loaded at runtime.

var _bgm_player: AudioStreamPlayer
var _sfx_player: AudioStreamPlayer
var _current_bgm: String = ""
var _bgm_volume: float = 0.4
var _sfx_volume: float = 0.6
var _bgm_streams: Dictionary = {}  # location_name → AudioStreamWAV
var _sfx_streams: Dictionary = {}  # sfx_name → AudioStreamWAV
var _initialized: bool = false

const BGM_MAP := {
	"town": "res://assets/audio/bgm_town.wav",
	"home": "res://assets/audio/bgm_home.wav",
	"tech_studio": "res://assets/audio/bgm_tech.wav",
	"library": "res://assets/audio/bgm_library.wav",
	"cafe": "res://assets/audio/bgm_cafe.wav",
	"art_studio": "res://assets/audio/bgm_art.wav",
	"community_center": "res://assets/audio/bgm_community.wav",
	"menu": "res://assets/audio/bgm_menu.wav",
}

const SFX_MAP := {
	"click": "res://assets/audio/sfx_click.wav",
	"notify": "res://assets/audio/sfx_notify.wav",
	"quest": "res://assets/audio/sfx_quest.wav",
	"buy": "res://assets/audio/sfx_buy.wav",
	"levelup": "res://assets/audio/sfx_levelup.wav",
	"door": "res://assets/audio/sfx_door.wav",
	"sleep": "res://assets/audio/sfx_sleep.wav",
}

func _ready() -> void:
	_bgm_player = AudioStreamPlayer.new()
	_bgm_player.bus = "Master"
	_bgm_player.volume_db = linear_to_db(_bgm_volume)
	add_child(_bgm_player)
	_sfx_player = AudioStreamPlayer.new()
	_sfx_player.bus = "Master"
	_sfx_player.volume_db = linear_to_db(_sfx_volume)
	add_child(_sfx_player)
	_load_streams()
	_initialized = true
	# Connect to location changes
	GameManager.location_changed.connect(_on_location_changed)
	GameManager.achievement_unlocked.connect(_on_achievement)
	GameManager.challenges_updated.connect(_on_challenge)
	# Start menu music if in menu
	if not GameManager.game_started:
		play_bgm("menu")

func _load_streams() -> void:
	# Load BGM
	for loc in BGM_MAP:
		var path: String = BGM_MAP[loc]
		if ResourceLoader.exists(path):
			var stream := load(path) as AudioStreamWAV
			if stream:
				stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
				_bgm_streams[loc] = stream
	# Load SFX
	for sfx in SFX_MAP:
		var path2: String = SFX_MAP[sfx]
		if ResourceLoader.exists(path2):
			var stream2 := load(path2) as AudioStreamWAV
			if stream2:
				_sfx_streams[sfx] = stream2

func play_bgm(location: String) -> void:
	if not _initialized:
		return
	if location == _current_bgm and _bgm_player.playing:
		return
	if not _bgm_streams.has(location):
		location = "menu"  # fallback
	if not _bgm_streams.has(location):
		return
	_current_bgm = location
	_bgm_player.stream = _bgm_streams[location]
	_bgm_player.play()

func stop_bgm() -> void:
	_bgm_player.stop()
	_current_bgm = ""

func play_sfx(sfx_name: String) -> void:
	if not _initialized:
		return
	if not _sfx_streams.has(sfx_name):
		return
	_sfx_player.stream = _sfx_streams[sfx_name]
	_sfx_player.play()

func set_bgm_volume(vol: float) -> void:
	_bgm_volume = clamp(vol, 0.0, 1.0)
	_bgm_player.volume_db = linear_to_db(_bgm_volume)

func set_sfx_volume(vol: float) -> void:
	_sfx_volume = clamp(vol, 0.0, 1.0)
	_sfx_player.volume_db = linear_to_db(_sfx_volume)

func get_bgm_volume() -> float:
	return _bgm_volume

func get_sfx_volume() -> float:
	return _sfx_volume

func _on_location_changed() -> void:
	var loc: String = GameManager.current_location
	play_bgm(loc)
	# Play door sound on location change
	if loc != "menu":
		play_sfx("door")

func _on_achievement(_aid: String) -> void:
	play_sfx("quest")

func _on_challenge() -> void:
	for c in GameManager.daily_challenges:
		if c.completed:
			play_sfx("notify")
			break
