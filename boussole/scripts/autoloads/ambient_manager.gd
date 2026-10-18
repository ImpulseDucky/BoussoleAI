extends Node
## AmbientManager — day/night color overlay + ambient particles (fireflies/leaves).
## Autoload singleton that persists across all scenes, adding atmosphere.

var _overlay: ColorRect
var _draw_node: Control
var _particles: Array = []
var _t: float = 0.0
var particles_enabled: bool = true
const MAX_PARTICLES := 28

# Day/night tint colors (alpha controls overlay strength)
const C_DAWN       := Color(1.08, 0.95, 0.75, 0.15)  # 6–8 AM warm golden
const C_MORNING    := Color(1.02, 0.98, 0.90, 0.07)   # 8–11 AM soft warm
const C_DAY        := Color(1.0, 1.0, 1.0, 0.0)        # 11 AM–3 PM clear
const C_AFTERNOON  := Color(1.06, 0.92, 0.75, 0.10)   # 3–6 PM warm
const C_DUSK       := Color(0.88, 0.72, 0.98, 0.22)    # 6–8 PM purple
const C_EVENING    := Color(0.62, 0.55, 0.92, 0.35)    # 8–10 PM deep purple
const C_NIGHT      := Color(0.28, 0.33, 0.60, 0.50)    # 10 PM–12 AM dark blue
const C_LATE       := Color(0.18, 0.22, 0.48, 0.55)   # 12–4 AM darker
const C_PRE_DAWN   := Color(0.25, 0.28, 0.52, 0.48)   # 4–6 AM still dark

func _ready() -> void:
	# Day/night overlay — CanvasLayer at 5 (above world+particles, below UI at 30+)
	var overlay_layer := CanvasLayer.new()
	overlay_layer.layer = 5
	add_child(overlay_layer)
	_overlay = ColorRect.new()
	_overlay.color = C_DAY
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay_layer.add_child(_overlay)

	# Particle draw node — CanvasLayer at 1 (above world tiles, below overlay)
	var particle_layer := CanvasLayer.new()
	particle_layer.layer = 1
	add_child(particle_layer)
	_draw_node = _ParticleDraw.new()
	_draw_node.set_anchors_preset(Control.PRESET_FULL_RECT)
	_draw_node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_draw_node.manager = self
	particle_layer.add_child(_draw_node)

	_init_particles()
	set_process(true)

func _process(delta: float) -> void:
	_t += delta
	_update_day_night(delta)
	if particles_enabled:
		_update_particles(delta)
	_draw_node.queue_redraw()

# ── Day / Night ──

func _update_day_night(delta: float) -> void:
	var h := float(GameManager.hour) + float(GameManager.minute) / 60.0
	var target := _get_tint(h)
	_overlay.color = _overlay.color.lerp(target, 1.2 * delta)

func _get_tint(h: float) -> Color:
	if h >= 6.0 and h < 8.0:
		return C_DAWN
	elif h >= 8.0 and h < 11.0:
		return C_MORNING
	elif h >= 11.0 and h < 15.0:
		return C_DAY
	elif h >= 15.0 and h < 18.0:
		return C_AFTERNOON
	elif h >= 18.0 and h < 20.0:
		return C_DUSK
	elif h >= 20.0 and h < 22.0:
		return C_EVENING
	elif h >= 22.0 and h < 24.0:
		return C_NIGHT
	elif h >= 0.0 and h < 4.0:
		return C_LATE
	else:
		return C_PRE_DAWN

func is_night() -> bool:
	return GameManager.hour >= 20 or GameManager.hour < 6

# ── Ambient Particles ──

func _init_particles() -> void:
	var w := 1280
	var h := 720
	for i in MAX_PARTICLES:
		_particles.append({
			"pos": Vector2(randf() * w, randf() * h),
			"vel": Vector2(randf_range(-12.0, 12.0), randf_range(-8.0, 8.0)),
			"size": randf_range(1.5, 3.5),
			"phase": randf() * TAU,
			"alpha": 0.0,
		})

func _update_particles(delta: float) -> void:
	var w := int(get_viewport().get_visible_rect().size.x)
	var h := int(get_viewport().get_visible_rect().size.y)
	var night := is_night()
	for p in _particles:
		p.phase += delta * 2.5
		p.pos += p.vel * delta
		# Wrap around screen edges
		if p.pos.x < -20: p.pos.x = w + 20
		if p.pos.x > w + 20: p.pos.x = -20
		if p.pos.y < -20: p.pos.y = h + 20
		if p.pos.y > h + 20: p.pos.y = -20
		# Fireflies twinkle at night, gentle fade for daytime pollen
		if night:
			p.alpha = 0.25 + 0.45 * (0.5 + 0.5 * sin(p.phase))
		else:
			p.alpha = 0.20

func draw_particles(canvas: CanvasItem) -> void:
	var night := is_night()
	for p in _particles:
		var col: Color
		if night:
			col = Color(1.0, 0.92, 0.45, p.alpha)  # firefly warm yellow
		else:
			col = Color(0.75, 0.88, 0.50, p.alpha)  # pollen/leaf pale green
		canvas.draw_circle(p.pos, p.size, col)

# ── Inner class for particle rendering ──

class _ParticleDraw extends Control:
	var manager: Node
	func _draw() -> void:
		if manager:
			manager.draw_particles(self)
