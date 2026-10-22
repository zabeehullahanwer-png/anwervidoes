"""Put the presenter into each virtual studio: background plate → presenter → desk layer.

Uses the retouched cut-out (base_1_cutout.png) as a stand-in for keyed green-screen footage; the same
geometry (scale from the camera, eye line at camera height, body hidden behind the desk) applies to
video.

  python3 brand/make_studio_previews.py [set ...]   ->  brand/studio/out/studio_<set>.jpg
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
PLATES = os.path.join(HERE, "studio", "plates")
OUT = os.path.join(HERE, "studio", "out")
CUT = os.path.join(HERE, "profile", "out", "base_1_cutout.png")
EMX, EMY, IOD_PX = 1069, 933.5, 274.0
IOD_M = 0.063                       # adult inter-pupillary distance
CAM_DIST, LENS, SENSOR = 2.8, 60, 36
CAM_Z, EYE_Z = 1.12, 1.22
W, H = 1920, 1080

# per-set colour match for the presenter (multipliers on R, G, B) and light-wrap colour strength
GRADE = {
    "library": ((1.05, 0.99, 0.90), 0.30),
    "broadcast": ((0.95, 0.98, 1.04), 0.25),
    "arches": ((1.06, 1.0, 0.92), 0.35),
    "brand": ((1.0, 0.98, 0.95), 0.25),
    "manuscript": ((1.06, 0.99, 0.90), 0.30),
}


def f32(im):
    return np.asarray(im).astype(np.float32) / 255


def blur(a, r):
    if a.ndim == 3:
        return np.dstack([blur(a[..., i], r) for i in range(a.shape[2])])
    return f32(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)))


def compose(name):
    bg = f32(Image.open(os.path.join(PLATES, f"{name}_bg.png")).convert("RGB").resize((W, H), Image.LANCZOS))
    fg = f32(Image.open(os.path.join(PLATES, f"{name}_fg.png")).convert("RGBA").resize((W, H), Image.LANCZOS))
    # presenter scale and eye position come from the studio camera (written by make_virtual_studios.py)
    import json
    meta = json.load(open(os.path.join(PLATES, f"{name}_meta.json")))
    ppm = meta["ppm"]
    s = ppm * IOD_M / IOD_PX
    cut = Image.open(CUT).convert("RGBA")
    cut = cut.resize((int(cut.width * s), int(cut.height * s)), Image.LANCZOS)
    ex, ey = EMX * s, EMY * s
    # eye line at the camera height (frame centre); push down if the cut-out's bottom edge would show
    da = fg[..., 3]
    cols = slice(int(W * 0.42), int(W * 0.55))
    desk_top = int(np.argmax((da[:, cols] > 0.5).any(axis=1)))
    y0 = int(meta["eye_y"] - ey)
    a_cut = np.asarray(cut.getchannel("A"))
    bottom = np.where(a_cut.max(axis=1) > 20)[0].max()
    if y0 + bottom < desk_top + 40:
        y0 = desk_top + 40 - bottom
    x0 = int(meta["eye_x"] - ex)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(cut, (x0, y0), cut)
    p = f32(layer)
    pc, pa = p[..., :3], p[..., 3:4]
    mult, wrap_k = GRADE.get(name, ((1, 1, 1), 0.3))
    pc = np.clip(pc * np.array(mult), 0, 1)
    # light wrap: the room's light bleeds a little around the edges
    wrap = blur(bg, 14) * (blur(1 - pa[..., 0], 5)[..., None] * pa) * wrap_k
    comp = pc * pa + bg * (1 - pa) + wrap
    # soft shadow of the presenter on the desk top, just in front of the body
    sh = np.zeros((H, W), np.float32)
    sh[desk_top:desk_top + 60, :] = blur(pa[..., 0], 25)[desk_top - 60:desk_top, :] * 0.0
    comp = fg[..., :3] * fg[..., 3:4] + comp * (1 - fg[..., 3:4])
    # finish: gentle vignette + grain
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = 1 - 0.22 * np.clip(np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / H) ** 2) * 1.7 - 0.25, 0, 1)
    comp = comp * v[..., None] + np.random.default_rng(1).normal(0, 0.006, comp.shape)
    out = Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"studio_{name}.jpg")
    out.save(path, quality=93)
    print(path, "desk_top", desk_top, "eye_y", y0 + ey)
    return path


if __name__ == "__main__":
    names = sys.argv[1:] or ["library", "broadcast", "arches", "brand", "manuscript"]
    for n in names:
        if os.path.exists(os.path.join(PLATES, f"{n}_bg.png")):
            compose(n)
