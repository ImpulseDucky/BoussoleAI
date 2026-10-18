"""Generate a pixelated tileset PNG (512x32, 16 tiles of 32x32).

Tiles:
  0  Grass       1  Path        2  Water      3  Wall
  4  Wood floor  5  Stone floor 6  Roof      7  Tree
  8  Flowers     9  Sand       10 Road       11 Desk
 12  Bookshelf  13  Bed       14  Counter    15 Computer
"""
import struct, zlib

TILE = 32
TILES = 16
W = TILE * TILES  # 512
H = TILE          # 32

pixels = bytearray(W * H * 4)


def set_px(x, y, r, g, b, a=255):
    """Set pixel at absolute (x, y) in the full 512x32 image."""
    idx = (y * W + x) * 4
    pixels[idx] = r
    pixels[idx + 1] = g
    pixels[idx + 2] = b
    pixels[idx + 3] = a


def set_px_tid(tid, x, y, r, g, b, a=255):
    """Set pixel at tile-relative (x, y) within tile `tid`."""
    set_px(tid * TILE + x, y, r, g, b, a)


def fill_tile(tid, r, g, b):
    for py in range(TILE):
        for px in range(TILE):
            set_px_tid(tid, px, py, r, g, b)


def draw_rect_tid(tid, x0, y0, x1, y1, r, g, b):
    for py in range(max(0, y0), min(TILE, y1 + 1)):
        for px in range(max(0, x0), min(TILE, x1 + 1)):
            set_px_tid(tid, px, py, r, g, b)


def hnoise(px, py, seed=0):
    return (px * 7 + py * 13 + seed * 3) % 7


# ─── Tile 0: Grass ───
fill_tile(0, 60, 122, 50)
# Better 2D noise hash — no horizontal banding
def grass_noise(px, py):
    return ((px * 73856093) ^ (py * 19349663) ^ 0x9e3779b9) & 0xff
for py in range(TILE):
    for px in range(TILE):
        h = grass_noise(px, py)
        if h < 12:
            set_px_tid(0, px, py, 45, 100, 35)   # darker blade
        elif h < 24:
            set_px_tid(0, px, py, 75, 145, 60)   # sunlit highlight
        elif h < 30:
            set_px_tid(0, px, py, 50, 110, 42)   # medium dark
# Sparse tuft clusters (4 small tufts) for texture
tufts = [(4, 6), (4, 7), (5, 6),
         (12, 18), (12, 19), (13, 18),
         (22, 9), (22, 10), (23, 9),
         (27, 23), (27, 24), (28, 23)]
for tx, ty in tufts:
    set_px_tid(0, tx, ty, 35, 85, 28)
    set_px_tid(0, tx + 1, ty, 40, 92, 32)

# ─── Tile 1: Path ───
fill_tile(1, 140, 120, 88)
for py in range(TILE):
    for px in range(TILE):
        h = hnoise(px, py, 1)
        if h == 0:
            set_px_tid(1, px, py, 115, 98, 72)
        elif h == 3:
            set_px_tid(1, px, py, 158, 138, 100)
        elif h == 5:
            set_px_tid(1, px, py, 128, 108, 80)

# ─── Tile 2: Water ───
fill_tile(2, 30, 80, 120)
for py in range(TILE):
    for px in range(TILE):
        h = hnoise(px, py, 2)
        if h == 0:
            set_px_tid(2, px, py, 20, 60, 90)
        elif h == 3:
            set_px_tid(2, px, py, 50, 110, 150)
# wave lines
for px in range(TILE):
    if px % 5 < 3:
        set_px_tid(2, px, 8, 60, 130, 170)
        set_px_tid(2, px, 22, 60, 130, 170)
    if px % 7 < 4:
        set_px_tid(2, px, 16, 45, 100, 145)

# ─── Tile 3: Wall (brick) ───
fill_tile(3, 70, 68, 75)
for py in range(TILE):
    for px in range(TILE):
        if px == 0 or px == TILE - 1 or py == 0 or py == TILE - 1:
            set_px_tid(3, px, py, 45, 43, 48)
        elif px == 1 or px == TILE - 2:
            set_px_tid(3, px, py, 90, 88, 95)
        elif py == 15:
            set_px_tid(3, px, py, 45, 43, 48)
        elif py == 7:
            set_px_tid(3, px, py, 55, 53, 58)
        elif py == 23:
            set_px_tid(3, px, py, 55, 53, 58)
        elif hnoise(px, py, 3) == 0:
            set_px_tid(3, px, py, 55, 53, 58)
        elif hnoise(px, py, 3) == 3:
            set_px_tid(3, px, py, 85, 83, 90)

# ─── Tile 4: Wood floor ───
fill_tile(4, 160, 130, 85)
for py in range(TILE):
    for px in range(TILE):
        if py % 8 == 0:
            set_px_tid(4, px, py, 130, 105, 68)  # plank line
        elif px % 16 == 0:
            set_px_tid(4, px, py, 130, 105, 68)  # vertical seam
        elif hnoise(px, py, 4) == 0:
            set_px_tid(4, px, py, 145, 118, 75)
        elif hnoise(px, py, 4) == 3:
            set_px_tid(4, px, py, 175, 145, 95)

# ─── Tile 5: Stone floor ───
fill_tile(5, 120, 120, 128)
for py in range(TILE):
    for px in range(TILE):
        if px % 16 == 0 or py % 16 == 0:
            set_px_tid(5, px, py, 95, 95, 100)  # grout lines
        elif hnoise(px, py, 5) == 0:
            set_px_tid(5, px, py, 108, 108, 115)
        elif hnoise(px, py, 5) == 3:
            set_px_tid(5, px, py, 135, 135, 142)

# ─── Tile 6: Roof ───
fill_tile(6, 140, 55, 45)
for py in range(TILE):
    for px in range(TILE):
        if py % 6 == 0:
            set_px_tid(6, px, py, 110, 40, 35)  # shingle line
        elif (px + py // 6 * 8) % 16 == 0:
            set_px_tid(6, px, py, 110, 40, 35)  # vertical seam
        elif hnoise(px, py, 6) == 0:
            set_px_tid(6, px, py, 125, 48, 38)
        elif hnoise(px, py, 6) == 3:
            set_px_tid(6, px, py, 160, 68, 52)

# ─── Tile 7: Tree ───
fill_tile(7, 52, 110, 42)  # grass base
# trunk
draw_rect_tid(7, 13, 20, 18, 31, 80, 50, 30)
draw_rect_tid(7, 14, 18, 17, 31, 90, 58, 35)
# canopy (circle-ish)
for py in range(TILE):
    for px in range(TILE):
        cx, cy = 16, 10
        d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
        if d < 12:
            if d < 8:
                set_px_tid(7, px, py, 30, 80, 25)
            else:
                set_px_tid(7, px, py, 38, 95, 28)
            if hnoise(px, py, 7) == 3:
                set_px_tid(7, px, py, 45, 105, 35)

# ─── Tile 8: Flowers ───
fill_tile(8, 52, 110, 42)  # grass base
flower_colors = [(200, 60, 60), (220, 200, 50), (150, 80, 180), (200, 180, 60), (180, 100, 140)]
positions = [(4, 4), (10, 8), (18, 6), (24, 12), (8, 18), (20, 20), (14, 14), (26, 24), (6, 24), (16, 26)]
for i, (fx, fy) in enumerate(positions):
    fc = flower_colors[i % len(flower_colors)]
    set_px_tid(8, fx, fy, fc[0], fc[1], fc[2])
    set_px_tid(8, fx + 1, fy, fc[0], fc[1], fc[2])
    set_px_tid(8, fx, fy + 1, fc[0], fc[1], fc[2])
    set_px_tid(8, fx + 1, fy + 1, fc[0] // 2, fc[1] // 2, fc[2] // 2)
    # stem
    set_px_tid(8, fx, max(0, fy - 1), 38, 85, 30)

# ─── Tile 9: Sand ───
fill_tile(9, 210, 190, 140)
for py in range(TILE):
    for px in range(TILE):
        h = hnoise(px, py, 9)
        if h == 0:
            set_px_tid(9, px, py, 185, 165, 120)
        elif h == 3:
            set_px_tid(9, px, py, 225, 205, 155)
        elif h == 5:
            set_px_tid(9, px, py, 198, 178, 130)

# ─── Tile 10: Road ───
fill_tile(10, 55, 55, 60)
for py in range(TILE):
    for px in range(TILE):
        if py == 0 or py == TILE - 1:
            set_px_tid(10, px, py, 40, 40, 45)
        elif hnoise(px, py, 10) == 0:
            set_px_tid(10, px, py, 48, 48, 52)
        elif hnoise(px, py, 10) == 3:
            set_px_tid(10, px, py, 63, 63, 68)
# yellow center line (dashed)
for px in range(2, TILE - 2, 6):
    for dx in range(3):
        set_px_tid(10, px + dx, 15, 200, 180, 40)
        set_px_tid(10, px + dx, 16, 200, 180, 40)

# ─── Tile 11: Desk ───
fill_tile(11, 120, 85, 50)  # wood base
draw_rect_tid(11, 0, 0, 31, 4, 100, 72, 42)  # top edge
draw_rect_tid(11, 0, 5, 31, 20, 130, 95, 58)  # surface
draw_rect_tid(11, 4, 8, 28, 18, 30, 30, 40)  # dark screen area
draw_rect_tid(11, 6, 10, 26, 16, 40, 120, 140)  # screen glow
draw_rect_tid(11, 0, 21, 31, 31, 100, 72, 42)  # front panel
# legs
set_px_tid(11, 2, 22, 80, 55, 32)
set_px_tid(11, 29, 22, 80, 55, 32)
set_px_tid(11, 2, 31, 80, 55, 32)
set_px_tid(11, 29, 31, 80, 55, 32)

# ─── Tile 12: Bookshelf ───
fill_tile(12, 100, 70, 40)  # wood frame
draw_rect_tid(12, 1, 1, 30, 7, 90, 62, 35)  # shelf 1 bg
draw_rect_tid(12, 1, 9, 30, 15, 90, 62, 35)  # shelf 2 bg
draw_rect_tid(12, 1, 17, 30, 23, 90, 62, 35)  # shelf 3 bg
draw_rect_tid(12, 1, 25, 30, 30, 90, 62, 35)  # shelf 4 bg
# book spines on each shelf
book_colors = [(160, 50, 50), (50, 80, 160), (50, 130, 60), (200, 180, 50), (150, 80, 180), (80, 160, 80)]
for shelf_y in [2, 10, 18, 26]:
    bx = 2
    bi = 0
    while bx < 30:
        bw = 2 + (bi % 3)  # varying widths
        bc = book_colors[bi % len(book_colors)]
        draw_rect_tid(12, bx, shelf_y, min(bx + bw, 30), shelf_y + 5, bc[0], bc[1], bc[2])
        bx += bw + 1
        bi += 1
# shelf dividers
for sy in [8, 16, 24]:
    draw_rect_tid(12, 0, sy, 31, sy + 1, 80, 55, 30)

# ─── Tile 13: Bed ───
fill_tile(13, 120, 90, 55)  # frame
draw_rect_tid(13, 2, 6, 29, 14, 220, 220, 230)  # pillow
draw_rect_tid(13, 2, 15, 29, 29, 60, 80, 140)  # blanket
draw_rect_tid(13, 3, 16, 28, 28, 70, 95, 155)  # blanket highlight
# pillow details
set_px_tid(13, 4, 8, 240, 240, 245)
set_px_tid(13, 6, 10, 240, 240, 245)
# frame edges
draw_rect_tid(13, 0, 0, 31, 5, 100, 75, 42)
draw_rect_tid(13, 0, 0, 1, 31, 100, 75, 42)
draw_rect_tid(13, 30, 0, 31, 31, 100, 75, 42)

# ─── Tile 14: Counter ───
fill_tile(14, 80, 55, 35)
draw_rect_tid(14, 0, 0, 31, 6, 100, 72, 48)  # top surface
draw_rect_tid(14, 0, 7, 31, 31, 72, 50, 30)  # front
for py in range(TILE):
    for px in range(TILE):
        if py > 6 and hnoise(px, py, 14) == 0:
            set_px_tid(14, px, py, 60, 42, 25)
        elif py <= 6 and hnoise(px, py, 14) == 3:
            set_px_tid(14, px, py, 115, 85, 55)
# counter top edge highlight
draw_rect_tid(14, 0, 0, 31, 1, 120, 90, 60)

# ─── Tile 15: Computer ───
fill_tile(15, 40, 40, 50)  # dark base
draw_rect_tid(15, 4, 2, 28, 4, 50, 50, 60)  # stand
draw_rect_tid(15, 6, 4, 26, 20, 30, 30, 40)  # monitor frame
draw_rect_tid(15, 8, 6, 24, 18, 40, 180, 200)  # screen
# screen content
draw_rect_tid(15, 10, 8, 22, 10, 50, 200, 220)  # text line
draw_rect_tid(15, 10, 12, 18, 13, 80, 220, 240)
draw_rect_tid(15, 10, 15, 20, 16, 80, 220, 240)
# keyboard
draw_rect_tid(15, 8, 24, 24, 30, 50, 50, 60)
draw_rect_tid(15, 10, 25, 22, 29, 60, 60, 70)
# glow
for py in range(6, 18):
    for px in range(8, 24):
        if hnoise(px, py, 15) == 3:
            set_px_tid(15, px, py, 60, 200, 220)


# ─── Write PNG ───
def write_png(filename, width, height, raw_pixels):
    def make_chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xffffffff)
        return struct.pack(">I", len(data)) + c + crc

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: None
        start = y * width * 4
        raw.extend(raw_pixels[start:start + width * 4])

    compressed = zlib.compress(bytes(raw))

    with open(filename, 'wb') as f:
        f.write(sig)
        f.write(make_chunk(b'IHDR', ihdr))
        f.write(make_chunk(b'IDAT', compressed))
        f.write(make_chunk(b'IEND', b''))


out = '/Users/danielchow/boussole/assets/tileset.png'
write_png(out, W, H, pixels)
print(f"Tileset created: {W}x{H} ({TILES} tiles) at {out}")
