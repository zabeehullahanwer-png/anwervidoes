"""Master portrait for all platforms: head levelled, kurta wrinkles and lint removed, soft light
on the face. The face is never reshaped or smoothed (geometry and skin texture stay as shot).

  python3 brand/make_profile_base.py brand/profile/src1.jpg --tilt -3.13 --eyes 932,941,1206,926 --name 1

Outputs (git-ignored) in brand/profile/out/:
  base_{name}_cutout.png   full-resolution transparent master (for covers, posters, thumbnails)
  base_{name}_studio.png   1080x1080 preview on a soft studio backdrop
  base_{name}_compare.png  before / after
"""
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_profile import backdrop, decontaminate, grade, matte  # noqa: E402

OUT = os.path.join(HERE, "profile", "out")


def blur(a, s):
    return cv2.GaussianBlur(a, (0, 0), s)


def masked_blur(a, m, s):
    """Gaussian blur of a inside mask m only (normalised convolution: no bleed from outside)."""
    num = blur(a * m[..., None] if a.ndim == 3 else a * m, s)
    den = np.maximum(blur(m, s), 1e-4)
    return num / (den[..., None] if a.ndim == 3 else den)


def cloth_mask(rgb, alpha, chin_y):
    """navy kurta: blue-dominant dark pixels of the person below the chin."""
    hsv = cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1] / 255, hsv[..., 2] / 255
    blue = (h > 98) & (h < 140) & (s > 0.16) & (v < 0.75)
    m = blue & (alpha > 0.9)
    m[: int(chin_y)] = False
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:                                   # the kurta is the one big piece
        m = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    holes = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))) & (alpha > 0.9)
    return holes.astype(np.float32)


def detail_mask(lum, cloth, scale, zone=None):
    """things on the kurta that must stay crisp: buttons and the light stitch lines."""
    local = masked_blur(lum, cloth, 8 * scale)
    bright = ((lum - local) > 0.07).astype(np.uint8)
    # drop isolated noise: keep only components big enough to be a button or a stitch run
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bright)
    big = stats[:, cv2.CC_STAT_AREA] > 60 * scale * scale
    big[0] = False
    d = big[lab].astype(np.uint8)
    if zone is not None:
        d = d * zone
    k = max(3, int(9 * scale)) | 1
    d = cv2.dilate(d, np.ones((k, k), np.uint8))
    return blur(d.astype(np.float32), 2 * scale)


def remove_lint(rgb, cloth, scale):
    """tiny light specks (dust, lint) on the dark cloth -> local median."""
    lum = rgb.mean(axis=2)
    med = cv2.medianBlur((rgb * 255).astype(np.uint8), max(5, int(9 * scale)) | 1).astype(np.float32) / 255
    speck = ((lum - med.mean(axis=2)) > 0.06).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(speck)
    keep = np.zeros_like(speck)
    small = (stats[:, cv2.CC_STAT_AREA] < 40 * scale * scale)
    small[0] = False
    keep[small[lab]] = 1
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8)).astype(np.float32) * cloth
    return rgb * (1 - keep[..., None]) + med * keep[..., None], keep


def smooth_wrinkles(rgb, cloth, scale, zone, amount=0.9):
    """frequency split on the cloth: keep the body's broad shading (> ~110 px) and a little of the
    finest weave, flatten the band in between where creases and folds live."""
    m = cloth
    inner = cv2.erode(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))).astype(np.float32)
    low = masked_blur(rgb, m, 70 * scale)
    smooth = masked_blur(rgb, m, 1.5 * scale)          # denoised cloth (JPEG grain removed)
    fine = smooth - masked_blur(rgb, m, 4 * scale)
    mid = smooth - low - fine
    keep = detail_mask(rgb.mean(axis=2), m, scale, zone)
    a = amount * (1 - keep)
    out = low + mid * (1 - a[..., None]) + fine * (0.7 + 0.3 * keep[..., None])
    out = out * (1 - keep[..., None]) + rgb * keep[..., None]   # buttons/stitches exactly as shot
    w = blur(inner, 28 * scale)[..., None] * m[..., None]
    return rgb * (1 - w) + out * w


def clean_edges(rgb, alpha, scale):
    """thin yellow curtain fringe on the outline: no edge pixel may be brighter or yellower than
    the person just inside it (per channel min). Dark detail (hair strands) is untouched, so the
    outline stays crisp."""
    core = cv2.erode((alpha > 0.97).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)
    inside = masked_blur(rgb, core, 3 * scale)
    band = (alpha < 0.97).astype(np.uint8)
    band = cv2.dilate(band, np.ones((7, 7), np.uint8)).astype(np.float32)
    band = blur(band, 1.0)[..., None]
    return rgb * (1 - band) + np.minimum(rgb, inside * 1.04) * band


def face_light(rgb, alpha, cx, cy, r):
    """soft key light: a gentle, broad exposure lift centred on the face (no local retouching)."""
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    g = np.exp(-(((xx - cx) / r) ** 2 + ((yy - cy) / (r * 1.25)) ** 2))
    lift = (1 + 0.12 * g)[..., None]
    out = 1 - (1 - np.clip(rgb, 0, 1)) ** lift          # brightens mids, protects highlights
    return out * alpha[..., None] + rgb * (1 - alpha[..., None])


def hide_undershirt(rgb, emx, emy, iod):
    """the sliver of white vest showing beside the top button -> filled from the surrounding kurta."""
    x0, x1 = int(emx - 0.13 * iod), int(emx - 0.0 * iod)
    y0, y1 = int(emy + 2.75 * iod), int(emy + 3.15 * iod)
    u8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(u8, cv2.COLOR_RGB2HSV)
    m = np.zeros(rgb.shape[:2], np.uint8)
    win = hsv[y0:y1, x0:x1]
    m[y0:y1, x0:x1] = ((win[..., 2] > 95) & (win[..., 1] < 120)).astype(np.uint8)
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    out = cv2.inpaint(u8, m * 255, 9, cv2.INPAINT_TELEA).astype(np.float32) / 255
    return out


def tame_shine(rgb, alpha, emx, emy, iod, amount=0.55):
    """oily highlights on forehead / nose / cheeks: pull the specular peaks down toward the
    surrounding skin tone. Light only: no smoothing, no shape change, skin texture kept."""
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    face = np.exp(-(((xx - emx) / (iod * 1.15)) ** 4 + ((yy - (emy + 0.2 * iod)) / (iod * 1.35)) ** 4))
    lum = rgb.max(axis=2)
    base = cv2.GaussianBlur(lum, (0, 0), iod * 0.12)
    spec = np.clip(base - 0.62, 0, None) / 0.38                 # broad shiny patches only
    tex = lum - cv2.GaussianBlur(lum, (0, 0), iod * 0.012)       # pores / fine texture to keep
    k = (amount * spec * face)[..., None]
    skin = cv2.GaussianBlur(rgb, (0, 0), iod * 0.5)
    target = skin * (base[..., None] * 0.0 + 1) * 0.92 + tex[..., None]
    return rgb * (1 - k) + np.clip(target, 0, 1) * k


def warp_level(img4, emx, emy, iod, head_deg, body_deg):
    """rotate the body by body_deg (shoulders level) and the head by head_deg (eyes level): the
    angle blends smoothly from head to body around the neck, so the face moves rigidly."""
    h, w = img4.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = emx, emy + 0.9 * iod
    r = np.sqrt(((xx - cx) / (1.2 * iod)) ** 2 + ((yy - cy) / (2.35 * iod)) ** 2)
    t = np.clip((r - 1.0) / 0.4, 0, 1)
    wgt = 1 - t * t * (3 - 2 * t)                                 # 1 on head+beard, 0 on shoulders
    ang = np.deg2rad(body_deg + (head_deg - body_deg) * wgt)
    # inverse map (dst -> src): rotate by -ang about the eye midpoint
    c, s_ = np.cos(-ang), np.sin(-ang)
    dx, dy = xx - emx, yy - emy
    mx = (emx + c * dx + s_ * dy).astype(np.float32)
    my = (emy - s_ * dx + c * dy).astype(np.float32)
    return cv2.remap(img4, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def shoulder_slope(al, emx, iod):
    """mean height difference (right minus left) of the shoulder outline, sampled symmetrically."""
    d = []
    for k in (1.9, 2.2, 2.5):
        ys = [np.where(al[:, int(emx + sgn * k * iod)] > 0.5)[0].min() for sgn in (-1, 1)]
        d.append(ys[1] - ys[0])
    return float(np.mean(d))


def level_shoulders(alpha, emx, emy, iod, head_deg):
    """body angle that makes the shoulders level after the warp (searched on a 1/4-size matte)."""
    f = 0.25
    small = cv2.resize(alpha, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    best = min(np.arange(-5.0, 1.0, 0.1),
               key=lambda b: abs(shoulder_slope(warp_level(small, emx * f, emy * f, iod * f, head_deg, b),
                                                emx * f, iod * f)))
    return float(best)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--tilt", type=float, required=True)
    ap.add_argument("--eyes", required=True)
    ap.add_argument("--body-tilt", type=float, default=None,
                    help="shoulder-line angle; default: measured from the matte")
    ap.add_argument("--name", default="1")
    a = ap.parse_args()
    ex1, ey1, ex2, ey2 = [float(v) for v in a.eyes.split(",")]
    emx, emy = (ex1 + ex2) / 2, (ey1 + ey2) / 2
    iod = np.hypot(ex2 - ex1, ey2 - ey1)              # inter-ocular distance sets every scale
    scale = iod / 275.0

    img = Image.open(a.src).convert("RGB")
    raw = np.asarray(img).astype(np.float32) / 255
    alpha = np.clip((matte(img) - 0.06) / 0.9, 0, 1)
    chin_y = emy + iod * 1.55
    cloth = cloth_mask(raw, alpha, chin_y)
    # white balance for the skin only: the kurta keeps its true deep navy
    cw = blur(cloth, 6 * scale)[..., None]
    rgb = grade(raw, alpha) * (1 - cw) + raw * cw
    rgb = decontaminate(rgb, alpha, None)
    rgb = clean_edges(rgb, alpha, scale)
    rgb = hide_undershirt(rgb, emx, emy, iod)
    rgb, _ = remove_lint(rgb, cloth, scale)
    # buttons, placket and collar stitching live in a narrow band down the centre and at the collar
    hh, ww = alpha.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    zone = ((np.abs(xx - emx) < iod * 0.45) | (yy < chin_y + iod * 0.9)).astype(np.uint8)
    rgb = smooth_wrinkles(rgb, cloth, scale, zone)
    rgb = tame_shine(rgb, alpha, emx, emy, iod)
    rgb = face_light(rgb, alpha, emx, emy + iod * 0.45, iod * 1.5)

    # level eyes AND shoulders: they lean by different amounts, so head and body get their own
    # rotation (the face itself is rotated rigidly, never bent)
    h, w = alpha.shape
    body = a.body_tilt
    if body is None:
        body = level_shoulders(alpha, emx, emy, iod, a.tilt)
    print(f"eye tilt {a.tilt:.2f} deg, shoulder tilt {body:.2f} deg")
    pm = np.dstack([rgb * alpha[..., None], alpha]).astype(np.float32)
    pm = np.clip(warp_level(pm, emx, emy, iod, a.tilt, body), 0, 1)
    al_r = pm[..., 3]
    rgba = np.dstack([np.clip(pm[..., :3] / np.maximum(al_r, 1e-3)[..., None], 0, 1), al_r])
    before = raw
    M = cv2.getRotationMatrix2D((emx, emy), body, 1.0)

    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(
        os.path.join(OUT, f"base_{a.name}_cutout.png"))

    # square head-and-shoulders preview, eyes at 38 %
    valid = cv2.warpAffine(np.ones((h, w), np.float32), M, (w, h), flags=cv2.INTER_NEAREST) > 0
    side = int(min(w, h, (h - emy) / 0.62))
    while True:
        x0 = int(np.clip(emx - side / 2, 0, w - side))
        y0 = int(np.clip(emy - side * 0.38, 0, h - side))
        if valid[y0:y0 + side, x0:x0 + side].all() or side < 600:
            break
        side -= 16
    crop = rgba[y0:y0 + side, x0:x0 + side]
    bg = backdrop(side, side, "charcoal", emx - x0, emy - y0 + side * 0.1)
    al = crop[..., 3:4]
    comp = crop[..., :3] * al + bg * (1 - al)
    studio = Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8)).resize((1080, 1080), Image.LANCZOS)
    studio.save(os.path.join(OUT, f"base_{a.name}_studio.png"))

    b = Image.fromarray((np.clip(before[y0:y0 + side, x0:x0 + side], 0, 1) * 255).astype(np.uint8))
    b = b.resize((1080, 1080), Image.LANCZOS)
    # before keeps its original tilt for an honest comparison
    b0 = Image.fromarray((raw * 255).astype(np.uint8)).crop((x0, y0, x0 + side, y0 + side)).resize((1080, 1080))
    cmp_ = Image.new("RGB", (2160, 1080))
    cmp_.paste(b0, (0, 0))
    cmp_.paste(studio, (1080, 0))
    cmp_.save(os.path.join(OUT, f"base_{a.name}_compare.png"))
    _ = b
    print(os.path.join(OUT, f"base_{a.name}_studio.png"))


if __name__ == "__main__":
    main()
