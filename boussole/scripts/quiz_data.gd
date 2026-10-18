class_name QuizData
extends RefCounted
## QuizData — self-discovery quiz questions for the personality assessment.
## Each question has 4 choices, each mapping to skill weights.
## After all questions, the highest-weighted skills form the player's profile.

const QUESTIONS := [
	{
		"text": "It's a free afternoon. What sounds most appealing?",
		"choices": [
			{"text": "Tinker with a gadget, code a small app, or fix something broken", "weights": {"technical": 3, "problem_solving": 1}},
			{"text": "Draw, write a story, or design something new", "weights": {"creativity": 3, "communication": 1}},
			{"text": "Call up friends and plan a group activity", "weights": {"communication": 3, "organization": 1}},
			{"text": "Organize your room, make a schedule, or plan a project step by step", "weights": {"organization": 3, "problem_solving": 1}},
		],
	},
	{
		"text": "When facing a tough problem, you tend to...",
		"choices": [
			{"text": "Break it into smaller parts and tackle each piece logically", "weights": {"problem_solving": 3, "technical": 1}},
			{"text": "Brainstorm wild ideas and look for unexpected connections", "weights": {"creativity": 3, "communication": 1}},
			{"text": "Talk it through with someone to get different perspectives", "weights": {"communication": 3, "organization": 1}},
			{"text": "Research what others have done, then make a detailed plan", "weights": {"organization": 3, "problem_solving": 1}},
		],
	},
	{
		"text": "What kind of satisfaction feels best to you?",
		"choices": [
			{"text": "Seeing something I built actually work", "weights": {"technical": 3, "problem_solving": 1}},
			{"text": "Creating something nobody has seen before", "weights": {"creativity": 3, "communication": 1}},
			{"text": "Helping someone understand something or feel better", "weights": {"communication": 3, "organization": 1}},
			{"text": "Turning chaos into a smooth, organized system", "weights": {"organization": 3, "problem_solving": 1}},
		],
	},
	{
		"text": "In a group project, you naturally...",
		"choices": [
			{"text": "Do the hands-on building or technical work", "weights": {"technical": 3, "problem_solving": 1}},
			{"text": "Come up with the creative concept and pitch", "weights": {"creativity": 3, "communication": 1}},
			{"text": "Keep everyone motivated and coordinate communication", "weights": {"communication": 3, "organization": 1}},
			{"text": "Make the timeline, assign tasks, and track progress", "weights": {"organization": 3, "problem_solving": 1}},
		],
	},
	{
		"text": "What's your favorite kind of game or puzzle?",
		"choices": [
			{"text": "Building games (Minecraft, SimCity) where you construct systems", "weights": {"technical": 2, "organization": 2}},
			{"text": "Story-driven games where you make creative choices", "weights": {"creativity": 3, "communication": 1}},
			{"text": "Party games or co-op games with friends", "weights": {"communication": 3, "creativity": 1}},
			{"text": "Strategy puzzles (Sudoku, chess) that test your logic", "weights": {"problem_solving": 3, "organization": 1}},
		],
	},
	{
		"text": "People most often describe you as...",
		"choices": [
			{"text": "The fixer — you can make anything work", "weights": {"technical": 3, "problem_solving": 1}},
			{"text": "The dreamer — you're full of ideas", "weights": {"creativity": 3, "communication": 1}},
			{"text": "The connector — you bring people together", "weights": {"communication": 3, "organization": 1}},
			{"text": "The planner — you always have a plan", "weights": {"organization": 3, "problem_solving": 1}},
		],
	},
	{
		"text": "If you could take one workshop, which would it be?",
		"choices": [
			{"text": "Learn to code or build electronics", "weights": {"technical": 3, "problem_solving": 1}},
			{"text": "Creative writing, painting, or graphic design", "weights": {"creativity": 3, "communication": 1}},
			{"text": "Public speaking or negotiation skills", "weights": {"communication": 3, "organization": 1}},
			{"text": "Project management or productivity systems", "weights": {"organization": 3, "problem_solving": 1}},
		],
	},
	{
		"text": "What frustrates you most?",
		"choices": [
			{"text": "When something is broken and nobody knows how to fix it", "weights": {"technical": 2, "problem_solving": 2}},
			{"text": "When everything is boring, repetitive, and leaves no room for imagination", "weights": {"creativity": 3, "communication": 1}},
			{"text": "When people don't communicate and things fall apart", "weights": {"communication": 3, "organization": 1}},
			{"text": "When there's no plan and everything is last-minute chaos", "weights": {"organization": 3, "problem_solving": 1}},
		],
	},
]

## Returns the personality type label based on accumulated skill weights.
static func get_profile_type(weights: Dictionary) -> String:
	var sorted := weights.duplicate()
	var keys: Array = sorted.keys()
	keys.sort_custom(func(a, b): return sorted[a] > sorted[b])

	var top: String = keys[0]
	var second: String = keys[1] if keys.size() > 1 else ""

	var top_label: String = top.replace("_", " ").capitalize()
	var second_label: String = second.replace("_", " ").capitalize() if second != "" else ""

	# Named personality types for common combinations
	if top == "creativity" and second == "communication":
		return "Creative Communicator"
	elif top == "technical" and second == "problem_solving":
		return "Technical Problem-Solver"
	elif top == "organization" and second == "communication":
		return "Organized Leader"
	elif top == "communication" and second == "creativity":
		return "Creative Communicator"
	elif top == "technical" and second == "creativity":
		return "Creative Builder"
	elif top == "problem_solving" and second == "technical":
		return "Analytical Engineer"
	elif top == "organization" and second == "problem_solving":
		return "Strategic Planner"
	elif top == "creativity" and second == "problem_solving":
		return "Innovative Thinker"
	elif top == "communication" and second == "organization":
		return "People Coordinator"
	else:
		return top_label + " / " + second_label
