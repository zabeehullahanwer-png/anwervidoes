"""Two Gen-Z style covers (9:16, 1080x1920) for the "three blessings / present moment" reel.

  python3 brand/make_thumbs_ep.py SRC_FRAME.png  -> videos/edited/thumb_{notification,player}.jpg

A  notification : phone lock screen, a glass notification "پوری دنیا آپ کے نام ہو چکی ہے"
                  with three ✓ chips (امن · صحت · روزی), the presenter below
B  player       : video-player bar  ⏪ ماضی | ▶ ابھی (LIVE) | مستقبل ⏩  and the line
                  «لمحۂ موجود میں جینا سیکھیے», the presenter below
The presenter is cut from a frame of the recording (green key x MODNet matte); the face is not altered.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_reel_samples import (DEEP, GOLD, GOLD_HI, IVORY, NASTALIQ, NAVY, OUT, POPPINS, font,  # noqa: E402
                               text_img)

W, H = 1080, 1920
MODNET = os.environ.get("MODNET_ONNX", "")


def cutout(path, garbage=((1030, 515, 1250, 690),)):
    im = Image.open(path).convert("RGB")
    f = np.asarray(im).astype(np.float32) / 255
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    a = 1 - np.clip((g - np.maximum(r, b) - 0.10) / 0.16, 0, 1)
    if MODNET and os.path.exists(MODNET):
        import onnxruntime as ort
        s = ort.InferenceSession(MODNET, providers=["CPUExecutionProvider"])
        x = np.asarray(im.resize((1024, 576), Image.BILINEAR)).astype(np.float32) / 255
        m = s.run(None, {"input": ((x - 0.5) / 0.5).transpose(2, 0, 1)[None]})[0][0, 0]
        m = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).resize(im.size, Image.BILINEAR)
        m = m.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(6))
        a = a * np.clip((np.asarray(m).astype(np.float32) / 255 - 0.15) / 0.35, 0, 1)
    lum = r * 0.3 + g * 0.59 + b * 0.11
    for x0, y0, x1, y1 in garbage:                      # carved chair top beside the beard
        sub = lum[y0:y1, x0:x1] > 0.36
        a[y0:y1, x0:x1] *= ~sub
    # keep only the presenter: the largest solid region (drops floating flecks of the carved chair)
    import cv2
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.5).astype(np.uint8), 8)
    if n > 2:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        keep = cv2.dilate((lab == big).astype(np.uint8), np.ones((7, 7), np.uint8))
        a = a * keep
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
                   .filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
    g2 = np.minimum(g, np.maximum(r, b) + 0.015)
    rgb = np.clip((np.dstack([r * 1.04, g2, b * 0.95]) - 0.5) * 1.08 + 0.51, 0, 1)
    return Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), "RGBA")


def bg(top=(10, 26, 48), mid=(28, 66, 112)):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    k = np.clip(1 - np.sqrt((xx - W / 2) ** 2 + ((yy - 620) * 0.9) ** 2) / 1150, 0, 1)[..., None] ** 1.4
    rgb = np.array(top, np.float32) * (1 - k) + np.array(mid, np.float32) * k
    return Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")


def place(cv, person, width=1900, top=None):
    s = width / person.width
    top = H - int(person.height * s) if top is None else top
    p = person.resize((int(person.width * s), int(person.height * s)), Image.LANCZOS)
    rim = Image.new("RGBA", p.size, GOLD_HI + (0,))
    rim.putalpha(p.getchannel("A").filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.6)))
    x = (W - p.width) // 2
    cv.alpha_composite(rim, (x, top - 6)) if x >= 0 else cv.paste(rim, (x, top - 6), rim)
    cv.paste(p, (x, top), p)


def check(d, cx, cy, r, fill=GOLD_HI, mark=DEEP):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
           fill=mark, width=max(3, int(r * 0.22)), joint="curve")


def glass(cv, box, radius=44, alpha=150):
    x0, y0, x1, y1 = box
    blur = cv.crop(box).filter(ImageFilter.GaussianBlur(24))
    m = Image.new("L", blur.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, blur.width - 1, blur.height - 1], radius, fill=255)
    cv.paste(blur, (x0, y0), m)
    ov = Image.new("RGBA", cv.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(box, radius, fill=(255, 255, 255, 34), outline=(255, 255, 255, alpha), width=2)
    cv.alpha_composite(ov)


def bottom_shade(cv, start=1500):
    a = np.zeros((H, W), np.float32)
    a[start:] = np.linspace(0, 1, H - start)[:, None] ** 1.3 * 230
    cv.alpha_composite(Image.fromarray(np.dstack([np.full((H, W, 3), DEEP), a]).astype(np.uint8), "RGBA"))


def thumb_notification(person):
    cv = bg()
    place(cv, person)
    bottom_shade(cv)
    d = ImageDraw.Draw(cv)
    # lock screen clock
    t = font(POPPINS.replace("SemiBold", "Regular"), 210)
    tw = d.textlength("6:00", font=t)
    d.text(((W - tw) / 2, 70), "6:00", font=t, fill=(255, 255, 255, 235))
    sub = text_img("آج صبح", NASTALIQ, 44, (255, 255, 255, 220), shadow=False)
    cv.alpha_composite(sub, ((W - sub.width) // 2, 300))
    # notification
    box = (50, 450, W - 50, 860)
    glass(cv, box)
    d = ImageDraw.Draw(cv)
    check(d, W - 130, 525, 40)
    app = text_img("نعمتوں کی اطلاع · ابھی", NASTALIQ, 30, (255, 255, 255, 200), shadow=False)
    cv.alpha_composite(app, (W - 190 - app.width, 482))
    msg = text_img("پوری دنیا آپ کے نام ہو چکی ہے", NASTALIQ, 56, IVORY, shadow=True)
    cv.alpha_composite(msg, ((W - msg.width) // 2, 545))
    # chips
    x = W - (W - 3 * 170) // 2 + 20
    for word in ["امن", "صحت", "روزی"]:
        ti = text_img(word, NASTALIQ, 36, DEEP, shadow=False)
        w = ti.width + 40
        d = ImageDraw.Draw(cv)
        d.rounded_rectangle([x - w, 772, x, 830], 29, fill=GOLD_HI + (255,))
        check(d, x - w + 30, 801, 16, fill=DEEP, mark=GOLD_HI)
        cv.alpha_composite(ti, (x - ti.width - 6, 801 - ti.height // 2 - 2))
        x -= w + 26
    # big bottom line
    line = text_img("تین نعمتیں = پوری دنیا", NASTALIQ, 92, IVORY, stroke=0)
    cv.alpha_composite(line, ((W - line.width) // 2, 1560))
    d = ImageDraw.Draw(cv)
    d.line([(W / 2 - 220, 1835), (W / 2 + 220, 1835)], fill=GOLD_HI, width=4)
    return cv


def thumb_player(person):
    cv = bg((8, 20, 38), (40, 52, 70))
    place(cv, person)
    bottom_shade(cv, 1400)
    d = ImageDraw.Draw(cv)
    # headline
    hl = text_img("لمحۂ موجود میں", NASTALIQ, 80, IVORY)
    hl2 = text_img("جینا سیکھیے", NASTALIQ, 104, GOLD_HI)
    cv.alpha_composite(hl, ((W - hl.width) // 2, 10))
    cv.alpha_composite(hl2, ((W - hl2.width) // 2, 165))
    # player bar
    y = 640
    glass(cv, (50, y - 95, W - 50, y + 215), radius=40, alpha=120)
    d = ImageDraw.Draw(cv)
    # progress line: past (dim) | now (gold dot) | future (dim)
    d.line([(110, y + 175), (W - 110, y + 175)], fill=(255, 255, 255, 70), width=8)
    d.line([(W / 2, y + 175), (W - 110, y + 175)], fill=(255, 255, 255, 150), width=8)   # RTL: past on the right
    d.ellipse([W / 2 - 18, y + 157, W / 2 + 18, y + 193], fill=GOLD_HI)
    # ⏪ / ⏩ shapes
    def tri(cx, cy, s, left, fill):
        k = -1 if left else 1
        d.polygon([(cx + k * s, cy), (cx - k * s * 0.6, cy - s * 0.9), (cx - k * s * 0.6, cy + s * 0.9)], fill=fill)
    dim = (255, 255, 255, 110)
    tri(W - 200, y, 26, False, dim); tri(W - 240, y, 26, False, dim)          # past = rewind side (right, RTL)
    tri(200, y, 26, True, dim); tri(240, y, 26, True, dim)                     # future = forward side (left)
    past = text_img("ماضی", NASTALIQ, 40, (255, 255, 255, 140), shadow=False)
    fut = text_img("مستقبل", NASTALIQ, 40, (255, 255, 255, 140), shadow=False)
    cv.alpha_composite(past, (W - 280 - past.width, y - past.height // 2 - 4))
    cv.alpha_composite(fut, (280, y - fut.height // 2 - 4))
    # play / now
    d.ellipse([W / 2 - 70, y - 70, W / 2 + 70, y + 70], fill=GOLD_HI)
    d.polygon([(W / 2 - 22, y - 36), (W / 2 - 22, y + 36), (W / 2 + 38, y)], fill=DEEP)
    now = text_img("ابھی", NASTALIQ, 44, GOLD_HI, shadow=False)
    cv.alpha_composite(now, ((W - now.width) // 2, y + 45))
    # LIVE badge
    d.rounded_rectangle([W / 2 + 85, y - 95, W / 2 + 205, y - 50], 10, fill=(214, 40, 40, 255))
    lf = font(POPPINS, 30)
    d.text((W / 2 + 104, y - 95), "LIVE", font=lf, fill=(255, 255, 255))
    # bottom line
    line = text_img("نہ ماضی کا غم · نہ کل کا خوف", NASTALIQ, 64, IVORY)
    cv.alpha_composite(line, ((W - line.width) // 2, 1620))
    return cv


if __name__ == "__main__":
    person = cutout(sys.argv[1])
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [("notification", thumb_notification), ("player", thumb_player)]:
        p = os.path.join(OUT, f"thumb_{name}.jpg")
        fn(person).convert("RGB").save(p, quality=92)
        print(p)
