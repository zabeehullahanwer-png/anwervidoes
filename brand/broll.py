"""Aniconic motion visuals for cutaways (no people): each returns an RGBA 1080x1920 frame for time t.

  sunrise   dawn over dunes, the sun rising with rays          (صبح)
  ecg       a glowing heartbeat line drawing across the screen (صحت)
  wheat     golden wheat stalks swaying in evening light       (روزی)
  globe     a slowly turning gold wire globe                   (پوری دنیا)
  race      arrows racing upward, motion streaks               (مقابلے کی دوڑ)
  clock     clock hands spinning (forward = future, back = past)
  hourglass sand falling in an hourglass                       (لمحۂ موجود)
  light     soft light through arches with drifting particles  (جنت / سکون)
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
GOLD = (222, 190, 128)
DEEP = (7, 20, 38)
_c = {}


def _grad(top, bot, h=H, w=W):
    y = np.linspace(0, 1, h)[:, None, None]
    return (np.array(top, np.float32) * (1 - y) + np.array(bot, np.float32) * y) * np.ones((1, w, 1), np.float32)


def _img(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


def _grain(im, t, amt=5):
    rng = np.random.default_rng(int(t * 30))
    n = rng.normal(0, amt, (H // 2, W // 2, 1)).repeat(2, 0).repeat(2, 1)
    a = np.asarray(im).astype(np.float32)
    a[..., :3] += n
    return _img(a[..., :3])


def sunrise(t, dur):
    k = t / max(dur, 0.1)
    sky = _grad((18, 30, 62), (226, 128, 70))
    sky = sky * (0.75 + 0.35 * k)
    sun_y = 1250 - 260 * k
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - 540) ** 2 + (yy - sun_y) ** 2)
    glow = np.clip(1 - d / 900, 0, 1) ** 2.2 * 140
    sky += glow[..., None] * np.array([1.0, 0.75, 0.45])
    ang = np.arctan2(yy - sun_y, xx - 540)
    rays = (0.5 + 0.5 * np.cos(ang * 18 + t * 0.4)) ** 8 * np.clip(1 - d / 1400, 0, 1) * 40 * (yy < sun_y)
    sky += rays[..., None] * np.array([1.0, 0.85, 0.6])
    disc = np.clip((120 - d) / 3, 0, 1)
    sky = sky * (1 - disc[..., None]) + np.array([255, 236, 190]) * disc[..., None]
    im = _img(sky)
    dr = ImageDraw.Draw(im)
    for i, (base, amp, col) in enumerate([(1330, 60, (60, 34, 30)), (1450, 80, (38, 22, 22)), (1600, 70, (20, 12, 14))]):
        pts = [(x, base + amp * math.sin(x / 260 + i * 1.7 + t * 0.05 * (i + 1)) + 30 * math.sin(x / 90 + i))
               for x in range(-10, W + 20, 20)]
        dr.polygon(pts + [(W, H), (0, H)], fill=col + (255,))
    return _grain(im, t, 3)


def ecg(t, dur):
    key = "ecg_bg"
    if key not in _c:
        _c[key] = _img(_grad((6, 16, 32), (12, 34, 60)))
        d = ImageDraw.Draw(_c[key])
        for x in range(0, W, 60):
            d.line([(x, 0), (x, H)], fill=(40, 80, 110, 60))
        for y in range(0, H, 60):
            d.line([(0, y), (W, y)], fill=(40, 80, 110, 60))
    im = _c[key].copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    head = (t * 520) % (W + 300)
    pts = []
    for x in range(0, int(min(head, W)) + 1, 4):
        ph = (x % 360) / 360
        y = 960
        if 0.40 < ph < 0.44:
            y -= (ph - 0.40) / 0.04 * 60
        elif 0.44 < ph < 0.48:
            y += -60 + (ph - 0.44) / 0.04 * 360
        elif 0.48 < ph < 0.53:
            y += 300 - (ph - 0.48) / 0.05 * 420
        elif 0.53 < ph < 0.57:
            y += -120 + (ph - 0.53) / 0.04 * 120
        pts.append((x, y))
    if len(pts) > 1:
        d.line(pts, fill=(255, 92, 92, 255), width=7, joint="curve")
        im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(14)))
        im.alpha_composite(lay)
        x, y = pts[-1]
        ImageDraw.Draw(im).ellipse([x - 12, y - 12, x + 12, y + 12], fill=(255, 220, 220, 255))
    return im


def wheat(t, dur):
    key = "wheat_bg"
    if key not in _c:
        sky = _grad((40, 28, 22), (196, 120, 60))
        _c[key] = _img(sky)
    im = _c[key].copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rng = np.random.default_rng(3)
    for i in range(46):
        bx = rng.uniform(-40, W + 40)
        h = rng.uniform(700, 1150)
        ph = rng.uniform(0, 6.28)
        sway = 26 * math.sin(t * 1.3 + ph)
        near = rng.uniform(0.5, 1.0)
        col = (int(150 + 90 * near), int(105 + 70 * near), int(40 + 25 * near), 255)
        top = (bx + sway, H - h)
        d.line([(bx, H), top], fill=col, width=int(3 + 3 * near))
        for g in range(9):
            gy = top[1] + g * 24
            gx = top[0] - sway * g / 40
            for s in (-1, 1):
                d.ellipse([gx + s * 9 - 8, gy - 13, gx + s * 9 + 8, gy + 13], fill=col)
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(1.2)))
    return _grain(im, t, 3)


def globe(t, dur):
    key = "globe_bg"
    if key not in _c:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        k = np.clip(1 - np.sqrt((xx - 540) ** 2 + (yy - 900) ** 2) / 900, 0, 1)[..., None] ** 1.5
        _c[key] = _img(np.array(DEEP, np.float32) * (1 - k) + np.array((30, 66, 110), np.float32) * k)
    im = _c[key].copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    R, cx, cy = 400, 540, 900
    rot = t * 0.35
    tilt = math.radians(20)

    def proj(lat, lon):
        x = math.cos(lat) * math.sin(lon + rot)
        y = math.sin(lat)
        z = math.cos(lat) * math.cos(lon + rot)
        y, z = y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt)
        return cx + R * x, cy - R * y, z
    for lat in range(-75, 90, 15):
        pts = [proj(math.radians(lat), math.radians(lo)) for lo in range(0, 365, 5)]
        for a, b in zip(pts, pts[1:]):
            al = 220 if a[2] > 0 else 50
            d.line([a[:2], b[:2]], fill=GOLD + (al,), width=2)
    for lon in range(0, 360, 20):
        pts = [proj(math.radians(la), math.radians(lon)) for la in range(-90, 91, 5)]
        for a, b in zip(pts, pts[1:]):
            al = 220 if a[2] > 0 else 50
            d.line([a[:2], b[:2]], fill=GOLD + (al,), width=2)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=GOLD + (255,), width=4)
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(6)))
    im.alpha_composite(lay)
    return im


def race(t, dur):
    im = _img(_grad((10, 14, 26), (30, 22, 30)))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rng = np.random.default_rng(7)
    for i in range(16):
        x = 60 + i * 64 + rng.uniform(-10, 10)
        speed = rng.uniform(500, 1400)
        y = H + 200 - ((t * speed + rng.uniform(0, 2000)) % (H + 600))
        L = speed * 0.35
        col = (255, 120, 80) if i % 3 == 0 else GOLD
        for k in range(12):
            d.line([(x, y + k * L / 12), (x, y + (k + 1) * L / 12)], fill=col + (int(255 * (1 - k / 12)),), width=8)
        d.polygon([(x, y - 34), (x - 22, y + 4), (x + 22, y + 4)], fill=col + (255,))
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(8)))
    im.alpha_composite(lay)
    return im


def clock(t, dur, direction=1):
    im = _img(_grad((12, 18, 30), (24, 30, 44)))
    if direction < 0:
        a = np.asarray(im).astype(np.float32)
        g = a[..., :3].mean(2, keepdims=True)
        im = _img(g.repeat(3, 2) * 0.9)
    d = ImageDraw.Draw(im)
    cx, cy, R = 540, 900, 380
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=GOLD + (255,), width=6)
    for i in range(60):
        a = math.radians(i * 6)
        r0 = R - (40 if i % 5 == 0 else 18)
        d.line([(cx + r0 * math.sin(a), cy - r0 * math.cos(a)), (cx + (R - 8) * math.sin(a), cy - (R - 8) * math.cos(a))],
               fill=GOLD + (255,), width=5 if i % 5 == 0 else 2)
    sp = direction * (1.5 + t * 1.6)
    for L, w_, ang in [(220, 12, t * sp * 0.6), (320, 7, t * sp * 6)]:
        a = ang
        d.line([(cx, cy), (cx + L * math.sin(a), cy - L * math.cos(a))], fill=(250, 240, 220, 255), width=w_)
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=GOLD + (255,))
    return im


def hourglass(t, dur):
    im = _img(_grad((8, 18, 34), (20, 40, 66)))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy, hw, hh = 540, 920, 260, 420
    glass = [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + 26, cy), (cx + hw, cy + hh), (cx - hw, cy + hh), (cx - 26, cy)]
    d.polygon(glass, outline=(220, 230, 240, 200), width=5)
    d.rectangle([cx - hw - 40, cy - hh - 40, cx + hw + 40, cy - hh], fill=(120, 80, 40, 255))
    d.rectangle([cx - hw - 40, cy + hh, cx + hw + 40, cy + hh + 40], fill=(120, 80, 40, 255))
    k = min(1, t / max(dur, 0.1)) * 0.25 + 0.4
    top_level = cy - hh * (1 - k)
    sand = (232, 186, 110, 255)
    # top sand (inverted triangle portion)
    wy = (cy - top_level) / hh * hw
    d.polygon([(cx - wy, top_level), (cx + wy, top_level), (cx + 20, cy - 6), (cx - 20, cy - 6)], fill=sand)
    # bottom pile
    ph = hh * k * 0.9
    d.polygon([(cx - hw + 10, cy + hh - 2), (cx + hw - 10, cy + hh - 2), (cx, cy + hh - ph)], fill=sand)
    # falling stream + grains
    d.line([(cx, cy), (cx, cy + hh - ph)], fill=sand, width=5)
    rng = np.random.default_rng(int(t * 30))
    for _ in range(40):
        y = rng.uniform(cy, cy + hh - ph)
        x = cx + rng.normal(0, 4)
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=sand)
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(10)).point(lambda v: v // 2) if False else lay)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - 300, cy - 300, cx + 300, cy + 300], fill=(255, 200, 120, 40))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(80)))
    return im


def light(t, dur, plate=None):
    if plate is not None:
        im = plate.resize((W, H)).convert("RGBA")
        z = 1 + 0.05 * t / max(dur, 0.1)
        cw, ch = W / z, H / z
        im = im.crop((int((W - cw) / 2), int((H - ch) / 2), int((W + cw) / 2), int((H + ch) / 2))).resize((W, H))
    else:
        im = _img(_grad((30, 26, 22), (90, 70, 48)))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = np.arctan2(xx - 540, yy + 300)
    rays = (0.5 + 0.5 * np.cos(ang * 16 + t * 0.3)) ** 6 * np.clip(1 - yy / 1700, 0, 1) * 70
    a = np.asarray(im).astype(np.float32)
    a[..., :3] += rays[..., None] * np.array([1.0, 0.86, 0.62])
    im = _img(a[..., :3])
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(11)
    for _ in range(70):
        x0, y0, sp = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(20, 70)
        y = (y0 - t * sp) % H
        x = x0 + 20 * math.sin(t + x0)
        r = rng.uniform(2, 5)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 236, 190, int(rng.uniform(80, 200))))
    return im


VISUALS = {"sunrise": sunrise, "ecg": ecg, "wheat": wheat, "globe": globe, "race": race,
           "clock_fwd": lambda t, d: clock(t, d, 1), "clock_back": lambda t, d: clock(t, d, -1),
           "hourglass": hourglass, "light": light}
