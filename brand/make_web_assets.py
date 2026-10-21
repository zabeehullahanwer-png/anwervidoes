"""Website share image (og:image 1200x630) and favicon set from the brand logo.

  python3 brand/make_web_assets.py   ->  brand/social/website_assets/
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_facebook import GOLD, IVORY, MUTED, NAME, ROLE, SUBLINE, TAGLINE, background, font, spaced  # noqa: E402
from make_youtube import logo_img, vignette  # noqa: E402

OUT = os.path.join(HERE, "social", "website_assets")


def og(S=2):
    W, H = 1200 * S, 630 * S
    img = background(W, H, W * 0.3, H * 0.5).convert("RGBA")
    lh = int(H * 0.66)
    lg = logo_img(lh)
    img.alpha_composite(lg, (int(110 * S), int((H - lh) / 2)))
    d = ImageDraw.Draw(img)
    tx, cy = 110 * S + lg.width + 70 * S, H / 2
    spaced(d, (tx, cy - 70 * S), NAME, font("CormorantGaramond-600-normal.ttf", int(46 * S)), IVORY, 5 * S, anchor_center=False)
    d.line((tx, cy - 44 * S, tx + 260 * S, cy - 44 * S), fill=GOLD, width=int(1.6 * S))
    d.text((tx, cy + 4 * S), TAGLINE, font=font("CormorantGaramond-600-normal.ttf", int(31 * S)), fill=IVORY, anchor="ls")
    d.text((tx, cy + 42 * S), SUBLINE, font=font("CormorantGaramond-500-italic.ttf", int(26 * S)), fill=MUTED, anchor="ls")
    spaced(d, (tx, cy + 88 * S), ROLE, font("Poppins-Regular.ttf", int(14 * S)), GOLD, 4 * S, anchor_center=False)
    return vignette(img, 0.25).resize((1200, 630), Image.LANCZOS)


def icon(n):
    """navy rounded square, calligraphy in ivory-silver: reads at 16 px as a light teardrop."""
    S = 8 if n < 256 else 2
    N = n * S
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, N - 1, N - 1), radius=int(N * 0.22), fill=(15, 42, 74, 255))
    lg = logo_img(int(N * 0.82))
    img.alpha_composite(lg, ((N - lg.width) // 2, (N - lg.height) // 2))
    return img.resize((n, n), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    og().save(os.path.join(OUT, "og-image.jpg"), quality=92, subsampling=0)
    icon(512).save(os.path.join(OUT, "icon-512.png"))
    icon(192).save(os.path.join(OUT, "icon-192.png"))
    icon(180).save(os.path.join(OUT, "apple-touch-icon.png"))
    icon(256).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(os.path.join(OUT, f)))


if __name__ == "__main__":
    main()
