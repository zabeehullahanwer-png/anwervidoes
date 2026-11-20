"""Synthesised transition sound effects (no music, no instruments) + a labelled demo video.

  python3 brand/make_sfx.py  -> brand/sfx/*.wav  and  videos/edited/sfx_demo.mp4
"""
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SR = 48000
HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, "sfx")
rng = np.random.default_rng(1)


def t_(d):
    return np.arange(int(d * SR)) / SR


def lp(x, a):          # one-pole low-pass, a in (0,1): smaller = darker
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y


def sweep_noise(d, f0, f1, shape):
    """noise through a moving low-pass: brightness follows f0 -> f1"""
    n = rng.normal(0, 1, int(d * SR))
    f = np.linspace(f0, f1, len(n))
    a = 1 - np.exp(-2 * np.pi * f / SR)
    y = np.zeros_like(n)
    acc = 0.0
    for i in range(len(n)):
        acc += a[i] * (n[i] - acc)
        y[i] = acc
    return y * shape


def env(d, att, rel):
    t = t_(d)
    e = np.minimum(1, t / max(att, 1e-4)) * np.exp(-np.maximum(0, t - att) / rel)
    return e


def whoosh():
    d = 0.9
    t = t_(d)
    shape = np.sin(np.pi * t / d) ** 2
    l = sweep_noise(d, 300, 3500, shape)
    return l


def swoosh():
    d = 0.35
    t = t_(d)
    return sweep_noise(d, 1500, 6000, np.sin(np.pi * t / d) ** 3)


def pop():
    d = 0.18
    t = t_(d)
    f = 900 * np.exp(-t * 30) + 250
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(d, 0.002, 0.04)


def tick():
    d = 0.08
    n = rng.normal(0, 1, int(d * SR)) * env(d, 0.0005, 0.006)
    return n - lp(n, 0.3)


def impact():
    d = 1.4
    t = t_(d)
    low = np.sin(2 * np.pi * (48 + 40 * np.exp(-t * 8)) * t) * env(d, 0.003, 0.45)
    hit = lp(rng.normal(0, 1, len(t)), 0.15) * env(d, 0.001, 0.05) * 1.5
    return low + hit


def riser():
    d = 1.6
    t = t_(d)
    shape = (t / d) ** 2.2
    return sweep_noise(d, 200, 8000, shape) * 1.4


def shutter():
    d = 0.22
    n = rng.normal(0, 1, int(d * SR))
    e = env(d, 0.001, 0.012)
    e2 = np.roll(env(d, 0.001, 0.02), int(0.07 * SR))
    return (n - lp(n, 0.2)) * (e + 0.8 * e2)


def page():
    d = 0.6
    t = t_(d)
    n = rng.normal(0, 1, len(t))
    flutter = (0.5 + 0.5 * np.sin(2 * np.pi * 26 * t)) * np.sin(np.pi * t / d) ** 2
    return (n - lp(n, 0.08)) * flutter * 0.8


SOUNDS = [
    ("whoosh", "وُوش (Whoosh)", "منظر بدلتے وقت ہوا کی سرسراہٹ", whoosh),
    ("swoosh", "سووش (Swoosh)", "لفظ یا تصویر کے تیزی سے آنے پر", swoosh),
    ("pop", "پاپ (Pop)", "لفظ یا نشان کے اچانک ابھرنے پر", pop),
    ("tick", "ٹِک / کلِک (Tick / Click)", "ٹائمر، فہرست یا ✓ کے ساتھ", tick),
    ("impact", "امپیکٹ / ہِٹ (Impact / Hit)", "اہم جملے پر زور دینے کے لیے", impact),
    ("riser", "رائزر (Riser)", "کسی بڑی بات سے پہلے ابھار", riser),
    ("shutter", "شٹر (Camera Shutter)", "تصویر یا فریم بدلنے پر", shutter),
    ("page", "ورق پلٹنا (Page Flip)", "کتاب یا حوالے کے کارڈ پر", page),
]


def save(name, y):
    y = y / (np.abs(y).max() + 1e-9) * 0.7
    st = np.stack([y, y], 1)
    with wave.open(os.path.join(OUTD, f"{name}.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


if __name__ == "__main__" and "--accents" not in sys.argv:
    import make_reel as R
    os.makedirs(OUTD, exist_ok=True)
    work = os.path.join(R.ROOT, "videos", "work", "sfx")
    os.makedirs(work, exist_ok=True)
    seg = 2.6
    audio = np.zeros(int(seg * len(SOUNDS) * SR + SR))
    for i, (name, ur, use, fn) in enumerate(SOUNDS):
        y = fn()
        save(name, y)
        y = y / (np.abs(y).max() + 1e-9) * 0.6
        for rep in (0, 1):                               # play each sound twice
            s = int((i * seg + 0.5 + rep * 1.0) * SR)
            audio[s:s + len(y)] += y[:len(audio) - s]
        bg = R.frame_bg() if hasattr(R, "frame_bg") else None
        cv = Image.new("RGBA", (1080, 1920), (8, 18, 34, 255))
        num = R.gold_text(f"{i + 1}", 140, R.POPPINS, None)
        cv.alpha_composite(num, ((1080 - num.width) // 2, 520))
        urdu, en = ur.split(" (")
        t1 = R.bold_word(urdu, 96, (255, 255, 255))
        cv.alpha_composite(t1, ((1080 - t1.width) // 2, 740))
        t3 = R.plain_text(en.rstrip(")"), 56, (255, 214, 120), R.POPPINS, None)
        cv.alpha_composite(t3, ((1080 - t3.width) // 2, 930))
        t2 = R.plain_text(use, 54, (232, 214, 180))
        cv.alpha_composite(t2, ((1080 - t2.width) // 2, 1060))
        cv.convert("RGB").save(os.path.join(work, f"card_{i:02d}.png"))
    st = np.stack([audio, audio], 1)
    wav = os.path.join(work, "demo.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes())
    out = os.path.join(R.OUT, "sfx_demo.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", f"1/{seg}", "-i", os.path.join(work, "card_%02d.png"),
                    "-i", wav, "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-c:a", "aac",
                    "-b:a", "192k", "-t", f"{seg * len(SOUNDS)}", "-movflags", "+faststart", out], check=True)
    print(out)


# ---- jump-cut accents: the short "ٹک" between two sentences -------------------------------------------

def tok():                     # wooden knock
    d = 0.12
    t = t_(d)
    body = np.sin(2 * np.pi * 820 * t) * env(d, 0.0005, 0.018) + 0.6 * np.sin(2 * np.pi * 1650 * t) * env(d, 0.0005, 0.008)
    n = rng.normal(0, 1, len(t)) * env(d, 0.0003, 0.002)
    return body + 0.5 * n


def mouse_click():
    n = int(0.09 * SR)
    a = np.pad(tick(), (0, n))[:n]
    return a + np.roll(a, int(0.045 * SR)) * 0.6


def thud():                    # low "dhum" used with a zoom punch-in
    d = 0.35
    t = t_(d)
    f = 70 + 90 * np.exp(-t * 40)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(d, 0.002, 0.08) + lp(rng.normal(0, 1, len(t)), 0.05) * env(d, 0.0005, 0.01)


def snap():
    d = 0.1
    n = rng.normal(0, 1, int(d * SR))
    bp = lp(n, 0.5) - lp(n, 0.12)
    return bp * env(d, 0.0003, 0.012) * 2


def soft_tick():               # clock-like
    d = 0.06
    t = t_(d)
    return np.sin(2 * np.pi * 2900 * t) * env(d, 0.0002, 0.004) + 0.4 * (tick()[: len(t)])


ACCENTS = [("tok", "ٹک (لکڑی کی ٹھک)", tok), ("click", "کلک (ماؤس)", mouse_click), ("thud", "دھم (زوم کے ساتھ)", thud),
           ("snap", "چٹکی (Snap)", snap), ("softtick", "گھڑی کی ٹک", soft_tick)]


def accent_demo():
    """the same cut from the reel, once per accent, with a zoom punch on the cut"""
    import make_reel as R
    work = os.path.join(R.ROOT, "videos", "work", "sfx")
    src = os.path.join(R.OUT, "three-blessings.mp4")
    a0, a1, cut = 3.6, 9.0, 6.27 - 3.6           # «...پوری دنیا آپ کے پاس موجود ہے» | «ترمذی شریف میں…»
    parts = []
    for i, (name, ur, fn) in enumerate(ACCENTS):
        save(name, fn())
        card = Image.new("RGBA", (1080, 1920), (8, 18, 34, 255))
        num = R.gold_text(f"{i + 1}", 150, R.POPPINS, None)
        card.alpha_composite(num, ((1080 - num.width) // 2, 640))
        t1 = R.bold_word(ur, 96, (255, 255, 255))
        card.alpha_composite(t1, ((1080 - t1.width) // 2, 860))
        cp = os.path.join(work, f"acc_{i}.png")
        card.convert("RGB").save(cp)
        clip = os.path.join(work, f"acc_{i}.mp4")
        fc = (f"[0:v]trim={a0}:{a1},setpts=PTS-STARTPTS,"
              f"scale=w='iw*(1+0.06*between(t,{cut},{cut}+0.25)*(1-(t-{cut})/0.25))':h=-2:eval=frame,"
              f"crop=1080:1920,format=yuv420p[v];"
              f"[0:a]atrim={a0}:{a1},asetpts=PTS-STARTPTS[a0];"
              f"[1:a]adelay={int(cut * 1000)}|{int(cut * 1000)},volume=0.55[s];"
              f"[a0][s]amix=inputs=2:normalize=0[a]")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", os.path.join(OUTD, f"{name}.wav"),
                        "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-r", "30", "-c:v", "libx264", "-crf", "20",
                        "-ar", "48000", "-ac", "2", "-c:a", "aac", clip], check=True)
        title = os.path.join(work, f"acc_t{i}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "1.2", "-i", cp, "-f", "lavfi", "-t", "1.2",
                        "-i", "anullsrc=r=48000:cl=stereo", "-r", "30", "-vf", "format=yuv420p", "-c:v", "libx264",
                        "-crf", "20", "-c:a", "aac", "-shortest", title], check=True)
        parts += [title, clip]
    lst = os.path.join(work, "acc_list.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    out = os.path.join(R.OUT, "cut_accents_demo.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    "-movflags", "+faststart", out], check=True)
    print(out)


if __name__ == "__main__" and "--accents" in sys.argv:
    accent_demo()
