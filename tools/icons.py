"""Writes flat versions of MO2's icons into src/icons/mo2, named after their resource alias.

Each one traces the original's shapes at the original's pixel size (the viewBox), in palette colors.
The conflict and flag icons are written as SVG directly; the rest are built from shapes with Qt's
painter paths, which cut real gaps where one shape sits on another.

Needs PyQt6: python tools/icons.py [name ...]
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shapes import (  # noqa: E402
    Icon, arc, arcArrow, arrowHead, circle, ellipse, fill, gear, line, poly, polyline, rect, text, union,
)

# TB: the marks and shines on colored icons, light in both bases; SHADE_MARK: their dark marks.
T, TB, TM = "var(--text)", "var(--icon-mark)", "var(--text-muted)"
SHADE_MARK = "var(--icon-shade)"
A, B, G, R = "var(--icon)", "var(--icon-alt)", "var(--icon-positive)", "var(--icon-negative)"

ICONS = {}
# MO2 paints the notification count onto the notifications icon at 64 pixels, its math holds only for an
# icon of at most that many: a larger one comes back at the screen's ratio and the badge lands off it.
INTRINSIC = {"warning": 64}


def icon(name, size):
    def register(build):
        ICONS[name] = (size, build)
        return build
    return register


# Shared shapes ------------------------------------------------------------------------------------------

def triangle(cx, top, bottom, half, r):
    return poly((cx, top), (cx + half, bottom), (cx - half, bottom), r=r)


def bang(cx, top, bottom, width, dot):
    """An exclamation mark: a stem from top to bottom and a dot below it."""
    stem = rect(cx - width / 2, top, width, bottom - top, width / 2)
    return stem | circle(cx, bottom + dot * 1.9, dot)


def question(cx, cy, s, width):
    """A question mark centered on the point, s high."""
    k = s / 10
    hook = line(
        f"M{cx - 2.6 * k} {cy - 2.2 * k} C{cx - 2.6 * k} {cy - 5.4 * k} {cx + 2.8 * k} {cy - 5.6 * k} "
        f"{cx + 2.8 * k} {cy - 2.4 * k} C{cx + 2.8 * k} {cy - 0.2 * k} {cx} {cy + 0.2 * k} {cx} {cy + 2 * k} "
        f"L{cx} {cy + 2.4 * k}",
        width,
    )
    return hook | circle(cx, cy + 4.6 * k, width * 0.62)


def straightArrow(size, direction, r):
    """A fat arrow, the go-up/down/next/previous kind, in a square of the size."""
    s = size / 22
    points = [(11, 2), (20, 11), (14.8, 11), (14.8, 19.8), (7.2, 19.8), (7.2, 11), (2, 11)]
    shape = poly(*[(x * s, y * s) for x, y in points], r=r)
    return shape.rotate({"up": 0, "right": 90, "down": 180, "left": 270}[direction], size / 2, size / 2)


def refresh(size, width, head):
    c = size / 2
    r = size * 0.33
    return (arcArrow(c, c, r, 200, 340, width, head, head * 1.5)
            | arcArrow(c, c, r, 20, 160, width, head, head * 1.5))


def globe(cx, cy, r, ocean, land):
    """A globe: the Americas on the left, Europe and Africa on the right, inside the ocean's circle."""
    s = r / 13.5
    disc = circle(cx, cy, r)

    def at(points):
        return [(cx + x * s, cy + y * s) for x, y in points]

    americas = poly(*at([(-10, -9), (-4, -11), (-2, -8), (-5, -5), (-6, -2), (-2, 0), (-1, 4), (-4, 9),
                         (-6, 12), (-7, 7), (-9, 2), (-12, -1), (-13, -6)]), r=0.8 * s)
    old = poly(*at([(2, -12), (8, -11), (12, -7), (9, -5), (11, -2), (13, 2), (9, 4), (7, 9), (4, 11),
                    (3, 6), (2, 2), (4, -1), (2, -4), (5, -7), (1, -9)]), r=0.8 * s)
    land_ = (americas | old) & disc.shrink(0.01)
    return [(disc, ocean), (land_, land)]


def heart(cx, cy, w):
    """A heart w wide, its middle on the point."""
    k = w / 14
    return fill(
        f"M{cx} {cy + 6 * k} C{cx - 3 * k} {cy + 3.8 * k} {cx - 7 * k} {cy + 1.2 * k} {cx - 7 * k} {cy - 2.2 * k} "
        f"C{cx - 7 * k} {cy - 4.4 * k} {cx - 5.4 * k} {cy - 6 * k} {cx - 3.4 * k} {cy - 6 * k} "
        f"C{cx - 1.9 * k} {cy - 6 * k} {cx - 0.7 * k} {cy - 5.1 * k} {cx} {cy - 3.8 * k} "
        f"C{cx + 0.7 * k} {cy - 5.1 * k} {cx + 1.9 * k} {cy - 6 * k} {cx + 3.4 * k} {cy - 6 * k} "
        f"C{cx + 5.4 * k} {cy - 6 * k} {cx + 7 * k} {cy - 4.4 * k} {cx + 7 * k} {cy - 2.2 * k} "
        f"C{cx + 7 * k} {cy + 1.2 * k} {cx + 3 * k} {cy + 3.8 * k} {cx} {cy + 6 * k} Z"
    )


def jigsaw(x, y, s, knobs, sockets):
    """A jigsaw piece: an s square with knobs and sockets on the named sides (top, right, bottom, left)."""
    k = s * 0.2
    shape = rect(x, y, s, s)
    centers = {"top": (x + s / 2, y), "right": (x + s, y + s / 2), "bottom": (x + s / 2, y + s),
               "left": (x, y + s / 2)}
    out = {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}
    for side in knobs:
        cx, cy = centers[side]
        dx, dy = out[side]
        shape = shape | circle(cx + dx * k * 0.9, cy + dy * k * 0.9, k)
    for side in sockets:
        cx, cy = centers[side]
        dx, dy = out[side]
        shape = shape - circle(cx - dx * k * 0.6, cy - dy * k * 0.6, k * 0.95)
    return shape


def wrench(x1, y1, x2, y2, width, jaw):
    """A wrench from its handle's end to its open jaw's middle."""
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    handle = polyline([(x1, y1), (x2, y2)], width)
    head = circle(x2, y2, jaw)
    # The jaw's opening points away from the handle.
    slot = rect(x2 - jaw * 0.38, y2 - jaw * 1.4, jaw * 0.76, jaw * 1.4).rotate(angle + 90, x2, y2)
    return (handle | head) - slot


def screwdriver(x1, y1, x2, y2, shaft, handle, split):
    """A screwdriver from its blade's tip to its handle's end, the handle from the share split on."""
    sx, sy = x1 + (x2 - x1) * split, y1 + (y2 - y1) * split
    blade = polyline([(x1, y1), (sx, sy)], shaft, "flat")
    grip = polyline([(sx, sy), (x2, y2)], handle)
    return blade, grip


# Toolbar --------------------------------------------------------------------------------------------------

@icon("installer", 32)
def _(i):
    # A box of software with a red spine, a disc in front of its corner.
    i.add(rect(4, 2.5, 19, 25, 2), T)
    i.add(rect(4, 2.5, 5, 25, 2) | rect(6, 2.5, 3, 25), R, gap=0.9)
    disc = circle(22, 21.5, 8.5)
    i.add(disc - circle(22, 21.5, 2.2), TM, gap=1.3)
    i.add(arc(22, 21.5, 5.2, 200, 260, 1.4, "round"), TB)



@icon("profiles", 32)
def _(i):
    # An ID card: a photo of a person on the left, lines of text on the right and a glow at the corner.
    card = rect(2, 8, 26, 19, 2.5)
    i.add(card, T)
    person = circle(9, 14.2, 2.6) | rect(4.6, 17.6, 8.8, 6.6, 3.3)
    lines = (rect(15.5, 12, 9.5, 1.8, 0.9) | rect(15.5, 15.6, 7, 1.8, 0.9)
             | union(*[rect(15.5 + 1.8 * k, 19.6, 0.9 if k % 2 else 1.2, 4, 0) for k in range(6)]))
    i.cut((person | lines) & rect(3, 9, 24, 17))
    i.add(circle(27, 7, 3.6), A, gap=1.1)


@icon("icon_executable", 32)
def _(i):
    # A green cog with a smaller blue one at its lower right.
    i.add(gear(12.5, 12.5, 11, 8.2, 8, hole=3.6), G)
    i.add(gear(24, 24, 7.2, 5.2, 8, rotation=22.5, hole=2.2), B, gap=1.2)



@icon("plugins", 32)
def _(i):
    # Jigsaw pieces: a grey square of three, the fourth, red, lifted off its top left corner.
    s = 11
    pieces = [
        (jigsaw(16, 5.5, s, ["bottom"], ["left"]), TM),
        (jigsaw(16, 16.5, s, [], ["top", "left"]), TM),
        (jigsaw(5, 16.5, s, ["right", "top"], []), TM),
    ]
    for shape, color in pieces:
        i.add(shape, color, gap=0.6)
    red = jigsaw(5, 5.5, s, ["right"], ["bottom"]).rotate(-12, 10.5, 11).move(-1.8, -2.6)
    i.add(red, R, gap=1)


@icon("settings", 32)
def _(i):
    # A wrench and a screwdriver crossed, the screwdriver's blue handle at the lower right.
    i.add(wrench(5, 27, 22, 10, 4.2, 6.4), TM)
    blade, grip = screwdriver(5, 5, 27.5, 27.5, 2.2, 5.6, 0.56)
    i.add(blade | grip, B, gap=1)
    i.layers[-1] = (blade, TB)
    i.add(grip, B)



@icon("internet-web-browser", 32)
def _(i):
    for shape, color in globe(16, 16, 13.5, B, T):
        i.add(shape, color)


@icon("update", 32)
def _(i):
    # A globe on a stand, circled by a blue arrow up its left and a red one down its right.
    i.add(rect(9.5, 27.5, 13, 2.8, 1.4) | rect(14.6, 22, 2.8, 6), TM)
    for shape, color in globe(16, 13, 8.2, B, T):
        i.add(shape, color, gap=1 if color == B else 0)
    i.add(arcArrow(16, 13, 12, 150, 260, 2.4, 4, 5.5), B, gap=0.8)
    i.add(arcArrow(16, 13, 12, -30, 80, 2.4, 4, 5.5), R, gap=0.8)



@icon("warning", 32)
def _(i):
    # A red-rimmed white triangle with a dark exclamation mark.
    i.add(triangle(16, 2.5, 29, 15, 2.2), R)
    i.add(triangle(16, 8.6, 25.6, 9.6, 0.6), TB)
    i.add(bang(16, 12, 19.4, 3, 1.7), SHADE_MARK)



@icon("help", 32)
def _(i):
    # A blue disc in a white ring with a white question mark.
    i.add(circle(16, 16, 15), TB)
    i.add(circle(16, 16, 13), B)
    i.add(question(16, 15, 15.5, 3.4), TB)


@icon("icon_favorite", 48)
def _(i):
    i.add(heart(24, 24, 42), R)


@icon("instance_switch", 48)
def _(i):
    # Two windows, a blue arrow over the top right and a red one under the bottom left between them.
    back = rect(4, 8, 24, 20, 2.5)
    front = rect(20, 22, 24, 20, 2.5)
    i.add(back, T)
    i.cut(rect(6.5, 13.5, 19, 12, 1))
    i.add(rect(6.5, 13.5, 19, 12, 1), TM)
    i.add(front, T, gap=1.5)
    i.cut(rect(22.5, 27.5, 19, 12, 1))
    i.add(rect(22.5, 27.5, 19, 12, 1), TM)
    i.add(arcArrow(28, 24, 18, -95, -12, 3.2, 6, 8), B, gap=1.2)
    i.add(arcArrow(20, 24, 18, 85, 168, 3.2, 6, 8), R, gap=1.2)



@icon("view-refresh", 22)
def _(i):
    i.add(refresh(22, 2.6, 4.4), B)


# Buttons --------------------------------------------------------------------------------------------------

@icon("refresh", 16)
def _(i):
    i.add(refresh(16, 2, 3.4), B)


@icon("open_folder", 22)
def _(i):
    # A yellow folder, open, with a green arrow curling out of it to the top right.
    back = poly((1.5, 5), (7.5, 5), (9.5, 7), (17, 7), (17, 19), (1.5, 19), r=1)
    i.add(back, A)
    flap = poly((5, 10.5), (21, 10.5), (17.5, 19.5), (1.5, 19.5), r=1)
    i.add(flap, A, gap=1)
    i.add(arcArrow(19.5, 11, 7.5, 200, 285, 2.2, 3.6, 5), G, gap=1)


@icon("restore", 32)
def _(i):
    # A yellow arrow turning back on itself to the left.
    # Its head points left along the top, its tail curves down the right side.
    i.add(arc(18.5, 17, 8, 100, -90, 5) | polyline([(19.5, 9), (11, 9)], 5, "flat")
          | arrowHead(2.5, 9, 180, 9.5, 13).round(0.8), A)



@icon("backup", 32)
def _(i):
    # A drive's tray, a blue arrow bending down into it.
    tray = rect(3, 18, 26, 11, 2.5)
    i.add(tray, TM)
    i.cut(union(*[rect(15 + 2.4 * k, 22.5, 1.2, 4, 0.6) for k in range(5)]))
    i.add(arcArrow(10, 15, 9, -165, 0, 4.4, 7, 11, soften=0.6), B, gap=1.2)



@icon("edit_clear", 16)
def _(i):
    # A broom, its handle from the top left and its yellow brush to the bottom right.
    i.add(polyline([(1.6, 1.6), (8.2, 8.2)], 1.7), TM)
    brush = poly((6.4, 9.4), (9.4, 6.4), (15.4, 10.4), (15.6, 15.6), (10.4, 15.4), r=0.6)
    i.add(brush, A, gap=0.7)
    i.cut(polyline([(9.4, 10.6), (12.2, 15.6)], 0.6) | polyline([(10.6, 9.4), (15.6, 12.2)], 0.6)
          | polyline([(10, 10), (14.2, 14.2)], 0.6))
    i.add(polyline([(5.8, 8.6), (8.6, 5.8)], 1.6), R, gap=0.6)



@icon("link", 22)
def _(i):
    # A blue arrow curving up and over to the right.
    i.add(arcArrow(12.5, 16, 8, 180, 330, 3, 5.4, 7.4, soften=0.5), B)


@icon("sort", 32)
def _(i):
    # Three bars stacked, the top one short, a blue arrow curling over their top right.
    i.add(rect(3, 4, 16, 5.5, 1.5) | rect(3, 13.25, 26, 5.5, 1.5) | rect(3, 22.5, 26, 5.5, 1.5), TM)
    i.add(arcArrow(25, 9.5, 4.6, 95, -160, 2.4, 4.2, 6), B, gap=1)



for _name, _direction in (("go-up", "up"), ("go-down", "down"), ("next", "right"), ("previous", "left")):
    ICONS[_name] = (22, lambda i, d=_direction: i.add(straightArrow(22, d, 1.2), G))


@icon("remove", 22)
def _(i):
    # A red octagon with a white cross.
    points = [(11 + 10 * math.cos(math.radians(22.5 + 45 * k)), 11 + 10 * math.sin(math.radians(22.5 + 45 * k)))
              for k in range(8)]
    i.add(poly(*points, r=1.4), R)
    i.add(polyline([(7.4, 7.4), (14.6, 14.6)], 2.6) | polyline([(14.6, 7.4), (7.4, 14.6)], 2.6), TB)


@icon("add", 22)
def _(i):
    i.add(rect(9, 3, 4, 16, 1) | rect(3, 9, 16, 4, 1), B)


@icon("list-remove", 22)
def _(i):
    i.add(rect(3, 9, 16, 4, 1), B)


@icon("tracked", 16)
def _(i):
    # A green push pin leaning right, its needle down to the bottom right.
    head = (rect(5.4, 0.8, 5.2, 2.2, 1.1) | poly((6.2, 2.6), (9.8, 2.6), (10.8, 7.6), (5.2, 7.6))
            | rect(3.2, 7.4, 9.6, 2, 1))
    needle = polyline([(8, 9), (8, 15.6)], 1.1)
    i.add(needle.rotate(-45, 8, 8).move(1, -1), TM)
    i.add(head.rotate(-45, 8, 8).move(-0.6, 0.6), G, gap=0.5)


@icon("locked", 16)
def _(i):
    # A grey padlock on a light tile.
    i.add(rect(0.8, 0.8, 14.4, 14.4, 2.2), T)
    shackle = arc(8, 6.6, 2.5, 180, 360, 1.5) | polyline([(5.5, 6.6), (5.5, 8)], 1.5, "flat") \
        | polyline([(10.5, 6.6), (10.5, 8)], 1.5, "flat")
    i.cut(shackle | rect(4.2, 7.6, 7.6, 5.6, 1))



# List flags -----------------------------------------------------------------------------------------------

@icon("information", 22)
def _(i):
    # A light bulb: a blue glass on a grey screw base.
    glass = circle(11, 8.5, 7) | poly((6.3, 12.5), (15.7, 12.5), (14, 16), (8, 16), r=0.8)
    i.add(glass, B)
    i.add(ellipse(8.4, 6.4, 1.6, 2).rotate(35, 8.4, 6.4), TB)
    i.add(rect(7.6, 16.6, 6.8, 1.6, 0.8) | rect(7.6, 18.6, 6.8, 1.6, 0.8) | rect(9.4, 20.4, 3.2, 1.2, 0.6), TM)


@icon("problem", 16)
def _(i):
    # A red tile with a white cross.
    i.add(rect(1, 1, 14, 14, 2.4), R)
    i.add(polyline([(5, 5), (11, 11)], 2.2) | polyline([(11, 5), (5, 11)], 2.2), TB)


@icon("emblem_backup", 16)
def _(i):
    # A blue floppy disk: a white label with a red line on top, the grey shutter below.
    disk = poly((1, 1), (13.4, 1), (15, 2.6), (15, 15), (1, 15), r=1)
    i.add(disk, B)
    label = rect(3.4, 1, 9.2, 6.4, 0.6)
    i.add(label, TB, gap=0.6)
    i.add(rect(3.4, 2.4, 9.2, 1.2), R)
    shutter = rect(4.4, 9.6, 7.2, 5.4, 0.6)
    i.add(shutter, TM, gap=0.6)
    i.cut(rect(8.6, 10.6, 1.6, 3.2, 0.4))


@icon("emblem_notes", 16)
def _(i):
    # A notepad with lines and a spiral binding, a yellow pencil across it.
    i.add(rect(2, 2.4, 11, 12.8, 1.2), T)
    i.cut(union(*[rect(4, y, 7, 1, 0.5) for y in (6, 8.6, 11.2)]))
    i.add(union(*[rect(3.6 + 2.4 * k, 0.8, 1.2, 3.2, 0.6) for k in range(4)]), TM, gap=0.5)
    pencil = polyline([(14.6, 3.2), (9, 8.8)], 2.4, "flat") | poly((9.85, 7.15), (7.3, 10.5), (10.65, 7.95))
    i.add(pencil, A, gap=0.8)


@icon("emblem_hidden_files", 16)
def _(i):
    # A page with a folded corner, dotted all over: files that are there but hidden.
    page = poly((2.5, 1), (10, 1), (13.5, 4.5), (13.5, 15), (2.5, 15), r=0.6)
    i.add(page, TM)
    i.cut(union(*[rect(4 + 2 * x + (y % 2), 6 + 2 * y, 1, 1) for x in range(4) for y in range(4)]))
    i.cut(poly((10, 1), (13.5, 4.5), (10, 4.5)).grow(0.5))
    i.add(poly((10, 1), (10, 4.5), (13.5, 4.5), r=0.3), T)


@icon("alternate_game", 16)
def _(i):
    # A green rook with an orange question mark at its right.
    rook = (poly((1.5, 1.5), (3.5, 1.5), (3.5, 3), (5, 3), (5, 1.5), (7, 1.5), (7, 3), (8.5, 3), (8.5, 1.5),
                 (10.5, 1.5), (10.5, 5), (9, 6.2), (9, 11.4), (10.5, 12.4), (10.5, 15), (1.5, 15), (1.5, 12.4),
                 (3, 11.4), (3, 6.2), (1.5, 5)))
    i.add(rook, G)
    i.add(question(13, 8, 9, 1.7), A, gap=0.8)


@icon("version_date", 16)
def _(i):
    # A calendar page showing 12, with two rings at the top.
    i.add(rect(1.2, 2.6, 13.6, 12.6, 1.6), T)
    i.cut(rect(1.2, 5.6, 13.6, 0.8) | text("12", 8, 10.9, 6.2))
    i.add(rect(3.8, 0.8, 1.6, 3.6, 0.8) | rect(10.6, 0.8, 1.6, 3.6, 0.8), TM, gap=0.6)


@icon("warning_16", 16)
def _(i):
    i.add(triangle(8, 1.2, 14.8, 7.6, 1.1), R)
    i.cut(bang(8, 5.2, 10.4, 1.9, 1.05))



@icon("unchecked-checkbox", 26)
def _(i):
    i.add(rect(3, 3, 20, 20, 3.6) - rect(5.2, 5.2, 15.6, 15.6, 1.8), T)


@icon("checked-checkbox", 26)
def _(i):
    i.add(rect(3, 3, 20, 20, 3.6) - rect(5.2, 5.2, 15.6, 15.6, 1.8), G)
    i.add(polyline([(8.4, 13.2), (11.6, 16.4), (17.8, 9.8)], 2.4), G)


@icon("indeterminate-checkbox", 26)
def _(i):
    i.add(rect(3, 3, 20, 20, 3.6) - rect(5.2, 5.2, 15.6, 15.6, 1.8), R)
    i.add(rect(8.5, 11.8, 9, 2.4, 1.2), R)


@icon("debug", 24)
def _(i):
    # A green cog with a magnifying glass over its lower right.
    cog = gear(10, 10, 9, 6.8, 8, hole=3.2)
    i.add(cog - cog.shrink(1.6), G)
    lens = circle(16, 16, 4.4)
    i.cut(lens.grow(1))
    i.add(lens - circle(16, 16, 2.6), G)
    i.add(polyline([(19.3, 19.3), (22.4, 22.4)], 2.4), G)


@icon("check", 16)
def _(i):
    i.add(polyline([(3, 8.6), (6.4, 12), (13, 4.6)], 2.4), TM)


@icon("run", 48)
def _(i):
    i.add(poly((13, 7), (41, 24), (13, 41), r=3), A)



# Content (white glyphs, on black tiles in the originals that this theme's dark rows stand in for) ----------

def tinker():
    w = wrench(4.5, 27.5, 23.5, 8.5, 3.6, 5.6)
    blade, grip = screwdriver(27.5, 27.5, 4.5, 4.5, 2, 5, 0.5)
    return [(w, T), (blade | grip, T)]


@icon("content/plugin", 32)
def _(i):
    i.add(jigsaw(7, 9, 16, ["top", "right"], ["left", "bottom"]).rotate(-12, 16, 17), T)


@icon("content/skyproc", 32)
def _(i):
    # A hand reaching in from the right under a branching antler.
    branch = (polyline([(3, 12), (29, 12)], 2) | polyline([(11, 12), (15, 5)], 1.8)
              | polyline([(21, 12), (25, 5.5)], 1.8) | polyline([(17, 12), (19, 8)], 1.6))
    i.add(branch, T)
    hand = (rect(14, 15, 15, 7.5, 3.6) | polyline([(15, 18.5), (6.5, 17.5)], 2.6)
            | polyline([(16, 21.5), (8.5, 23.5)], 2.2) | polyline([(17.5, 22.5), (12, 27)], 2.2)
            | polyline([(20, 22.5), (16.5, 28)], 2.2))
    i.add(hand, T, gap=1)


@icon("content/texture", 32)
def _(i):
    i.add(union(*[rect(3 + 3.25 * x, 3 + 3.25 * y, 3.25, 3.25) for x in range(8) for y in range(8)
                  if (x + y) % 2 == 0]), T)


@icon("content/music", 32)
def _(i):
    # Two notes joined by two beams.
    heads = ellipse(8.5, 24, 4, 3).rotate(-25, 8.5, 24) | ellipse(23.5, 20.5, 4, 3).rotate(-25, 23.5, 20.5)
    stems = rect(11.2, 7.6, 1.8, 16) | rect(26.2, 4, 1.8, 16)
    beams = poly((11.2, 7.6), (28, 4), (28, 7.4), (11.2, 11)) | poly((11.2, 12.6), (28, 9), (28, 11.4), (11.2, 15))
    i.add(heads | stems | beams, T)


@icon("content/sound", 32)
def _(i):
    # A lyre: two curved arms meeting below, scrolls at their tops, strings between them.
    frame = line("M7 6 C3 10 4 22 16 27 C28 22 29 10 25 6", 2.6)
    scrolls = arc(9, 6, 2.4, 180, 470, 1.8, "round") | arc(23, 6, 2.4, 70, 360, 1.8, "round")
    bar = rect(8, 9, 16, 2.2, 1.1)
    strings = union(*[rect(12 + 2.6 * k, 10, 1.2, 14.5) for k in range(4)])
    i.add(frame | scrolls | bar | strings, T)


@icon("content/interface", 32)
def _(i):
    # An open hand inside a ring.
    i.add(circle(16, 16, 14) - circle(16, 16, 11.6), T)
    palm = rect(12, 15, 10, 9, 4)
    fingers = union(*[polyline([(13.2 + 2.6 * k, 16), (12.4 + 3 * k, 8 + abs(k - 1.4) * 1.1)], 2.2)
                      for k in range(4)])
    thumb = polyline([(13, 20), (8.4, 15.6)], 2.4)
    i.add(palm | fingers | thumb, T)


@icon("content/skse", 32)
def _(i):
    # A tree of boxes: one on the left branching to three on the right.
    boxes = [rect(3, 13, 8, 6, 0.5)] + [rect(19, y, 10, 6, 0.5) for y in (4, 13, 22)]
    hollow = union(*[b - b.shrink(1.5) for b in boxes])
    links = polyline([(11, 16), (19, 16)], 1.6, "flat") | polyline([(15, 7), (15, 25)], 1.6, "flat") \
        | polyline([(15, 7), (19, 7)], 1.6, "flat") | polyline([(15, 25), (19, 25)], 1.6, "flat")
    i.add(hollow | links, T)


@icon("content/script", 32)
def _(i):
    w, sd = tinker()
    i.add(*w)
    i.add(sd[0], T, gap=1)


@icon("content/mesh", 32)
def _(i):
    # A breastplate between two banded shoulder guards, two banded tassets below.
    chest = fill("M9 8 C12 6 20 6 23 8 C25 12 24 18 16 23 C8 18 7 12 9 8 Z")
    i.add(chest, T)
    i.cut(rect(15.2, 6, 1.6, 18))
    for cx in (6, 26):
        guard = ellipse(cx, 6.5, 4.4, 3.4)
        i.add(guard, T, gap=0.8)
        i.cut(union(*[rect(cx - 5 + 2.6 * k, 3, 0.9, 7) for k in range(4)]).rotate(-15 if cx < 16 else 15, cx, 6.5))
    for cx, angle in ((10, 30), (22, -30)):
        tasset = rect(cx - 4, 22, 8, 7, 2).rotate(angle, cx, 25.5)
        i.add(tasset, T, gap=0.8)
        i.cut(union(*[rect(cx - 4, 23.6 + 2.2 * k, 8, 0.8) for k in range(2)]).rotate(angle, cx, 25.5))


@icon("content/string", 32)
def _(i):
    # Two speech bubbles, the larger at the top left, with lines of text.
    big = ellipse(13, 10, 11, 7.4) | poly((6, 15), (11, 16), (6.4, 21.5))
    small = ellipse(22.5, 22, 7.4, 5.4) | poly((25, 25.5), (29, 24.5), (29.4, 29.6))
    i.add(big, T)
    i.cut(rect(6, 7.4, 14, 1.6, 0.8) | rect(6, 11, 11, 1.6, 0.8))
    i.add(small, T, gap=1.2)
    i.cut(rect(17.5, 20.6, 10, 1.4, 0.7) | rect(17.5, 23.4, 7, 1.4, 0.7))


@icon("content/bsa", 32)
def _(i):
    # A chest with a domed lid, two straps and a lock plate.
    lid = fill("M3 13 C3 4 29 4 29 13 Z")
    box = rect(3, 14.2, 26, 14, 1.2)
    i.add(lid | box, T)
    i.cut(rect(3, 13, 26, 1.2) | rect(8, 6, 1.4, 22.2) | rect(22.6, 6, 1.4, 22.2))
    i.cut(rect(13, 11, 6, 8, 1) - rect(14.6, 12.6, 2.8, 4.8, 0.6))
    i.cut(rect(15.4, 13.4, 1.2, 2.6, 0.6))


@icon("content/menu", 32)
def _(i):
    # A settings page: three radio buttons, the middle one set, each with a row of dots.
    i.add(rect(3, 2.5, 26, 1.6) | rect(3, 27.9, 26, 1.6), T)
    for k, y in enumerate((9, 16, 23)):
        ring = circle(8, y, 3.2) - circle(8, y, 2)
        if k == 1:
            ring = ring | circle(8, y, 1.2)
        i.add(ring | union(*[rect(14 + 4.2 * d, y - 1, 2, 2) for d in range(3)]), T)


@icon("content/inifile", 32)
def _(i):
    # A scroll with lines written on it and a quill across them.
    sheet = rect(5, 4, 22, 23, 1)
    i.add(sheet, T)
    i.add(circle(5, 4.8, 2.6) | rect(4, 25, 25, 4.4, 2.2), T)
    i.cut(union(*[rect(8, 9.5 + 4 * k, 14, 1.2) for k in range(4)]))
    quill = fill("M26 5 C22 6 15 13 12.5 20 L13.8 20.5 C17 14 23 9 26 5 Z") | polyline([(12.6, 20.4), (10.4, 25)], 1.1)
    i.add(quill, T, gap=1)


@icon("content/modgroup", 32)
def _(i):
    # A cog inside a ring.
    i.add(circle(16, 16, 14.5) - circle(16, 16, 13), T)
    i.add(gear(16, 16, 11, 8.6, 9, top=0.5, bottom=0.6), T)


@icon("content/facegen", 32)
def _(i):
    # A face: hair falling around it, eyes and a mouth.
    hair = fill("M6 30 C3 22 4 6 13 3 C22 0 30 6 29 30 L25 30 C26 22 26 14 22 10 C18 13 12 13 9 11 "
                "C8 18 9 25 10 30 Z")
    i.add(hair, T)
    face = fill("M9.5 11.5 C12 13 18 13 21.5 10.5 C24 13 24.5 19 22 23.5 C20 27 14 27.5 12 24.5 "
                "C10 21 9.2 16 9.5 11.5 Z")
    i.add(face - (ellipse(13.4, 16.6, 1.6, 1.1) | ellipse(19.6, 16.6, 1.6, 1.1)
                  | rect(14.4, 22, 4, 1, 0.5)), T, gap=0.9)


@icon("content/material", 32)
def _(i):
    # The radiation sign: three blades around a dot, in a disc.
    disc = circle(16, 16, 14)
    blades = union(*[
        (circle(16, 16, 11) - circle(16, 16, 3.6)) & poly((16, 16), *[
            (16 + 20 * math.cos(math.radians(a)), 16 + 20 * math.sin(math.radians(a)))
            for a in (base - 30, base, base + 30)])
        for base in (-90, 30, 150)])
    i.add(disc - blades - circle(16, 16, 2.4), T)


@icon("content/media", 32)
def _(i):
    # A strip of film with a play button.
    strip = rect(3, 3, 26, 26, 1.5)
    holes = union(*[rect(5 + 4.6 * k, y, 2.6, 2.6, 0.4) for k in range(5) for y in (4.6, 24.8)])
    i.add(strip - holes - rect(3, 8.4, 26, 1.2) - rect(3, 22.4, 26, 1.2), T)
    i.cut(poly((12.5, 11), (21, 16), (12.5, 21), r=0.6))


@icon("content/geometries", 32)
def _(i):
    # A cube drawn as its outline and the three edges from its near corner.
    edges = [(16, 3), (28, 9.5), (28, 22.5), (16, 29), (4, 22.5), (4, 9.5)]
    hull = polyline(edges + [edges[0]], 2, "round", "round")
    inner = polyline([(4, 9.5), (16, 16), (28, 9.5)], 2) | polyline([(16, 16), (16, 29)], 2)
    i.add(hull | inner, T)


# Conflict and flag icons, written as SVG directly --------------------------------------------------

OUTLINE = "var(--bg-1)"
SHADE = "var(--bg-0)"


def rawSvg(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        + body
        + "</svg>\n"
    )


def rawLine(path: str, color: str, width: float, outline: bool, cap: str = "butt") -> str:
    result = ""
    if outline:
        result += (
            f'<path d="{path}" fill="none" stroke="{OUTLINE}" stroke-width="{width + 2}" '
            f'stroke-linecap="square" stroke-linejoin="miter"/>'
        )
    return result + (
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="{cap}"/>'
    )


# The originals' bolt: narrow and tall, with the arm sticking out to the left.
BOLT = "M7 0.3 H11.3 L10 4.2 H12.6 L5.3 15.7 L7.4 6.1 H3 Z"


def bolt(color: str) -> str:
    return f'<path d="{BOLT}" fill="{color}"/>'


# Chest, like the originals: a rounded box tipped toward the viewer, strapped down the front and across
# the middle, with a shine on the left. Drawn inset, the thick round stroke rounds its corners like the
# original's.
CHEST = "M3.6 1.4 L10.9 4.7 V10 L6.6 12.1 L1.4 9.8 V3.2 Z"


def chest(color: str) -> str:
    return (
        f'<path d="{CHEST}" fill="{color}" stroke="{color}" stroke-width="2.6" stroke-linejoin="round"/>'
        f'<path d="M0.3 5.6 Q6.6 9.2 12 5.6 M8.3 4.2 L6.6 13.2" fill="none" stroke="{SHADE}" '
        'stroke-opacity="0.4" stroke-width="1.1"/>'
        '<ellipse cx="3.8" cy="7" rx="1" ry="0.9" fill="var(--icon-mark)"/>'
    )


def plus(y: float, halfHeight: float, outline: bool) -> str:
    return rawLine(f"M12 {y - halfHeight} V{y + halfHeight} M8 {y} H16", "var(--icon-positive)", 2, outline)


def minus(y: float, outline: bool) -> str:
    return rawLine(f"M8 {y} H16", "var(--icon-negative)", 2, outline)


def boltPlus() -> str:
    return plus(12, 4, False)


def boltMinus() -> str:
    return minus(12, False)


def boltMixed() -> str:
    return plus(9, 3, False) + minus(14, False)


def chestPlus() -> str:
    return plus(12, 3.5, True)


def chestMinus() -> str:
    return minus(14, True)


def chestMixed() -> str:
    return plus(8.5, 3, True) + minus(14, True)


def burst() -> str:
    points = []
    for i in range(16):
        angle = math.pi * i / 8 - math.pi / 2
        radius = 8 if i % 2 == 0 else 5.4
        points.append(f"{8 + radius * math.cos(angle):.2f} {8 + radius * math.sin(angle):.2f}")
    return "M" + " L".join(points) + " Z"


RAW_ICONS = {
    # Loose files that conflict with other loose files.
    "emblem_conflict_overwrite": bolt("var(--icon)") + boltPlus(),
    "emblem_conflict_overwritten": bolt("var(--icon)") + boltMinus(),
    "emblem_conflict_mixed": bolt("var(--icon)") + boltMixed(),
    "emblem_conflict_redundant": bolt("var(--text-muted)"),
    # Loose files that conflict with archives.
    "archive_loose_conflict_overwrite": bolt("var(--icon-alt)") + boltPlus(),
    "archive_loose_conflict_overwritten": chest("var(--icon-negative)") + chestMinus(),
    # Archives that conflict with other archives, and a plugin that loads archives.
    "archive_conflict_winner": chest("var(--icon)") + chestPlus(),
    "archive_conflict_loser": chest("var(--icon)") + chestMinus(),
    "archive_conflict_mixed": chest("var(--icon)") + chestMixed(),
    "archive_conflict_neutral": chest("var(--icon)"),
    # A heart with a question mark hanging below it.
    "emblem_notendorsed": (
        '<path d="M7.8 13.3 C4.9 11 1.1 8.7 1.1 5.4 C1.1 3.4 2.6 2 4.5 2 C5.9 2 7.1 2.8 7.8 4 '
        'C8.5 2.8 9.7 2 11.2 2 C13.2 2 14.8 3.4 14.8 5.4 C14.8 8.7 10.8 11 7.8 13.3 Z" '
        'fill="var(--icon-negative)"/>'
        + rawLine("M7.4 6.5 C7.4 5 8.5 4.3 9.7 4.3 C11 4.3 12 5.1 12 6.4 C12 8 10.1 8.3 10.1 9.8 V11.2",
               "var(--icon-positive)", 1.8, True)
        + f'<rect x="8.6" y="12.6" width="3" height="3" fill="{OUTLINE}"/>'
        + '<rect x="9.2" y="13.2" width="1.8" height="1.8" fill="var(--icon-positive)"/>'
    ),
    # A clip whose outer wire wraps the bottom, inner wire loops over the top.
    "attachment": (
        '<path d="M3.5 4.4 V12.5 A4 3 0 0 0 11.5 12.5 V3.5 A3 3 0 0 0 5.5 3.5 V10.5 '
        'A2 2 0 0 0 9.5 10.5 V6.4" fill="none" stroke="var(--text)" stroke-width="1.3" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "awaiting": '<circle cx="8" cy="8" r="5" fill="var(--icon)"/>',
    # An eight-pointed burst with a down arrow, like the original.
    "update_available": (
        f'<path d="{burst()}" fill="var(--icon)"/>'
        '<path d="M7 4.8 H9 V8.2 H11 L8 11.4 L5 8.2 H7 Z" fill="var(--icon-mark)"/>'
    ),
}


# Badges on the notifications button --------------------------------------------------------------------------

for _n in list(range(1, 10)) + ["more"]:
    def _badge(i, n=_n):
        i.add(circle(16, 16, 14), A)
        mark = rect(14.2, 8.5, 3.6, 15, 1.4) | rect(8.5, 14.2, 15, 3.6, 1.4) if n == "more" else text(str(n), 16, 16, 15)
        # Drawn dark rather than cut out: the badge sits on the notifications icon.
        i.add(mark, SHADE_MARK)
    ICONS[f"badge_{_n}"] = (32, _badge)


def main():
    repo = Path(__file__).resolve().parent.parent
    names = sys.argv[1:] or [*RAW_ICONS, *ICONS]
    out = repo / "src" / "icons" / "mo2"
    for name in names:
        if name in RAW_ICONS:
            (out / f"{name}.svg").write_text(rawSvg(RAW_ICONS[name]), encoding="utf-8", newline="")
            continue
        size, build = ICONS[name]
        image = Icon(size, INTRINSIC.get(name, 128))
        build(image)
        target = out / f"{name}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(image.svg(), encoding="utf-8", newline="")
    print(f"wrote {len(names)} icons")


if __name__ == "__main__":
    main()
