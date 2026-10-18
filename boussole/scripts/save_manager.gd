extends Node
## SaveManager — singleton autoload. Save/load game state to JSON file.

const SAVE_PATH = "user://boussole_save.json"

func has_save() -> bool:
	return FileAccess.file_exists(SAVE_PATH)

func save_game() -> void:
	var data = {
		"time": {"hour": GameManager.hour, "minute": GameManager.minute, "day": GameManager.day},
		"stats": {"money": GameManager.money, "energy": GameManager.energy, "happiness": GameManager.happiness},
		"skills": GameManager.skills.duplicate(true),
		"quests": {
			"active": GameManager.active_quest,
			"completed": GameManager.completed_quests.duplicate(),
			"step": GameManager.quest_step
		},
		"jobs": {
			"completed": GameManager.completed_jobs.duplicate(true),
			"total": GameManager.total_jobs_completed,
			"pinned": GameManager.pinned_jobs.duplicate(),
			"career_progress": GameManager.career_progress.duplicate(true),
		},
		"career": GameManager.career,
		"quiz_taken": GameManager.quiz_taken,
		"quiz_profile": GameManager.quiz_profile,
		"location": GameManager.current_location,
		"position": {"x": GameManager.return_position.x, "y": GameManager.return_position.y},
		"achievements": {
			"unlocked": GameManager.unlocked_achievements.duplicate(true),
			"visited": GameManager.visited_locations.duplicate(),
			"total_earned": GameManager.total_money_earned,
		},
		"challenges": {
			"daily": GameManager.daily_challenges.duplicate(true),
			"claimed": GameManager.challenge_rewards_claimed,
		},
		"items": GameManager.owned_items.duplicate(true),
		"day_track": {
			"quests": GameManager.quests_today,
			"xp": GameManager.xp_today.duplicate(true),
			"earned": GameManager.money_earned_today,
			"spent": GameManager.money_spent_today,
			"energy": GameManager.energy_used_today,
			"happiness": GameManager.happiness_today,
			"friendship": GameManager.friendship_today,
			"talked_today": GameManager.npc_talked_today.duplicate(true),
		},
		"settings": {
			"bgm": GameManager.settings_bgm_volume,
			"sfx": GameManager.settings_sfx_volume,
			"particles": GameManager.settings_particles,
			"fullscreen": GameManager.settings_fullscreen,
		},
		"npc_friendship": GameManager.npc_friendship.duplicate(true),
	}
	var file = FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file == null:
		push_error("SaveManager: cannot open save file for writing")
		return
	file.store_string(JSON.stringify(data, "  "))
	file.close()

func load_game() -> bool:
	if not has_save():
		return false
	var file = FileAccess.open(SAVE_PATH, FileAccess.READ)
	if file == null:
		return false
	var text = file.get_as_text()
	file.close()
	var data = JSON.parse_string(text)
	if data == null:
		return false

	var t = data.get("time", {})
	GameManager.hour = int(t.get("hour", 8))
	GameManager.minute = int(t.get("minute", 0))
	GameManager.day = int(t.get("day", 1))

	var s = data.get("stats", {})
	GameManager.money = int(s.get("money", 250))
	GameManager.energy = float(s.get("energy", 80))
	GameManager.happiness = float(s.get("happiness", 70))

	GameManager.skills = data.get("skills", GameManager.skills)

	var q = data.get("quests", {})
	GameManager.active_quest = q.get("active", "")
	GameManager.completed_quests = q.get("completed", [])
	GameManager.quest_step = int(q.get("step", 0))

	var j = data.get("jobs", {})
	GameManager.completed_jobs = j.get("completed", {})
	GameManager.total_jobs_completed = int(j.get("total", 0))
	GameManager.pinned_jobs = j.get("pinned", [])
	GameManager.career_progress = j.get("career_progress", {})

	GameManager.career = data.get("career", "")
	GameManager.quiz_taken = data.get("quiz_taken", false)
	GameManager.quiz_profile = data.get("quiz_profile", "")
	GameManager.set_location(data.get("location", "town"))

	var p = data.get("position", {})
	GameManager.return_position = Vector2(float(p.get("x", 1280)), float(p.get("y", 960)))

	var ach = data.get("achievements", {})
	GameManager.unlocked_achievements = ach.get("unlocked", {})
	GameManager.visited_locations = ach.get("visited", [])
	GameManager.total_money_earned = int(ach.get("total_earned", 0))

	var ch = data.get("challenges", {})
	GameManager.daily_challenges = ch.get("daily", [])
	GameManager.challenge_rewards_claimed = ch.get("claimed", false)

	GameManager.owned_items = data.get("items", {})

	var dt = data.get("day_track", {})
	GameManager.quests_today = int(dt.get("quests", 0))
	GameManager.xp_today = dt.get("xp", {})
	GameManager.money_earned_today = int(dt.get("earned", 0))
	GameManager.money_spent_today = int(dt.get("spent", 0))
	GameManager.energy_used_today = float(dt.get("energy", 0.0))
	GameManager.happiness_today = float(dt.get("happiness", 0.0))
	GameManager.friendship_today = float(dt.get("friendship", 0.0))
	GameManager.npc_talked_today = dt.get("talked_today", {})

	var st = data.get("settings", {})
	GameManager.settings_bgm_volume = float(st.get("bgm", 0.4))
	GameManager.settings_sfx_volume = float(st.get("sfx", 0.6))
	GameManager.settings_particles = bool(st.get("particles", true))
	GameManager.settings_fullscreen = bool(st.get("fullscreen", false))
	AudioManager.set_bgm_volume(GameManager.settings_bgm_volume)
	AudioManager.set_sfx_volume(GameManager.settings_sfx_volume)
	AmbientManager.particles_enabled = GameManager.settings_particles

	GameManager.npc_friendship = data.get("npc_friendship", {})

	GameManager.game_started = true
	GameManager.stats_changed.emit()
	GameManager.time_changed.emit()
	GameManager.quest_updated.emit()
	return true

func delete_save() -> void:
	if has_save():
		DirAccess.remove_absolute(SAVE_PATH)
