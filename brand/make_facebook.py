"""Facebook profile picture + cover in the brand theme (navy / ivory / antique gold).

  python3 brand/make_facebook.py
Outputs (git-ignored, personal photo) in brand/social/facebook/:
  facebook_profile.png  1080x1080  (the mihrab portrait; Facebook crops it to a circle)
  facebook_cover.png    1640x624   (logo, name, tagline; everything inside the mobile safe area)
  *_preview.png         how they look on the page (circle crop / mobile crop guides)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "scripts"))
import graphics  # noqa: E402

OUT = os.path.join(HERE, "social", "facebook")
FONTS = os.path.join(HERE, "fonts")
SKF = os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "assets", "fonts")

NAVY, NAVY_DEEP, NAVY_LIGHT = (15, 42, 74), (6, 20, 38), (30, 62, 104)
IVORY, GOLD, MUTED = (247, 243, 234), (176, 141, 87), (196, 204, 214)
NAME, TAGLINE, ROLE = "ZABEEHULLAH LEGHARI", "Exploring the Timeless Guidance of Islam", "ISLAMIC SCHOLAR  •  RESEARCHER"


def font(name, size):
    for d in (FONTS, SKF):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise FileNotFoundError(name)


def spaced(draw, xy, text, fnt, fill, tracking, anchor_center=True):
    """draw text with letter spacing (tracking in px), centred on xy."""
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill, anchor="ls")
        x += w + tracking
    return total


def background(W, H, cx, cy):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - cx) / (W * 0.42)) ** 2 + ((yy - cy) / (H * 0.95)) ** 2)
    g = np.exp(-d ** 2 * 1.3)[..., None]
    bg = np.array(NAVY_DEEP) / 255 + (np.array(NAVY_LIGHT) / 255 - np.array(NAVY_DEEP) / 255) * g
    # faint geometric lattice, a touch stronger in the light
    T = H // 3
    tile = graphics.islamic_tile(T, line_w=max(1.5, H / 520))
    pat = np.frombuffer(graphics.tiled_mask(tile, T, W, H), dtype=np.uint8).reshape(H, W).astype(np.float32) / 255
    bg = bg * (1 + 0.16 * pat[..., None] * (0.35 + g))
    bg += np.random.default_rng(5).normal(0, 0.004, bg.shape)
    return Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8))


def cover(W=1640, H=624, scale=2):
    S = scale
    w, h = W * S, H * S
    # composition: logo on the left of centre, text block to its right; the whole group is
    # centred so it survives the mobile crop (sides cut) and the desktop profile-photo overlap
    logo = Image.open(os.path.join(HERE, "logo", "calligraphy_navy_ivory_transparent.png")).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    lh = int(h * 0.66)
    logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)

    f_name = font("CormorantGaramond-600-normal.ttf", int(56 * S))
    f_tag = font("CormorantGaramond-500-italic.ttf", int(32 * S))
    f_role = font("Poppins-Regular.ttf", int(15 * S))
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    name_w = sum(tmp.textlength(c, font=f_name) for c in NAME) + 7 * S * (len(NAME) - 1)
    tag_w = tmp.textlength(TAGLINE, font=f_tag)
    text_w = max(name_w, tag_w)
    gap = int(52 * S)
    group_w = logo.width + gap + text_w
    gx = (w - group_w) / 2
    logo_x = int(gx)
    logo_y = int((h - lh) / 2)
    tx = gx + logo.width + gap + text_w / 2           # text block centre

    img = background(w, h, logo_x + logo.width / 2, h * 0.45).convert("RGBA")
    # soft halo behind the calligraphy
    halo = Image.new("L", (w, h), 0)
    ImageDraw.Draw(halo).ellipse((logo_x - lh * 0.1, logo_y, logo_x + logo.width + lh * 0.1, logo_y + lh), fill=70)
    halo = halo.filter(ImageFilter.GaussianBlur(lh * 0.18))
    img = Image.composite(Image.new("RGBA", (w, h), (60, 100, 150, 255)), img, halo)
    shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    shadow.putalpha(logo.getchannel("A").point(lambda v: v * 0.55))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6 * S)), (logo_x + 3 * S, logo_y + 5 * S))
    img.alpha_composite(logo, (logo_x, logo_y))

    d = ImageDraw.Draw(img)
    cy = h * 0.5
    spaced(d, (tx, cy - 28 * S), NAME, f_name, IVORY, 7 * S)
    # gold rule with a small diamond in the middle
    rl = text_w * 0.42
    ry = cy + 4 * S
    d.line((tx - rl, ry, tx - 12 * S, ry), fill=GOLD, width=max(2, int(1.6 * S)))
    d.line((tx + 12 * S, ry, tx + rl, ry), fill=GOLD, width=max(2, int(1.6 * S)))
    k = 6 * S
    d.polygon([(tx, ry - k), (tx + k, ry), (tx, ry + k), (tx - k, ry)], fill=GOLD)
    d.text((tx, cy + 52 * S), TAGLINE, font=f_tag, fill=IVORY, anchor="ms")
    spaced(d, (tx, cy + 94 * S), ROLE, f_role, GOLD, 4 * S)

    # gentle vignette
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = 1 - 0.30 * np.clip(np.sqrt(((xx - w / 2) / w) ** 2 * 1.2 + ((yy - h / 2) / h) ** 2 * 0.6) * 1.8 - 0.35, 0, 1)
    arr = np.asarray(img.convert("RGB")).astype(np.float32) * v[..., None]
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    prof = Image.open(os.path.join(HERE, "profile", "out", "profile_dai_final_navy.png")).convert("RGB")
    prof.save(os.path.join(OUT, "facebook_profile.png"))
    # circle preview
    m = Image.new("L", prof.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0) + prof.size, fill=255)
    pv = Image.new("RGB", prof.size, (240, 242, 245))
    pv.paste(prof, (0, 0), m)
    pv.save(os.path.join(OUT, "facebook_profile_preview.png"))

    cv = cover()
    cv.save(os.path.join(OUT, "facebook_cover.png"))
    # mobile safe-area guide: phones show roughly the centre 1230x624 of the upload
    g = cv.copy()
    d = ImageDraw.Draw(g)
    mw = int(624 * 640 / 360 * 1.11) if False else 1230
    x0 = (1640 - mw) // 2
    d.rectangle((x0, 0, x0 + mw, 623), outline=(255, 80, 80), width=2)
    g.save(os.path.join(OUT, "facebook_cover_preview.png"))
    print(OUT)


if __name__ == "__main__":
    main()
