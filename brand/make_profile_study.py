"""Composite the levelled portrait into the rendered scholar's study (books behind, podcast mic in
front). Face untouched: rotation to level the eyes, background replacement, global grade only.

  python3 brand/make_profile_study.py brand/profile/src1.jpg --tilt -3.13 --eyes 932,941,1206,926 --name 1
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_profile import decontaminate, grade, matte  # noqa: E402

PLATES = os.path.join(HERE, "profile", "plates")
OUT = os.path.join(HERE, "profile", "out")


def f32(im):
    return np.asarray(im).astype(np.float32) / 255.0


def gblur(a, r):
    if a.ndim == 3:
        return np.dstack([gblur(a[..., i], r) for i in range(a.shape[2])])
    return f32(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--tilt", type=float, required=True)
    ap.add_argument("--eyes", required=True)
    ap.add_argument("--name", default="1")
    ap.add_argument("--eye-y", type=float, default=0.38, help="eye line position (fraction of height)")
    ap.add_argument("--size", type=int, default=1080)
    a = ap.parse_args()
    ex1, ey1, ex2, ey2 = [float(v) for v in a.eyes.split(",")]
    emx, emy = (ex1 + ex2) / 2, (ey1 + ey2) / 2

    img = Image.open(a.src).convert("RGB")
    alpha = np.clip((matte(img) - 0.06) / 0.9, 0, 1)
    rgb = grade(f32(img), alpha)
    fg = decontaminate(rgb, alpha, None)
    rgba = Image.fromarray((np.dstack([fg, alpha]) * 255).astype(np.uint8), "RGBA")
    rgba = rgba.rotate(a.tilt, resample=Image.BICUBIC, center=(emx, emy))
    w, h = rgba.size
    valid = np.asarray(Image.new("L", (w, h), 255).rotate(a.tilt, resample=Image.NEAREST, center=(emx, emy))) > 0
    side = int(min(w, h, (h - emy) / (1 - a.eye_y)))
    while True:
        x0 = int(np.clip(emx - side / 2, 0, w - side))
        y0 = int(np.clip(emy - side * a.eye_y, 0, h - side))
        if valid[y0:y0 + side, x0:x0 + side].all() or side < 600:
            break
        side -= 16
    person = rgba.crop((x0, y0, x0 + side, y0 + side))

    bg_img = Image.open(os.path.join(PLATES, "study_bg.png")).convert("RGB")
    S = bg_img.size[0]
    bg = f32(bg_img)
    mic = f32(Image.open(os.path.join(PLATES, "study_mic.png")).convert("RGBA").resize((S, S), Image.LANCZOS))
    p = f32(person.resize((S, S), Image.LANCZOS))
    fgc, al = p[..., :3], p[..., 3:4]

    # match the person to the room: warm the shadows slightly, light-wrap the background into the edges
    fgc = np.clip(fgc * np.array([1.02, 1.0, 0.97]), 0, 1)
    wrap = gblur(bg, S * 0.012) * (gblur(1 - al, S * 0.006) * al) * 0.35
    comp = fgc * al + bg * (1 - al) + wrap
    # soft contact shadow of the sitter on the (far, blurred) shelves is negligible at 1.85 m: skip
    # podcast mic in front
    comp = mic[..., :3] * mic[..., 3:4] + comp * (1 - mic[..., 3:4])
    # cinematic finish: gentle S-curve, warm highlights, vignette, fine grain
    comp = np.clip(comp, 0, 1)
    comp = comp + 0.06 * (comp - comp ** 2) * (comp - 0.5) * -4  # mild S-curve
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    vig = 1 - 0.28 * np.clip(np.sqrt((xx - 0.5) ** 2 + (yy - 0.42) ** 2) * 1.6 - 0.25, 0, 1)
    comp = comp * vig[..., None]
    comp += np.random.default_rng(3).normal(0, 0.008, comp.shape)
    out = Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8)).resize((a.size, a.size), Image.LANCZOS)
    out = out.filter(ImageFilter.UnsharpMask(1.0, 35, 3))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"profile_study_{a.name}.png")
    out.save(path)
    print(path)


if __name__ == "__main__":
    main()
