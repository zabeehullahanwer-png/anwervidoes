"""Photo pack for the website developer, from the retouched master (base_1_cutout.png).

  python3 brand/make_website_photos.py
Outputs (git-ignored) in brand/social/website/.
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "profile", "out", "base_1_cutout.png")
OUT = os.path.join(HERE, "social", "website")
EMX, EMY = 1069, 933.5                          # eye midpoint in the master

THEMES = {
    "ivory": ((0.985, 0.972, 0.945), (0.86, 0.84, 0.80)),   # matches the site background #F7F3EA
    "navy": ((0.20, 0.33, 0.52), (0.024, 0.08, 0.15)),     # brand navy #0F2A4A
}


def studio(w, h, theme, cx, cy):
    inner, outer = (np.array(c) for c in THEMES[theme])
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / (w * 0.75)) ** 2 + ((yy - cy) / (h * 0.75)) ** 2)
    g = np.exp(-d ** 2 * 1.5)[..., None]
    bg = outer + (inner - outer) * g
    return bg + np.random.default_rng(4).normal(0, 0.004, bg.shape)


def place(cut, w, h, theme):
    """crop the master to w:h around the face (eyes ~36 % from the top) and put it on a backdrop."""
    W, H = cut.size
    H -= 16                                     # matte fades in the last rows of the photo
    ratio = w / h
    ch = H
    cw = int(round(ch * ratio))
    if cw > W:
        cw = W
        ch = int(round(cw / ratio))
    x0 = int(np.clip(EMX - cw / 2, 0, W - cw))
    y0 = int(np.clip(EMY - ch * 0.36, 0, H - ch))
    crop = np.asarray(cut.crop((x0, y0, x0 + cw, y0 + ch))).astype(np.float32) / 255
    bg = studio(cw, ch, theme, EMX - x0, EMY - y0)
    a = crop[..., 3:4]
    comp = crop[..., :3] * a + bg * (1 - a)
    im = Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8))
    return im.resize((w, h), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    cut = Image.open(SRC).convert("RGBA")
    # 1) transparent cut-out, trimmed to the person: the developer can put it on any background
    trimmed = cut.crop(cut.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
    trimmed.save(os.path.join(OUT, "zabeehullah-leghari-cutout.png"), optimize=True)
    # 2) portrait 4:5 (About / introduction section), both site colours
    for theme in THEMES:
        place(cut, 1600, 2000, theme).save(
            os.path.join(OUT, f"zabeehullah-leghari-portrait-{theme}.jpg"), quality=93, subsampling=0, optimize=True)
    # 3) square (cards, author box, social previews)
    place(cut, 1200, 1200, "ivory").save(
        os.path.join(OUT, "zabeehullah-leghari-square-ivory.jpg"), quality=93, subsampling=0, optimize=True)
    for f in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, f)
        print(f, Image.open(p).size, f"{os.path.getsize(p) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
