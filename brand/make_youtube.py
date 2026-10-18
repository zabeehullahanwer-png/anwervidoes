"""YouTube channel kit in the brand theme (navy / ivory / antique gold).

  python3 brand/make_youtube.py
Outputs (git-ignored, personal photo) in brand/social/youtube/:
  youtube_profile.jpg       800x800    channel picture (YouTube shows it as a circle)
  youtube_banner.jpg        2560x1440  channel art; logo + name + taglines + portrait inside the
                                       1546x423 area that every device shows
  youtube_banner_guide.png  same, with the device safe areas drawn on it
  youtube_watermark.png     150x150    video branding watermark (transparent)
  youtube_thumbnail_sample.jpg 1280x720 thumbnail template with a sample title
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_facebook import (GOLD, IVORY, MUTED, NAME, ROLE, SUBLINE, TAGLINE,  # noqa: E402
                           background, font, portrait_disc, spaced)

OUT = os.path.join(HERE, "social", "youtube")
LOGO = os.path.join(HERE, "logo", "calligraphy_navy_ivory_transparent.png")
CUTOUT = os.path.join(HERE, "profile", "out", "base_1_cutout.png")
EMX, EMY, IOD = 1069, 933.5, 274.0          # eye midpoint / inter-ocular distance in the master


def logo_img(height):
    lg = Image.open(LOGO).convert("RGBA")
    lg = lg.crop(lg.getbbox())
    return lg.resize((int(lg.width * height / lg.height), height), Image.LANCZOS)


def vignette(img, strength=0.30):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = 1 - strength * np.clip(np.sqrt(((xx - w / 2) / w) ** 2 * 1.2 + ((yy - h / 2) / h) ** 2 * 0.6) * 1.8 - 0.35, 0, 1)
    arr = np.asarray(img.convert("RGB")).astype(np.float32) * v[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def banner(S=2):
    """2560x1440. Everything that matters sits in the centre 1546x423 (visible on every device)."""
    W, H = 2560 * S, 1440 * S
    sw, sh = 1546 * S, 423 * S
    sx, sy = (W - sw) // 2, (H - sh) // 2
    img = background(W, H, W / 2, H / 2).convert("RGBA")

    lh = int(sh * 0.86)
    logo = logo_img(lh)
    D = int(sh * 0.86)
    disc, pad = portrait_disc(D, S * 1.35)
    f_name = font("CormorantGaramond-600-normal.ttf", int(58 * S))
    f_tag = font("CormorantGaramond-600-normal.ttf", int(36 * S))
    f_sub = font("CormorantGaramond-500-italic.ttf", int(31 * S))
    f_role = font("Poppins-Regular.ttf", int(17 * S))
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    name_w = sum(tmp.textlength(c, font=f_name) for c in NAME) + 7 * S * (len(NAME) - 1)
    text_w = max(name_w, tmp.textlength(TAGLINE, font=f_tag), tmp.textlength(SUBLINE, font=f_sub))
    gap = int(56 * S)
    group_w = logo.width + gap + text_w + gap + D
    gx = sx + (sw - group_w) / 2
    cy = sy + sh / 2
    logo_x, logo_y = int(gx), int(cy - lh / 2)
    tx = gx + logo.width + gap + text_w / 2
    disc_x = int(gx + logo.width + gap + text_w + gap) - pad
    disc_y = int(cy - D / 2) - pad

    halo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(halo).ellipse((logo_x - lh * 0.1, logo_y, logo_x + logo.width + lh * 0.1, logo_y + lh), fill=60)
    halo = halo.filter(ImageFilter.GaussianBlur(lh * 0.18))
    img = Image.composite(Image.new("RGBA", (W, H), (60, 100, 150, 255)), img, halo)
    shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    shadow.putalpha(logo.getchannel("A").point(lambda v: v * 0.55))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6 * S)), (logo_x + 3 * S, logo_y + 5 * S))
    img.alpha_composite(logo, (logo_x, logo_y))
    img.alpha_composite(disc, (disc_x, disc_y))

    d = ImageDraw.Draw(img)
    spaced(d, (tx, cy - 62 * S), NAME, f_name, IVORY, 7 * S)
    rl, ry = text_w * 0.40, cy - 26 * S
    d.line((tx - rl, ry, tx - 13 * S, ry), fill=GOLD, width=int(1.8 * S))
    d.line((tx + 13 * S, ry, tx + rl, ry), fill=GOLD, width=int(1.8 * S))
    k = 6 * S
    d.polygon([(tx, ry - k), (tx + k, ry), (tx, ry + k), (tx - k, ry)], fill=GOLD)
    d.text((tx, cy + 28 * S), TAGLINE, font=f_tag, fill=IVORY, anchor="ms")
    d.text((tx, cy + 74 * S), SUBLINE, font=f_sub, fill=MUTED, anchor="ms")
    spaced(d, (tx, cy + 128 * S), ROLE, f_role, GOLD, 5 * S)
    return vignette(img, 0.35).resize((2560, 1440), Image.LANCZOS)


def guide(b):
    g = b.copy()
    d = ImageDraw.Draw(g)
    for (w, h, col, label) in [(2560, 1440, (255, 200, 0), "TV"), (2560, 423, (80, 200, 255), "Desktop max"),
                               (1855, 423, (80, 255, 120), "Tablet"), (1546, 423, (255, 80, 80), "Phone / safe area")]:
        x0, y0 = (2560 - w) // 2, (1440 - h) // 2
        d.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), outline=col, width=4)
        d.text((x0 + 12, y0 + 8), label, fill=col, font=font("Poppins-Regular.ttf", 28))
    return g


def profile():
    p = Image.open(os.path.join(HERE, "profile", "out", "profile_dai_hd_navy.png")).convert("RGB")
    return p.resize((800, 800), Image.LANCZOS)


def watermark():
    """150x150: the calligraphy on a navy disc with a thin gold ring (reads at small size on any video)."""
    S = 8
    n = 150 * S
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    m = Image.new("L", (n, n), 0)
    ImageDraw.Draw(m).ellipse((0, 0, n - 1, n - 1), fill=255)
    disc = Image.new("RGBA", (n, n), (15, 42, 74, 235))
    img.paste(disc, (0, 0), m)
    ImageDraw.Draw(img).ellipse((5 * S, 5 * S, n - 5 * S, n - 5 * S), outline=GOLD + (255,), width=3 * S)
    lg = logo_img(int(n * 0.72))
    img.alpha_composite(lg, ((n - lg.width) // 2, (n - lg.height) // 2))
    return img.resize((150, 150), Image.LANCZOS)


def thumbnail(title_lines, kicker="درسِ حدیث"):
    """1280x720 template: portrait on the right, big Nastaliq title on the left, small logo."""
    S = 2
    W, H = 1280 * S, 720 * S
    img = background(W, H, W * 0.72, H * 0.42).convert("RGBA")
    # warm light behind the head
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.52, H * 0.02, W * 0.98, H * 0.95), fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(H * 0.12))
    img = Image.composite(Image.new("RGBA", (W, H), (70, 110, 160, 255)), img, glow)

    cut = Image.open(CUTOUT).convert("RGBA")
    side = int(IOD * 4.6)
    x0, y0 = int(EMX - side * 0.5), int(EMY - side * 0.34)
    person = cut.crop((x0, y0, x0 + side, y0 + int(side * 1.0)))
    ph = int(H * 1.0)
    person = person.resize((int(person.width * ph / person.height), ph), Image.LANCZOS)
    img.alpha_composite(person, (int(W - person.width + W * 0.02), H - ph + int(H * 0.04)))

    d = ImageDraw.Draw(img)
    ur = os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "assets", "fonts", "NotoNastaliqUrdu-Bold.ttf")
    f_k = ImageFont.truetype(ur, int(40 * S), layout_engine=ImageFont.Layout.RAQM)
    f_t = ImageFont.truetype(ur, int(66 * S), layout_engine=ImageFont.Layout.RAQM)
    left_c = W * 0.30
    # kicker pill
    kw = d.textlength(kicker, font=f_k, direction="rtl", language="ur")
    py = H * 0.17
    d.rounded_rectangle((left_c - kw / 2 - 30 * S, py - 34 * S, left_c + kw / 2 + 30 * S, py + 40 * S),
                        radius=36 * S, fill=GOLD)
    d.text((left_c, py), kicker, font=f_k, fill=(15, 42, 74), anchor="mm", direction="rtl", language="ur")
    y = H * 0.40
    for i, line in enumerate(title_lines):
        col = IVORY if i == 0 else (233, 200, 140)
        d.text((left_c + 3 * S, y + 4 * S), line, font=f_t, fill=(0, 0, 0, 150), anchor="mm", direction="rtl", language="ur")
        d.text((left_c, y), line, font=f_t, fill=col, anchor="mm", direction="rtl", language="ur")
        y += 150 * S
    lg = logo_img(int(H * 0.17))
    img.alpha_composite(lg, (int(28 * S), int(H - lg.height - 22 * S)))
    f_n = font("Poppins-SemiBold.ttf", int(19 * S))
    spaced(d, (28 * S + lg.width + 16 * S, H - 52 * S), NAME, f_n, IVORY, 3 * S, anchor_center=False)
    return vignette(img, 0.25).resize((1280, 720), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    profile().save(os.path.join(OUT, "youtube_profile.jpg"), quality=95, subsampling=0)
    b = banner()
    b.save(os.path.join(OUT, "youtube_banner.jpg"), quality=95, subsampling=0, optimize=True)
    guide(b).resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, "youtube_banner_guide.png"))
    watermark().save(os.path.join(OUT, "youtube_watermark.png"))
    thumbnail(["ظاہری حالت دیکھ کر", "فیصلہ نہ کریں"]).save(
        os.path.join(OUT, "youtube_thumbnail_sample.jpg"), quality=93, subsampling=0)
    for f in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, f)
        print(f, Image.open(p).size, f"{os.path.getsize(p) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
