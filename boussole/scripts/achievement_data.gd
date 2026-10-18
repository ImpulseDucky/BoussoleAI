extends RefCounted
## AchievementData — static definitions for all achievements in the game.
## Each achievement has: id, name, description, category, icon (emoji string).

class_name AchievementData

const ACHIEVEMENTS := [
	# ── Quests ──
	{"id": "first_quest", "name": "First Steps", "desc": "Complete your first career quest", "category": "Quests", "icon": "*"},
	{"id": "quest_10", "name": "Getting Started", "desc": "Complete 10 career quests", "category": "Quests", "icon": "**"},
	{"id": "quest_25", "name": "Career Explorer", "desc": "Complete 25 career quests", "category": "Quests", "icon": "***"},
	{"id": "quest_50", "name": "Dedicated Worker", "desc": "Complete 50 career quests", "category": "Quests", "icon": "****"},
	{"id": "quest_135", "name": "Career Master", "desc": "Complete all 135 career quests!", "category": "Quests", "icon": "*****"},

	# ── Careers ──
	{"id": "first_career", "name": "Career Complete", "desc": "Finish all 5 quests in one career", "category": "Careers", "icon": "+"},
	{"id": "careers_5", "name": "Renaissance Person", "desc": "Complete 5 different careers", "category": "Careers", "icon": "++"},
	{"id": "careers_27", "name": "Jack of All Trades", "desc": "Complete all 27 careers!", "category": "Careers", "icon": "+++"},

	# ── Skills ──
	{"id": "skill_5", "name": "Skilled", "desc": "Reach level 5 in any skill", "category": "Skills", "icon": "S"},
	{"id": "skill_10", "name": "Expert", "desc": "Reach level 10 in any skill", "category": "Skills", "icon": "S+"},
	{"id": "all_skills_5", "name": "Well-Rounded", "desc": "Reach level 5 in all 5 skills", "category": "Skills", "icon": "S*"},

	# ── Wealth ──
	{"id": "money_500", "name": "Pocket Change", "desc": "Accumulate $500", "category": "Wealth", "icon": "$"},
	{"id": "money_2000", "name": "Comfortable", "desc": "Accumulate $2,000", "category": "Wealth", "icon": "$$"},
	{"id": "money_5000", "name": "Wealthy", "desc": "Accumulate $5,000", "category": "Wealth", "icon": "$$$"},

	# ── Time ──
	{"id": "day_7", "name": "First Week", "desc": "Reach day 7", "category": "Journey", "icon": "D"},
	{"id": "day_30", "name": "Monthly Milestone", "desc": "Reach day 30", "category": "Journey", "icon": "DD"},

	# ── Discovery ──
	{"id": "quiz_taken", "name": "Self-Aware", "desc": "Take the personality quiz", "category": "Discovery", "icon": "?"},
	{"id": "first_pin", "name": "Goal Setter", "desc": "Pin your first career goal", "category": "Discovery", "icon": "!"},
	{"id": "pin_5", "name": "Ambitious", "desc": "Pin 5 career goals at once", "category": "Discovery", "icon": "!!"},
	{"id": "all_locations", "name": "Explorer", "desc": "Visit all 6 buildings", "category": "Discovery", "icon": "X"},

	# ── Relationships ──
	{"id": "first_friend", "name": "Friendly Face", "desc": "Reach friendship level 1 with any NPC", "category": "Relationships", "icon": "H"},
	{"id": "close_friend", "name": "Close Companion", "desc": "Reach friendship level 3 with any NPC", "category": "Relationships", "icon": "HHH"},
	{"id": "social_butterfly", "name": "Social Butterfly", "desc": "Reach friendship level 2+ with all 7 NPCs", "category": "Relationships", "icon": "HH"},
]

static func get_all() -> Array:
	return ACHIEVEMENTS

static func get_count() -> int:
	return ACHIEVEMENTS.size()

static func get_by_id(aid: String) -> Dictionary:
	for a in ACHIEVEMENTS:
		if a.id == aid:
			return a
	return {}

static func get_categories() -> Array:
	var cats: Array = []
	for a in ACHIEVEMENTS:
		if not cats.has(a.category):
			cats.append(a.category)
	return cats
