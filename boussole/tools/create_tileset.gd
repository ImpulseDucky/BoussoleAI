extends SceneTree
## One-shot script: generates a TileSet resource from the tileset PNG atlas.
## Creates all 16 tiles explicitly so they exist in the atlas.
## Run: godot --headless --script tools/create_tileset.gd

func _init():
	var ts := TileSet.new()
	ts.tile_size = Vector2i(32, 32)

	var source := TileSetAtlasSource.new()
	source.texture = load("res://assets/tileset.png")
	source.texture_region_size = Vector2i(32, 32)
	source.margins = Vector2i(0, 0)
	source.separation = Vector2i(0, 0)

	# Explicitly create all 16 tiles (atlas coords are (column, row) = (0..15, 0))
	for i in 16:
		source.create_tile(Vector2i(i, 0))

	var source_id := ts.add_source(source)

	# Verify tiles were created
	var verified := 0
	for i in 16:
		if source.has_tile(Vector2i(i, 0)):
			verified += 1
	print("TileSet source ID: ", source_id, " verified tiles: ", verified, "/16")

	var err := ResourceSaver.save(ts, "res://assets/tileset.tres")
	if err == OK:
		print("TileSet saved to res://assets/tileset.tres")
	else:
		push_error("Failed to save TileSet, error: " + str(err))
	quit()
