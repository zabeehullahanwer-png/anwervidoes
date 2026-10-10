"""Premium version of the teardrop calligraphy logo: 2048 px, sharpened metal letters,
an embossed Islamic-geometric wall, soft halo and vignette. Keeps the original lighting
and wall shadows from the reference render.

  python3 brand/premium_logo.py
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "scripts"))
import graphics  # noqa: E402  (pure-python Islamic lattice tile)

SRC = os.path.join(HERE, "reference", "chatgpt_calligraphy_gold.png")
OUT = os.path.join(HERE, "logo")
N = 2048

PALETTES = {
    # letters (metal tint), highlight tint, wall colour, wall gain, halo colour
    "emerald": ((0.90, 0.94, 0.95), (1.0, 1.0, 1.0), (0.035, 0.27, 0.20), 1.9, (0.55, 0.95, 0.80)),
    "navy": ((1.00, 0.95, 0.85), (1.0, 0.98, 0.92), (0.045, 0.13, 0.27), 1.9, (0.70, 0.82, 1.00)),
}


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def arr(img):
    return np.asarray(img).astype(np.float32) / 255.0


def blur(a, r):
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return arr(img.filter(ImageFilter.GaussianBlur(r)))


def lattice(n, tile):
    t = graphics.islamic_tile(tile, line_w=max(2.0, tile / 90))
    raw = graphics.tiled_mask(t, tile, n, n)
    return np.frombuffer(raw, dtype=np.uint8).reshape(n, n).astype(np.float32) / 255.0


def main():
    src = Image.open(SRC).convert("RGB").resize((N, N), Image.LANCZOS)
    im = arr(src)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mask = smooth(r - b, 0.06, 0.20) * smooth(lum, 0.05, 0.16)
    mask = blur(mask, 1.1)[..., None]

    # sharpened shading for the metal letters
    sharp = arr(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.UnsharpMask(3, 120, 2)))
    shade = np.clip((sharp - 0.05) / 0.85, 0, 1) ** 0.8
    spec = smooth(sharp, 0.72, 0.95)  # brightest bevel edges -> near white

    # wall: original light pool + marble + cast shadows, plus a faint embossed lattice
    wall_lum = lum / max(1e-3, np.percentile(lum[mask[..., 0] < 0.05], 99.5))
    pat = lattice(N, 256)
    emboss = np.clip(pat - np.roll(np.roll(pat, 3, 0), 3, 1), -1, 1)  # light from top-left
    pool = blur(wall_lum, 60)  # where the light falls, the relief shows

    yy, xx = np.mgrid[0:N, 0:N] / N
    vignette = np.clip(1.25 - ((xx - 0.5) ** 2 + (yy - 0.45) ** 2) ** 0.5 * 1.1, 0.55, 1.0)

    os.makedirs(OUT, exist_ok=True)
    for name, (metal, hi, wallc, wg, halo_c) in PALETTES.items():
        bg = (0.12 + 0.88 * wall_lum[..., None]) ** 1.05 * np.array(wallc) * wg
        bg *= (1 + 0.30 * pat[..., None] * (0.35 + pool[..., None]))            # recessed lines catch light
        bg += 0.05 * emboss[..., None] * (0.3 + pool[..., None])               # bevel of the relief
        halo = blur(mask[..., 0], 38)[..., None] * np.array(halo_c) * 0.16
        bg = np.clip((bg + halo) * vignette[..., None], 0, 1)
        letters = shade[..., None] * np.array(metal) * 1.12
        letters = letters * (1 - spec[..., None]) + np.array(hi) * spec[..., None] * 1.0
        letters = np.clip(letters, 0, 1)
        out = letters * mask + bg * (1 - mask)
        Image.fromarray((out * 255).astype(np.uint8)).save(os.path.join(OUT, f"logo_premium_{name}.png"))
        rgba = np.dstack([letters, mask[..., 0]])
        Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(
            os.path.join(OUT, f"logo_premium_{name}_transparent.png"))
        print("wrote", name)
        reel_plate(name, metal, hi, wallc, wg, halo_c, letters, mask[..., 0], wall_lum, pat)


def reel_plate(name, metal, hi, wallc, wg, halo_c, letters, mask, wall_lum, pat, W=1080, H=1920,
               S=1500, cx=540, cy=860):
    """9:16 plate for the intro: procedural wall over the whole frame, the logo (letters plus
    their cast shadows, transferred from the reference) placed at (cx, cy) at size S."""
    shadow = np.clip(wall_lum / np.maximum(blur(wall_lum, 40), 1e-3), 0.0, 1.0)  # <1 inside cast shadows
    shadow = np.where(mask > 0.5, 1.0, shadow)

    def place(a, fill):
        img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize((S, S), Image.LANCZOS)
        canvas = Image.new(img.mode, (W, H), fill)
        canvas.paste(img, (cx - S // 2, cy - S // 2))
        return arr(canvas)

    L = place(letters, (0, 0, 0))
    M = place(mask, 0)
    SH = place(shadow, 255)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # spotlight pool falling from above onto the logo
    pool = np.exp(-(((xx - cx) / (W * 0.55)) ** 2 + ((yy - (cy - S * 0.30)) / (H * 0.38)) ** 2))
    tile = arr(Image.fromarray((pat * 255).astype(np.uint8)).resize((pat.shape[1] * 3 // 4,) * 2))
    reps = (H // tile.shape[0] + 1, W // tile.shape[1] + 1)
    P = np.tile(tile, reps)[:H, :W]
    E = np.clip(P - np.roll(np.roll(P, 3, 0), 3, 1), -1, 1)
    base = (0.10 + 0.95 * pool)[..., None] * np.array(wallc) * wg
    base *= (1 + 0.30 * P[..., None] * (0.35 + pool[..., None]))
    base += 0.05 * E[..., None] * (0.3 + pool[..., None])
    vig = np.clip(1.25 - (((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / H) ** 2) ** 0.5 * 1.3, 0.45, 1.0)
    halo = blur(M, 30)[..., None] * np.array(halo_c) * 0.16
    bg = np.clip((base * SH[..., None] + halo) * vig[..., None], 0, 1)
    out = L * M[..., None] + bg * (1 - M[..., None])
    Image.fromarray((out * 255).astype(np.uint8)).save(os.path.join(OUT, f"reel_plate_{name}.png"))
    Image.fromarray((M * 255).astype(np.uint8)).save(os.path.join(OUT, f"reel_mask_{name}.png"))


if __name__ == "__main__":
    main()
