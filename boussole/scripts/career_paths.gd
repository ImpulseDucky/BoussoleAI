class_name CareerPaths
extends RefCounted
## CareerPaths — defines visual career path trees showing how careers connect.
## Each path is a named progression of career IDs, grouped by shared skills.

const PATHS := [
	{
		"name": "Tech Builder Path",
		"color": Color(0.30, 0.50, 0.80),
		"desc": "Build things with code and systems",
		"careers": ["tech_it", "tech_bug_hunt", "tech_website", "tech_data"],
	},
	{
		"name": "Design Path",
		"color": Color(0.55, 0.40, 0.65),
		"desc": "Blend creativity with technical skills",
		"careers": ["tech_it", "tech_ux", "tech_website", "town_marketing"],
	},
	{
		"name": "Culinary Path",
		"color": Color(0.75, 0.55, 0.30),
		"desc": "Create experiences through food and service",
		"careers": ["cafe_service", "cafe_latte", "cafe_chef", "cafe_catering"],
	},
	{
		"name": "Events & Marketing Path",
		"color": Color(0.80, 0.65, 0.25),
		"desc": "Plan, promote, and run events",
		"careers": ["cafe_service", "town_event_plan", "town_event_run", "town_marketing"],
	},
	{
		"name": "Research & Writing Path",
		"color": Color(0.35, 0.55, 0.35),
		"desc": "Investigate, organize, and communicate knowledge",
		"careers": ["lib_archive", "lib_research", "lib_catalog", "lib_writer", "home_content"],
	},
	{
		"name": "Consulting Path",
		"color": Color(0.65, 0.45, 0.55),
		"desc": "Solve problems and advise others",
		"careers": ["lib_research", "lib_writer", "town_marketing", "town_consult", "town_event_run"],
	},
	{
		"name": "Independent Path",
		"color": Color(0.45, 0.60, 0.50),
		"desc": "Work independently with multiple skills",
		"careers": ["home_freelance", "home_content", "town_marketing", "town_consult"],
	},
	{
		"name": "Creative Arts Path",
		"color": Color(0.65, 0.35, 0.55),
		"desc": "Express ideas through visual and digital arts",
		"careers": ["art_graphic", "art_illustrator", "art_photo", "art_animator"],
	},
	{
		"name": "Community Service Path",
		"color": Color(0.35, 0.55, 0.65),
		"desc": "Help people and build stronger communities",
		"careers": ["cc_social", "cc_youth", "cc_nonprofit", "cc_organizer"],
	},
]

static func get_path_count() -> int:
	return PATHS.size()

static func get_path_data(idx: int) -> Dictionary:
	if idx < 0 or idx >= PATHS.size():
		return {}
	return PATHS[idx]
