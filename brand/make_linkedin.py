"""LinkedIn kit: formal profile photo (light background) + 1584x396 banner.

  python3 brand/make_linkedin.py
Outputs (git-ignored) in brand/social/linkedin/. The profile photo covers the banner's lower-left
corner on every device, so the banner keeps that corner empty and puts its content on the right.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_facebook import GOLD, IVORY, MUTED, SUBLINE, TAGLINE, background, font, spaced  # noqa: E402
from make_youtube import logo_img, vignette  # noqa: E402

OUT = os.path.join(HERE, "social", "linkedin")
FIELDS = "ISLAMIC STUDIES  •  RESEARCH  •  TEACHING"


def banner(S=2):
    W, H = 1584 * S, 396 * S
    img = background(W, H, W * 0.70, H * 0.45).convert("RGBA")
    lh = int(H * 0.78)
    lg = logo_img(lh)
    lx, ly = int(W - 70 * S - lg.width), int((H - lh) / 2)
    halo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(halo).ellipse((lx - lh * 0.15, ly, lx + lg.width + lh * 0.15, ly + lh), fill=60)
    halo = halo.filter(ImageFilter.GaussianBlur(lh * 0.18))
    img = Image.composite(Image.new("RGBA", (W, H), (60, 100, 150, 255)), img, halo)
    img.alpha_composite(lg, (lx, ly))

    d = ImageDraw.Draw(img)
    f_tag = font("CormorantGaramond-600-normal.ttf", int(42 * S))
    f_sub = font("CormorantGaramond-500-italic.ttf", int(30 * S))
    f_role = font("Poppins-Regular.ttf", int(15 * S))
    tx = lx - 60 * S                                   # text block is right-aligned to the logo
    cy = H * 0.5
    d.text((tx, cy - 22 * S), TAGLINE, font=f_tag, fill=IVORY, anchor="rs")
    d.text((tx, cy + 24 * S), SUBLINE, font=f_sub, fill=MUTED, anchor="rs")
    tw = d.textlength(TAGLINE, font=f_tag)
    d.line((tx - tw, cy + 50 * S, tx, cy + 50 * S), fill=GOLD + (160,), width=int(1.5 * S))
    role_w = sum(d.textlength(c, font=f_role) for c in FIELDS) + 4 * S * (len(FIELDS) - 1)
    spaced(d, (tx - role_w, cy + 88 * S), FIELDS, f_role, GOLD, 4 * S, anchor_center=False)
    return vignette(img, 0.25).resize((1584, 396), Image.LANCZOS)


def preview(b, photo):
    """how LinkedIn desktop shows it: photo circle over the lower-left corner."""
    pv = Image.new("RGB", (1584, 396 + 140), (243, 242, 239))
    pv.paste(b, (0, 0))
    D = 304
    ph = photo.resize((D, D), Image.LANCZOS)
    m = Image.new("L", (D, D), 0)
    ImageDraw.Draw(m).ellipse((0, 0, D - 1, D - 1), fill=255)
    ring = Image.new("L", (D + 16, D + 16), 0)
    ImageDraw.Draw(ring).ellipse((0, 0, D + 15, D + 15), fill=255)
    x, y = 48, 396 - D // 2 - 20
    pv.paste((255, 255, 255), (x - 8, y - 8), ring)
    pv.paste(ph, (x, y), m)
    return pv


def main():
    os.makedirs(OUT, exist_ok=True)
    photo = Image.open(os.path.join(HERE, "social", "website", "zabeehullah-leghari-square-ivory.jpg")).convert("RGB")
    # tighter head-and-shoulders: LinkedIn shows a small circle, the face should fill ~60 % of it
    photo = photo.crop((150, 40, 1050, 940)).resize((1200, 1200), Image.LANCZOS)
    photo.save(os.path.join(OUT, "linkedin_profile.jpg"), quality=95, subsampling=0)
    b = banner()
    b.save(os.path.join(OUT, "linkedin_banner.jpg"), quality=95, subsampling=0)
    preview(b, photo).save(os.path.join(OUT, "linkedin_preview.png"))
    for f in sorted(os.listdir(OUT)):
        print(f, Image.open(os.path.join(OUT, f)).size)


if __name__ == "__main__":
    main()
