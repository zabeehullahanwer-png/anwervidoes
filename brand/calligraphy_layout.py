"""Teardrop calligraphy composition of the name (2D contours, shared by preview + 3D render).

Each element is a list of closed contours in a common coordinate space (units ~ metres in
the 3D scene). Elements are kept separate so overlapping words stay solid when extruded.
"""
import math

import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AMIRI = os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "assets", "fonts", "Amiri-Bold.ttf")


class FlatPen(BasePen):
    def __init__(self, gs, dx, dy, steps=12):
        super().__init__(gs)
        self.dx, self.dy, self.steps = dx, dy, steps
        self.contours, self.cur = [], []

    def _p(self, pt):
        return (pt[0] + self.dx, pt[1] + self.dy)

    def _moveTo(self, pt):
        self.cur = [self._p(pt)]

    def _lineTo(self, pt):
        self.cur.append(self._p(pt))

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        a, b, c = self._p(p1), self._p(p2), self._p(p3)
        for i in range(1, self.steps + 1):
            t = i / self.steps
            m = 1 - t
            self.cur.append((m ** 3 * p0[0] + 3 * m * m * t * a[0] + 3 * m * t * t * b[0] + t ** 3 * c[0],
                             m ** 3 * p0[1] + 3 * m * m * t * a[1] + 3 * m * t * t * b[1] + t ** 3 * c[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        a, b = self._p(p1), self._p(p2)
        for i in range(1, self.steps + 1):
            t = i / self.steps
            m = 1 - t
            self.cur.append((m * m * p0[0] + 2 * m * t * a[0] + t * t * b[0],
                             m * m * p0[1] + 2 * m * t * a[1] + t * t * b[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def shaped(text, font=AMIRI, tracking=0):
    f = hb.Font(hb.Face(hb.Blob.from_file_path(font)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(f, buf, {})
    tt = TTFont(font)
    gs, order, upem = tt.getGlyphSet(), tt.getGlyphOrder(), tt["head"].unitsPerEm
    x, out = 0, []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = FlatPen(gs, x + pos.x_offset, pos.y_offset)
        gs[order[info.codepoint]].draw(pen)
        out += pen.contours
        x += pos.x_advance + tracking
    return [[(px / upem, py / upem) for px, py in c] for c in out]


def place(contours, width=None, height=None, cx=0.0, cy=0.0, sx=1.0):
    xs = [p[0] for c in contours for p in c]
    ys = [p[1] for c in contours for p in c]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    s = width / w if width else height / h
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [[((x - mx) * s * sx + cx, (y - my) * s + cy) for x, y in c] for c in contours]


def swoosh(p0, p1, p2, p3, w0, w1, n=120):
    """tapered calligraphic stroke along a cubic bezier: width w0 at start -> w1 at end"""
    def bez(t):
        m = 1 - t
        return (m ** 3 * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t ** 3 * p3[0],
                m ** 3 * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t ** 3 * p3[1])
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        a, b = bez(max(0, t - 1e-3)), bez(min(1, t + 1e-3))
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        # smooth taper (ease) with a soft rounded start
        w = w0 + (w1 - w0) * (t ** 0.8)
        w *= min(1.0, 0.35 + 3 * t) if t < 0.2 else 1.0
        x, y = bez(t)
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    return [left + right[::-1]]


def diamond(cx, cy, r):
    return [[(cx, cy + r), (cx + r * 0.7, cy), (cx, cy - r), (cx - r * 0.7, cy)]]


def composition():
    """returns {name: contours}. Teardrop ~2.4 wide, tip at y≈+2.05, base at y≈-1.55"""
    el = {}
    el["ذبيح"] = place(shaped("ذبيح"), width=1.20, cx=0.42, cy=0.42)
    el["الله"] = place(shaped("الله"), width=0.95, cx=-0.52, cy=0.66)
    el["لغاري"] = place(shaped("لغاري"), width=2.35, cx=-0.10, cy=-0.74)
    # big outer swoosh: rises from the base on the right and closes into the teardrop tip
    el["swoosh_r"] = swoosh((0.62, -1.55), (1.80, -1.20), (1.62, 1.10), (0.0, 2.02), 0.022, 0.135)
    # thin echo on the left, from the tip down towards the base
    el["swoosh_l"] = swoosh((0.0, 1.92), (-0.85, 1.45), (-1.42, 0.60), (-1.45, -0.30), 0.05, 0.012)
    el["dot_tip"] = diamond(0.0, 2.17, 0.07)
    return el


def to_svg(el, path, scale=230, w=1100, h=1100, ox=550, oy=560):
    parts = []
    for name, cs in el.items():
        d = ""
        for c in cs:
            d += "M" + " L".join(f"{x * scale + ox:.1f},{oy - y * scale:.1f}" for x, y in c) + " Z "
        parts.append(f'<path d="{d}" fill="#E2B867" fill-rule="nonzero" opacity="0.92"/>')
    with open(path, "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="#151515"/>'
                + "".join(parts) + "</svg>")


if __name__ == "__main__":
    import subprocess
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/callig.svg"
    to_svg(composition(), out)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", out, "-frames:v", "1", out.replace(".svg", ".png")])
