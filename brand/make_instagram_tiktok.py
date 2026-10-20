"""Instagram + TikTok kit in the brand theme (navy / ivory / antique gold).

  python3 brand/make_instagram_tiktok.py
Outputs (git-ignored, personal photo) in brand/social/instagram_tiktok/:
  profile_1080.jpg                 profile picture for both (shown as a circle)
  highlight_<name>.jpg             1080x1920 Instagram highlight covers (Nastaliq word in a gold ring)
  post_template_ayah.jpg           1080x1350 quote / ayah post template (sample: Hud 11:88)
  reel_cover_sample.jpg            1080x1920 reel cover; title and face inside the 3:4 grid crop
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_facebook import GOLD, IVORY, MUTED, NAME, background, font, spaced  # noqa: E402
from make_youtube import CUTOUT, EMX, EMY, IOD, logo_img, vignette  # noqa: E402

OUT = os.path.join(HERE, "social", "instagram_tiktok")
SKF = os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "assets", "fonts")
NAVY_TXT = (15, 42, 74)


def ur(size, bold=True):
    f = "NotoNastaliqUrdu-Bold.ttf" if bold else "NotoNastaliqUrdu-Regular.ttf"
    return ImageFont.truetype(os.path.join(SKF, f), size, layout_engine=ImageFont.Layout.RAQM)


def ar(size, bold=False):
    f = "Amiri-Bold.ttf" if bold else "Amiri-Regular.ttf"
    return ImageFont.truetype(os.path.join(SKF, f), size, layout_engine=ImageFont.Layout.RAQM)


def rtl(d, xy, text, f, fill, lang="ur", shadow=True):
    if shadow:
        d.text((xy[0] + 4, xy[1] + 5), text, font=f, fill=(0, 0, 0, 140), anchor="mm", direction="rtl", language=lang)
    d.text(xy, text, font=f, fill=fill, anchor="mm", direction="rtl", language=lang)


def gold_ring(d, cx, cy, r, w):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=GOLD, width=w)
    r2 = r + w * 3
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), outline=GOLD + (140,), width=max(2, w // 3))


def highlight(word):
    """story-size cover; Instagram shows only the centre circle, so the word sits dead centre."""
    W, H = 1080, 1920
    img = background(W, H, W / 2, H / 2).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    gold_ring(d, W // 2, H // 2, 330, 9)
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img)
    rtl(d, (W // 2, H // 2 + 10), word, ur(150), IVORY)
    return img.convert("RGB")


def post_ayah():
    """1080x1350 ayah card. Text and reference are exactly the site footer's (Hud 11:88)."""
    W, H = 1080, 1350
    img = background(W, H, W / 2, H * 0.42).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    m = 60
    d.rounded_rectangle((m, m, W - m, H - m), radius=28, outline=GOLD + (200,), width=3)
    d.rounded_rectangle((m + 16, m + 16, W - m - 16, H - m - 16), radius=20, outline=GOLD + (90,), width=2)
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img)
    rtl(d, (W // 2, 520), "وَمَا تَوْفِيقِي إِلَّا بِاللَّهِ", ar(104, True), (233, 200, 140), lang="ar")
    d.line((W / 2 - 150, 650, W / 2 - 14, 650), fill=GOLD, width=2)
    d.line((W / 2 + 14, 650, W / 2 + 150, 650), fill=GOLD, width=2)
    d.polygon([(W / 2, 642), (W / 2 + 8, 650), (W / 2, 658), (W / 2 - 8, 650)], fill=GOLD)
    rtl(d, (W // 2, 760), "اور مجھے توفیق صرف اللہ ہی سے ملتی ہے", ur(52, False), IVORY)
    d.text((W / 2, 870), "“My success is only through Allah.”",
           font=font("CormorantGaramond-500-italic.ttf", 40), fill=MUTED, anchor="mm")
    rtl(d, (W // 2, 960), "سورۂ ہود، آیت ۸۸", ur(36, False), GOLD, shadow=False)
    lg = logo_img(120)
    img.alpha_composite(lg, (W // 2 - lg.width // 2, H - m - 40 - 120 - 40))
    spaced(d, (W / 2, H - m - 46), NAME, font("Poppins-Regular.ttf", 22), IVORY, 4)
    return vignette(img, 0.2)


def reel_cover(title_lines, kicker="درسِ حدیث"):
    """1080x1920; the profile grid shows the centre 1080x1440 (3:4), so all content lives there."""
    W, H = 1080, 1920
    img = background(W, H, W / 2, H * 0.40).convert("RGBA")
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.08, H * 0.18, W * 0.92, H * 0.66), fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(H * 0.08))
    img = Image.composite(Image.new("RGBA", (W, H), (70, 110, 160, 255)), img, glow)
    cut = Image.open(CUTOUT).convert("RGBA")
    side = int(IOD * 5.0)
    x0, y0 = int(EMX - side / 2), int(EMY - side * 0.36)
    person = cut.crop((x0, y0, x0 + side, y0 + side))
    pw = int(W * 0.90)
    person = person.resize((pw, pw), Image.LANCZOS)
    top3x4 = (H - 1440) // 2                      # 240: top of the 3:4 grid crop
    py = top3x4 - 10
    img.alpha_composite(person, ((W - pw) // 2, py))
    # dark band so the title reads over the kurta
    band = Image.new("L", (W, H), 0)
    ImageDraw.Draw(band).rectangle((0, int(H * 0.56), W, H), fill=255)
    band = band.filter(ImageFilter.GaussianBlur(70))
    img = Image.composite(Image.new("RGBA", (W, H), (8, 22, 42, 255)), img, band.point(lambda v: int(v * 0.92)))
    d = ImageDraw.Draw(img)
    f_k = ur(44)
    kw = d.textlength(kicker, font=f_k, direction="rtl", language="ur")
    ky = 1185
    d.rounded_rectangle((W / 2 - kw / 2 - 34, ky - 40, W / 2 + kw / 2 + 34, ky + 46), radius=42, fill=GOLD)
    d.text((W / 2, ky), kicker, font=f_k, fill=NAVY_TXT, anchor="mm", direction="rtl", language="ur")
    y = 1325
    for i, line in enumerate(title_lines):
        rtl(d, (W // 2, y), line, ur(78), IVORY if i == 0 else (233, 200, 140))
        y += 150
    spaced(d, (W / 2, top3x4 + 1440 - 40), NAME, font("Poppins-SemiBold.ttf", 24), IVORY, 4)
    return vignette(img, 0.2)


def main():
    os.makedirs(OUT, exist_ok=True)
    p = Image.open(os.path.join(HERE, "profile", "out", "profile_dai_hd_navy.png")).convert("RGB")
    p.resize((1080, 1080), Image.LANCZOS).save(os.path.join(OUT, "profile_1080.jpg"), quality=95, subsampling=0)
    for slug, word in [("hadith", "حدیث"), ("quran", "قرآن"), ("naseehat", "نصیحت"),
                       ("seerat", "سیرت"), ("sawalat", "سوالات"), ("reels", "ریلز")]:
        highlight(word).save(os.path.join(OUT, f"highlight_{slug}.jpg"), quality=93)
    post_ayah().save(os.path.join(OUT, "post_template_ayah.jpg"), quality=95, subsampling=0)
    reel_cover(["ظاہری حالت دیکھ کر", "فیصلہ نہ کریں"]).save(
        os.path.join(OUT, "reel_cover_sample.jpg"), quality=93, subsampling=0)
    for f in sorted(os.listdir(OUT)):
        print(f, Image.open(os.path.join(OUT, f)).size)


if __name__ == "__main__":
    main()
