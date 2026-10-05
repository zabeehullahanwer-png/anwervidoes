"""Pure-Python image generators (no PIL / numpy needed).

Everything here writes PGM (grayscale masks) or PAM (RGBA) files that ffmpeg
reads natively. Images are generated once per render and cached in the work dir.

Design rule: backgrounds are aniconic — geometric patterns, light and colour
only, no living beings — so they suit Islamic content for every audience.
"""

import math
import os
import random


def _clamp01(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def write_pgm(path, w, h, data):
    with open(path, "wb") as f:
        f.write(b"P5\n%d %d\n255\n" % (w, h))
        f.write(bytes(data))


def write_pam_rgba(path, w, h, data):
    with open(path, "wb") as f:
        f.write(b"P7\nWIDTH %d\nHEIGHT %d\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n" % (w, h))
        f.write(bytes(data))


def hex_rgb(hx):
    hx = hx.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)


# ---------------------------------------------------------------------------
# Islamic geometric lattice (8-point star / Rub el Hizb grid)
# ---------------------------------------------------------------------------

def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx - px, ay + t * dy - py
    return math.sqrt(qx * qx + qy * qy)


def islamic_tile(T, line_w=2.2, variant="star8"):
    """Return a T*T grayscale tile (bytearray) that repeats seamlessly."""
    c = T / 2.0
    a = 0.22 * T            # half-size of the axis-aligned square
    b = a * math.sqrt(2)    # vertex distance of the rotated square
    segs = []
    # square A (axis aligned)
    A = [(c - a, c - a), (c + a, c - a), (c + a, c + a), (c - a, c + a)]
    # square B (rotated 45 degrees)
    B = [(c, c - b), (c + b, c), (c, c + b), (c - b, c)]
    for poly in (A, B):
        for i in range(4):
            segs.append((*poly[i], *poly[(i + 1) % 4]))
    # connectors to neighbouring stars (edges) and to tile corners
    segs += [(c + b, c, T, c), (c - b, c, 0, c), (c, c + b, c, T), (c, c - b, c, 0)]
    segs += [(c + a, c + a, T, T), (c - a, c - a, 0, 0), (c + a, c - a, T, 0), (c - a, c + a, 0, T)]
    if variant == "star8":
        # small diamond around each tile corner -> secondary stars where 4 tiles meet
        d = 0.12 * T
        for (x0, y0) in ((0, 0), (T, 0), (0, T), (T, T)):
            pts = [(x0, y0 - d), (x0 + d, y0), (x0, y0 + d), (x0 - d, y0)]
            for i in range(4):
                segs.append((*pts[i], *pts[(i + 1) % 4]))
    circle_r = 0.085 * T
    half = line_w / 2.0
    out = bytearray(T * T)
    for y in range(T):
        py = y + 0.5
        for x in range(T):
            px = x + 0.5
            d = min(_seg_dist(px, py, *s) for s in segs)
            d = min(d, abs(math.hypot(px - c, py - c) - circle_r))
            v = _clamp01(1.0 - (d - half))
            out[y * T + x] = int(v * 255)
    return out


def tiled_mask(tile, T, W, H):
    """Repeat a T*T tile over W*H (W, H may be any size)."""
    rows = []
    for y in range(H):
        src = tile[(y % T) * T:(y % T + 1) * T]
        reps = W // T + 1
        rows.append((bytes(src) * reps)[:W])
    return b"".join(rows)


def particle_field(W, H, n=40, seed=7, rmin=1.5, rmax=5.0):
    """Soft glowing dots on a W x 2H canvas whose two halves are identical,
    so cropping with y = mod(t*speed, H) scrolls seamlessly."""
    rnd = random.Random(seed)
    buf = bytearray(W * H)
    for _ in range(n):
        cx, cy = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.uniform(rmin, rmax)
        peak = rnd.uniform(0.35, 1.0)
        R = int(r * 3) + 1
        for yy in range(int(cy) - R, int(cy) + R + 1):
            wy = yy % H
            for xx in range(max(0, int(cx) - R), min(W, int(cx) + R + 1)):
                dd = ((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)
                v = peak * math.exp(-dd)
                if v > 0.01:
                    i = wy * W + xx
                    buf[i] = min(255, buf[i] + int(v * 255))
    return bytes(buf) + bytes(buf)


# ---------------------------------------------------------------------------
# Rounded speaker card: alpha mask + plate (shadow + gold border)
# ---------------------------------------------------------------------------

def _rrect_sdf(px, py, hw, hh, r):
    qx = abs(px) - (hw - r)
    qy = abs(py) - (hh - r)
    ox, oy = max(qx, 0.0), max(qy, 0.0)
    return math.hypot(ox, oy) + min(max(qx, qy), 0.0) - r


def rounded_mask(w, h, r):
    """Grayscale alpha mask (w*h) with anti-aliased rounded corners."""
    hw, hh = w / 2.0, h / 2.0
    out = bytearray(b"\xff" * (w * h))
    for y in range(h):
        py = y + 0.5 - hh
        if abs(py) < hh - r - 1:
            continue  # straight section: fully opaque
        for x in list(range(0, int(r) + 2)) + list(range(w - int(r) - 2, w)):
            if 0 <= x < w:
                d = _rrect_sdf(x + 0.5 - hw, py, hw, hh, r)
                out[y * w + x] = int(_clamp01(0.5 - d) * 255)
    return out


def card_plate(cw, ch, r, pad, border_px, border_hex, shadow_alpha=0.55, shadow_blur=26, shadow_dy=14):
    """RGBA plate drawn *behind* the speaker card: soft shadow + gold border ring.
    Size (cw+2*pad) x (ch+2*pad); the card sits at offset (pad, pad)."""
    W, H = cw + 2 * pad, ch + 2 * pad
    br, bg, bb = hex_rgb(border_hex)
    hw, hh = cw / 2.0, ch / 2.0
    cx, cy = W / 2.0, H / 2.0
    out = bytearray(W * H * 4)
    row_cache = {}
    for y in range(H):
        py = y + 0.5 - cy
        psy = py - shadow_dy
        # rows inside the straight band are identical -> cache them
        key = None
        if abs(py) < hh - r - border_px - 2 and abs(psy) < hh - r - shadow_blur - 2:
            key = "mid"
            if key in row_cache:
                out[y * W * 4:(y + 1) * W * 4] = row_cache[key]
                continue
        row = bytearray(W * 4)
        for x in range(W):
            px = x + 0.5 - cx
            # shadow
            ds = _rrect_sdf(px, psy, hw, hh, r)
            sa = shadow_alpha * _clamp01(0.5 - ds / shadow_blur) if ds > -shadow_blur else shadow_alpha
            # border ring (outside card edge up to border_px)
            d = _rrect_sdf(px, py, hw + border_px, hh + border_px, r + border_px)
            ba = _clamp01(0.5 - d)
            a = ba + sa * (1 - ba)
            if a <= 0:
                continue
            rr = (br * ba) / a
            gg = (bg * ba) / a
            bbv = (bb * ba) / a
            i = x * 4
            row[i] = int(rr)
            row[i + 1] = int(gg)
            row[i + 2] = int(bbv)
            row[i + 3] = int(a * 255)
        if key:
            row_cache[key] = bytes(row)
        out[y * W * 4:(y + 1) * W * 4] = row
    return W, H, out


def ensure_background_assets(work, W, H, style, tile_px=None):
    """Create (or reuse) pattern + particle masks for a style. Returns paths."""
    bgcfg = style["background"]
    T = tile_px or int(round(W / 4.5))
    T -= T % 2
    pat_path = os.path.join(work, f"pattern_{W}x{H}_{T}.pgm")
    if not os.path.exists(pat_path):
        tile = islamic_tile(T, line_w=max(1.6, W / 600.0))
        PW, PH = W + T, H + T
        write_pgm(pat_path, PW, PH, tiled_mask(tile, T, PW, PH))
    n = int(bgcfg.get("particles", 36))
    par_path = os.path.join(work, f"particles_{W}x{H}_{n}.pgm")
    if not os.path.exists(par_path):
        write_pgm(par_path, W, 2 * H, particle_field(W, H, n=n, rmax=max(3.0, W / 260.0)))
    return pat_path, T, par_path


# ---------------------------------------------------------------------------
# Extra background layers: rosette, light rays, masjid skyline
# (all aniconic: geometry, light, architecture)
# ---------------------------------------------------------------------------

class _Canvas:
    """Grayscale canvas with an anti-aliased stroke stamp (fast enough in pure Python)."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.buf = bytearray(w * h)

    def dot(self, x, y, r):
        x0, x1 = max(0, int(x - r - 1)), min(self.w - 1, int(x + r + 1))
        y0, y1 = max(0, int(y - r - 1)), min(self.h - 1, int(y + r + 1))
        for yy in range(y0, y1 + 1):
            row = yy * self.w
            dy = (yy + 0.5 - y) ** 2
            for xx in range(x0, x1 + 1):
                d = math.sqrt((xx + 0.5 - x) ** 2 + dy)
                v = int(_clamp01(r + 0.5 - d) * 255)
                if v > self.buf[row + xx]:
                    self.buf[row + xx] = v

    def line(self, ax, ay, bx, by, r):
        L = math.hypot(bx - ax, by - ay)
        n = max(1, int(L / max(0.6, r * 0.7)))
        for i in range(n + 1):
            t = i / n
            self.dot(ax + (bx - ax) * t, ay + (by - ay) * t, r)

    def circle(self, cx, cy, rad, r):
        n = max(12, int(2 * math.pi * rad / max(0.6, r * 0.7)))
        for i in range(n):
            a = 2 * math.pi * i / n
            self.dot(cx + rad * math.cos(a), cy + rad * math.sin(a), r)

    def poly(self, pts, r):
        for i in range(len(pts)):
            self.line(*pts[i], *pts[(i + 1) % len(pts)], r)


def rosette(S, stroke=None):
    """Large 16-fold Islamic rosette (star polygons + rings) as an S*S mask."""
    c = _Canvas(S, S)
    cx = cy = S / 2.0
    r = stroke or max(1.0, S / 520.0)
    R = S * 0.47
    for k, rr in enumerate((R, R * 0.78, R * 0.42, R * 0.16)):
        c.circle(cx, cy, rr, r * (1.3 if k == 0 else 1.0))
    # {16/5} and {8/3} star polygons
    def star(n, step, rad, rot=0.0):
        pts = [(cx + rad * math.cos(rot + 2 * math.pi * i / n), cy + rad * math.sin(rot + 2 * math.pi * i / n))
               for i in range(n)]
        for i in range(n):
            c.line(*pts[i], *pts[(i + step) % n], r)
    star(16, 5, R * 0.78)
    star(8, 3, R * 0.42, math.pi / 8)
    star(8, 3, R * 0.42)
    # petals between the outer rings
    for i in range(32):
        a = 2 * math.pi * i / 32
        a2 = 2 * math.pi * (i + 0.5) / 32
        c.line(cx + R * 0.78 * math.cos(a), cy + R * 0.78 * math.sin(a),
               cx + R * math.cos(a2), cy + R * math.sin(a2), r * 0.8)
        c.line(cx + R * 0.78 * math.cos(a + 2 * math.pi / 32), cy + R * 0.78 * math.sin(a + 2 * math.pi / 32),
               cx + R * math.cos(a2), cy + R * math.sin(a2), r * 0.8)
    return c.buf


def light_rays(w, h, n=7, seed=3):
    """Soft god-rays falling from above (small; scale up in ffmpeg)."""
    rnd = random.Random(seed)
    sx, sy = w * 0.5, -h * 0.25
    rays = [(rnd.uniform(-0.55, 0.55), rnd.uniform(0.02, 0.06), rnd.uniform(0.4, 1.0)) for _ in range(n)]
    out = bytearray(w * h)
    for y in range(h):
        fade = max(0.0, 1.0 - y / (h * 0.85)) ** 1.4
        for x in range(w):
            ang = math.atan2(x - sx, y - sy)
            v = 0.0
            for a0, wd, st in rays:
                d = (ang - a0) / wd
                v += st * math.exp(-d * d)
            out[y * w + x] = int(min(1.0, v) * fade * 255)
    return out


def skyline(w, h, seed=5):
    """Masjid silhouette (domes + minarets) as a w*h mask, ground at the bottom."""
    rnd = random.Random(seed)
    top = [h] * w  # first filled row per column

    def fill(x0, x1, ytop_fn):
        for x in range(max(0, int(x0)), min(w, int(x1) + 1)):
            yt = ytop_fn(x)
            if yt is not None and yt < top[x]:
                top[x] = max(0, int(yt))

    base = h * 0.78
    fill(0, w, lambda x: base)
    # central great dome + side domes
    for cxf, rf, drum in ((0.5, 0.17, 0.10), (0.27, 0.09, 0.05), (0.73, 0.09, 0.05), (0.1, 0.06, 0.03),
                          (0.9, 0.06, 0.03)):
        cx, r = w * cxf, w * rf
        db = base - h * drum
        fill(cx - r * 1.05, cx + r * 1.05, lambda x, cx=cx, db=db: db)
        def dome(x, cx=cx, r=r, db=db):
            u = (x - cx) / r
            if abs(u) > 1:
                return None
            return db - r * 0.95 * math.sqrt(1 - u * u) * (1 + 0.25 * (1 - abs(u)) ** 3)
        fill(cx - r, cx + r, dome)
        # finial
        fill(cx - 1.5, cx + 1.5, lambda x, cx=cx, r=r, db=db: db - r * 1.25 - h * 0.05)
    # minarets
    for mf in (0.17, 0.38, 0.62, 0.83):
        mx, mw = w * mf, max(3, w * 0.012)
        mt = h * rnd.uniform(0.08, 0.16)
        fill(mx - mw, mx + mw, lambda x, mt=mt: mt + h * 0.04)
        fill(mx - mw * 1.7, mx + mw * 1.7, lambda x, mt=mt: mt + h * 0.16)  # balcony
        def spire(x, mx=mx, mw=mw, mt=mt):
            u = abs(x - mx) / mw
            return mt + u * h * 0.04 if u <= 1 else None
        fill(mx - mw, mx + mw, spire)
    out = bytearray(w * h)
    for x in range(w):
        for y in range(top[x], h):
            out[y * w + x] = 255
    # soft top edge (1px AA)
    for x in range(1, w - 1):
        y = top[x] - 1
        if 0 <= y < h:
            out[y * w + x] = max(out[y * w + x], 110)
    return out


def ensure_layer_assets(work, W, H):
    paths = {}
    S = even_int(W * 0.98)
    p = os.path.join(work, f"rosette_{S}.pgm")
    if not os.path.exists(p):
        write_pgm(p, S, S, rosette(S))
    paths["rosette"] = (p, S)
    rw, rh = W // 4, H // 4
    p = os.path.join(work, f"rays_{rw}x{rh}.pgm")
    if not os.path.exists(p):
        write_pgm(p, rw, rh, light_rays(rw, rh))
    paths["rays"] = (p, rw, rh)
    sw, sh = W + W // 5, even_int(H * 0.28)
    p = os.path.join(work, f"skyline_{sw}x{sh}.pgm")
    if not os.path.exists(p):
        write_pgm(p, sw, sh, skyline(sw, sh))
    paths["skyline"] = (p, sw, sh)
    return paths


def even_int(x):
    x = int(round(x))
    return x - (x % 2)
