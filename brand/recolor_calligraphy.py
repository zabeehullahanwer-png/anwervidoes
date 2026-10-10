"""Recolour the teardrop calligraphy logo (gold letters on a dark wall) into palettes
suited to a da'i, keeping the original lighting, bevels and wall shadows.

  python3 brand/recolor_calligraphy.py
"""
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "reference", "chatgpt_calligraphy_gold.png")
OUT = os.path.join(HERE, "logo")

# name: (letter metal colour, letter gain, wall colour, wall gain)
PALETTES = {
    # silver/pearl letters on deep emerald: green = Islam, silver = simplicity & dignity
    "emerald_silver": ((0.92, 0.95, 0.96), 1.15, (0.05, 0.30, 0.22), 1.35),
    # warm ivory letters on deep navy: calm, scholarly (matches the video style)
    "navy_ivory": ((1.00, 0.95, 0.84), 1.10, (0.06, 0.16, 0.30), 1.35),
    # white letters on charcoal: simplest, most sober
    "charcoal_white": ((0.97, 0.97, 0.97), 1.10, (0.20, 0.20, 0.21), 1.0),
}


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def main():
    im = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32) / 255.0
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # gold = strongly warm (R >> B); the marble wall is neutral grey
    warmth = r - b
    mask = smooth(warmth, 0.06, 0.20) * smooth(lum, 0.05, 0.16)
    m_img = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    mask = np.asarray(m_img).astype(np.float32)[..., None] / 255.0

    # letter shading: gold luminance re-mapped so highlights stay bright, shadows keep depth
    shade = np.clip((lum - 0.05) / 0.85, 0, 1) ** 0.85
    wall = lum / max(1e-3, np.percentile(lum[mask[..., 0] < 0.05], 99.5))  # wall light falloff + shadows
    os.makedirs(OUT, exist_ok=True)
    for name, (metal, mg, wallc, wg) in PALETTES.items():
        letters = np.clip(shade[..., None] * np.array(metal) * mg + 0.04 * shade[..., None] ** 6, 0, 1)
        bg = np.clip(wall[..., None] ** 1.05 * np.array(wallc) * wg, 0, 1)
        out = letters * mask + bg * (1 - mask)
        Image.fromarray((out * 255).astype(np.uint8)).save(os.path.join(OUT, f"calligraphy_{name}.png"))
        # transparent letters-only version for video overlays
        rgba = np.dstack([letters, mask[..., 0]])
        Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(
            os.path.join(OUT, f"calligraphy_{name}_transparent.png"))
        print("wrote", name)


if __name__ == "__main__":
    main()
