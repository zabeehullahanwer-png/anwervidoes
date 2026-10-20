"""X (Twitter) header + profile, and the photo for academic profiles.

  python3 brand/make_x_academic.py
Outputs (git-ignored) in brand/social/x/ and brand/social/academic/.
X shows the profile photo over the header's lower-left, and phones trim the header top and bottom,
so the content sits in the right-hand middle band.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_facebook import GOLD, IVORY, MUTED, NAME, ROLE, SUBLINE, TAGLINE, background, font, spaced  # noqa: E402
from make_youtube import logo_img, vignette  # noqa: E402


def x_header(S=2):
    W, H = 1500 * S, 500 * S
    img = background(W, H, W * 0.66, H * 0.5).convert("RGBA")
    lh = int(H * 0.62)
    lg = logo_img(lh)
    lx, ly = int(W - 90 * S - lg.width), int((H - lh) / 2)
    halo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(halo).ellipse((lx - lh * 0.15, ly, lx + lg.width + lh * 0.15, ly + lh), fill=60)
    img = Image.composite(Image.new("RGBA", (W, H), (60, 100, 150, 255)), img, halo.filter(ImageFilter.GaussianBlur(lh * 0.18)))
    img.alpha_composite(lg, (lx, ly))
    d = ImageDraw.Draw(img)
    tx, cy = lx - 60 * S, H * 0.5
    spaced_w = sum(d.textlength(c, font=font("CormorantGaramond-600-normal.ttf", int(40 * S))) for c in NAME) + 6 * S * (len(NAME) - 1)
    spaced(d, (tx - spaced_w, cy - 52 * S), NAME, font("CormorantGaramond-600-normal.ttf", int(40 * S)), IVORY, 6 * S, anchor_center=False)
    d.line((tx - spaced_w, cy - 30 * S, tx, cy - 30 * S), fill=GOLD + (170,), width=int(1.5 * S))
    d.text((tx, cy + 12 * S), TAGLINE, font=font("CormorantGaramond-600-normal.ttf", int(30 * S)), fill=IVORY, anchor="rs")
    d.text((tx, cy + 46 * S), SUBLINE, font=font("CormorantGaramond-500-italic.ttf", int(25 * S)), fill=MUTED, anchor="rs")
    f_role = font("Poppins-Regular.ttf", int(13 * S))
    rw = sum(d.textlength(c, font=f_role) for c in ROLE) + 4 * S * (len(ROLE) - 1)
    spaced(d, (tx - rw, cy + 84 * S), ROLE, f_role, GOLD, 4 * S, anchor_center=False)
    return vignette(img, 0.25).resize((1500, 500), Image.LANCZOS)


def main():
    xo = os.path.join(HERE, "social", "x")
    ac = os.path.join(HERE, "social", "academic")
    os.makedirs(xo, exist_ok=True)
    os.makedirs(ac, exist_ok=True)
    navy = Image.open(os.path.join(HERE, "profile", "out", "profile_dai_hd_navy.png")).convert("RGB")
    navy.resize((1080, 1080), Image.LANCZOS).save(os.path.join(xo, "x_profile.jpg"), quality=95, subsampling=0)
    x_header().save(os.path.join(xo, "x_header.jpg"), quality=95, subsampling=0)
    # academic sites: formal, light background, face filling the frame (same crop as LinkedIn)
    li = Image.open(os.path.join(HERE, "social", "linkedin", "linkedin_profile.jpg")).convert("RGB")
    li.save(os.path.join(ac, "academic_profile_photo.jpg"), quality=95, subsampling=0)
    li.resize((600, 600), Image.LANCZOS).save(os.path.join(ac, "academic_profile_photo_600.jpg"), quality=93)
    for d in (xo, ac):
        for f in sorted(os.listdir(d)):
            print(f, Image.open(os.path.join(d, f)).size)


if __name__ == "__main__":
    main()
