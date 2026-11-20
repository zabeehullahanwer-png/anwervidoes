"""Premium cinematic covers for the reel: the presenter in the desk studio, a glowing gold globe and dawn light
behind him, a gold title and three line-art blessing icons.  No boxes or stickers.

  python3 brand/make_thumb_premium.py SRC_FRAME.png  -> videos/edited/cover_{9x16,16x9}.jpg
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import broll  # noqa: E402
import make_reel as R  # noqa: E402

GOLD_HI = (232, 200, 140)
OUT = R.OUT


def presenter(src):
    im = Image.open(src).convert("RGB").resize((R.KW, R.KH), Image.LANCZOS)
    return R.key(np.asarray(im))


def globe_glow(t=2.0):
    g = broll.globe(t, 4)                       # 1080x1920, globe centred at (540, 900), R=400
    a = np.asarray(g).astype(np.float32)
    lum = a[..., :3].max(2)
    alpha = np.clip((lum - 60) / 120, 0, 1)     # keep only the gold wires and their glow
    out = np.dstack([a[..., :3], alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def gold_title(txt, size, path=R.NASKH):
    g = R.gold_text(txt, size, path, grad=((255, 236, 190), (206, 150, 70)))
    glow = Image.new("RGBA", g.size, (0, 0, 0, 0))
    glow.putalpha(g.getchannel("A").filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.55)))
    gl = Image.new("RGBA", g.size, (255, 190, 90, 0))
    gl.putalpha(glow.getchannel("A"))
    out = Image.new("RGBA", g.size, (0, 0, 0, 0))
    out.alpha_composite(gl)
    out.alpha_composite(g)
    return out


def icon(kind, s=120, col=GOLD_HI):
    S = 4
    im = Image.new("RGBA", (s * S, s * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    z = s * S
    lw = int(z * 0.055)
    c = col + (255,)
    if kind == "home":
        d.line([(z * .12, z * .48), (z * .5, z * .14), (z * .88, z * .48)], fill=c, width=lw, joint="curve")
        d.line([(z * .22, z * .42), (z * .22, z * .86), (z * .78, z * .86), (z * .78, z * .42)], fill=c, width=lw,
               joint="curve")
        d.arc([z * .40, z * .56, z * .60, z * .76], 180, 360, fill=c, width=lw)
        d.line([(z * .40, z * .66), (z * .40, z * .86)], fill=c, width=lw)
        d.line([(z * .60, z * .66), (z * .60, z * .86)], fill=c, width=lw)
    elif kind == "heart":
        pts = []
        for i in range(0, 361, 4):
            a = math.radians(i)
            x = 16 * math.sin(a) ** 3
            y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
            pts.append((z * .5 + x * z * .027, z * .48 - y * z * .027))
        d.line(pts + [pts[0]], fill=c, width=lw, joint="curve")
        d.line([(z * .18, z * .52), (z * .38, z * .52), (z * .45, z * .38), (z * .53, z * .66), (z * .60, z * .52),
                (z * .82, z * .52)], fill=c, width=int(lw * .8), joint="curve")
    elif kind == "wheat":
        d.line([(z * .5, z * .92), (z * .5, z * .12)], fill=c, width=lw)
        for i in range(5):
            y = z * (.22 + i * .13)
            for sgn in (-1, 1):
                cx = z * .5 + sgn * z * .1
                box = [cx - z * .07, y - z * .1, cx + z * .07, y + z * .1]
                im2 = Image.new("RGBA", im.size, (0, 0, 0, 0))
                ImageDraw.Draw(im2).ellipse(box, outline=c, width=int(lw * .8))
                im.alpha_composite(im2.rotate(sgn * -28, center=(cx, y)))
    im = im.resize((s, s), Image.LANCZOS)
    glow = Image.new("RGBA", im.size, (255, 190, 90, 0))
    glow.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(8)))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(im)
    return out


def cover_9x16(person, eyes):
    def behind(bg):
        a = np.asarray(bg).astype(np.float32)
        a[..., :3] *= 0.72                                           # dim the room so the globe glows
        yy, xx = np.mgrid[0:R.H, 0:R.W].astype(np.float32)
        d = np.sqrt((xx - 540) ** 2 + (yy - 820) ** 2)
        a[..., :3] += (np.clip(1 - d / 760, 0, 1) ** 2 * 120)[..., None] * np.array([1.0, 0.72, 0.38])
        bg.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA"))
        gl = globe_glow()
        gl = gl.resize((int(gl.width * 1.05), int(gl.height * 1.05)), Image.LANCZOS)
        bg.alpha_composite(gl, ((R.W - gl.width) // 2, 860 - int(900 * 1.05)))
    cv = R.studio_frame(person, eyes, 2.5, 1040, behind)
    sh = np.zeros((R.H, R.W), np.float32)
    sh[:520] = np.linspace(1, 0, 520)[:, None] ** 1.2 * 200
    sh[1250:] = np.linspace(0, 1, R.H - 1250)[:, None] ** 1.1 * 245
    cv.alpha_composite(Image.fromarray(np.dstack([np.full((R.H, R.W, 3), (6, 12, 24)), sh]).astype(np.uint8), "RGBA"))
    clean = cv.copy()
    R.HEADLINE = "لمحۂ موجود میں جینا سیکھیے"
    R.SERIES = "SEERAT|insights"
    R.draw_logo(cv)
    R.draw_headline(cv)
    k = R.bold_word("صبح یہ تین نعمتیں ہیں؟", 70, (255, 255, 255))
    cv.alpha_composite(k, ((R.W - k.width) // 2, 315))
    t = gold_title("پوری دنیا", 200)
    cv.alpha_composite(t, ((R.W - t.width) // 2, 420))
    s2 = R.bold_word("آپ کے پاس ہے", 78, (255, 255, 255))
    cv.alpha_composite(s2, ((R.W - s2.width) // 2, 700))
    labels = [("home", "امن"), ("heart", "صحت"), ("wheat", "روزی")]
    xs = [R.W - 210, R.W // 2, 210]
    for (kind, lab), x in zip(labels, xs):
        ic = icon(kind, 120)
        cv.alpha_composite(ic, (x - ic.width // 2, 1390))
        lb = R.gold_text(lab, 60)
        cv.alpha_composite(lb, (x - lb.width // 2, 1490))
    R.draw_strip(cv)
    return cv, clean


def cover_16x9(c916):
    W, H = 1920, 1080
    # right: the presenter panel from the 9:16 cover; left: title on the dark room
    base = c916.resize((int(c916.width * H / c916.height * 1.55), int(H * 1.55)), Image.LANCZOS)
    cv = Image.new("RGBA", (W, H), (6, 12, 24, 255))
    room = c916.crop((0, 700, 1080, 1307)).resize((W, int(W * 607 / 1080))).filter(ImageFilter.GaussianBlur(24))
    cv.alpha_composite(room, (0, (H - room.height) // 2))
    cv.alpha_composite(Image.new("RGBA", (W, H), (6, 12, 24, 150)))
    panel = base.crop(((base.width - 1000) // 2, int(base.height * 0.30), (base.width - 1000) // 2 + 1000,
                       int(base.height * 0.30) + H))
    m = np.ones((H, 1000), np.float32)
    m[:, :260] = np.linspace(0, 1, 260)[None, :] ** 1.4
    panel.putalpha(Image.fromarray((m * 255).astype(np.uint8)))
    cv.alpha_composite(panel, (W - 1000, 0))
    k = R.bold_word("صبح یہ تین نعمتیں ہیں؟", 70, (255, 255, 255))
    t = gold_title("پوری دنیا", 220)
    s2 = R.bold_word("آپ کے پاس ہے", 80, (255, 255, 255))
    cx = 540
    cv.alpha_composite(k, (cx - k.width // 2, 70))
    cv.alpha_composite(t, (cx - t.width // 2, 190))
    cv.alpha_composite(s2, (cx - s2.width // 2, 500))
    for (kind, lab), x in zip([("home", "امن"), ("heart", "صحت"), ("wheat", "روزی")], [cx + 280, cx, cx - 280]):
        ic = icon(kind, 120)
        cv.alpha_composite(ic, (x - ic.width // 2, 740))
        lb = R.gold_text(lab, 56)
        cv.alpha_composite(lb, (x - lb.width // 2, 840))
    lg = Image.open(R.LOGO).convert("RGBA")
    lg.thumbnail((140, 140))
    cv.alpha_composite(lg, (30, 30))
    return cv


if __name__ == "__main__":
    person = presenter(sys.argv[1])
    eyes = [int(v) for v in os.environ.get("THUMB_EYES", "1088,524,170").split(",")]
    eyes = [eyes[0] * R.KW / 2560, eyes[1] * R.KH / 1440, eyes[2] * R.KW / 2560]
    c, clean = cover_9x16(person, eyes)
    c.convert("RGB").save(os.path.join(OUT, "cover_9x16.jpg"), quality=93)
    cover_16x9(clean).convert("RGB").save(os.path.join(OUT, "cover_16x9.jpg"), quality=93)
    print("ok")
