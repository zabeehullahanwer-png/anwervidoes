"""Full 9:16 reel from the green-screen takes, driven by an edit plan (JSON).

  python3 brand/make_reel.py brand/edits/<plan>.json [--still t1,t2,...] [--draft]
  -> videos/edited/<plan>.mp4   (1080x1920, 30 fps)

Look (chosen by the user after the samples):
  * the presenter inside the vertical library studio, medium-wide ("W": the whole presenter and the room)
    and close ("C": a push-in on the face) shots; the chair stays — only the green screen is keyed
  * editorial kinetic type instead of subtitles: one key word at a time in gold Nastaliq that wipes in
    right-to-left with a drawn gold rule; numbered lists; glass cards for ayat and ahadith;
    full-screen ayah cards (the presenter's own audio is muted there)
  * voice cleaned and levelled; an optional vocal-only nasheed bed (NASHEED=path) ducked under the voice
Plan times are SOURCE times of a take; pauses longer than 0.45 s inside a segment are shortened,
and overlays are anchored to source times so they follow the cuts.
"""
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_reel_samples import (AMIRI, DEEP, GOLD, GOLD_HI, HANDLE, IVORY, NAME, NASTALIQ, NAVY,  # noqa: E402
                               POPPINS, font, smooth, text_img)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RAW = os.path.join(ROOT, "videos", "raw")
OUT = os.path.join(ROOT, "videos", "edited")
PLATES = os.path.join(HERE, "studio", "plates")
W, H, FPS = 1080, 1920, 30
KW, KH = 1600, 900
ZOOM = {"W": 1.55, "M": 1.8, "C": 2.1}
_cache = {}


def src_path(take):
    return os.path.join(RAW, f"VID_20261119_{take}.mp4")


# ---- audio analysis / cut list ------------------------------------------------------------------

def take_wav(take, work):
    p = os.path.join(work, f"{take}_16k.wav")
    if not os.path.exists(p):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src_path(take), "-vn", "-ac", "1", "-ar", "16000", p],
                       check=True)
    with wave.open(p, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def energy(x, hop=320):           # 20 ms frames, dBFS
    n = len(x) // hop
    e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-10)
    return 20 * np.log10(e)


def snap(edb, t, lo=-0.12, hi=0.12):
    """move a cut point to the quietest 20 ms frame nearby"""
    a, b = max(0, int((t + lo) * 50)), min(len(edb) - 1, int((t + hi) * 50))
    return (a + int(np.argmin(edb[a:b + 1]))) / 50 if b > a else t


def subclips(edb, t0, t1, thr=-42, min_gap=0.45, keep=0.24):
    """split [t0,t1] at long pauses; each pause is shortened to `keep` seconds"""
    a, b = int(t0 * 50), int(t1 * 50)
    quiet = edb[a:b] < thr
    out, start, i = [], t0, 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) / 50 >= min_gap and i > 0 and j < len(quiet):
                g0, g1 = t0 + i / 50, t0 + j / 50
                out.append((start, g0 + keep * 0.55))
                start = g1 - keep * 0.45
            i = j
        else:
            i += 1
    out.append((start, t1))
    return [(x, y) for x, y in out if y - x > 0.12]


def build_cuts(plan, work):
    """-> list of pieces: {"take","in","out","shot"} or {"card":..., "dur"}; plus a source->output time map"""
    edbs = {}
    pieces = []
    for seg in plan["segments"]:
        if "card" in seg:
            pieces.append({"card": seg["card"], "dur": seg["dur"]})
            continue
        tk = seg["take"]
        if tk not in edbs:
            edbs[tk] = energy(take_wav(tk, work))
        e = edbs[tk]
        t0, t1 = snap(e, seg["in"]), snap(e, seg["out"])
        subs = subclips(e, t0, t1) if seg.get("trim", True) else [(t0, t1)]
        shots = seg.get("shots", ["W"])
        for k, (x, y) in enumerate(subs):
            # frame-exact lengths so audio and video stay in step
            n = max(1, int(round((y - x) * FPS)))
            pieces.append({"take": tk, "in": x, "out": x + n / FPS, "shot": shots[k % len(shots)],
                           "push": seg.get("push", False)})
    t = 0.0
    for p in pieces:
        p["t"] = t
        t += p["dur"] if "card" in p else p["out"] - p["in"]
    return pieces, t


def out_time(pieces, take, ts):
    for p in pieces:
        if "card" not in p and p["take"] == take and p["in"] - 0.05 <= ts < p["out"] + 0.05:
            return p["t"] + max(0.0, ts - p["in"])
    best = None
    for p in pieces:                                   # inside a removed pause: next kept piece
        if "card" not in p and p["take"] == take and p["in"] > ts:
            if best is None or p["in"] < best["in"]:
                best = p
    return best["t"] if best else None


def make_audio(pieces, total, work, path):
    parts, labels, n = [], [], 0
    for p in pieces:
        if "card" in p:
            parts += ["-f", "lavfi", "-t", f"{p['dur']}", "-i", "anullsrc=r=48000:cl=mono"]
            labels.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=mono[a{n}]")
        else:
            d = p["out"] - p["in"]
            parts += ["-ss", f"{p['in']}", "-t", f"{d}", "-i", src_path(p["take"])]
            labels.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=mono,atrim=0:{d},asetpts=PTS-STARTPTS,"
                          f"afade=t=in:d=0.03,afade=t=out:st={max(0, d - 0.04)}:d=0.04[a{n}]")
        n += 1
    fc = ";".join(labels) + ";" + "".join(f"[a{i}]" for i in range(n)) + \
        f"concat=n={n}:v=0:a=1,highpass=f=80,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=150," \
        f"loudnorm=I=-14:TP=-1.5:LRA=7,afade=t=in:d=0.1,afade=t=out:st={total - 0.6}:d=0.6[v]"
    nasheed = os.environ.get("NASHEED")
    if nasheed and os.path.exists(nasheed):
        parts += ["-stream_loop", "-1", "-i", nasheed]
        fc += (f";[{n}:a]aformat=sample_rates=48000:channel_layouts=mono,atrim=0:{total},volume=0.22,"
               f"afade=t=in:d=1.5,afade=t=out:st={total - 2}:d=2[bed];[v]asplit[v1][vk];"
               f"[bed][vk]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[bd];"
               f"[v1][bd]amix=inputs=2:normalize=0[a]")
    else:
        fc = fc[:-3] + "[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *parts, "-filter_complex", fc, "-map", "[a]", "-t", f"{total}",
                    "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", path], check=True)


# ---- keying -----------------------------------------------------------------------------------

def key(frame):
    f = frame.astype(np.float32) / 255
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    d = g - np.maximum(r, b)
    a = 1 - np.clip((d - 0.10) / 0.16, 0, 1)
    am = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.9))
    a = np.asarray(am).astype(np.float32) / 255
    g2 = np.minimum(g, np.maximum(r, b) + 0.015)
    rgb = np.dstack([r * 1.03, g2 * 0.995, b * 0.95])
    rgb = np.clip((rgb - 0.5) * 1.06 + 0.51, 0, 1)
    return Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), "RGBA")


def frames_of(p):
    n = int(round((p["out"] - p["in"]) * FPS))
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{p['in']}", "-i", src_path(p["take"]), "-frames:v", str(n),
                           "-vf", f"fps={FPS},scale={KW}:{KH}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    last = None
    for _ in range(n):
        buf = pr.stdout.read(KW * KH * 3)
        if len(buf) == KW * KH * 3:
            last = np.frombuffer(buf, np.uint8).reshape(KH, KW, 3)
        if last is not None:
            yield last
    pr.wait()


# ---- studio composition -----------------------------------------------------------------------

PLATE = os.environ.get("PLATE", "library_vd")          # 9:16 studio camera behind the desk (bg + fg layers)
EYE_Y = {"W": 860, "M": 870, "C": 880}               # where the eyes sit on screen for each shot


def plate():
    if "plate" not in _cache:
        _cache["plate"] = Image.open(os.path.join(PLATES, f"{PLATE}_bg.png")).convert("RGB")
        fgp = os.path.join(PLATES, f"{PLATE}_fg.png")
        _cache["fg"] = Image.open(fgp).convert("RGBA") if os.path.exists(fgp) else None
        _cache["meta"] = json.load(open(os.path.join(PLATES, f"{PLATE}_meta.json")))
    return _cache["plate"], _cache["meta"]


def studio_frame(person, eyes, z, eye_y):
    """studio camera zoomed by z; the presenter sits between the room and the desk layer, eyes at eye_y"""
    pl, meta = plate()
    fg = _cache["fg"]
    ex, ey, iod = eyes
    s = meta["ppm"] * 0.063 / iod
    E = (meta["eye_x"], meta["eye_y"])
    x0, y0 = E[0] - (W / 2) / z, E[1] - eye_y / z
    box = (int(round(x0)), int(round(y0)), int(round(x0 + W / z)), int(round(y0 + H / z)))
    bg = pl.crop(box).resize((W, H), Image.BICUBIC).convert("RGBA")
    ss = s * z
    pw, ph = int(KW * ss), int(KH * ss)
    p = person.resize((pw, ph), Image.BILINEAR)
    bg.paste(p, (int(W / 2 - ex * ss), int(eye_y - ey * ss)), p)
    if fg is not None:
        bg.alpha_composite(fg.crop(box).resize((W, H), Image.BICUBIC))
    return bg


def shade():
    if "shade" not in _cache:
        a = np.zeros((H, W), np.float32)
        a[:420] = np.linspace(1, 0, 420)[:, None] ** 1.6 * 120          # top: headroom for type
        a[1500:] = np.linspace(0, 1, H - 1500)[:, None] ** 1.5 * 150
        _cache["shade"] = Image.fromarray(np.dstack([np.zeros((H, W, 3)), a]).astype(np.uint8), "RGBA")
    return _cache["shade"]


# ---- kinetic type -----------------------------------------------------------------------------

def gold_text(txt, size, path=NASTALIQ, direction="rtl", grad=((246, 222, 170), (196, 152, 86))):
    key = ("gt", txt, size, path)
    if key in _cache:
        return _cache[key]
    f = font(path, size)
    l, t, r, b = f.getbbox(txt, direction=direction)
    pad = 40
    w, h = r - l + 2 * pad, b - t + 2 * pad
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), txt, font=f, fill=255, direction=direction)
    ys = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array(grad[0], np.float32), np.array(grad[1], np.float32)
    rgb = np.broadcast_to(top * (1 - ys) + bot * ys, (h, w, 3))
    im = Image.fromarray(np.dstack([rgb, np.asarray(m)]).astype(np.uint8), "RGBA")
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(m.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.75)))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 6))
    out.alpha_composite(im)
    _cache[key] = out
    return out


def plain_text(txt, size, fill=IVORY, path=NASTALIQ, direction="rtl"):
    key = ("pt", txt, size, fill, path)
    if key not in _cache:
        f = font(path, size)
        l, t, r, b = f.getbbox(txt, direction=direction)
        pad = 30
        w, h = r - l + 2 * pad, b - t + 2 * pad
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).text((pad - l, pad - t), txt, font=f, fill=255, direction=direction)
        im = Image.new("RGBA", (w, h), fill + (0,))
        im.putalpha(m)
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sh.putalpha(m.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.8)))
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.alpha_composite(sh, (0, 4))
        out.alpha_composite(im)
        _cache[key] = out
    return _cache[key]


def wipe(im, k, rtl=True, soft=60):
    """reveal from the right (RTL) with a soft edge; k 0..1"""
    if k >= 1:
        return im
    w, h = im.size
    x = np.arange(w, dtype=np.float32)
    edge = (1 - k) * (w + soft) - soft if rtl else k * (w + soft)
    a = np.clip((x - edge) / soft, 0, 1) if rtl else np.clip((edge - x) / soft, 0, 1)
    arr = np.asarray(im).copy()
    arr[..., 3] = (arr[..., 3] * a[None, :]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def fade(im, k):
    if k >= 1:
        return im
    arr = np.asarray(im).copy()
    arr[..., 3] = (arr[..., 3] * max(0.0, k)).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def env(t, dur, tin=0.55, tout=0.35):
    return smooth(t / tin), 1 - smooth((t - (dur - tout)) / tout)


def draw_word(cv, ov, t, y):
    """big gold word, optional small ivory kicker above, a gold rule drawing out beneath"""
    dur = ov["dur"]
    kin, kout = env(t, dur)
    size = ov.get("size", 118)
    g = gold_text(ov["text"], size)
    if g.width > W - 80:
        g = g.resize((W - 80, int(g.height * (W - 80) / g.width)), Image.LANCZOS)
    drift = int(26 * (1 - kin) - 18 * (1 - kout))
    im = fade(wipe(g, kin), kout)
    cx = W // 2
    gy = y - g.height // 2 + drift
    if ov.get("kicker"):
        kk = plain_text(ov["kicker"], 42, (232, 222, 200))
        k2 = smooth((t - 0.15) / 0.5)
        cv.alpha_composite(fade(kk, k2 * kout), (cx - kk.width // 2, gy - kk.height + 70))
    cv.alpha_composite(im, (cx - im.width // 2, gy))
    # rule
    rk = smooth((t - 0.3) / 0.6) * kout
    if rk > 0:
        d = ImageDraw.Draw(cv)
        ry = gy + g.height - 52
        half = min(g.width * 0.42, 300) * rk
        d.line([(cx - half, ry), (cx + half, ry)], fill=GOLD_HI + (int(235 * kout),), width=3)
        q = 7 * rk
        d.polygon([(cx, ry - q), (cx + q, ry), (cx, ry + q), (cx - q, ry)], fill=GOLD_HI + (int(255 * kout),))


def draw_list(cv, items, t_out, y0):
    """numbered list, right-aligned (RTL): each row slides in at its own time"""
    d = ImageDraw.Draw(cv)
    for i, it in enumerate(items):
        t = t_out - it["t"]
        if t < 0 or t_out > it["end"]:
            continue
        kin, kout = env(t, it["end"] - it["t"], 0.5, 0.4)
        y = y0 + i * 150
        num = gold_text("۱۲۳۴۵"[i], 104)
        word = plain_text(it["text"], 84)
        x_right = W - 150 + int(60 * (1 - kin))
        a = kin * kout
        cv.alpha_composite(fade(num, a), (x_right - num.width // 2 + 40, y - num.height // 2))
        cv.alpha_composite(fade(wipe(word, kin), kout), (x_right - 70 - word.width, y - word.height // 2 + 4))
        lw = (560 * smooth((t - 0.2) / 0.5)) * kout
        d.line([(x_right - 40 - lw, y + 58), (x_right - 40, y + 58)], fill=GOLD + (int(200 * a),), width=2)


def glass(cv, box, radius=36, tint=(10, 24, 44, 150)):
    x0, y0, x1, y1 = [int(v) for v in box]
    reg = cv.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(22))
    m = Image.new("L", reg.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, reg.width - 1, reg.height - 1], radius, fill=255)
    cv.paste(reg, (x0, y0), m)
    ov = Image.new("RGBA", cv.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle([x0, y0, x1, y1], radius, fill=tint, outline=GOLD_HI + (170,), width=2)
    cv.alpha_composite(ov)


def draw_card(cv, ov, t, y):
    """glass card for an ayah / hadith: Arabic (Amiri, gold) + reference; optional Urdu line"""
    kin, kout = env(t, ov["dur"], 0.5, 0.4)
    ar = gold_text(ov["arabic"], ov.get("size", 64), AMIRI)
    if ar.width > W - 120:
        ar = ar.resize((W - 120, int(ar.height * (W - 120) / ar.width)), Image.LANCZOS)
    ref = plain_text(ov["ref"], 36, (226, 214, 190))
    ur = plain_text(ov["urdu"], 44) if ov.get("urdu") else None
    h = ar.height - 30 + ref.height - 20 + (ur.height - 20 if ur else 0)
    box = (50, y - 10, W - 50, y + h)
    layer = cv.copy()
    glass(layer, box)
    yy = y - 20
    layer.alpha_composite(wipe(ar, smooth((t - 0.15) / 0.8)), ((W - ar.width) // 2, yy))
    yy += ar.height - 40
    if ur:
        layer.alpha_composite(fade(ur, smooth((t - 0.6) / 0.5)), ((W - ur.width) // 2, yy))
        yy += ur.height - 30
    layer.alpha_composite(fade(ref, smooth((t - 0.8) / 0.5)), ((W - ref.width) // 2, yy))
    a = kin * kout
    if a < 1:
        cv.paste(Image.blend(cv, layer, a) if a > 0 else cv, (0, 0))
    else:
        cv.paste(layer, (0, 0))


def draw_lower(cv, t):
    kin, kout = env(t, 5.0, 0.6, 0.5)
    if kout <= 0 or t < 0:
        return
    n = plain_text(NAME, 52)
    hd = plain_text(HANDLE, 26, GOLD_HI, POPPINS, None)
    x = W - 60 - n.width + int(50 * (1 - kin))
    y = 1600
    a = kin * kout
    d = ImageDraw.Draw(cv)
    d.line([(W - 60, y + 40), (W - 60, y + 170)], fill=GOLD_HI + (int(255 * a),), width=4)
    cv.alpha_composite(fade(n, a), (x - 10, y))
    cv.alpha_composite(fade(hd, a), (W - 80 - hd.width, y + n.height - 50))


def full_card(card, t, dur):
    """full-screen ayah card over the blurred studio"""
    if "fc_bg" not in _cache:
        pl, _ = plate()
        b = pl.resize((W, H)).filter(ImageFilter.GaussianBlur(18)).convert("RGBA")
        b.alpha_composite(Image.new("RGBA", (W, H), DEEP + (170,)))
        _cache["fc_bg"] = b
    cv = _cache["fc_bg"].copy()
    kin, kout = env(t, dur, 0.5, 0.5)
    ar = gold_text(card["arabic"], card.get("size", 78), AMIRI)
    if ar.width > W - 100:
        ar = ar.resize((W - 100, int(ar.height * (W - 100) / ar.width)), Image.LANCZOS)
    y = 640
    if card.get("kicker"):
        kk = plain_text(card["kicker"], 44, (230, 218, 192))
        cv.alpha_composite(fade(kk, kin * kout), ((W - kk.width) // 2, y - 170))
    cv.alpha_composite(fade(wipe(ar, smooth(t / 1.0)), kout), ((W - ar.width) // 2, y))
    y += ar.height - 30
    d = ImageDraw.Draw(cv)
    rk = smooth((t - 0.6) / 0.6) * kout
    d.line([(W / 2 - 220 * rk, y + 10), (W / 2 + 220 * rk, y + 10)], fill=GOLD_HI + (int(230 * kout),), width=3)
    if card.get("urdu"):
        ur = plain_text(card["urdu"], 50)
        if ur.width > W - 80:
            ur = ur.resize((W - 80, int(ur.height * (W - 80) / ur.width)), Image.LANCZOS)
        cv.alpha_composite(fade(ur, smooth((t - 0.8) / 0.6) * kout), ((W - ur.width) // 2, y + 20))
        y += ur.height
    ref = plain_text(card["ref"], 38, (226, 214, 190))
    cv.alpha_composite(fade(ref, smooth((t - 1.1) / 0.6) * kout), ((W - ref.width) // 2, y + 40))
    if card.get("end"):
        n = plain_text(NAME, 64)
        hd = plain_text(HANDLE, 30, GOLD_HI, POPPINS, None)
        cv.alpha_composite(fade(n, kin * kout), ((W - n.width) // 2, 1350))
        cv.alpha_composite(fade(hd, kin * kout), ((W - hd.width) // 2, 1350 + n.height - 40))
    return cv


# ---- render -----------------------------------------------------------------------------------

def resolve_overlays(plan, pieces):
    res = []
    for ov in plan["overlays"]:
        if "at" in ov:
            t = out_time(pieces, ov["take"], ov["at"])
            if t is None:
                print("overlay not placed:", ov.get("text") or ov.get("ref"))
                continue
            ov = dict(ov, t=t)
            if "until" in ov:
                ov["dur"] = max(0.8, out_time(pieces, ov["take"], ov["until"]) - t)
        if ov["type"] == "list":
            items = []
            for it in ov["items"]:
                items.append({"text": it["text"], "t": out_time(pieces, ov["take"], it["at"])})
            end = out_time(pieces, ov["take"], ov["until"])
            for it in items:
                it["end"] = end
            ov = dict(ov, items=items, t=items[0]["t"], dur=end - items[0]["t"])
        res.append(ov)
    return res


def frame_at(fi, pieces, overlays, piece, person, eyes):
    t = fi / FPS
    if "card" in piece:
        cv = full_card(piece["card"], t - piece["t"], piece["dur"])
    else:
        z = ZOOM[piece["shot"]]
        if piece.get("push"):
            z *= 1 + 0.06 * (t - piece["t"]) / max(0.1, piece["out"] - piece["in"])
        cv = studio_frame(person, eyes, z, EYE_Y[piece["shot"]])
        cv.alpha_composite(shade())
        for ov in overlays:
            if ov["t"] <= t < ov["t"] + ov["dur"]:
                lt = t - ov["t"]
                if ov["type"] == "word":
                    draw_word(cv, ov, lt, ov.get("y", 540))
                elif ov["type"] == "list":
                    draw_list(cv, ov["items"], t, ov.get("y", 380))
                elif ov["type"] == "card":
                    draw_card(cv, ov, lt, ov.get("y", 230))
        if plan_lower is not None:
            draw_lower(cv, t - plan_lower)
    return cv


plan_lower = None


def main():
    global plan_lower
    plan_path = sys.argv[1]
    plan = json.load(open(plan_path))
    name = os.path.splitext(os.path.basename(plan_path))[0]
    work = os.path.join(ROOT, "videos", "work", name)
    os.makedirs(work, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    pieces, total = build_cuts(plan, work)
    overlays = resolve_overlays(plan, pieces)
    plan_lower = plan.get("lower_third_at")
    eyes = plan["eyes"]
    json.dump({"pieces": pieces, "total": total}, open(os.path.join(work, "cuts.json"), "w"), indent=1)
    print(f"{len(pieces)} pieces, {total:.1f} s")
    if "--still" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--still") + 1].split(",")]
        for ts_ in ts:
            p = [q for q in pieces if q["t"] <= ts_][-1]
            person = None
            if "card" not in p:
                off = ts_ - p["t"]
                raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{p['in'] + off}", "-i", src_path(p["take"]),
                                      "-frames:v", "1", "-vf", f"scale={KW}:{KH}:flags=area", "-f", "rawvideo",
                                      "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
                person = key(np.frombuffer(raw, np.uint8).reshape(KH, KW, 3))
            cv = frame_at(int(ts_ * FPS), pieces, overlays, p, person, eyes.get(p.get("take"), [0, 0, 1]))
            cv.convert("RGB").save(os.path.join(work, f"still_{ts_:.1f}.jpg"), quality=88)
        return
    wav = os.path.join(work, "audio.wav")
    make_audio(pieces, total, work, wav)
    out = os.path.join(OUT, f"{name}{'_draft' if '--draft' in sys.argv else ''}.mp4")
    nfr = int(round(total * FPS))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", wav,
                            "-vf", f"vignette=angle=PI/5,fade=t=in:d=0.4,fade=t=out:st={total - 0.6}:d=0.6,format=yuv420p",
                            "-t", f"{total}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac",
                            "-b:a", "192k", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    fi = 0
    for p in pieces:
        if "card" in p:
            for _ in range(int(round(p["dur"] * FPS))):
                enc.stdin.write(frame_at(fi, pieces, overlays, p, None, None).convert("RGB").tobytes())
                fi += 1
        else:
            ey = eyes[p["take"]]
            for fr in frames_of(p):
                enc.stdin.write(frame_at(fi, pieces, overlays, p, key(fr), ey).convert("RGB").tobytes())
                fi += 1
        print(f"  {fi}/{nfr} frames", flush=True)
    enc.stdin.close()
    enc.wait()
    print(out)


if __name__ == "__main__":
    main()
