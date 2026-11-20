"""Bold explainer-style covers (big face with a white outline, huge yellow/white Urdu, check pills, an arrow):
the high-contrast look of popular Urdu education channels, in the brand's navy.

  python3 brand/make_thumb_bold.py SRC_FRAME.png -> videos/edited/thumb_bold_{9x16,16x9}.jpg
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_reel_samples import NASTALIQ, OUT, font  # noqa: E402
from make_thumbs_ep import cutout  # noqa: E402

YELLOW = (255, 214, 10)
WHITE = (255, 255, 255)
RED = (225, 38, 38)
INK = (8, 10, 16)


def bg(w, h):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    k = np.clip(1 - np.sqrt(((xx - w * 0.62) / w) ** 2 + ((yy - h * 0.45) / h) ** 2) * 1.5, 0, 1)[..., None]
    rgb = np.array((6, 14, 30), np.float32) * (1 - k) + np.array((22, 58, 104), np.float32) * k
    im = Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")
    # soft light streaks
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(7):
        x = int(w * (0.15 + i * 0.13))
        d.polygon([(x, 0), (x + 60, 0), (x - 260, h), (x - 320, h)], fill=(255, 255, 255, 9))
    im.alpha_composite(ov.filter(ImageFilter.GaussianBlur(6)))
    return im


def outlined(person, scale, stroke=10):
    p = person.resize((int(person.width * scale), int(person.height * scale)), Image.LANCZOS)
    a = p.getchannel("A")
    ring = a.filter(ImageFilter.MaxFilter(stroke * 2 + 1))
    out = Image.new("RGBA", p.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", p.size, (0, 0, 0, 0))
    sh.putalpha(ring.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.8)))
    out.alpha_composite(sh, (0, 0))
    wr = Image.new("RGBA", p.size, WHITE + (0,))
    wr.putalpha(ring)
    out.alpha_composite(wr)
    out.alpha_composite(p)
    return out


def bold_text(txt, size, fill, stroke=9, shadow=True):
    f = font(NASTALIQ, size)
    l, t, r, b = f.getbbox(txt, direction="rtl", stroke_width=stroke)
    pad = 40
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    if shadow:
        s = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(s).text((pad - l + 6, pad - t + 10), txt, font=f, fill=(0, 0, 0, 200), direction="rtl",
                               stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        im.alpha_composite(s.filter(ImageFilter.GaussianBlur(8)))
    ImageDraw.Draw(im).text((pad - l, pad - t), txt, font=f, fill=fill, direction="rtl", stroke_width=stroke,
                            stroke_fill=INK)
    return im


def pill(txt, size=54):
    t = bold_text(txt, size, INK, stroke=0, shadow=False)
    w, h = t.width + 70, 110
    im = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], 55, fill=YELLOW, outline=INK, width=6)
    cx, cy, r = 62, h // 2 + 8, 30
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(22, 150, 70))
    d.line([(cx - 14, cy + 1), (cx - 4, cy + 12), (cx + 15, cy - 11)], fill=WHITE, width=8, joint="curve")
    im.alpha_composite(t, (w - t.width + 6, (h + 16 - t.height) // 2 - 2))
    return im


def arrow(length=260, width=34, color=RED):
    im = Image.new("RGBA", (length + 40, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 80
    d.line([(20, y), (length - 60, y)], fill=INK, width=width + 12)
    d.polygon([(length + 10, y), (length - 80, y - 66), (length - 80, y + 66)], fill=INK)
    d.line([(26, y), (length - 60, y)], fill=color, width=width)
    d.polygon([(length - 4, y), (length - 74, y - 52), (length - 74, y + 52)], fill=color)
    return im


def cover_9x16(person):
    W, H = 1080, 1920
    cv = bg(W, H)
    p = outlined(person, 1900 / person.width)
    cv.alpha_composite(p, ((W - p.width) // 2, H - p.height + 30)) if p.width <= W else \
        cv.paste(p, ((W - p.width) // 2, H - p.height + 30), p)
    t1 = bold_text("صبح یہ ۳ چیزیں ہیں؟", 86, WHITE)
    t2 = bold_text("پوری دنیا", 190, YELLOW, stroke=12)
    t3 = bold_text("آپ کے پاس ہے!", 96, WHITE)
    cv.alpha_composite(t1, ((W - t1.width) // 2, 40))
    cv.alpha_composite(t2, ((W - t2.width) // 2, 230))
    cv.alpha_composite(t3, ((W - t3.width) // 2, 560))
    y = 830
    for i, w in enumerate(["امن", "صحت", "روزی"]):
        pl = pill(w)
        x = [W - pl.width - 40, (W - pl.width) // 2, 40][i]
        cv.alpha_composite(pl, (x, y + (i % 2) * 0))
    return cv


def cover_16x9(person):
    W, H = 1920, 1080
    cv = bg(W, H)
    p = outlined(person, 1550 / person.width)
    x = -330
    cv.paste(p, (x, H - p.height + 40), p)
    t1 = bold_text("صبح یہ ۳ چیزیں ہیں؟", 84, WHITE)
    t2 = bold_text("پوری دنیا", 200, YELLOW, stroke=13)
    t3 = bold_text("آپ کے پاس ہے!", 92, WHITE)
    rx = W - 60
    cv.alpha_composite(t1, (rx - t1.width, 20))
    cv.alpha_composite(t2, (rx - t2.width, 190))
    cv.alpha_composite(t3, (rx - t3.width, 520))
    y = 830
    xx = rx
    for w in ["امن", "صحت", "روزی"]:
        pl = pill(w, 50)
        cv.alpha_composite(pl, (xx - pl.width, y))
        xx -= pl.width + 24
    ar = arrow(240)
    cv.alpha_composite(ar.transpose(Image.FLIP_LEFT_RIGHT), (rx - t2.width - ar.width + 30, 330))
    return cv


if __name__ == "__main__":
    person = cutout(sys.argv[1])
    # clear the carved chair top beside the beard completely (the white outline would trace it)
    a = np.asarray(person).copy()
    a[470:678, 980:1235, 3] = 0
    person = Image.fromarray(a, "RGBA")
    for name, fn in [("9x16", cover_9x16), ("16x9", cover_16x9)]:
        p = os.path.join(OUT, f"thumb_bold_{name}.jpg")
        fn(person).convert("RGB").save(p, quality=93)
        print(p)
