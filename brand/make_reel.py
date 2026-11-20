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


def subclips(edb, t0, t1, thr=-42, min_gap=0.42, keep=0.26):
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
        if seg.get("snap", True):
            t0, t1 = snap(e, seg["in"]), snap(e, seg["out"])
        else:
            t0, t1 = seg["in"], seg["out"]
        # remove fillers ("آ…") and the like listed in the plan, then shorten the pauses
        parts = [(t0, t1)]
        for rtk, r0, r1 in plan.get("remove", []):
            if rtk != tk:
                continue
            nxt = []
            for a, b in parts:
                if r1 <= a or r0 >= b:
                    nxt.append((a, b))
                else:
                    if r0 > a:
                        nxt.append((a, r0))
                    if r1 < b:
                        nxt.append((r1, b))
            parts = nxt
        subs = []
        for a, b in parts:
            subs += subclips(e, a, b) if seg.get("trim", True) else [(a, b)]
        shots = seg.get("shots", ["W"])
        for k, (x, y) in enumerate(subs):
            # frame-exact lengths so audio and video stay in step
            n = max(1, int(round((y - x) * FPS)))
            first = k == 0 and len(pieces) > 0 and not seg.get("join")
            pieces.append({"take": tk, "in": x, "out": x + n / FPS, "shot": shots[k % len(shots)],
                           "push": seg.get("push", False), "seg_start": first,
                           "alt": (k % 2 == 1) if not seg.get("join") else (k % 2 == 0)})
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
        nd = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                   nasheed], capture_output=True, text=True).stdout)
        parts += ["-i", nasheed, "-i", nasheed]
        x = 4.0                                            # crossfade when the nasheed loops
        fc += (f";[{n}:a]aformat=sample_rates=48000:channel_layouts=mono[n1];"
               f"[{n + 1}:a]aformat=sample_rates=48000:channel_layouts=mono[n2];"
               f"[n1][n2]acrossfade=d={x}:c1=tri:c2=tri,atrim=0:{total},asetpts=PTS-STARTPTS,"
               f"loudnorm=I=-31:TP=-8:LRA=11,afade=t=in:d=2,afade=t=out:st={total - 2.5}:d=2.5[bed];"
               f"[v]asplit[v1][vk];"
               f"[bed][vk]sidechaincompress=threshold=0.03:ratio=5:attack=40:release=600:makeup=1[bd];"
               f"[v1][bd]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]")
    else:
        fc = fc[:-3] + "[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *parts, "-filter_complex", fc, "-map", "[a]", "-t", f"{total}",
                    "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", path], check=True)


def add_clicks(wav, times, sfx, gain=0.32):
    """mix a short click at every sentence cut (a hair before the cut, as editors place it)"""
    with wave.open(wav, "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, ch) / 32768
    with wave.open(sfx, "rb") as w:
        c = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, w.getnchannels())
        c = c[:, :1] / 32768
    for t in times:
        i = max(0, int((t - 0.015) * sr))
        j = min(len(a), i + len(c))
        a[i:j] += c[: j - i] * gain
    with wave.open(wav, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


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
        from PIL import ImageEnhance
        pl = Image.open(os.path.join(PLATES, f"{PLATE}_bg.png")).convert("RGB")
        pl = ImageEnhance.Brightness(pl).enhance(float(os.environ.get("ROOM_EXPOSURE", "1.22")))
        _cache["plate"] = ImageEnhance.Contrast(pl).enhance(0.92)
        fgp = os.path.join(PLATES, f"{PLATE}_fg.png")
        _cache["fg"] = Image.open(fgp).convert("RGBA") if os.path.exists(fgp) else None
        _cache["meta"] = json.load(open(os.path.join(PLATES, f"{PLATE}_meta.json")))
    return _cache["plate"], _cache["meta"]


def relight(person, eyes):
    """virtual lighting for a flatly lit phone recording: a soft warm key on the face, lifted shadows,
    and a warm rim on the lamp side (screen right) and the top of the cap"""
    ex, ey, iod = eyes
    key = ("light", int(ex), int(ey))
    if key not in _cache:
        yy, xx = np.mgrid[0:KH, 0:KW].astype(np.float32)
        k = np.exp(-(((xx - ex - 30) / 300) ** 2 + ((yy - ey - 80) / 340) ** 2) / 2)
        gain = (1.08 + 0.34 * k)[..., None] * np.array([1.0, 0.985, 0.995], np.float32)
        side = np.clip((xx - ex + 120) / 500, 0, 1) * 0.8 + np.clip((ey - yy + 200) / 300, 0, 1) * 0.5
        _cache[key] = (gain, np.clip(side, 0, 1))
    gain, side = _cache[key]
    a = np.asarray(person).astype(np.float32) / 255
    rgb = np.clip(a[..., :3], 0, 1) ** 0.84 * 1.02         # lift the shadows (high-key, like a lit set)
    rgb = rgb * gain
    al = person.getchannel("A")
    inner = np.asarray(al.filter(ImageFilter.MinFilter(9)).filter(ImageFilter.GaussianBlur(4))).astype(np.float32) / 255
    rim = np.clip(a[..., 3] - inner, 0, 1) * side
    rgb = rgb + rim[..., None] * np.array([1.0, 0.80, 0.52], np.float32) * 0.55
    out = np.dstack([np.clip(rgb, 0, 1), a[..., 3]])
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def studio_frame(person, eyes, z, eye_y, behind=None):
    """studio camera zoomed by z; the presenter sits between the room and the desk layer, eyes at eye_y"""
    pl, meta = plate()
    fg = _cache["fg"]
    ex, ey, iod = eyes
    s = meta["ppm"] * 0.063 / iod
    E = (meta["eye_x"], meta["eye_y"])
    x0, y0 = E[0] - (W / 2) / z, E[1] - eye_y / z
    box = (int(round(x0)), int(round(y0)), int(round(x0 + W / z)), int(round(y0 + H / z)))
    bg = pl.crop(box).resize((W, H), Image.BICUBIC).convert("RGBA")
    if behind is not None:
        behind(bg)
    ss = s * z
    pw, ph = int(KW * ss), int(KH * ss)
    if os.environ.get("RELIGHT", "1") == "1":
        person = relight(person, eyes)
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
        y = y0 + i * 125
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
    n = name_en(46)
    a = kin * kout
    x = W - 70 - n.width + int(50 * (1 - kin))
    y = 1600
    d = ImageDraw.Draw(cv)
    d.line([(W - 56, y + 4), (W - 56, y + n.height - 4)], fill=GOLD_HI + (int(255 * a),), width=4)
    cv.alpha_composite(wipe(fade(n, a), kin), (x, y))


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
        lg = Image.open(LOGO).convert("RGBA")
        lg.thumbnail((300, 300), Image.LANCZOS)
        cv.alpha_composite(fade(lg, kin * kout), ((W - lg.width) // 2, 1180))
        n = name_en(52)
        cv.alpha_composite(fade(n, kin * kout), ((W - n.width) // 2, 1510))
    return cv




CORMORANT = os.path.join(HERE, "fonts", "CormorantGaramond-700-normal.ttf")
NAME_EN = "ZABEEHULLAH LEGHARI"


def name_en(size=44, spacing=0.18, fill=None):
    """the presenter's name in letter-spaced Cormorant capitals with a gold gradient"""
    key = ("name_en", size, spacing, fill)
    if key in _cache:
        return _cache[key]
    f = font(CORMORANT, size)
    gap = int(size * spacing)
    widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] if ch != " " else size // 3 for ch in NAME_EN]
    w = sum(widths) + gap * (len(NAME_EN) - 1) + 40
    h = int(size * 1.6)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    x = 20
    for ch, cw in zip(NAME_EN, widths):
        if ch != " ":
            d.text((x - f.getbbox(ch)[0], int(size * 0.2)), ch, font=f, fill=255)
        x += cw + gap
    ys = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array((248, 226, 178), np.float32), np.array((196, 150, 84), np.float32)
    rgb = np.broadcast_to(top * (1 - ys) + bot * ys, (h, w, 3)) if fill is None else np.full((h, w, 3), fill, np.float32)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(m.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.8)))
    out.alpha_composite(sh, (0, 3))
    out.alpha_composite(Image.fromarray(np.dstack([rgb, np.asarray(m)]).astype(np.uint8), "RGBA"))
    _cache[key] = out
    return out

# ---- channel furniture: logo, countdown, social strip --------------------------------------------
NASKH = os.path.join(ROOT, ".claude", "skills", "dai-video-editor", "assets", "fonts", "NotoNaskhArabic-Bold.ttf")
LOGO = os.path.join(HERE, "logo", "logo_premium_navy_transparent.png")


HEADLINE = None


def draw_headline(cv):
    """persistent title in an ornate gold frame: navy glass panel with an ogee arch on top, double gold
    border, corner rosettes and side finials; the Nastaliq title in gold sits inside"""
    if not HEADLINE:
        return
    if "headline" not in _cache:
        S = 3
        txt = gold_text(HEADLINE, 66, NASTALIQ, grad=((255, 246, 220), (228, 184, 104)))
        maxw = W - 260
        if txt.width - 40 > maxw:
            txt = txt.resize((maxw + 40, int(txt.height * (maxw + 40) / txt.width)), Image.LANCZOS)
        bw, bh = txt.width - 40 + 130, 132
        arch = 26
        w, h = bw + 80, bh + arch + 50
        im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        x0, y0 = 40, 25 + arch
        x1, y1 = x0 + bw, y0 + bh

        def outline(inset):
            xa, ya, xb, yb = x0 + inset, y0 + inset, x1 - inset, y1 - inset
            cx = (xa + xb) / 2
            pts = [(xa, yb), (xa, ya)]
            # ogee arch along the top edge
            for i in range(41):
                t = i / 40
                x = xa + (xb - xa) * t
                bump = (math.sin(math.pi * t) ** 6) * (arch - inset * 0.5)
                pts.append((x, ya - bump))
            pts += [(xb, ya), (xb, yb)]
            return [(px * S, py * S) for px, py in pts]
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).polygon(outline(0), fill=(0, 0, 0, 190))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12 * S)))
        d = ImageDraw.Draw(im)
        d.polygon(outline(0), fill=(9, 24, 48, 232))
        d.line(outline(0) + [outline(0)[0]], fill=GOLD_HI + (255,), width=4 * S, joint="curve")
        d.line(outline(9) + [outline(9)[0]], fill=GOLD + (210,), width=int(1.5 * S), joint="curve")
        for (cx, cy) in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:            # corner rosettes
            for k in range(8):
                a_ = math.pi * k / 4
                d.ellipse([(cx + 9 * math.cos(a_) - 3.5) * S, (cy + 9 * math.sin(a_) - 3.5) * S,
                           (cx + 9 * math.cos(a_) + 3.5) * S, (cy + 9 * math.sin(a_) + 3.5) * S], fill=GOLD_HI + (255,))
            d.ellipse([(cx - 5) * S, (cy - 5) * S, (cx + 5) * S, (cy + 5) * S], fill=(9, 24, 48, 255),
                      outline=GOLD_HI + (255,), width=2 * S)
        cy = (y0 + y1) / 2                                                   # side finials
        for sgn, x in ((-1, x0), (1, x1)):
            d.polygon([((x + sgn * 30) * S, cy * S), ((x + sgn * 4) * S, (cy - 12) * S),
                       ((x + sgn * 4) * S, (cy + 12) * S)], fill=GOLD_HI + (255,))
        ax = (x0 + x1) / 2                                                   # crest on the arch
        d.polygon([(ax * S, (y0 - arch - 18) * S), ((ax + 9) * S, (y0 - arch - 6) * S), (ax * S, (y0 - arch + 6) * S),
                   ((ax - 9) * S, (y0 - arch - 6) * S)], fill=GOLD_HI + (255,))
        im = im.resize((w, h), Image.LANCZOS)
        im.alpha_composite(txt, ((w - txt.width) // 2, y0 + (bh - txt.height) // 2 + 6))
        _cache["headline"] = im
    hl = _cache["headline"]
    cv.alpha_composite(hl, ((W - hl.width) // 2, 100))


def draw_logo(cv):
    if "logo" not in _cache:
        lg = Image.open(LOGO).convert("RGBA")
        lg.thumbnail((150, 150), Image.LANCZOS)
        sh = Image.new("RGBA", (lg.width + 30, lg.height + 30), (0, 0, 0, 0))
        m = lg.getchannel("A").filter(ImageFilter.GaussianBlur(6))
        dark = Image.new("RGBA", lg.size, (0, 0, 0, 0))
        dark.putalpha(m.point(lambda v: int(v * 0.7)))
        sh.alpha_composite(dark, (15, 19))
        sh.alpha_composite(lg, (15, 15))
        _cache["logo"] = sh
    cv.alpha_composite(_cache["logo"], (22, 36))


def draw_timer(cv, t, total):
    left = max(0, total - t)
    txt = f"{int(left // 60):02d}:{int(left % 60):02d}"
    f = font(POPPINS, 30)
    d = ImageDraw.Draw(cv)
    w = int(d.textlength(txt, font=f)) + 70
    x1, y0 = W - 30, 62
    d.rounded_rectangle([x1 - w, y0, x1, y0 + 52], 26, fill=(8, 18, 34, 200), outline=GOLD_HI + (200,), width=2)
    blink = 255 if int(t * 2) % 2 == 0 else 120
    d.ellipse([x1 - w + 18, y0 + 18, x1 - w + 34, y0 + 34], fill=(230, 50, 50, blink))
    d.text((x1 - w + 46, y0 + 7), txt, font=f, fill=(255, 255, 255, 240))
    # progress line along the very bottom
    d.rectangle([0, H - 8, W, H], fill=(0, 0, 0, 120))
    d.rectangle([W - int(W * t / total), H - 8, W, H], fill=GOLD_HI + (255,))


def _icon(kind, size=44):
    key = ("icon", kind)
    if key in _cache:
        return _cache[key]
    S = 4
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = GOLD_HI + (255,)
    z = size * S
    lw = 3 * S
    if kind == "fb":
        d.ellipse([0, 0, z - 1, z - 1], fill=c)
        d.text((z * 0.36, z * 0.08), "f", font=font(POPPINS, int(z * 0.78)), fill=DEEP + (255,))
    elif kind == "yt":
        d.rounded_rectangle([0, z * 0.18, z - 1, z * 0.82], z * 0.18, fill=c)
        d.polygon([(z * 0.40, z * 0.34), (z * 0.40, z * 0.66), (z * 0.68, z * 0.50)], fill=DEEP + (255,))
    elif kind == "ig":
        d.rounded_rectangle([lw, lw, z - lw, z - lw], z * 0.28, outline=c, width=lw)
        d.ellipse([z * 0.3, z * 0.3, z * 0.7, z * 0.7], outline=c, width=lw)
        d.ellipse([z * 0.70, z * 0.18, z * 0.80, z * 0.28], fill=c)
    elif kind == "tt":
        d.line([(z * 0.55, z * 0.08), (z * 0.55, z * 0.70)], fill=c, width=lw + S)
        d.ellipse([z * 0.22, z * 0.55, z * 0.58, z * 0.90], outline=c, width=lw + S)
        d.arc([z * 0.55, z * 0.0, z * 0.95, z * 0.40], 90, 180, fill=c, width=lw + S)
    elif kind == "x":
        d.line([(z * 0.15, z * 0.12), (z * 0.85, z * 0.88)], fill=c, width=lw + S)
        d.line([(z * 0.85, z * 0.12), (z * 0.15, z * 0.88)], fill=c, width=lw)
    _cache[key] = im.resize((size, size), Image.LANCZOS)
    return _cache[key]


SERIES = None
CORM_IT = os.path.join(HERE, "fonts", "CormorantGaramond-500-italic.ttf")


def series_title(spec):
    """"SEERAT" in gold serif capitals with a light italic "insights" riding over it"""
    big, small = spec.split("|")
    f1 = font(CORMORANT, 128)
    f2 = font(CORM_IT, 66)
    w = int(f1.getlength(big)) + 60
    h = 200
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((30, 52), big, font=f1, fill=255)
    ys = np.linspace(0, 1, h)[:, None, None]
    rgb = np.broadcast_to(np.array((255, 232, 120), np.float32) * (1 - ys) + np.array((222, 168, 40), np.float32) * ys,
                          (h, w, 3))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(7)))
    out.alpha_composite(sh, (0, 5))
    out.alpha_composite(Image.fromarray(np.dstack([rgb, np.asarray(m)]).astype(np.uint8), "RGBA"))
    d = ImageDraw.Draw(out)
    sw = f2.getlength(small)
    d.text((w - sw - 26, 8), small, font=f2, fill=(255, 250, 240, 255), stroke_width=1, stroke_fill=(0, 0, 0, 160))
    return out


def draw_strip(cv):
    if "strip" not in _cache:
        st = Image.new("RGBA", (W, 96), (0, 0, 0, 0))
        d = ImageDraw.Draw(st)
        d.rectangle([0, 0, W, 96], fill=(6, 14, 28, 225))
        d.line([(0, 1), (W, 1)], fill=GOLD_HI + (200,), width=2)
        x = 40
        for k in ["fb", "yt", "tt", "ig", "x"]:
            st.alpha_composite(_icon(k), (x, 26))
            x += 60
        nm = name_en(46, 0.12)
        st.alpha_composite(nm, (W - 20 - nm.width, 48 - nm.height // 2))
        _cache["strip"] = st
    cv.alpha_composite(_cache["strip"], (0, H - 104))
    if SERIES:
        if "series" not in _cache:
            _cache["series"] = series_title(SERIES)
        sr = _cache["series"]
        cv.alpha_composite(sr, (W - 24 - sr.width, H - 104 - sr.height + 18))


# ---- bold words (JTR-style) and giant background words ---------------------------------------------

def bold_word(txt, size, fill=(255, 255, 255), hl=None):
    key = ("bw", txt, size, fill, hl)
    if key in _cache:
        return _cache[key]
    f = font(NASKH, size)
    l, t, r, b = f.getbbox(txt, direction="rtl")
    pad = 50
    w, h = r - l + 2 * pad, b - t + 2 * pad
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), txt, font=f, fill=255, direction="rtl")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(12)))
    out.alpha_composite(sh, (0, 10))
    ys = np.linspace(0, 1, h)[:, None, None]
    top = np.array(fill, np.float32)
    bot = np.array(hl if hl else fill, np.float32) * 0.86
    rgb = np.broadcast_to(top * (1 - ys) + bot * ys, (h, w, 3))
    face = Image.fromarray(np.dstack([rgb, np.asarray(m)]).astype(np.uint8), "RGBA")
    out.alpha_composite(face)
    _cache[key] = out
    return out


def draw_bold(cv, ov, t, y):
    dur = ov["dur"]
    pop = min(1.0, t / 0.18)
    sc = 0.7 + 0.42 * pop - 0.12 * smooth((t - 0.18) / 0.2)       # punch in, settle at 1.0
    kout = 1 - smooth((t - (dur - 0.25)) / 0.25)
    col = (255, 214, 10) if ov.get("color") == "yellow" else (255, 255, 255)
    g = bold_word(ov["text"], ov.get("size", 156), col)
    if g.width > W - 40:
        g = g.resize((W - 40, int(g.height * (W - 40) / g.width)), Image.LANCZOS)
    gw, gh = max(1, int(g.width * sc)), max(1, int(g.height * sc))
    im = fade(g.resize((gw, gh), Image.LANCZOS), kout * min(1, t / 0.1))
    cv.alpha_composite(im, (W // 2 - gw // 2, int(y - gh / 2)))


def bg_word_painter(ov, t):
    """giant soft word drawn on the room, behind the presenter"""
    def paint(bg):
        dur = ov["dur"]
        k = smooth(t / 0.6) * (1 - smooth((t - (dur - 0.5)) / 0.5))
        if k <= 0:
            return
        g = bold_word(ov["text"], 420, (255, 236, 200))
        drift = int(40 * t)
        im = fade(g.filter(ImageFilter.GaussianBlur(3)), 0.34 * k)
        bg.alpha_composite(im, (W // 2 - im.width // 2 + 120 - drift, ov.get("y", 700) - im.height // 2)
                           if im.width < 4000 else (0, 0))
    return paint


def draw_broll(cv, ov, t):
    """full-screen cutaway (the voice continues) with a caption, or a picture-in-picture card"""
    import broll
    dur = ov["dur"]
    fn = broll.VISUALS[ov["visual"]]
    if ov["visual"] == "light":
        pl = _cache.get("arches")
        if pl is None:
            ap = os.path.join(PLATES, "arches_v_bg.png")
            pl = Image.open(ap).convert("RGB") if os.path.exists(ap) else None
            _cache["arches"] = pl
        vis = broll.light(t, dur, pl)
    else:
        vis = fn(t, dur)
    k = smooth(t / 0.22) * (1 - smooth((t - (dur - 0.22)) / 0.22))
    if ov.get("mode", "full") == "full":
        if ov.get("caption"):
            g = bold_word(ov["caption"], ov.get("size", 140), (255, 255, 255))
            ci = min(1, t / 0.25)
            vis.alpha_composite(fade(g, ci), (W // 2 - g.width // 2, ov.get("cy", 1420) - g.height // 2))
        cv.paste(Image.blend(cv, vis, k) if k < 1 else vis, (0, 0))
    else:
        side = 620
        sq = vis.crop(((W - 1080) // 2, 600, (W - 1080) // 2 + 1080, 1680)).resize((side, side), Image.LANCZOS)
        m = Image.new("L", (side, side), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, side - 1, side - 1], 40, fill=255)
        sq.putalpha(m)
        y = int(260 - 80 * (1 - k))
        x = (W - side) // 2
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([x, y + 16, x + side, y + side + 16], 40, fill=(0, 0, 0, int(150 * k)))
        cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
        cv.alpha_composite(fade(sq, k), (x, y))
        ImageDraw.Draw(cv).rounded_rectangle([x - 2, y - 2, x + side + 2, y + side + 2], 42,
                                             outline=GOLD_HI + (int(255 * k),), width=4)


def mono(cv, k):
    a = np.asarray(cv).astype(np.float32)
    g = (a[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None]
    a[..., :3] = a[..., :3] * (1 - k) + (g * np.array([1.0, 0.97, 0.92])) * k
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")

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


def frame_at(fi, pieces, overlays, piece, person, eyes, total=None):
    t = fi / FPS
    active = [ov for ov in overlays if ov["t"] <= t < ov["t"] + ov["dur"]]
    if "card" in piece:
        cv = full_card(piece["card"], t - piece["t"], piece["dur"])
    else:
        z = ZOOM[piece["shot"]]
        if piece.get("push"):
            z *= 1 + 0.06 * (t - piece["t"]) / max(0.1, piece["out"] - piece["in"])
        if piece.get("alt"):
            z *= 1.12                                              # every other piece of a sentence: tighter framing
        if piece.get("seg_start") and CUT_SFX and t - piece["t"] < 0.22:
            z *= 1 + 0.035 * (1 - (t - piece["t"]) / 0.22) ** 2      # tiny punch with the click
        painters = [bg_word_painter(ov, t - ov["t"]) for ov in active if ov["type"] == "bgword"]
        cv = studio_frame(person, eyes, z, EYE_Y[piece["shot"]],
                          (lambda bg: [p(bg) for p in painters]) if painters else None)
        for ov in active:
            if ov["type"] == "grade":
                lt = t - ov["t"]
                cv = mono(cv, 0.9 * smooth(lt / 0.4) * (1 - smooth((lt - ov["dur"] + 0.4) / 0.4)))
        cv.alpha_composite(shade())
        for ov in active:
            lt = t - ov["t"]
            if ov["type"] == "word":
                draw_word(cv, ov, lt, ov.get("y", 540))
            elif ov["type"] == "bold":
                draw_bold(cv, ov, lt, ov.get("y", 560))
            elif ov["type"] == "list":
                draw_list(cv, ov["items"], t, ov.get("y", 380))
            elif ov["type"] == "card":
                draw_card(cv, ov, lt, ov.get("y", 230))
        if plan_lower is not None:
            draw_lower(cv, t - plan_lower)
        for ov in active:
            if ov["type"] == "broll":
                draw_broll(cv, ov, t - ov["t"])
    if total and not piece.get("card", {}).get("end"):
        draw_logo(cv)
        draw_timer(cv, t, total)
        draw_strip(cv)
        draw_headline(cv)
    return cv


plan_lower = None
CUT_SFX = os.environ.get("CUT_SFX")


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
    global HEADLINE, SERIES
    HEADLINE = plan.get("headline")
    SERIES = plan.get("series")
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
            cv = frame_at(int(ts_ * FPS), pieces, overlays, p, person, eyes.get(p.get("take"), [0, 0, 1]), total)
            cv.convert("RGB").save(os.path.join(work, f"still_{ts_:.1f}.jpg"), quality=88)
        return
    wav = os.path.join(work, "audio.wav")
    make_audio(pieces, total, work, wav)
    if CUT_SFX and os.path.exists(CUT_SFX):
        brs = [ov["t"] for ov in overlays if ov["type"] == "broll"]
        times, last = [], -99
        for p in pieces:
            if p.get("seg_start") and p["t"] - last >= 6 and all(abs(p["t"] - b) > 0.6 for b in brs):
                times.append(p["t"])
                last = p["t"]
        add_clicks(wav, times, CUT_SFX, gain=float(os.environ.get("CUT_GAIN", "0.5")))
    out = os.path.join(OUT, f"{name}{'_draft' if '--draft' in sys.argv else ''}.mp4")
    nfr = int(round(total * FPS))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", wav,
                            "-vf", f"vignette=angle=PI/5,fade=t=in:d=0.4,fade=t=out:st={total - 0.6}:d=0.6,format=yuv420p",
                            "-t", f"{total}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac",
                            "-b:a", "192k", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    fi = 0
    prev = None
    for p in pieces:
        if "card" in p:
            prev = None
            for _ in range(int(round(p["dur"] * FPS))):
                enc.stdin.write(frame_at(fi, pieces, overlays, p, None, None, total).convert("RGB").tobytes())
                fi += 1
        else:
            ey = eyes[p["take"]]
            for j, fr in enumerate(frames_of(p)):
                img = frame_at(fi, pieces, overlays, p, key(fr), ey, total).convert("RGB")
                if j < 3 and prev is not None and not p.get("seg_start"):
                    img = Image.blend(prev, img, (j + 1) / 4)      # hide the jump of an internal cut
                enc.stdin.write(img.tobytes())
                prev = img
                fi += 1
        print(f"  {fi}/{nfr} frames", flush=True)
    enc.stdin.close()
    enc.wait()
    print(out)


if __name__ == "__main__":
    main()
