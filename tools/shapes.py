"""Flat icon geometry on Qt's painter paths: unions, cuts and outlines, written out as SVG paths."""

import math
import re
import sys

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QGuiApplication, QPainterPath, QPainterPathStroker, QPolygonF, QTransform

app = QGuiApplication.instance() or QGuiApplication(sys.argv)

# Qt flattens curves for its boolean operations, finely enough only when the shapes are large.
SCALE = 64
UP, DOWN = QTransform.fromScale(SCALE, SCALE), QTransform.fromScale(1 / SCALE, 1 / SCALE)


class Shape:
    def __init__(self, path: QPainterPath = None):
        self.path = path if path is not None else QPainterPath()

    def _op(self, other, name):
        a, b = UP.map(self.path), UP.map(other.path)
        return Shape(DOWN.map(getattr(a, name)(b)))

    def __or__(self, other):
        return self._op(other, "united")

    def __sub__(self, other):
        return self._op(other, "subtracted")

    def __and__(self, other):
        return self._op(other, "intersected")

    def grow(self, amount):
        return self | outline(self, 2 * amount)

    def shrink(self, amount):
        return self - outline(self, 2 * amount)

    def round(self, radius):
        """Rounds every corner, keeping the outline where it is straight."""
        return self.shrink(radius).grow(radius)

    def transformed(self, transform: QTransform):
        return Shape(transform.map(self.path))

    def move(self, dx, dy):
        return self.transformed(QTransform.fromTranslate(dx, dy))

    def rotate(self, degrees, cx, cy):
        t = QTransform()
        t.translate(cx, cy)
        t.rotate(degrees)
        t.translate(-cx, -cy)
        return self.transformed(t)

    def scale(self, sx, sy=None, cx=0, cy=0):
        t = QTransform()
        t.translate(cx, cy)
        t.scale(sx, sx if sy is None else sy)
        t.translate(-cx, -cy)
        return self.transformed(t)

    def mirror(self, cx):
        return self.scale(-1, 1, cx, 0)

    def flip(self, cy):
        return self.scale(1, -1, 0, cy)


def union(*shapes):
    result = Shape()
    for shape in shapes:
        result = result | shape
    return result


def outline(shape: Shape, width, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin):
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(cap)
    stroker.setJoinStyle(join)
    stroker.setMiterLimit(8)
    return Shape(stroker.createStroke(shape.path)) | Shape()


def rect(x, y, w, h, r=0):
    path = QPainterPath()
    if r:
        path.addRoundedRect(QRectF(x, y, w, h), r, r)
    else:
        path.addRect(QRectF(x, y, w, h))
    return Shape(path)


def circle(cx, cy, r):
    return ellipse(cx, cy, r, r)


def ellipse(cx, cy, rx, ry):
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), rx, ry)
    return Shape(path)


def poly(*points, r=0):
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
    path.closeSubpath()
    shape = Shape(path)
    return shape.round(r) if r else shape


CAPS = {"round": Qt.PenCapStyle.RoundCap, "flat": Qt.PenCapStyle.FlatCap, "square": Qt.PenCapStyle.SquareCap}
JOINS = {"round": Qt.PenJoinStyle.RoundJoin, "miter": Qt.PenJoinStyle.MiterJoin, "bevel": Qt.PenJoinStyle.BevelJoin}


def parse(d: str) -> QPainterPath:
    """An SVG path's M, L, H, V, C, Q and Z commands, absolute or relative."""
    path = QPainterPath()
    tokens = re.findall(r"[MLHVCQZmlhvcqz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    i, cmd, x, y, sx, sy = 0, None, 0.0, 0.0, 0.0, 0.0

    def num():
        nonlocal i
        i += 1
        return float(tokens[i - 1])

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                path.closeSubpath()
                x, y = sx, sy
                continue
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (x, y) if rel else (0, 0)
        if c == "M":
            x, y = ox + num(), oy + num()
            path.moveTo(x, y)
            sx, sy = x, y
            cmd = "l" if rel else "L"
        elif c == "L":
            x, y = ox + num(), oy + num()
            path.lineTo(x, y)
        elif c == "H":
            x = (x if rel else 0) + num()
            path.lineTo(x, y)
        elif c == "V":
            y = (y if rel else 0) + num()
            path.lineTo(x, y)
        elif c == "C":
            a = (ox + num(), oy + num())
            b = (ox + num(), oy + num())
            x, y = ox + num(), oy + num()
            path.cubicTo(*a, *b, x, y)
        elif c == "Q":
            a = (ox + num(), oy + num())
            x, y = ox + num(), oy + num()
            path.quadTo(*a, x, y)
    return path


def fill(d: str):
    """A closed SVG path as a filled shape."""
    path = parse(d)
    path.setFillRule(Qt.FillRule.WindingFill)
    return Shape(path) | Shape()


def line(d: str, width, cap="round", join="round"):
    """An SVG path drawn with a pen of the width, as a filled shape."""
    return outline(Shape(parse(d)), width, CAPS[cap], JOINS[join])


def polyline(points, width, cap="round", join="round"):
    return line("M" + " L".join(f"{x} {y}" for x, y in points), width, cap, join)


def arcPoints(cx, cy, r, start, end, steps=None):
    """Points along a circle, angles in degrees clockwise from the right, as on screen."""
    steps = steps or max(8, int(abs(end - start) / 4))
    return [
        (cx + r * math.cos(math.radians(start + (end - start) * k / steps)),
         cy + r * math.sin(math.radians(start + (end - start) * k / steps)))
        for k in range(steps + 1)
    ]


def arc(cx, cy, r, start, end, width, cap="flat"):
    return polyline(arcPoints(cx, cy, r, start, end), width, cap)


def arrowHead(tipX, tipY, angle, length, width):
    """A triangle pointing at the angle (degrees, clockwise from the right) with its tip on the point."""
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    bx, by = tipX - dx * length, tipY - dy * length
    return poly((tipX, tipY), (bx - dy * width / 2, by + dx * width / 2), (bx + dy * width / 2, by - dx * width / 2))


def arcArrow(cx, cy, r, start, end, width, headLength, headWidth, soften=0):
    """A band along a circle from start to end, ending in an arrow head along the circle."""
    direction = 1 if end > start else -1
    # The head's length along the circle, as an angle.
    headAngle = math.degrees(headLength / r) * direction
    band = arc(cx, cy, r, start, end - headAngle * 0.6, width)
    tipAngle = end
    tx, ty = cx + r * math.cos(math.radians(tipAngle)), cy + r * math.sin(math.radians(tipAngle))
    # Points the head along the chord from its base to its tip, so it sits on the circle.
    baseAngle = end - headAngle
    bx, by = cx + r * math.cos(math.radians(baseAngle)), cy + r * math.sin(math.radians(baseAngle))
    chord = math.degrees(math.atan2(ty - by, tx - bx))
    head = arrowHead(tx, ty, chord, headLength, headWidth)
    if soften:
        head = head.round(soften)
    return band | head


def text(s, cx, cy, size, bold=True, family="Segoe UI"):
    """Text as outlines, centered on the point by its ink."""
    font = QFont(family)
    font.setPixelSize(100)
    font.setBold(bold)
    path = QPainterPath()
    path.addText(0, 0, font, s)
    box = path.boundingRect()
    scale = size / box.height()
    t = QTransform()
    t.translate(cx, cy)
    t.scale(scale, scale)
    t.translate(-box.center().x(), -box.center().y())
    return Shape(t.map(path)) | Shape()


def gear(cx, cy, outer, inner, teeth, top=0.45, bottom=0.65, rotation=0, hole=0):
    """A cog: teeth as trapezoids, the share of each tooth's pitch at its top and its root."""
    points = []
    pitch = 360 / teeth
    for k in range(teeth):
        a = rotation + k * pitch
        for angle, radius in (
            (a - pitch * bottom / 2, inner),
            (a - pitch * top / 2, outer),
            (a + pitch * top / 2, outer),
            (a + pitch * bottom / 2, inner),
        ):
            points.append((cx + radius * math.cos(math.radians(angle)), cy + radius * math.sin(math.radians(angle))))
    shape = poly(*points) | circle(cx, cy, inner)
    if hole:
        shape = shape - circle(cx, cy, hole)
    return shape


# In viewBox units, how far a simplified outline may stray from the flattened one.
TOLERANCE = 0.012


def simplify(points):
    """Drops the points of a polyline that lie within the tolerance of the line through their neighbors."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (ax, ay), (bx, by) = points[first], points[last]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1e-9
        worst, index = 0.0, None
        for k in range(first + 1, last):
            px, py = points[k]
            distance = abs(dy * (px - ax) - dx * (py - ay)) / length if (dx or dy) else math.hypot(px - ax, py - ay)
            if distance > worst:
                worst, index = distance, k
        if index is not None and worst > TOLERANCE:
            keep[index] = True
            stack += [(first, index), (index, last)]
    return [point for point, kept in zip(points, keep) if kept]


def svgPath(shape: Shape) -> str:
    path = shape.path

    def fmt(v):
        text = f"{v:.2f}".rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text

    # Subpaths as runs: straight runs of points get simplified, curves are kept as they are.
    out = []
    run = []

    def flush():
        if run:
            points = simplify(run)
            out.extend(f"L{fmt(x)} {fmt(y)}" for x, y in points[1:])
            run.clear()

    i = 0
    count = path.elementCount()
    while i < count:
        e = path.elementAt(i)
        if e.type == QPainterPath.ElementType.MoveToElement:
            flush()
            out.append(f"M{fmt(e.x)} {fmt(e.y)}")
            run.append((e.x, e.y))
            i += 1
        elif e.type == QPainterPath.ElementType.LineToElement:
            run.append((e.x, e.y))
            i += 1
        else:
            flush()
            a, b = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{fmt(e.x)} {fmt(e.y)} {fmt(a.x)} {fmt(a.y)} {fmt(b.x)} {fmt(b.y)}")
            run.append((b.x, b.y))
            i += 3
    flush()
    return "".join(out) + "Z" if out else ""


class Icon:
    """Layers of flat shapes, bottom first. A layer added with a gap cuts that much room around itself
    out of the layers under it."""

    def __init__(self, size, intrinsic=128):
        self.size = size
        self.intrinsic = intrinsic
        self.layers = []

    def add(self, shape: Shape, color: str, gap=0):
        if gap:
            cut = shape.grow(gap)
            self.layers = [(below - cut, c) for below, c in self.layers]
        self.layers.append((shape, color))
        return self

    def cut(self, shape: Shape):
        """Cuts the shape out of every layer so far, letting the background through."""
        self.layers = [(below - shape, c) for below, c in self.layers]
        return self

    def svg(self) -> str:
        body = "".join(
            f'<path d="{svgPath(shape)}" fill="{color}"'
            + (' fill-rule="evenodd"' if shape.path.fillRule() == Qt.FillRule.OddEvenFill else "")
            + "/>"
            for shape, color in self.layers
            if not shape.path.isEmpty()
        )
        # The large size is what Qt reads an icon at when a stylesheet sets it, and scales down from.
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.intrinsic}" height="{self.intrinsic}" '
            f'viewBox="0 0 {self.size} {self.size}">{body}</svg>\n'
        )
