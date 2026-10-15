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
SUBLINE = "Rooted in Tradition, Conversant with the Age"


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


def portrait_disc(D, S):
    """head-and-shoulders from the retouched master inside a circle with a double gold ring."""
    cut = Image.open(os.path.join(HERE, "profile", "out", "base_1_cutout.png")).convert("RGBA")
    emx, emy, iod = 1069, 933.5, 274.0                       # eye midpoint of the master (src1)
    side = int(iod * 5.2)
    x0, y0 = int(emx - side / 2), int(emy - side * 0.40)
    person = cut.crop((x0, y0, x0 + side, y0 + side)).resize((D, D), Image.LANCZOS)
    # inside the disc: lighter navy studio glow so the navy kurta still separates
    yy, xx = np.mgrid[0:D, 0:D].astype(np.float32) / D
    g = np.exp(-(((xx - 0.5) / 0.45) ** 2 + ((yy - 0.38) / 0.5) ** 2))[..., None]
    inner = np.array((10, 28, 52)) + (np.array((52, 92, 140)) - np.array((10, 28, 52))) * g
    disc = Image.fromarray(inner.astype(np.uint8)).convert("RGBA")
    disc.alpha_composite(person)
    m = Image.new("L", (D * 2, D * 2), 0)
    ImageDraw.Draw(m).ellipse((0, 0, D * 2 - 1, D * 2 - 1), fill=255)
    m = m.resize((D, D), Image.LANCZOS)
    pad = int(26 * S)
    out = Image.new("RGBA", (D + 2 * pad, D + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", out.size, 0)
    ImageDraw.Draw(sh).ellipse((pad, pad + 8 * S, pad + D, pad + D + 8 * S), fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(14 * S))
    out.paste((0, 0, 0, 255), (0, 0), sh)
    out.paste(disc, (pad, pad), m)
    big = 3
    ring = Image.new("RGBA", (out.width * big, out.height * big), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ring)
    r0 = pad * big
    dr.ellipse((r0 - 3 * S * big, r0 - 3 * S * big, r0 + (D + 3 * S) * big, r0 + (D + 3 * S) * big),
               outline=GOLD + (255,), width=int(2.6 * S * big))
    r1 = 13 * S * big
    dr.ellipse((r0 - r1, r0 - r1, r0 + D * big + r1, r0 + D * big + r1), outline=GOLD + (150,), width=int(1.1 * S * big))
    out.alpha_composite(ring.resize(out.size, Image.LANCZOS))
    return out, pad


def cover(W=1640, H=624, scale=2, out_w=2048):
    S = scale
    w, h = W * S, H * S
    # composition, all inside the centre ~1230 px that phones keep:
    #   calligraphy logo | name + taglines | portrait in a gold-ringed circle
    logo = Image.open(os.path.join(HERE, "logo", "calligraphy_navy_ivory_transparent.png")).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    lh = int(h * 0.50)
    logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
    D = int(h * 0.60)
    disc, pad = portrait_disc(D, S)

    f_name = font("CormorantGaramond-600-normal.ttf", int(42 * S))
    f_tag = font("CormorantGaramond-600-normal.ttf", int(27 * S))
    f_sub = font("CormorantGaramond-500-italic.ttf", int(23 * S))
    f_role = font("Poppins-Regular.ttf", int(13 * S))
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    name_w = sum(tmp.textlength(c, font=f_name) for c in NAME) + 5 * S * (len(NAME) - 1)
    text_w = max(name_w, tmp.textlength(TAGLINE, font=f_tag), tmp.textlength(SUBLINE, font=f_sub))
    gap = int(34 * S)
    group_w = logo.width + gap + text_w + gap + D
    gx = (w - group_w) / 2
    logo_x, logo_y = int(gx), int((h - lh) / 2)
    tx = gx + logo.width + gap + text_w / 2
    disc_x = int(gx + logo.width + gap + text_w + gap) - pad
    disc_y = int((h - D) / 2) - pad

    img = background(w, h, w / 2, h * 0.45).convert("RGBA")
    halo = Image.new("L", (w, h), 0)
    ImageDraw.Draw(halo).ellipse((logo_x - lh * 0.1, logo_y, logo_x + logo.width + lh * 0.1, logo_y + lh), fill=60)
    halo = halo.filter(ImageFilter.GaussianBlur(lh * 0.18))
    img = Image.composite(Image.new("RGBA", (w, h), (60, 100, 150, 255)), img, halo)
    shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    shadow.putalpha(logo.getchannel("A").point(lambda v: v * 0.55))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6 * S)), (logo_x + 3 * S, logo_y + 5 * S))
    img.alpha_composite(logo, (logo_x, logo_y))
    img.alpha_composite(disc, (disc_x, disc_y))

    d = ImageDraw.Draw(img)
    cy = h * 0.5
    spaced(d, (tx, cy - 50 * S), NAME, f_name, IVORY, 5 * S)
    rl = text_w * 0.40
    ry = cy - 22 * S
    d.line((tx - rl, ry, tx - 11 * S, ry), fill=GOLD, width=max(2, int(1.5 * S)))
    d.line((tx + 11 * S, ry, tx + rl, ry), fill=GOLD, width=max(2, int(1.5 * S)))
    k = 5 * S
    d.polygon([(tx, ry - k), (tx + k, ry), (tx, ry + k), (tx - k, ry)], fill=GOLD)
    d.text((tx, cy + 22 * S), TAGLINE, font=f_tag, fill=IVORY, anchor="ms")
    d.text((tx, cy + 58 * S), SUBLINE, font=f_sub, fill=MUTED, anchor="ms")
    spaced(d, (tx, cy + 100 * S), ROLE, f_role, GOLD, 4 * S)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = 1 - 0.30 * np.clip(np.sqrt(((xx - w / 2) / w) ** 2 * 1.2 + ((yy - h / 2) / h) ** 2 * 0.6) * 1.8 - 0.35, 0, 1)
    arr = np.asarray(img.convert("RGB")).astype(np.float32) * v[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((out_w, round(out_w * H / W)), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    prof = Image.open(os.path.join(HERE, "profile", "out", "profile_dai_hd_navy.png")).convert("RGB")
    prof.save(os.path.join(OUT, "facebook_profile.png"), optimize=True)
    # circle preview
    m = Image.new("L", prof.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0) + prof.size, fill=255)
    pv = Image.new("RGB", prof.size, (240, 242, 245))
    pv.paste(prof, (0, 0), m)
    pv.save(os.path.join(OUT, "facebook_profile_preview.png"))

    cv = cover()
    # PNG (lossless) + sRGB: Facebook keeps text and gradients clean; 2048 px wide is the largest
    # it stores, so it never has to upscale (upscaling is what makes uploads look soft or blocky)
    cv.save(os.path.join(OUT, "facebook_cover.png"), optimize=True)
    cv = cv.resize((1640, 624), Image.LANCZOS)
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
