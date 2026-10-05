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
