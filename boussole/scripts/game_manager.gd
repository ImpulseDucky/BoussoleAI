extends Node
## GameManager — singleton autoload. Tracks all game state: time, stats, skills, quests.

# ── Time ──
var hour: int = 8
var minute: int = 0
var day: int = 1

# ── Stats ──
var money: int = 250
var energy: float = 80.0
var max_energy: float = 100.0
var happiness: float = 70.0
var max_happiness: float = 100.0

# ── Skills ──
var skills: Dictionary = {
	"technical": {"level": 1, "xp": 0},
	"creativity": {"level": 1, "xp": 0},
	"communication": {"level": 1, "xp": 0},
	"problem_solving": {"level": 1, "xp": 0},
	"organization": {"level": 1, "xp": 0}
}

# ── Quests (legacy, kept for save compat) ──
var active_quest: String = ""
var quest_step: int = 0
var completed_quests: Array = []

# ── Jobs (free-form career exploration) ──
var completed_jobs: Dictionary = {}  # job_id → completion count (legacy)
var total_jobs_completed: int = 0    # legacy
var pinned_jobs: Array = []  # career_ids the player is tracking

# ── Career Quest Progress ──
# career_id → number of quests completed (0 to 5)
var career_progress: Dictionary = {}

# ── Career ──
var career: String = ""

# ── Quiz ──
var quiz_taken: bool = false
var quiz_profile: String = ""  # personality type label from quiz

# ── Navigation ──
var return_position: Vector2 = Vector2(1280, 768)  # tile (40, 24) — on the road, not in water
var current_location: String = "town"

func set_location(loc: String) -> void:
	current_location = loc
	if not visited_locations.has(loc) and loc != "town":
		visited_locations.append(loc)
	location_changed.emit()
	_check_achievements()

# ── State ──
var game_started: bool = false
var is_paused: bool = false

# ── Settings (persisted) ──
var settings_bgm_volume: float = 0.4
var settings_sfx_volume: float = 0.6
var settings_particles: bool = true
var settings_fullscreen: bool = false

# ── Day Tracking (reset on sleep) ──
var quests_today: int = 0
var xp_today: Dictionary = {}
var money_earned_today: int = 0
var money_spent_today: int = 0
var energy_used_today: float = 0.0
var happiness_today: float = 0.0
var friendship_today: float = 0.0
var last_day_summary: Dictionary = {}  # captured at sleep time

# ── Achievements ──
var unlocked_achievements: Dictionary = {}  # achievement_id → true
var visited_locations: Array = []  # track which locations have been visited
var total_money_earned: int = 0  # lifetime money earned (for achievements)

# ── Daily Challenges ──
var daily_challenges: Array = []  # array of challenge dicts: {id, desc, target, progress, reward, completed}
var challenge_rewards_claimed: bool = false

# ── Shop Items ──
var owned_items: Dictionary = {}  # item_id → count

# ── NPC Relationships ──
# Maps career location → NPC dialogue_id for friendship gain on quest complete
const NPC_BY_LOCATION := {
	"Tech Studio": "mentor",
	"Library": "librarian",
	"Cafe": "barista",
	"Art Studio": "art_guide",
	"Community Center": "cc_guide",
	"Town Square": "guide",
}
# All 7 NPC dialogue IDs (for achievement tracking)
const ALL_NPC_IDS := ["mentor", "librarian", "barista", "guide", "friend", "art_guide", "cc_guide"]
var npc_friendship: Dictionary = {}      # dialogue_id → int (0-100)
var npc_talked_today: Dictionary = {}     # dialogue_id → bool

# ── Signals ──
signal stats_changed
signal time_changed
signal quest_updated
signal location_changed
signal achievement_unlocked  # param: achievement_id (String)
signal challenges_updated

# ── Time ──

func advance_time(hours: float) -> void:
	minute += int(hours * 60)
	while minute >= 60:
		minute -= 60
		hour += 1
	while hour >= 24:
		hour -= 24
		day += 1
		energy = min(max_energy, energy + 20)  # partial recovery each new day
	time_changed.emit()
	stats_changed.emit()
	_check_achievements()

func get_time_string() -> String:
	var ampm = "AM" if hour < 12 else "PM"
	var h = hour
	if h == 0: h = 12
	elif h > 12: h -= 12
	return "%d:%02d %s" % [h, minute, ampm]

func is_late_night() -> bool:
	return hour >= 22 or hour < 6

# ── Stats ──

func spend_energy(amount: float) -> void:
	energy = max(0, energy - amount)
	energy_used_today += amount
	stats_changed.emit()
	update_challenge_progress()

func restore_energy(amount: float) -> void:
	energy = min(max_energy, energy + amount)
	stats_changed.emit()

func add_money(amount: int) -> void:
	money += amount
	if amount > 0:
		money_earned_today += amount
		total_money_earned += amount
	elif amount < 0:
		money_spent_today += abs(amount)
	stats_changed.emit()
	_check_achievements()
	update_challenge_progress()

func add_happiness(amount: float) -> void:
	happiness = clamp(happiness + amount, 0, max_happiness)
	happiness_today += amount
	stats_changed.emit()

func has_energy(amount: float) -> bool:
	return energy >= amount

# ── Skills ──

func add_skill_xp(skill_name: String, amount: int) -> void:
	if not skills.has(skill_name):
		return
	var s = skills[skill_name]
	s.xp += amount
	var needed = s.level * 100
	while s.xp >= needed:
		s.xp -= needed
		s.level += 1
		needed = s.level * 100
	# Track daily XP
	if not xp_today.has(skill_name):
		xp_today[skill_name] = 0
	xp_today[skill_name] = xp_today[skill_name] + amount
	stats_changed.emit()
	_check_achievements()
	update_challenge_progress()

func get_skill_level(skill_name: String) -> int:
	if skills.has(skill_name):
		return skills[skill_name].level
	return 0

func get_skill_xp(skill_name: String) -> int:
	if skills.has(skill_name):
		return skills[skill_name].xp
	return 0

func get_xp_needed(skill_name: String) -> int:
	if skills.has(skill_name):
		return skills[skill_name].level * 100
	return 100

# ── Quests ──

func start_quest(quest_id: String) -> void:
	active_quest = quest_id
	quest_step = 0
	quest_updated.emit()

func advance_quest_step() -> void:
	quest_step += 1
	quest_updated.emit()

func complete_quest(quest_id: String) -> void:
	if not completed_quests.has(quest_id):
		completed_quests.append(quest_id)
	active_quest = ""
	quest_updated.emit()

func is_quest_active(quest_id: String) -> bool:
	return active_quest == quest_id

func is_quest_completed(quest_id: String) -> bool:
	return completed_quests.has(quest_id)

func get_quest_step() -> int:
	return quest_step

# ── Jobs ──

func complete_job(job_id: String) -> void:
	if completed_jobs.has(job_id):
		completed_jobs[job_id] += 1
	else:
		completed_jobs[job_id] = 1
	total_jobs_completed += 1
	stats_changed.emit()
	quest_updated.emit()

func get_job_count(job_id: String) -> int:
	return completed_jobs.get(job_id, 0)

func has_done_job(job_id: String) -> bool:
	return completed_jobs.has(job_id)

func get_unique_jobs_completed() -> int:
	return completed_jobs.size()

func pin_job(job_id: String) -> void:
	if not pinned_jobs.has(job_id):
		pinned_jobs.append(job_id)
		quest_updated.emit()
		_check_achievements()

func unpin_job(job_id: String) -> void:
	pinned_jobs.erase(job_id)
	quest_updated.emit()

func is_job_pinned(job_id: String) -> bool:
	return pinned_jobs.has(job_id)

func clear_pinned_jobs() -> void:
	pinned_jobs.clear()
	quest_updated.emit()

# ── Career Quest Progress ──

func get_career_progress(career_id: String) -> int:
	return career_progress.get(career_id, 0)

func complete_career_quest(career_id: String) -> void:
	var current: int = get_career_progress(career_id)
	career_progress[career_id] = current + 1
	quests_today += 1
	quest_updated.emit()
	_check_achievements()
	update_challenge_progress()

func get_total_quests_done() -> int:
	var total: int = 0
	for career_id in career_progress:
		total += career_progress[career_id]
	return total

func get_total_career_quests() -> int:
	return CareerData.get_total_quests()  # 135

func is_career_complete(career_id: String) -> bool:
	return get_career_progress(career_id) >= CareerData.get_quest_count(career_id)

func get_careers_completed_count() -> int:
	var count: int = 0
	for career_id in career_progress:
		if career_progress[career_id] >= CareerData.get_quest_count(career_id):
			count += 1
	return count

# ── Sleep ──

func sleep() -> void:
	# Capture day summary before resetting
	last_day_summary = {
		"day": day,
		"quests": quests_today,
		"xp": xp_today.duplicate(),
		"money_earned": money_earned_today,
		"money_spent": money_spent_today,
		"energy_used": energy_used_today,
		"happiness_change": happiness_today,
		"friendship_change": friendship_today,
	}
	# Reset day trackers
	quests_today = 0
	xp_today.clear()
	money_earned_today = 0
	money_spent_today = 0
	energy_used_today = 0.0
	happiness_today = 0.0
	friendship_today = 0.0
	npc_talked_today.clear()
	# Generate new daily challenges for the new day
	generate_daily_challenges()
	# Sleep
	hour = 8
	minute = 0
	day += 1
	energy = max_energy
	happiness = min(max_happiness, happiness + 5)
	time_changed.emit()
	stats_changed.emit()
	_check_achievements()

# ── New Game ──

func new_game() -> void:
	hour = 8
	minute = 0
	day = 1
	money = 250
	energy = 80.0
	happiness = 70.0
	skills = {
		"technical": {"level": 1, "xp": 0},
		"creativity": {"level": 1, "xp": 0},
		"communication": {"level": 1, "xp": 0},
		"problem_solving": {"level": 1, "xp": 0},
		"organization": {"level": 1, "xp": 0}
	}
	active_quest = ""
	quest_step = 0
	completed_quests.clear()
	completed_jobs.clear()
	total_jobs_completed = 0
	pinned_jobs.clear()
	career_progress.clear()
	career = ""
	quiz_taken = false
	quiz_profile = ""
	quests_today = 0
	xp_today.clear()
	money_earned_today = 0
	money_spent_today = 0
	energy_used_today = 0.0
	happiness_today = 0.0
	friendship_today = 0.0
	last_day_summary.clear()
	unlocked_achievements.clear()
	visited_locations.clear()
	total_money_earned = 0
	owned_items.clear()
	npc_friendship.clear()
	npc_talked_today.clear()
	generate_daily_challenges()
	set_location("town")
	return_position = Vector2(1280, 768)
	game_started = true
	stats_changed.emit()
	time_changed.emit()
	quest_updated.emit()

# ── Achievements ──

func _check_achievements() -> void:
	var total_quests := get_total_quests_done()
	var careers_done := get_careers_completed_count()
	var max_skill_level := 0
	var all_at_5 := true
	for skill_name in skills:
		var lvl: int = skills[skill_name].level
		if lvl > max_skill_level:
			max_skill_level = lvl
		if lvl < 5:
			all_at_5 = false

	# Quest achievements
	_try_unlock("first_quest", total_quests >= 1)
	_try_unlock("quest_10", total_quests >= 10)
	_try_unlock("quest_25", total_quests >= 25)
	_try_unlock("quest_50", total_quests >= 50)
	_try_unlock("quest_135", total_quests >= 135)
	# Career achievements
	_try_unlock("first_career", careers_done >= 1)
	_try_unlock("careers_5", careers_done >= 5)
	_try_unlock("careers_27", careers_done >= 27)
	# Skill achievements
	_try_unlock("skill_5", max_skill_level >= 5)
	_try_unlock("skill_10", max_skill_level >= 10)
	_try_unlock("all_skills_5", all_at_5)
	# Wealth achievements
	_try_unlock("money_500", money >= 500)
	_try_unlock("money_2000", money >= 2000)
	_try_unlock("money_5000", money >= 5000)
	# Time achievements
	_try_unlock("day_7", day >= 7)
	_try_unlock("day_30", day >= 30)
	# Discovery achievements
	_try_unlock("quiz_taken", quiz_taken)
	_try_unlock("first_pin", pinned_jobs.size() >= 1)
	_try_unlock("pin_5", pinned_jobs.size() >= 5)
	_try_unlock("all_locations", visited_locations.size() >= 6)

	# Relationship achievements
	var max_friend_level: int = 0
	var npcs_at_2plus: int = 0
	for npc_id in ALL_NPC_IDS:
		var lvl: int = get_npc_friendship_level(npc_id)
		if lvl > max_friend_level:
			max_friend_level = lvl
		if lvl >= 2:
			npcs_at_2plus += 1
	_try_unlock("first_friend", max_friend_level >= 1)
	_try_unlock("close_friend", max_friend_level >= 3)
	_try_unlock("social_butterfly", npcs_at_2plus >= ALL_NPC_IDS.size())

func _try_unlock(aid: String, condition: bool) -> void:
	if condition and not unlocked_achievements.has(aid):
		unlocked_achievements[aid] = true
		achievement_unlocked.emit(aid)

func is_achievement_unlocked(aid: String) -> bool:
	return unlocked_achievements.has(aid)

func get_unlocked_count() -> int:
	return unlocked_achievements.size()

# ── Daily Challenges ──

func generate_daily_challenges() -> void:
	daily_challenges.clear()
	challenge_rewards_claimed = false
	var pool: Array = [
		{"id": "dq_quests2", "desc": "Complete 2 quests today", "target": 2, "reward": 30},
		{"id": "dq_quests4", "desc": "Complete 4 quests today", "target": 4, "reward": 60},
		{"id": "dq_earn50", "desc": "Earn $50 today", "target": 50, "reward": 25},
		{"id": "dq_earn100", "desc": "Earn $100 today", "target": 100, "reward": 50},
		{"id": "dq_energy", "desc": "Use 60 energy today", "target": 60, "reward": 20},
		{"id": "dq_explore", "desc": "Visit 3 different buildings", "target": 3, "reward": 35},
		{"id": "dq_skills", "desc": "Gain 80 total skill XP today", "target": 80, "reward": 40},
	]
	# Pick 3 random challenges
	pool.shuffle()
	for i in range(mini(3, pool.size())):
		var c = pool[i].duplicate()
		c["progress"] = 0
		c["completed"] = false
		daily_challenges.append(c)
	challenges_updated.emit()

func update_challenge_progress() -> void:
	for c in daily_challenges:
		if c.completed:
			continue
		match c.id:
			"dq_quests2", "dq_quests4":
				c.progress = quests_today
			"dq_earn50", "dq_earn100":
				c.progress = money_earned_today
			"dq_energy":
				c.progress = int(energy_used_today)
			"dq_explore":
				c.progress = visited_locations.size()
			"dq_skills":
				var total_xp: int = 0
				for skill in xp_today:
					total_xp += xp_today[skill]
				c.progress = total_xp
		if c.progress >= c.target:
			c.completed = true
	challenges_updated.emit()

func claim_challenge_rewards() -> int:
	if challenge_rewards_claimed:
		return 0
	var total_reward: int = 0
	for c in daily_challenges:
		if c.completed:
			total_reward += c.reward
	challenge_rewards_claimed = true
	if total_reward > 0:
		add_money(total_reward)
	return total_reward

func all_challenges_done() -> bool:
	for c in daily_challenges:
		if not c.completed:
			return false
	return true

# ── Shop ──

func buy_item(item_id: String, cost: int) -> bool:
	if money < cost:
		return false
	money -= cost
	money_spent_today += cost
	if not owned_items.has(item_id):
		owned_items[item_id] = 0
	owned_items[item_id] = owned_items[item_id] + 1
	stats_changed.emit()
	return true

func get_item_count(item_id: String) -> int:
	return owned_items.get(item_id, 0)

# ── NPC Friendship ──

func get_npc_friendship(dialogue_id: String) -> int:
	return int(npc_friendship.get(dialogue_id, 0))

func add_npc_friendship(dialogue_id: String, amount: int) -> void:
	var current: int = get_npc_friendship(dialogue_id)
	npc_friendship[dialogue_id] = clamp(current + amount, 0, 100)
	friendship_today += amount
	stats_changed.emit()
	_check_achievements()

func has_talked_today(dialogue_id: String) -> bool:
	return bool(npc_talked_today.get(dialogue_id, false))

func mark_talked_today(dialogue_id: String) -> void:
	npc_talked_today[dialogue_id] = true

func get_npc_friendship_level(dialogue_id: String) -> int:
	var f: int = get_npc_friendship(dialogue_id)
	if f >= 75:
		return 3
	if f >= 50:
		return 2
	if f >= 25:
		return 1
	return 0

func add_quest_friendship(career_id: String) -> void:
	var loc: String = CareerData.get_career_location(career_id)
	var npc_id: String = NPC_BY_LOCATION.get(loc, "")
	if npc_id != "":
		add_npc_friendship(npc_id, 5)

func get_total_friendship() -> int:
	var total: int = 0
	for id in npc_friendship:
		total += npc_friendship[id]
	return total
