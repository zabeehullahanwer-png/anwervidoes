"""Premium 9:16 reel samples from the green-screen recordings (Facebook first).

  python3 brand/make_reel_samples.py [style ...]   styles: library arches frame cinematic
  -> videos/edited/sample_<style>.mp4  (1080x1920, 30 fps, ~12-15 s)

One edit (CLIPS: source file + in/out, taken from the two takes) is keyed once and then placed in
several looks so the user can choose:
  library / arches : the presenter inside a rendered vertical studio (brand/studio/plates/<set>_v_bg.png)
  frame            : "Facebook frame" — headline on top, a gold-bordered 16:9 studio card in the middle,
                     keyword medallions below
  cinematic        : the presenter over a navy set with a slowly turning gold rosette and light rays
Keyword medallions (one big Urdu word in a gold ring, with a turning dotted ring and side rules) replace
running subtitles, as the user asked: only the key words appear on screen.
Keying: green dominance key (black cap, beard and brown kurta stay solid) x MODNet person matte, so the
carved chair top and set bits outside the presenter drop out.  No music; the voice is cleaned and levelled.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RAW = os.path.join(ROOT, "videos", "raw")
OUT = os.path.join(ROOT, "videos", "edited")
WORK = os.path.join(ROOT, "videos", "work", "reel_samples")
PLATES = os.path.join(HERE, "studio", "plates")
FONTS = os.path.join(ROOT, ".claude", "skills", "dai-video-editor", "assets", "fonts")
NASTALIQ = os.path.join(FONTS, "NotoNastaliqUrdu-Bold.ttf")
AMIRI = os.path.join(FONTS, "Amiri-Bold.ttf")
POPPINS = os.path.join(FONTS, "Poppins-SemiBold.ttf")
MODNET = os.environ.get("MODNET_ONNX", "")

W, H, FPS = 1080, 1920, 30
KW, KH = 1600, 900                        # keying resolution (source is 2560x1440)
NAVY = (15, 42, 74)
DEEP = (7, 20, 38)
IVORY = (247, 243, 234)
GOLD = (176, 141, 87)
GOLD_HI = (222, 190, 128)

# ---- the edit ---------------------------------------------------------------------------------
# (take, in, out, zoom) in source seconds. Filled from the transcripts of both takes.
CLIPS = json.loads(os.environ.get("CLIPS", "[]"))
# keyword medallions: (output time, duration, word, position 'top'|'left'|'right')
KEYWORDS = json.loads(os.environ.get("KEYWORDS", "[]"))
HOOK = os.environ.get("HOOK", "آج صبح آپ کو پوری دنیا مل گئی؟")
HEADLINE = os.environ.get("HEADLINE", "تین نعمتیں = پوری دنیا")
KICKER = os.environ.get("KICKER", "ایک حدیث · ایک منٹ")
NAME = "ذبیح اللہ لغاری"
HANDLE = "@zabeehullahleghari"
EYES = json.loads(os.environ.get("EYES", "{}"))   # take -> [ex, ey, iod] in KW x KH pixels


def font(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def ease_out_back(x, s=1.7):
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---- keying -----------------------------------------------------------------------------------

def key_clips():
    """decode every clip at KW x KH, key it, save RGBA PNG frames (cached)."""
    kdir = os.path.join(WORK, "keyed")
    stamp = os.path.join(kdir, "clips.json")
    if os.path.exists(stamp) and json.load(open(stamp)) == CLIPS:
        return kdir, sorted(f for f in os.listdir(kdir) if f.endswith(".png"))
    os.makedirs(kdir, exist_ok=True)
    for f in os.listdir(kdir):
        os.remove(os.path.join(kdir, f))
    sess = None
    if MODNET and os.path.exists(MODNET):
        import onnxruntime as ort
        sess = ort.InferenceSession(MODNET, providers=["CPUExecutionProvider"])
    n = 0
    for take, t0, t1, _ in CLIPS:
        src = os.path.join(RAW, f"VID_20261119_{take}.mp4")
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", src,
                              "-vf", f"fps={FPS},scale={KW}:{KH}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             stdout=subprocess.PIPE)
        mat = None
        i = 0
        while True:
            buf = p.stdout.read(KW * KH * 3)
            if len(buf) < KW * KH * 3:
                break
            f = np.frombuffer(buf, np.uint8).reshape(KH, KW, 3).astype(np.float32) / 255
            r, g, b = f[..., 0], f[..., 1], f[..., 2]
            d = g - np.maximum(r, b)
            a = 1 - np.clip((d - 0.10) / 0.16, 0, 1)
            if sess is not None and i % 2 == 0:            # person matte every 2nd frame (slow on CPU)
                x = np.asarray(Image.fromarray((f * 255).astype(np.uint8)).resize((672, 384), Image.BILINEAR))
                x = ((x.astype(np.float32) / 255 - 0.5) / 0.5).transpose(2, 0, 1)[None]
                m = sess.run(None, {"input": x})[0][0, 0]
                m = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).resize((KW, KH), Image.BILINEAR)
                m = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
                mat = np.clip((np.asarray(m).astype(np.float32) / 255 - 0.15) / 0.35, 0, 1)
            if mat is not None:
                a = a * mat
            am = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(
                ImageFilter.GaussianBlur(0.9))
            a = np.asarray(am).astype(np.float32) / 255
            g2 = np.minimum(g, np.maximum(r, b) + 0.015)     # green spill clamp
            # gentle grade: warm, a touch of contrast, lifted blacks
            rgb = np.dstack([r * 1.03, g2 * 0.995, b * 0.95])
            rgb = np.clip((rgb - 0.5) * 1.06 + 0.5 + 0.01, 0, 1)
            Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), "RGBA").save(
                os.path.join(kdir, f"f{n:05d}.png"), compress_level=1)
            n += 1
            i += 1
        p.wait()
    json.dump(CLIPS, open(stamp, "w"))
    return kdir, sorted(f for f in os.listdir(kdir) if f.endswith(".png"))


def clip_index():
    """output frame -> (clip number, zoom)"""
    idx = []
    for c, (_, t0, t1, z) in enumerate(CLIPS):
        idx += [(c, z)] * int(round((t1 - t0) * FPS))
    return idx


def audio(path):
    parts, labels = [], []
    for c, (take, t0, t1, _) in enumerate(CLIPS):
        parts += ["-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", os.path.join(RAW, f"VID_20261119_{take}.mp4")]
        labels.append(f"[{c}:a]afade=t=in:d=0.04,afade=t=out:st={t1 - t0 - 0.05}:d=0.05[a{c}]")
    fc = ";".join(labels) + ";" + "".join(f"[a{c}]" for c in range(len(CLIPS))) + \
        f"concat=n={len(CLIPS)}:v=0:a=1,highpass=f=80,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120," \
        f"loudnorm=I=-14:TP=-1.5,afade=t=in:d=0.15[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *parts, "-filter_complex", fc, "-map", "[a]",
                    "-ar", "48000", "-c:a", "pcm_s16le", path], check=True)


# ---- graphics ---------------------------------------------------------------------------------

def text_img(txt, path, size, fill, shadow=True, stroke=0):
    f = font(path, size)
    l, t, r, b = f.getbbox(txt, direction="rtl" if path != POPPINS else None)
    pad = 30
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    kw = dict(font=f, direction="rtl") if path != POPPINS else dict(font=f)
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - l + 3, pad - t + 5), txt, fill=(0, 0, 0, 170), **kw)
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(6)))
        d = ImageDraw.Draw(im)
    d.text((pad - l, pad - t), txt, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 120), **kw)
    return im


_cache = {}


def medallion(word, t, dur, R=170, rules=True):
    """animated keyword medallion; t = seconds since it appeared. Returns RGBA (size 4R x 2.6R)."""
    S = 2                                                # supersample
    w, h = int(R * 4.2), int(R * 2.7)
    cx, cy = w // 2, h // 2
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k_in = ease_out_back(t / 0.45)
    k_out = 1 - smooth((t - (dur - 0.3)) / 0.3)
    sc = k_in * (1 + 0.08 * (1 - k_out))
    r = R * sc
    if r < 2:
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # glow
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([(cx - r * 1.25) * S, (cy - r * 1.25) * S, (cx + r * 1.25) * S, (cy + r * 1.25) * S],
                                 fill=GOLD_HI + (90,))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(28 * S)))
    d = ImageDraw.Draw(im)
    # side rules with diamond tips
    ext = smooth((t - 0.25) / 0.45) * R * 0.95 if rules else 0
    if ext > 2:
        for sgn in (-1, 1):
            x0 = cx + sgn * (r + 18)
            x1 = x0 + sgn * ext
            d.line([(x0 * S, cy * S), (x1 * S, cy * S)], fill=GOLD_HI + (235,), width=3 * S)
            d.line([(x0 * S, (cy - 10) * S), ((x0 + sgn * ext * 0.6) * S, (cy - 10) * S)], fill=GOLD + (170,), width=1 * S)
            d.line([(x0 * S, (cy + 10) * S), ((x0 + sgn * ext * 0.6) * S, (cy + 10) * S)], fill=GOLD + (170,), width=1 * S)
            q = 9
            d.polygon([((x1 + sgn * q) * S, cy * S), (x1 * S, (cy - q) * S), ((x1 - sgn * q) * S, cy * S),
                       (x1 * S, (cy + q) * S)], fill=GOLD_HI + (255,))
    # disc: navy radial
    disc = Image.new("RGBA", im.size, (0, 0, 0, 0))
    yy, xx = np.mgrid[0:h * S, 0:w * S].astype(np.float32)
    dist = np.sqrt((xx - cx * S) ** 2 + (yy - (cy - r * 0.35) * S) ** 2) / (r * S * 1.6)
    col = np.clip(1 - dist, 0, 1)[..., None]
    rgb = np.array(DEEP, np.float32) * (1 - col) + np.array((28, 64, 108), np.float32) * col
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=245)
    disc = Image.fromarray(np.dstack([rgb, np.asarray(mask, np.float32)]).astype(np.uint8), "RGBA")
    im = Image.alpha_composite(im, disc)
    d = ImageDraw.Draw(im)
    # rings: one draws on (arc sweep), one thin inner
    sweep = 360 * smooth(t / 0.55)
    d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], -90, -90 + sweep, fill=GOLD_HI + (255,), width=6 * S)
    ri = r - 14
    d.ellipse([(cx - ri) * S, (cy - ri) * S, (cx + ri) * S, (cy + ri) * S], outline=GOLD + (200,), width=2 * S)
    # turning dotted ring (24 diamonds)
    ro = r + 22
    rot = t * 18
    for i in range(24):
        a = math.radians(i * 15 + rot)
        px, py = cx + ro * math.cos(a), cy + ro * math.sin(a)
        q = 4.5 if i % 3 == 0 else 2.5
        d.polygon([((px + q) * S, py * S), (px * S, (py - q) * S), ((px - q) * S, py * S), (px * S, (py + q) * S)],
                  fill=GOLD_HI + (int(230 * min(1, t / 0.6)),))
    im = im.resize((w, h), Image.LANCZOS)
    # the word
    key = (word, R)
    if key not in _cache:
        size = int(R * 0.62)
        ti = text_img(word, NASTALIQ, size, IVORY, shadow=False)
        maxw = R * 1.62
        if ti.width - 60 > maxw:
            size = int(size * maxw / (ti.width - 60))
            ti = text_img(word, NASTALIQ, size, IVORY, shadow=False)
        _cache[key] = ti
    ti = _cache[key]
    ts = max(0.01, sc)
    tw, th = max(1, int(ti.width * ts)), max(1, int(ti.height * ts))
    tt = ti.resize((tw, th), Image.LANCZOS)
    # light sweep over the word
    sx = (t - 0.5) / 0.6
    if 0 < sx < 1:
        band = np.zeros((th, tw), np.float32)
        x = np.arange(tw)[None, :] - (sx * (tw + th) - th)
        y = np.arange(th)[:, None] * 0.5
        band = np.clip(1 - np.abs(x + y) / 40, 0, 1) * 0.8
        arr = np.asarray(tt).astype(np.float32)
        arr[..., :3] = arr[..., :3] * (1 - band[..., None]) + np.array(GOLD_HI) * band[..., None]
        tt = Image.fromarray(arr.astype(np.uint8), "RGBA")
    im.alpha_composite(tt, (cx - tw // 2, cy - th // 2 + int(R * 0.06)))
    if k_out < 1:
        a = np.asarray(im).copy()
        a[..., 3] = (a[..., 3] * k_out).astype(np.uint8)
        im = Image.fromarray(a, "RGBA")
    return im


def hook_card(t, dur):
    """top headline for the first seconds: kicker + big hook line, slides down and fades."""
    k = smooth(t / 0.4) * (1 - smooth((t - dur + 0.35) / 0.35))
    if k <= 0:
        return None, 0
    ti = text_img(HOOK, NASTALIQ, 64, IVORY, stroke=0)
    w = min(W - 60, ti.width + 80)
    box = Image.new("RGBA", (W, ti.height + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    x0 = (W - w) // 2
    d.rounded_rectangle([x0, 10, x0 + w, box.height - 10], 34, fill=DEEP + (215,), outline=GOLD + (230,), width=3)
    box.alpha_composite(ti, ((W - ti.width) // 2, (box.height - ti.height) // 2))
    a = np.asarray(box).copy()
    a[..., 3] = (a[..., 3] * k).astype(np.uint8)
    return Image.fromarray(a, "RGBA"), int(-40 * (1 - k))


def lower_third(t):
    """name strip, slides in from the right (RTL), ~5 s"""
    k = smooth(t / 0.5) * (1 - smooth((t - 4.6) / 0.4))
    if k <= 0:
        return None
    n = text_img(NAME, NASTALIQ, 50, IVORY)
    h = text_img(HANDLE, POPPINS, 26, GOLD_HI, shadow=False)
    w = max(n.width, h.width) + 60
    im = Image.new("RGBA", (w + 20, n.height + h.height - 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 10, w, im.height - 4], 22, fill=DEEP + (210,))
    d.rectangle([w - 8, 18, w - 2, im.height - 12], fill=GOLD_HI + (255,))
    im.alpha_composite(n, (w - n.width - 20, -10))
    im.alpha_composite(h, (w - h.width - 26, n.height - 50))
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * k).astype(np.uint8)
    return Image.fromarray(a, "RGBA"), int(60 * (1 - k))


def rosette_layer(t, size=1500):
    """slowly turning 16-point gold rosette with fine lines (cinematic style background element)."""
    key = ("ros", size)
    if key not in _cache:
        S = 1
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        c = size / 2
        for ring, (rad, alpha) in enumerate([(0.48, 70), (0.40, 55), (0.30, 45), (0.20, 40)]):
            R = size * rad
            pts = []
            for i in range(32):
                a = math.pi * 2 * i / 32 + (ring % 2) * math.pi / 32
                rr = R if i % 2 == 0 else R * 0.80
                pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
            d.polygon(pts, outline=GOLD_HI + (alpha,), width=2)
            d.ellipse([c - R * 0.80, c - R * 0.80, c + R * 0.80, c + R * 0.80], outline=GOLD + (alpha // 2,), width=1)
        for i in range(16):
            a = math.pi * 2 * i / 16
            d.line([(c, c), (c + size * 0.48 * math.cos(a), c + size * 0.48 * math.sin(a))], fill=GOLD + (28,), width=1)
        _cache[key] = im
    return _cache[key].rotate(t * 3.0, resample=Image.BICUBIC)


def cinematic_bg(t):
    key = "cine_bg"
    if key not in _cache:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dist = np.sqrt((xx - W / 2) ** 2 + ((yy - 800) * 0.8) ** 2) / 1100
        k = np.clip(1 - dist, 0, 1)[..., None] ** 1.6
        rgb = np.array(DEEP, np.float32) * (1 - k) + np.array((34, 74, 120), np.float32) * k
        # light rays from above
        ang = np.arctan2(xx - W / 2, yy + 400)
        rays = (0.5 + 0.5 * np.cos(ang * 22)) ** 6 * np.clip(1 - yy / 1500, 0, 1) * 18
        rgb = rgb + rays[..., None] * np.array([1.0, 0.85, 0.6])
        _cache[key] = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    bg = _cache[key].copy()
    ros = rosette_layer(t)
    bg.alpha_composite(ros, ((W - ros.width) // 2, 820 - ros.height // 2))
    return bg


def frame_bg():
    key = "frame_bg"
    if key not in _cache:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        k = np.clip(1 - np.sqrt((xx - W / 2) ** 2 + (yy - 960) ** 2) / 1300, 0, 1)[..., None]
        rgb = np.array(DEEP, np.float32) * (1 - k) + np.array(NAVY, np.float32) * k
        bg = Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")
        # faint lattice of 8-point stars
        d = ImageDraw.Draw(bg)
        step = 120
        for y in range(-step, H + step, step):
            for x in range(-step, W + step, step):
                ox = (y // step % 2) * step / 2
                cx, cy = x + ox, y
                for a0 in (0, 45):
                    pts = [(cx + 34 * math.cos(math.radians(a0 + i * 90)), cy + 34 * math.sin(math.radians(a0 + i * 90)))
                           for i in range(4)]
                    d.polygon(pts, outline=GOLD + (26,))
        _cache[key] = bg
    return _cache[key].copy()


# ---- composition ------------------------------------------------------------------------------

def place_person(canvas, person, s, ox, oy):
    pw, ph = int(KW * s), int(KH * s)
    p = person.resize((pw, ph), Image.BILINEAR)
    canvas.alpha_composite(p, (int(ox), int(oy))) if ox >= 0 and oy >= 0 else canvas.paste(p, (int(ox), int(oy)), p)


def eyes_of(clip):
    take = CLIPS[clip][0]
    return EYES.get(take, [880, 205, 90])


GARBAGE = json.loads(os.environ.get("GARBAGE", "{}"))   # take -> [[x0,y0,x1,y1], ...] chair-carving boxes


def clean(person, clip):
    """drop the light carved chair top beside the beard: inside the given boxes, pixels brighter than the
    beard/kurta lose their alpha (beard is near-black, kurta mid-brown, carving light gold)."""
    boxes = GARBAGE.get(CLIPS[clip][0], [])
    if not boxes:
        return person
    import cv2
    a = np.asarray(person).copy()
    for x0, y0, x1, y1 in boxes:
        reg = a[y0:y1, x0:x1].astype(np.float32) / 255
        lum = reg[..., 0] * 0.3 + reg[..., 1] * 0.59 + reg[..., 2] * 0.11
        light = ((lum > 0.36) & (reg[..., 3] > 0.3)).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(light, 8)
        kill = np.zeros_like(light)
        hh, ww = light.shape
        for c in range(1, n):
            x, y, w, h = st[c, :4]
            # a light patch that reaches the top or right edge of the box belongs to the face/cheek: keep it;
            # an island inside the box is the carved chair top: drop it
            if y > 0 and x + w < ww:
                kill[lab == c] = 255
        k = np.asarray(Image.fromarray(kill).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5)))
        k = k.astype(np.float32) / 255
        a[y0:y1, x0:x1, 3] = (a[y0:y1, x0:x1, 3] * (1 - k)).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def compose(style, fi, person, clip, zoom, tsec):
    person = clean(person, clip)
    ex, ey, iod = eyes_of(clip)
    if style in ("library", "arches", "brand"):
        if ("plate", style) not in _cache:
            _cache[("plate", style)] = Image.open(os.path.join(PLATES, f"{style}_v_bg.png")).convert("RGBA").resize((W, H))
            _cache[("meta", style)] = json.load(open(os.path.join(PLATES, f"{style}_v_meta.json")))
        cv = _cache[("plate", style)].copy()
        meta = _cache[("meta", style)]
        s = max(1.38, (H - meta["eye_y"]) / (KH - ey) + 0.02)
        place_person(cv, person, s, W / 2 - ex * s, meta["eye_y"] - ey * s)
        # bottom shade so lower graphics read
        sh = _cache.get("shade")
        if sh is None:
            a = np.zeros((H, W), np.float32)
            a[1300:] = np.linspace(0, 1, H - 1300)[:, None] ** 1.5 * 170
            sh = Image.fromarray(np.dstack([np.zeros((H, W, 3)), a]).astype(np.uint8), "RGBA")
            _cache["shade"] = sh
        cv.alpha_composite(sh)
        cv = punch(cv, zoom, (W / 2, meta["eye_y"]))
        kw_y = 520
    elif style == "cinematic":
        cv = cinematic_bg(tsec)
        eye_y = 1010
        s = max(1.38, (H - eye_y) / (KH - ey) + 0.02)
        # soft rim light: blurred gold copy of the matte behind the presenter
        pw, ph = int(KW * s), int(KH * s)
        p = person.resize((pw, ph), Image.BILINEAR)
        rim = Image.new("RGBA", p.size, GOLD_HI + (0,))
        rim.putalpha(p.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.55)))
        ox, oy = int(W / 2 - ex * s), int(eye_y - ey * s)
        cv.paste(rim, (ox, oy - 4), rim)
        cv.paste(p, (ox, oy), p)
        cv = punch(cv, zoom, (W / 2, eye_y))
        kw_y = 520
    elif style == "frame":
        cv = frame_bg()
        # studio card 16:9 (horizontal library plate)
        if ("hplate",) not in _cache:
            _cache[("hplate",)] = Image.open(os.path.join(PLATES, "library_bg.png")).convert("RGBA")
            _cache[("hfg",)] = Image.open(os.path.join(PLATES, "library_fg.png")).convert("RGBA")
            _cache[("hmeta",)] = json.load(open(os.path.join(PLATES, "library_meta.json")))
        card = _cache[("hplate",)].copy()
        meta = _cache[("hmeta",)]
        s = meta["ppm"] * 0.063 / iod
        place_person(card, person, s, meta["eye_x"] - ex * s, meta["eye_y"] - ey * s)
        card.alpha_composite(_cache[("hfg",)])
        card = punch(card, 1.9 * zoom, (meta["eye_x"], meta["eye_y"]))
        cw, ch = 1000, 562
        card = card.resize((cw, ch), Image.LANCZOS)
        m = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, cw - 1, ch - 1], 30, fill=255)
        card.putalpha(m)
        y0 = 640
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([40, y0 + 18, 40 + cw, y0 + ch + 18], 30, fill=(0, 0, 0, 160))
        cv.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
        cv.alpha_composite(card, (40, y0))
        ImageDraw.Draw(cv).rounded_rectangle([38, y0 - 2, 42 + cw, y0 + ch + 2], 32, outline=GOLD_HI + (255,), width=4)
        # headline area
        if "frame_head" not in _cache:
            k = text_img(KICKER, NASTALIQ, 38, GOLD_HI, shadow=False)
            hl = text_img(HEADLINE, NASTALIQ, 76, IVORY)
            _cache["frame_head"] = (k, hl)
        k, hl = _cache["frame_head"]
        kk = smooth(tsec / 0.6)
        cv.alpha_composite(k, ((W - k.width) // 2, 150 + int(20 * (1 - kk))))
        cv.alpha_composite(hl, ((W - hl.width) // 2, 250 + int(30 * (1 - kk))))
        d = ImageDraw.Draw(cv)
        d.line([(W / 2 - 160 * kk, 600), (W / 2 + 160 * kk, 600)], fill=GOLD + (220,), width=2)
        hb = _cache.get("frame_handle") or text_img(HANDLE, POPPINS, 30, GOLD_HI, shadow=False)
        _cache["frame_handle"] = hb
        cv.alpha_composite(hb, ((W - hb.width) // 2, 1800))
        kw_y = 1470
    else:
        raise SystemExit(style)
    # overlays (in output time)
    if style != "frame":
        hk, dy = hook_card(tsec, 3.2) if HOOK else (None, 0)
        if hk is not None:
            cv.alpha_composite(hk, (0, 200 + dy))
        lt = lower_third(tsec - 1.0)
        if lt is not None:
            im, dx = lt
            cv.alpha_composite(im, (W - im.width - 30 + dx, 1560))
    for (t0, dur, word, pos, kind) in KEYWORDS:
        if t0 <= tsec < t0 + dur:
            if kind == "banner":
                bn = banner(word, tsec - t0, dur)
                cv.alpha_composite(bn, (int(W / 2 - bn.width / 2), int(kw_y + 215 - bn.height / 2)))
                continue
            row = kind == "row"
            R = (100 if row else (150 if style == "frame" else 165))
            md = medallion(word, tsec - t0, dur, R=R, rules=not row)
            cx = {"top": W / 2, "left": W * 0.2, "right": W * 0.8, "center": W / 2}[pos]
            cv.alpha_composite(md, (int(cx - md.width / 2), int(kw_y - md.height / 2)))
    return cv


def banner(txt, t, dur):
    k = ease_out_back(t / 0.4)
    ko = 1 - smooth((t - (dur - 0.25)) / 0.25)
    ti = text_img(txt, NASTALIQ, 70, IVORY, shadow=False)
    w, h = ti.width + 90, ti.height + 10
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 20, w - 4, h - 20], (h - 40) // 2, fill=(120, 92, 48, 235), outline=GOLD_HI + (255,), width=4)
    im.alpha_composite(ti, ((w - ti.width) // 2, (h - ti.height) // 2 - 4))
    sc = max(0.05, k)
    im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * max(0, min(1, ko))).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def punch(img, zoom, center):
    if abs(zoom - 1) < 1e-3:
        return img
    w, h = img.size
    cw, ch = w / zoom, h / zoom
    # keep the eye line where it is, so a punch-in never pushes the head into the graphics above
    x0 = min(max(center[0] - center[0] / zoom, 0), w - cw)
    y0 = min(max(center[1] - center[1] / zoom, 0), h - ch)
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BICUBIC)


def render(style, kdir, frames, wav, seconds=None):
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, f"sample_{style}.mp4")
    idx = clip_index()
    n = min(len(frames), len(idx))
    if seconds:
        n = min(n, int(seconds * FPS))
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", wav,
                          "-vf", f"vignette=angle=PI/5,fade=t=in:d=0.3,fade=t=out:st={n / FPS - 0.4}:d=0.4,format=yuv420p",
                          "-af", f"afade=t=out:st={n / FPS - 0.4}:d=0.4",
                          "-t", f"{n / FPS}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for fi in range(n):
        person = Image.open(os.path.join(kdir, frames[fi])).convert("RGBA")
        clip, zoom = idx[fi]
        cv = compose(style, fi, person, clip, zoom, fi / FPS)
        p.stdin.write(cv.convert("RGB").tobytes())
    p.stdin.close()
    p.wait()
    print(out)


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    kdir, frames = key_clips()
    wav = os.path.join(WORK, "voice.wav")
    audio(wav)
    styles = [a for a in sys.argv[1:] if not a.startswith("--")] or ["library", "arches", "frame", "cinematic"]
    still = "--still" in sys.argv
    for st in styles:
        if still:
            idx = clip_index()
            for t in json.loads(os.environ.get("STILLS", "[1.0, 6.0]")):
                fi = int(t * FPS)
                person = Image.open(os.path.join(kdir, frames[fi])).convert("RGBA")
                compose(st, fi, person, idx[fi][0], idx[fi][1], t).convert("RGB").save(
                    os.path.join(WORK, f"still_{st}_{t:.1f}.jpg"), quality=88)
        else:
            render(st, kdir, frames, wav)
