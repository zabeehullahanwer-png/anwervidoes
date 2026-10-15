"""Da'i-style profile picture: head levelled (eye line made horizontal), background replaced
with a mihrab arch, a faint Islamic lattice and soft light. The face itself is untouched.

  python3 brand/make_profile_dai.py brand/profile/src1.jpg --tilt -3.13 --eyes 932,941,1206,926 --name 1
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "scripts"))
from make_profile import decontaminate, grade, matte  # noqa: E402
import graphics  # noqa: E402

OUT = os.path.join(HERE, "profile", "out")
THEMES = {
    "emerald": dict(inner=(0.13, 0.42, 0.34), outer=(0.008, 0.06, 0.05), line=(0.86, 0.74, 0.46), glow=(0.9, 1.0, 0.92)),
    "navy": dict(inner=(0.12, 0.24, 0.42), outer=(0.01, 0.025, 0.06), line=(0.86, 0.76, 0.52), glow=(0.92, 0.95, 1.0)),
}


def arch_path(cx, base_y, half_w, spring_y, steps=80):
    """pointed (Islamic) arch: straight jambs up to spring_y, two arcs meeting at the apex."""
    r = half_w * 1.6  # radius > half width -> pointed apex
    pts = [(cx - half_w, base_y), (cx - half_w, spring_y)]
    # left arc centre is to the right of the left jamb
    lc = (cx - half_w + r, spring_y)
    apex_dx = cx - lc[0]
    a0 = np.pi
    a1 = np.pi - np.arccos(np.clip(apex_dx / -r, -1, 1)) if False else np.pi + np.arccos(np.clip((cx - lc[0]) / r, -1, 1)) - np.pi
    left = [(lc[0] + r * np.cos(t), spring_y - r * np.sin(t)) for t in np.linspace(np.pi, np.arccos((cx - lc[0]) / r), steps)]
    rc = (cx + half_w - r, spring_y)
    right = [(rc[0] + r * np.cos(t), spring_y - r * np.sin(t)) for t in np.linspace(np.arccos((cx - rc[0]) / r), 0, steps)]
    _ = (a0, a1, apex_dx)
    return pts + left + right + [(cx + half_w, spring_y), (cx + half_w, base_y)]


def backdrop(S, theme, head_cx, head_top):
    th = THEMES[theme]
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    d = np.sqrt(((xx - head_cx) / (S * 0.6)) ** 2 + ((yy - head_top - S * 0.12) / (S * 0.6)) ** 2)
    g = np.exp(-d ** 2 * 1.6)[..., None]
    bg = np.array(th["outer"]) + (np.array(th["inner"]) - np.array(th["outer"])) * g
    # faint lattice, stronger near the light
    T = S // 6
    tile = graphics.islamic_tile(T, line_w=max(1.5, S / 900))
    pat = np.frombuffer(graphics.tiled_mask(tile, T, S, S), dtype=np.uint8).reshape(S, S).astype(np.float32) / 255
    bg = bg * (1 + 0.22 * pat[..., None] * (0.25 + g))

    # mihrab arch (double gold line) with a soft glow inside
    hw = S * 0.34
    path = arch_path(head_cx, S + 10, hw, head_top + S * 0.40)
    inner = arch_path(head_cx, S + 10, hw - S * 0.022, head_top + S * 0.40)
    big = 2
    lay = Image.new("L", (S * big, S * big), 0)
    dr = ImageDraw.Draw(lay)
    dr.line([(x * big, y * big) for x, y in path], fill=255, width=int(S * 0.006 * big), joint="curve")
    dr.line([(x * big, y * big) for x, y in inner], fill=170, width=int(S * 0.0025 * big), joint="curve")
    lines = np.asarray(lay.resize((S, S), Image.LANCZOS)).astype(np.float32)[..., None] / 255
    fill = Image.new("L", (S, S), 0)
    ImageDraw.Draw(fill).polygon(inner, fill=255)
    inside = np.asarray(fill.filter(ImageFilter.GaussianBlur(S * 0.03))).astype(np.float32)[..., None] / 255
    bg = bg * (1 - 0.25 * inside) + inside * g * np.array(th["glow"]) * 0.10 + bg * inside * 0.25
    glow_lines = np.asarray(Image.fromarray((lines[..., 0] * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(S * 0.006))).astype(np.float32)[..., None] / 255
    bg = bg + glow_lines * np.array(th["line"]) * 0.35
    bg = bg * (1 - lines) + np.array(th["line"]) * lines * (0.75 + 0.25 * g)
    bg += np.random.default_rng(2).normal(0, 0.005, bg.shape)
    return np.clip(bg, 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--tilt", type=float, required=True, help="eye-line angle in degrees (image coords)")
    ap.add_argument("--eyes", required=True, help="x1,y1,x2,y2 pupil centres")
    ap.add_argument("--name", default="1")
    ap.add_argument("--cutout", help="use the retouched master (base_*_cutout.png): already levelled")
    a = ap.parse_args()
    ex1, ey1, ex2, ey2 = [float(v) for v in a.eyes.split(",")]
    emx, emy = (ex1 + ex2) / 2, (ey1 + ey2) / 2

    if a.cutout:
        rgba = Image.open(a.cutout).convert("RGBA")
        a.tilt = 0.0
    else:
        img = Image.open(a.src).convert("RGB")
        alpha = matte(img)
        alpha = np.clip((alpha - 0.06) / 0.9, 0, 1)
        rgb = grade(np.asarray(img).astype(np.float32) / 255.0, alpha)
        fg = decontaminate(rgb, alpha, None)
        # level the head: rotate about the eye midpoint (no other change to the face)
        rgba = Image.fromarray((np.dstack([fg, alpha]) * 255).astype(np.uint8), "RGBA")
        rgba = rgba.rotate(a.tilt, resample=Image.BICUBIC, center=(emx, emy), expand=False)
    arr = np.asarray(rgba).astype(np.float32) / 255
    fg, alpha = arr[..., :3], arr[..., 3]
    w, h = rgba.size

    # which pixels still come from the original photo after the rotation
    valid = np.asarray(Image.new("L", (w, h), 255).rotate(a.tilt, resample=Image.NEAREST, center=(emx, emy))) > 0

    # framing: eyes at 40% height, centred; shrink until no rotated photo edge is in frame
    side = int(min(w, h, (h - emy) / 0.60))
    while True:
        x0 = int(np.clip(emx - side / 2, 0, w - side))
        y0 = int(np.clip(emy - side * 0.40, 0, h - side))
        if valid[y0:y0 + side, x0:x0 + side].all() or side < 600:
            break
        side -= 16
    fg = fg[y0:y0 + side, x0:x0 + side]
    al = alpha[y0:y0 + side, x0:x0 + side][..., None]
    ys = np.where(al[..., 0] > 0.5)[0]
    head_top = ys.min() if len(ys) else side * 0.1
    head_cx = emx - x0

    os.makedirs(OUT, exist_ok=True)
    for theme in THEMES:
        bg = backdrop(side, theme, head_cx, head_top)
        comp = fg * al + bg * (1 - al)
        yy, xx = np.mgrid[0:side, 0:side].astype(np.float32) / side
        v = 1 - 0.22 * np.clip(np.sqrt((xx - 0.5) ** 2 + (yy - 0.42) ** 2) * 1.7 - 0.35, 0, 1)
        comp = np.clip(comp * v[..., None], 0, 1)
        im = Image.fromarray((comp * 255).astype(np.uint8)).resize((1080, 1080), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(1.2, 40, 3))
        p = os.path.join(OUT, f"profile_dai_{a.name}_{theme}.png")
        im.save(p)
        print(p)


if __name__ == "__main__":
    main()
