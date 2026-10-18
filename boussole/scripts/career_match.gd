class_name CareerMatch
extends RefCounted
## CareerMatch — scores every career against the player's skill profile (0-100%).
## Compares the player's skill levels to each career's required skills.
## Higher levels in the required skills = higher match score.

## Returns a 0-100 match score for a career based on player's skill levels.
static func get_career_match(career_id: String) -> int:
	var career: Dictionary = CareerData.get_career(career_id)
	if career.is_empty():
		return 0
	var req_skills: Array = career.get("skills", [])
	if req_skills.is_empty():
		return 0

	# Average level across the career's required skills
	var total_level: float = 0.0
	for skill in req_skills:
		total_level += GameManager.get_skill_level(skill)
	var avg_level: float = total_level / req_skills.size()

	# Also consider all 5 skills — a well-rounded profile gets a small bonus
	var all_skills: Array = ["technical", "creativity", "communication", "problem_solving", "organization"]
	var all_total: float = 0.0
	for skill in all_skills:
		all_total += GameManager.get_skill_level(skill)
	var all_avg: float = all_total / all_skills.size()

	# Weighted: 70% required-skill match, 30% general level
	var score: float = (avg_level * 0.7 + all_avg * 0.3)

	# Convert level (1-∞) to percentage. Level 1 = ~20%, Level 3 = ~60%, Level 5 = ~100%
	# Cap at 100
	var pct: int = int(score * 20.0)
	return clampi(pct, 0, 100)

## Returns sorted list of top career matches.
## Each entry: { career_id, name, score, reasoning }
static func get_top_matches(count: int = 5) -> Array:
	var results: Array = []
	for career_id in CareerData.get_all_career_ids():
		var score: int = get_career_match(career_id)
		var career: Dictionary = CareerData.get_career(career_id)
		var req_skills: Array = career.get("skills", [])
		var reasoning: String = _build_reasoning(career_id, req_skills, score)
		results.append({
			"career_id": career_id,
			"name": CareerData.get_career_name(career_id),
			"score": score,
			"reasoning": reasoning,
		})
	# Sort by score descending
	results.sort_custom(func(a, b): return a.score > b.score)
	# Return top N
	if results.size() > count:
		results = results.slice(0, count)
	return results

## Returns a human-readable explanation of why a career matches (or doesn't).
static func _build_reasoning(career_id: String, req_skills: Array, score: int) -> String:
	var parts: Array = []
	for skill in req_skills:
		var lvl: int = GameManager.get_skill_level(skill)
		var label: String = skill.replace("_", " ").capitalize()
		if lvl >= 3:
			parts.append("strong " + label + " (Lv " + str(lvl) + ")")
		elif lvl >= 2:
			parts.append("growing " + label + " (Lv " + str(lvl) + ")")
		else:
			parts.append("low " + label + " (Lv " + str(lvl) + ")")

	# Also check quests completed for this career
	var progress: int = GameManager.get_career_progress(career_id)
	var total: int = CareerData.get_quest_count(career_id)
	if progress > 0:
		if progress >= total:
			return "Mastered! All " + str(total) + " quests complete. Consider mentoring others."
		else:
			return "In progress — " + str(progress) + "/" + str(total) + " quests done. " + " | ".join(parts)

	if score >= 80:
		return "Excellent fit — your skills align strongly. " + " | ".join(parts)
	elif score >= 60:
		return "Good potential — try it to build your skills. " + " | ".join(parts)
	elif score >= 40:
		return "Stretch career — will challenge you. " + " | ".join(parts)
	else:
		return "New territory — could be a growth opportunity. " + " | ".join(parts)

## Returns the player's strongest skill name.
static func get_strongest_skill() -> String:
	var skills: Array = ["technical", "creativity", "communication", "problem_solving", "organization"]
	var best: String = "technical"
	var best_level: int = 0
	for skill in skills:
		var lvl: int = GameManager.get_skill_level(skill)
		if lvl > best_level:
			best_level = lvl
			best = skill
	return best

## Returns the player's weakest skill name.
static func get_weakest_skill() -> String:
	var skills: Array = ["technical", "creativity", "communication", "problem_solving", "organization"]
	var worst: String = "technical"
	var worst_level: int = 999
	for skill in skills:
		var lvl: int = GameManager.get_skill_level(skill)
		if lvl < worst_level:
			worst_level = lvl
			worst = skill
	return worst

## Returns a personality summary based on skill distribution.
static func get_personality_summary() -> String:
	var skills: Array = ["technical", "creativity", "communication", "problem_solving", "organization"]
	var levels: Dictionary = {}
	for skill in skills:
		levels[skill] = GameManager.get_skill_level(skill)

	var strongest: String = get_strongest_skill()

	# Determine personality type
	var top_score: int = levels[strongest]
	if top_score <= 1:
		return "You're still discovering your strengths. Try different careers to find what clicks!"
	elif strongest == "creativity" and levels.get("communication", 0) >= 2:
		return "You're a Creative Communicator — you thrive when expressing ideas and connecting with people."
	elif strongest == "technical" and levels.get("problem_solving", 0) >= 2:
		return "You're a Technical Problem-Solver — you love breaking down complex systems and finding solutions."
	elif strongest == "organization" and levels.get("communication", 0) >= 2:
		return "You're an Organized Leader — you bring order to chaos and help teams stay on track."
	elif strongest == "communication":
		return "You're a People Person — you excel at understanding, motivating, and connecting with others."
	elif strongest == "creativity":
		return "You're a Creative Spirit — you see possibilities others miss and love bringing new ideas to life."
	elif strongest == "technical":
		return "You're a Hands-On Builder — you enjoy working with tools, code, and systems to make things work."
	elif strongest == "problem_solving":
		return "You're an Analytical Thinker — you love puzzles, logic, and finding the root cause."
	elif strongest == "organization":
		return "You're a Detail Planner — you thrive on structure, systems, and keeping things running smoothly."
	else:
		return "You're a Versatile Learner — your skills are balanced across many areas."
